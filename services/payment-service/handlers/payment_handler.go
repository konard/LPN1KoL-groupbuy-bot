package handlers

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"payment-service/kafka"
	"payment-service/models"
)

type PaymentHandler struct {
	db       *pgxpool.Pool
	kafka    *kafka.Producer
}

func NewPaymentHandler(db *pgxpool.Pool, kp *kafka.Producer) *PaymentHandler {
	return &PaymentHandler{db: db, kafka: kp}
}

// ─── Request / Response helpers ───────────────────────────────────────────────

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}

func decodeBody(r *http.Request, dst any) error {
	if err := json.NewDecoder(r.Body).Decode(dst); err != nil {
		return fmt.Errorf("invalid JSON: %w", err)
	}
	return nil
}

// ─── Health ───────────────────────────────────────────────────────────────────

func (h *PaymentHandler) Health(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok", "service": "payment-service"})
}

// ─── Get Wallet ───────────────────────────────────────────────────────────────

func (h *PaymentHandler) GetWallet(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "X-User-ID header required")
		return
	}

	wallet, err := h.getOrCreateWallet(r.Context(), userID)
	if err != nil {
		log.Printf("GetWallet error: %v", err)
		writeError(w, http.StatusInternalServerError, "failed to get wallet")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": wallet})
}

// ─── Top Up ───────────────────────────────────────────────────────────────────

type TopUpRequest struct {
	Amount         int64  `json:"amount"`           // minor units
	Currency       string `json:"currency"`
	IdempotencyKey string `json:"idempotency_key"`
	ExternalRef    string `json:"external_ref"`
}

func (h *PaymentHandler) TopUp(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "X-User-ID header required")
		return
	}

	var req TopUpRequest
	if err := decodeBody(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if req.Amount <= 0 {
		writeError(w, http.StatusBadRequest, "amount must be positive")
		return
	}
	if req.IdempotencyKey == "" {
		req.IdempotencyKey = uuid.New().String()
	}

	tx, err := h.idempotentOperation(r.Context(), req.IdempotencyKey, func(ctx context.Context) (*models.Transaction, error) {
		return h.doTopUp(ctx, userID, req)
	})
	if err != nil {
		log.Printf("TopUp error: %v", err)
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": tx})
}

// ─── Hold ─────────────────────────────────────────────────────────────────────

type HoldRequest struct {
	Amount         int64  `json:"amount"`
	Currency       string `json:"currency"`
	IdempotencyKey string `json:"idempotency_key"`
	PurchaseID     string `json:"purchase_id"`
	Description    string `json:"description"`
}

func (h *PaymentHandler) Hold(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "X-User-ID header required")
		return
	}

	var req HoldRequest
	if err := decodeBody(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if req.Amount <= 0 {
		writeError(w, http.StatusBadRequest, "amount must be positive")
		return
	}
	if req.IdempotencyKey == "" {
		req.IdempotencyKey = uuid.New().String()
	}

	tx, err := h.idempotentOperation(r.Context(), req.IdempotencyKey, func(ctx context.Context) (*models.Transaction, error) {
		return h.doHold(ctx, userID, req)
	})
	if err != nil {
		log.Printf("Hold error: %v", err)
		if errors.Is(err, ErrInsufficientFunds) {
			writeError(w, http.StatusPaymentRequired, "insufficient funds")
			return
		}
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": tx})
}

// ─── Commit ───────────────────────────────────────────────────────────────────

type CommitRequest struct {
	HoldTransactionID string `json:"hold_transaction_id"`
	IdempotencyKey    string `json:"idempotency_key"`
}

func (h *PaymentHandler) Commit(w http.ResponseWriter, r *http.Request) {
	var req CommitRequest
	if err := decodeBody(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if req.HoldTransactionID == "" {
		writeError(w, http.StatusBadRequest, "hold_transaction_id required")
		return
	}
	if req.IdempotencyKey == "" {
		req.IdempotencyKey = uuid.New().String()
	}

	tx, err := h.idempotentOperation(r.Context(), req.IdempotencyKey, func(ctx context.Context) (*models.Transaction, error) {
		return h.doCommit(ctx, req.HoldTransactionID)
	})
	if err != nil {
		log.Printf("Commit error: %v", err)
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": tx})
}

// ─── Release (cancel hold) ────────────────────────────────────────────────────

type ReleaseRequest struct {
	HoldTransactionID string `json:"hold_transaction_id"`
	IdempotencyKey    string `json:"idempotency_key"`
}

func (h *PaymentHandler) Release(w http.ResponseWriter, r *http.Request) {
	var req ReleaseRequest
	if err := decodeBody(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if req.HoldTransactionID == "" {
		writeError(w, http.StatusBadRequest, "hold_transaction_id required")
		return
	}
	if req.IdempotencyKey == "" {
		req.IdempotencyKey = uuid.New().String()
	}

	tx, err := h.idempotentOperation(r.Context(), req.IdempotencyKey, func(ctx context.Context) (*models.Transaction, error) {
		return h.doRelease(ctx, req.HoldTransactionID)
	})
	if err != nil {
		log.Printf("Release error: %v", err)
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": tx})
}

// ─── Webhook (Stripe / YooKassa) ──────────────────────────────────────────────

func (h *PaymentHandler) StripeWebhook(w http.ResponseWriter, r *http.Request) {
	// In production: verify Stripe-Signature header
	var event map[string]any
	if err := decodeBody(r, &event); err != nil {
		writeError(w, http.StatusBadRequest, "invalid payload")
		return
	}
	eventType, _ := event["type"].(string)
	log.Printf("Stripe webhook: %s", eventType)

	switch eventType {
	case "payment_intent.succeeded":
		// Extract metadata, top up wallet
		h.kafka.Send(r.Context(), "payment.stripe.succeeded", "", map[string]any{"event": event})
	case "payment_intent.payment_failed":
		h.kafka.Send(r.Context(), "payment.stripe.failed", "", map[string]any{"event": event})
	}
	w.WriteHeader(http.StatusOK)
}

func (h *PaymentHandler) YooKassaWebhook(w http.ResponseWriter, r *http.Request) {
	var event map[string]any
	if err := decodeBody(r, &event); err != nil {
		writeError(w, http.StatusBadRequest, "invalid payload")
		return
	}
	eventType, _ := event["event"].(string)
	log.Printf("YooKassa webhook: %s", eventType)

	switch eventType {
	case "payment.succeeded":
		h.kafka.Send(r.Context(), "payment.yookassa.succeeded", "", map[string]any{"event": event})
	case "payment.canceled":
		h.kafka.Send(r.Context(), "payment.yookassa.cancelled", "", map[string]any{"event": event})
	}
	w.WriteHeader(http.StatusOK)
}

// ─── Errors ───────────────────────────────────────────────────────────────────

var ErrInsufficientFunds = errors.New("insufficient funds")
var ErrOptimisticLock = errors.New("optimistic lock conflict, retry")

// ─── Core Business Logic ──────────────────────────────────────────────────────

// idempotentOperation checks idempotency key first, executes fn if not found,
// saves result.
func (h *PaymentHandler) idempotentOperation(
	ctx context.Context,
	key string,
	fn func(ctx context.Context) (*models.Transaction, error),
) (*models.Transaction, error) {
	// Check if already processed
	existing, err := h.findTransactionByIdempotencyKey(ctx, key)
	if err == nil && existing != nil {
		return existing, nil
	}
	return fn(ctx)
}

func (h *PaymentHandler) doTopUp(ctx context.Context, userID string, req TopUpRequest) (*models.Transaction, error) {
	const maxRetries = 3
	for attempt := 0; attempt < maxRetries; attempt++ {
		wallet, err := h.getOrCreateWallet(ctx, userID)
		if err != nil {
			return nil, err
		}

		var tx *models.Transaction
		pgTx, err := h.db.Begin(ctx)
		if err != nil {
			return nil, err
		}

		// Optimistic lock: update only if version matches
		tag, err := pgTx.Exec(ctx,
			`UPDATE wallets SET balance = balance + $1, version = version + 1, updated_at = NOW()
			 WHERE id = $2 AND version = $3`,
			req.Amount, wallet.ID, wallet.Version,
		)
		if err != nil {
			pgTx.Rollback(ctx)
			return nil, err
		}
		if tag.RowsAffected() == 0 {
			pgTx.Rollback(ctx)
			if attempt < maxRetries-1 {
				time.Sleep(time.Duration(attempt+1) * 10 * time.Millisecond)
				continue
			}
			return nil, ErrOptimisticLock
		}

		txID := uuid.New().String()
		extRef := req.ExternalRef
		_, err = pgTx.Exec(ctx,
			`INSERT INTO transactions (id, idempotency_key, wallet_id, type, amount, currency, status, external_ref, description, created_at, updated_at)
			 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())`,
			txID, req.IdempotencyKey, wallet.ID, models.TxTypeTopUp, req.Amount,
			req.Currency, models.TxStatusCompleted, extRef, "Wallet top-up",
		)
		if err != nil {
			pgTx.Rollback(ctx)
			return nil, err
		}

		if err := pgTx.Commit(ctx); err != nil {
			return nil, err
		}

		tx = &models.Transaction{
			ID:             txID,
			IdempotencyKey: req.IdempotencyKey,
			WalletID:       wallet.ID,
			Type:           models.TxTypeTopUp,
			Amount:         req.Amount,
			Currency:       req.Currency,
			Status:         models.TxStatusCompleted,
		}

		h.kafka.Send(ctx, "payment.topup.completed", wallet.UserID, map[string]any{
			"userId":         userID,
			"walletId":       wallet.ID,
			"transactionId":  txID,
			"amount":         req.Amount,
			"currency":       req.Currency,
		})

		return tx, nil
	}
	return nil, ErrOptimisticLock
}

func (h *PaymentHandler) doHold(ctx context.Context, userID string, req HoldRequest) (*models.Transaction, error) {
	const maxRetries = 3
	for attempt := 0; attempt < maxRetries; attempt++ {
		wallet, err := h.getOrCreateWallet(ctx, userID)
		if err != nil {
			return nil, err
		}

		if wallet.AvailableBalance() < req.Amount {
			return nil, ErrInsufficientFunds
		}

		pgTx, err := h.db.Begin(ctx)
		if err != nil {
			return nil, err
		}

		tag, err := pgTx.Exec(ctx,
			`UPDATE wallets SET held_amount = held_amount + $1, version = version + 1, updated_at = NOW()
			 WHERE id = $2 AND version = $3 AND (balance - held_amount) >= $1`,
			req.Amount, wallet.ID, wallet.Version,
		)
		if err != nil {
			pgTx.Rollback(ctx)
			return nil, err
		}
		if tag.RowsAffected() == 0 {
			pgTx.Rollback(ctx)
			// Refresh wallet to check if it's funds or lock conflict
			fresh, _ := h.loadWallet(ctx, wallet.ID)
			if fresh != nil && fresh.AvailableBalance() < req.Amount {
				return nil, ErrInsufficientFunds
			}
			if attempt < maxRetries-1 {
				time.Sleep(time.Duration(attempt+1) * 10 * time.Millisecond)
				continue
			}
			return nil, ErrOptimisticLock
		}

		txID := uuid.New().String()
		purchaseID := req.PurchaseID
		_, err = pgTx.Exec(ctx,
			`INSERT INTO transactions (id, idempotency_key, wallet_id, type, amount, currency, status, purchase_id, description, created_at, updated_at)
			 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())`,
			txID, req.IdempotencyKey, wallet.ID, models.TxTypeHold, req.Amount,
			req.Currency, models.TxStatusCompleted, purchaseID, req.Description,
		)
		if err != nil {
			pgTx.Rollback(ctx)
			return nil, err
		}

		if err := pgTx.Commit(ctx); err != nil {
			return nil, err
		}

		tx := &models.Transaction{
			ID:             txID,
			IdempotencyKey: req.IdempotencyKey,
			WalletID:       wallet.ID,
			Type:           models.TxTypeHold,
			Amount:         req.Amount,
			Status:         models.TxStatusCompleted,
		}

		h.kafka.Send(ctx, "payment.hold.created", wallet.UserID, map[string]any{
			"userId":        userID,
			"walletId":      wallet.ID,
			"transactionId": txID,
			"amount":        req.Amount,
			"purchaseId":    purchaseID,
		})

		return tx, nil
	}
	return nil, ErrOptimisticLock
}

func (h *PaymentHandler) doCommit(ctx context.Context, holdTxID string) (*models.Transaction, error) {
	// Load the hold transaction
	holdTx, err := h.loadTransaction(ctx, holdTxID)
	if err != nil {
		return nil, fmt.Errorf("hold transaction not found: %w", err)
	}
	if holdTx.Type != models.TxTypeHold {
		return nil, errors.New("transaction is not a hold")
	}
	if holdTx.Status != models.TxStatusCompleted {
		return nil, errors.New("hold transaction is not in completed state")
	}

	pgTx, err := h.db.Begin(ctx)
	if err != nil {
		return nil, err
	}

	// Deduct balance and held amount
	tag, err := pgTx.Exec(ctx,
		`UPDATE wallets SET balance = balance - $1, held_amount = held_amount - $1, version = version + 1, updated_at = NOW()
		 WHERE id = $2 AND held_amount >= $1`,
		holdTx.Amount, holdTx.WalletID,
	)
	if err != nil {
		pgTx.Rollback(ctx)
		return nil, err
	}
	if tag.RowsAffected() == 0 {
		pgTx.Rollback(ctx)
		return nil, errors.New("commit failed: insufficient held amount")
	}

	// Mark hold as rolled back (consumed)
	_, err = pgTx.Exec(ctx,
		`UPDATE transactions SET status = $1, updated_at = NOW() WHERE id = $2`,
		models.TxStatusRolledBack, holdTxID,
	)
	if err != nil {
		pgTx.Rollback(ctx)
		return nil, err
	}

	// Create commit transaction
	txID := uuid.New().String()
	_, err = pgTx.Exec(ctx,
		`INSERT INTO transactions (id, idempotency_key, wallet_id, type, amount, currency, status, related_tx_id, purchase_id, description, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW())`,
		txID, uuid.New().String(), holdTx.WalletID, models.TxTypeCommit,
		holdTx.Amount, holdTx.Currency, models.TxStatusCompleted,
		&holdTxID, holdTx.PurchaseID, "Payment committed",
	)
	if err != nil {
		pgTx.Rollback(ctx)
		return nil, err
	}

	if err := pgTx.Commit(ctx); err != nil {
		return nil, err
	}

	tx := &models.Transaction{
		ID:          txID,
		WalletID:    holdTx.WalletID,
		Type:        models.TxTypeCommit,
		Amount:      holdTx.Amount,
		Status:      models.TxStatusCompleted,
		RelatedTxID: &holdTxID,
	}

	h.kafka.Send(ctx, "payment.committed", holdTx.WalletID, map[string]any{
		"walletId":      holdTx.WalletID,
		"transactionId": txID,
		"holdTxId":      holdTxID,
		"amount":        holdTx.Amount,
	})

	return tx, nil
}

func (h *PaymentHandler) doRelease(ctx context.Context, holdTxID string) (*models.Transaction, error) {
	holdTx, err := h.loadTransaction(ctx, holdTxID)
	if err != nil {
		return nil, fmt.Errorf("hold transaction not found: %w", err)
	}
	if holdTx.Type != models.TxTypeHold {
		return nil, errors.New("transaction is not a hold")
	}

	pgTx, err := h.db.Begin(ctx)
	if err != nil {
		return nil, err
	}

	tag, err := pgTx.Exec(ctx,
		`UPDATE wallets SET held_amount = held_amount - $1, version = version + 1, updated_at = NOW()
		 WHERE id = $2 AND held_amount >= $1`,
		holdTx.Amount, holdTx.WalletID,
	)
	if err != nil {
		pgTx.Rollback(ctx)
		return nil, err
	}
	if tag.RowsAffected() == 0 {
		pgTx.Rollback(ctx)
		return nil, errors.New("release failed")
	}

	_, err = pgTx.Exec(ctx,
		`UPDATE transactions SET status = $1, updated_at = NOW() WHERE id = $2`,
		models.TxStatusRolledBack, holdTxID,
	)
	if err != nil {
		pgTx.Rollback(ctx)
		return nil, err
	}

	txID := uuid.New().String()
	_, err = pgTx.Exec(ctx,
		`INSERT INTO transactions (id, idempotency_key, wallet_id, type, amount, currency, status, related_tx_id, purchase_id, description, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW())`,
		txID, uuid.New().String(), holdTx.WalletID, models.TxTypeRelease,
		holdTx.Amount, holdTx.Currency, models.TxStatusCompleted,
		&holdTxID, holdTx.PurchaseID, "Hold released",
	)
	if err != nil {
		pgTx.Rollback(ctx)
		return nil, err
	}

	if err := pgTx.Commit(ctx); err != nil {
		return nil, err
	}

	tx := &models.Transaction{
		ID:          txID,
		WalletID:    holdTx.WalletID,
		Type:        models.TxTypeRelease,
		Amount:      holdTx.Amount,
		Status:      models.TxStatusCompleted,
		RelatedTxID: &holdTxID,
	}

	h.kafka.Send(ctx, "payment.released", holdTx.WalletID, map[string]any{
		"walletId":      holdTx.WalletID,
		"transactionId": txID,
		"holdTxId":      holdTxID,
		"amount":        holdTx.Amount,
	})

	return tx, nil
}

// ─── DB helpers ───────────────────────────────────────────────────────────────

func (h *PaymentHandler) getOrCreateWallet(ctx context.Context, userID string) (*models.Wallet, error) {
	wallet, err := h.loadWalletByUserID(ctx, userID)
	if err == nil {
		return wallet, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return nil, err
	}

	// Create wallet
	id := uuid.New().String()
	_, err = h.db.Exec(ctx,
		`INSERT INTO wallets (id, user_id, balance, held_amount, currency, status, version, created_at, updated_at)
		 VALUES ($1, $2, 0, 0, 'RUB', 'active', 0, NOW(), NOW())
		 ON CONFLICT (user_id) DO NOTHING`,
		id, userID,
	)
	if err != nil {
		return nil, err
	}
	return h.loadWalletByUserID(ctx, userID)
}

func (h *PaymentHandler) loadWalletByUserID(ctx context.Context, userID string) (*models.Wallet, error) {
	row := h.db.QueryRow(ctx,
		`SELECT id, user_id, balance, held_amount, currency, status, version, created_at, updated_at
		 FROM wallets WHERE user_id = $1`, userID)
	return scanWallet(row)
}

func (h *PaymentHandler) loadWallet(ctx context.Context, id string) (*models.Wallet, error) {
	row := h.db.QueryRow(ctx,
		`SELECT id, user_id, balance, held_amount, currency, status, version, created_at, updated_at
		 FROM wallets WHERE id = $1`, id)
	return scanWallet(row)
}

func scanWallet(row pgx.Row) (*models.Wallet, error) {
	w := &models.Wallet{}
	err := row.Scan(&w.ID, &w.UserID, &w.Balance, &w.HeldAmount,
		&w.Currency, &w.Status, &w.Version, &w.CreatedAt, &w.UpdatedAt)
	if err != nil {
		return nil, err
	}
	return w, nil
}

func (h *PaymentHandler) loadTransaction(ctx context.Context, id string) (*models.Transaction, error) {
	row := h.db.QueryRow(ctx,
		`SELECT id, idempotency_key, wallet_id, type, amount, currency, status, related_tx_id, purchase_id, description, created_at, updated_at
		 FROM transactions WHERE id = $1`, id)
	tx := &models.Transaction{}
	err := row.Scan(&tx.ID, &tx.IdempotencyKey, &tx.WalletID, &tx.Type,
		&tx.Amount, &tx.Currency, &tx.Status, &tx.RelatedTxID,
		&tx.PurchaseID, &tx.Description, &tx.CreatedAt, &tx.UpdatedAt)
	if err != nil {
		return nil, err
	}
	return tx, nil
}

func (h *PaymentHandler) findTransactionByIdempotencyKey(ctx context.Context, key string) (*models.Transaction, error) {
	row := h.db.QueryRow(ctx,
		`SELECT id, idempotency_key, wallet_id, type, amount, currency, status, related_tx_id, purchase_id, description, created_at, updated_at
		 FROM transactions WHERE idempotency_key = $1`, key)
	tx := &models.Transaction{}
	err := row.Scan(&tx.ID, &tx.IdempotencyKey, &tx.WalletID, &tx.Type,
		&tx.Amount, &tx.Currency, &tx.Status, &tx.RelatedTxID,
		&tx.PurchaseID, &tx.Description, &tx.CreatedAt, &tx.UpdatedAt)
	if err != nil {
		return nil, err
	}
	return tx, nil
}
