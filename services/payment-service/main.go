package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/gorilla/mux"
	"github.com/jackc/pgx/v5/pgxpool"

	"payment-service/handlers"
	"payment-service/kafka"
)

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func initDB(ctx context.Context) (*pgxpool.Pool, error) {
	dsn := getEnv("DATABASE_URL", "postgresql://payment_user:payment_password@localhost:5432/payment_db")
	config, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, fmt.Errorf("parse dsn: %w", err)
	}
	config.MaxConns = 20
	config.MinConns = 2
	config.MaxConnLifetime = time.Hour
	config.MaxConnIdleTime = 30 * time.Minute

	pool, err := pgxpool.NewWithConfig(ctx, config)
	if err != nil {
		return nil, fmt.Errorf("create pool: %w", err)
	}

	if err := pool.Ping(ctx); err != nil {
		return nil, fmt.Errorf("ping db: %w", err)
	}
	return pool, nil
}

func runMigrations(ctx context.Context, pool *pgxpool.Pool) error {
	migration := `
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TYPE IF NOT EXISTS wallet_status AS ENUM ('active', 'frozen', 'closed');
CREATE TYPE IF NOT EXISTS tx_type AS ENUM ('top_up', 'hold', 'commit', 'release', 'withdraw', 'refund', 'escrow_in', 'escrow_out', 'commission');
CREATE TYPE IF NOT EXISTS escrow_status AS ENUM ('active', 'released', 'disputed', 'refunded');
CREATE TYPE IF NOT EXISTS commission_status AS ENUM ('held', 'committed', 'released');
CREATE TYPE IF NOT EXISTS tx_status AS ENUM ('pending', 'completed', 'failed', 'rolled_back');

CREATE TABLE IF NOT EXISTS wallets (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL,
    balance      BIGINT NOT NULL DEFAULT 0,
    held_amount  BIGINT NOT NULL DEFAULT 0,
    currency     CHAR(3) NOT NULL DEFAULT 'RUB',
    status       wallet_status NOT NULL DEFAULT 'active',
    version      BIGINT NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT wallets_user_unique UNIQUE (user_id),
    CONSTRAINT wallets_balance_positive CHECK (balance >= 0),
    CONSTRAINT wallets_held_non_negative CHECK (held_amount >= 0),
    CONSTRAINT wallets_balance_gte_held CHECK (balance >= held_amount)
);

CREATE TABLE IF NOT EXISTS transactions (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    idempotency_key  VARCHAR(255) NOT NULL,
    wallet_id        UUID NOT NULL REFERENCES wallets(id),
    type             tx_type NOT NULL,
    amount           BIGINT NOT NULL,
    currency         CHAR(3) NOT NULL DEFAULT 'RUB',
    status           tx_status NOT NULL DEFAULT 'pending',
    related_tx_id    UUID REFERENCES transactions(id),
    purchase_id      UUID,
    description      TEXT NOT NULL DEFAULT '',
    external_ref     VARCHAR(500),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT transactions_idempotency_unique UNIQUE (idempotency_key),
    CONSTRAINT transactions_amount_positive CHECK (amount > 0)
);

CREATE TABLE IF NOT EXISTS escrow_accounts (
    id                     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    purchase_id            UUID NOT NULL,
    total_amount           BIGINT NOT NULL DEFAULT 0,
    released_amount        BIGINT NOT NULL DEFAULT 0,
    status                 escrow_status NOT NULL DEFAULT 'active',
    threshold              BIGINT NOT NULL DEFAULT 0,
    confirmations_required INT NOT NULL DEFAULT 1,
    confirmations_received INT NOT NULL DEFAULT 0,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT escrow_purchase_unique UNIQUE (purchase_id),
    CONSTRAINT escrow_amount_non_negative CHECK (total_amount >= 0),
    CONSTRAINT escrow_released_non_negative CHECK (released_amount >= 0),
    CONSTRAINT escrow_confirmations_non_negative CHECK (confirmations_received >= 0)
);

CREATE TABLE IF NOT EXISTS commission_holds (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    purchase_id         UUID NOT NULL,
    organizer_wallet_id UUID NOT NULL,
    amount              BIGINT NOT NULL,
    percent             DECIMAL(4,2) NOT NULL,
    status              commission_status NOT NULL DEFAULT 'held',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT commission_amount_positive CHECK (amount > 0),
    CONSTRAINT commission_percent_range CHECK (percent > 0 AND percent <= 100)
);

CREATE INDEX IF NOT EXISTS idx_wallets_user ON wallets (user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_wallet ON transactions (wallet_id);
CREATE INDEX IF NOT EXISTS idx_transactions_idempotency ON transactions (idempotency_key);
CREATE INDEX IF NOT EXISTS idx_transactions_purchase ON transactions (purchase_id) WHERE purchase_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_escrow_purchase ON escrow_accounts (purchase_id);
CREATE INDEX IF NOT EXISTS idx_commission_purchase ON commission_holds (purchase_id);
CREATE INDEX IF NOT EXISTS idx_commission_wallet ON commission_holds (organizer_wallet_id);
`
	_, err := pool.Exec(ctx, migration)
	return err
}

func main() {
	ctx := context.Background()

	pool, err := initDB(ctx)
	if err != nil {
		log.Fatalf("DB init failed: %v", err)
	}
	defer pool.Close()

	if err := runMigrations(ctx, pool); err != nil {
		log.Printf("Warning: migration error (may be ok if types already exist): %v", err)
	}

	kp := kafka.NewProducer()
	defer kp.Close()

	h := handlers.NewPaymentHandler(pool, kp)
	eh := handlers.NewEscrowHandler(pool, kp)
	ch := handlers.NewCommissionHandler(pool, kp)

	r := mux.NewRouter()
	r.HandleFunc("/health", h.Health).Methods(http.MethodGet)
	r.HandleFunc("/wallet", h.GetWallet).Methods(http.MethodGet)
	r.HandleFunc("/wallet/topup", h.TopUp).Methods(http.MethodPost)
	r.HandleFunc("/wallet/hold", h.Hold).Methods(http.MethodPost)
	r.HandleFunc("/wallet/commit", h.Commit).Methods(http.MethodPost)
	r.HandleFunc("/wallet/release", h.Release).Methods(http.MethodPost)

	// Escrow endpoints
	r.HandleFunc("/escrow", eh.CreateEscrow).Methods(http.MethodPost)
	r.HandleFunc("/escrow/{purchaseId}", eh.GetEscrow).Methods(http.MethodGet)
	r.HandleFunc("/escrow/{purchaseId}/deposit", eh.DepositToEscrow).Methods(http.MethodPost)
	r.HandleFunc("/escrow/{purchaseId}/confirm", eh.ConfirmDelivery).Methods(http.MethodPost)
	r.HandleFunc("/escrow/{purchaseId}/release", eh.ReleaseEscrow).Methods(http.MethodPost)
	r.HandleFunc("/escrow/{purchaseId}/dispute", eh.DisputeEscrow).Methods(http.MethodPost)

	// Commission endpoints
	r.HandleFunc("/commission/hold", ch.HoldCommission).Methods(http.MethodPost)
	r.HandleFunc("/commission/commit", ch.CommitCommission).Methods(http.MethodPost)
	r.HandleFunc("/commission/release", ch.ReleaseCommission).Methods(http.MethodPost)
	r.HandleFunc("/commission/{purchaseId}", ch.GetCommission).Methods(http.MethodGet)

	// Webhook endpoints (no auth)
	r.HandleFunc("/webhooks/stripe", h.StripeWebhook).Methods(http.MethodPost)
	r.HandleFunc("/webhooks/yookassa", h.YooKassaWebhook).Methods(http.MethodPost)

	port := getEnv("PORT", "4003")
	srv := &http.Server{
		Addr:         ":" + port,
		Handler:      r,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	log.Printf("Payment service starting on :%s", port)
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Server error: %v", err)
	}
}
