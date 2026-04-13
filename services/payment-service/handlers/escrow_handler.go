package handlers

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"payment-service/kafka"
	"payment-service/models"
)

type EscrowHandler struct {
	db    *pgxpool.Pool
	kafka *kafka.Producer
}

func NewEscrowHandler(db *pgxpool.Pool, kp *kafka.Producer) *EscrowHandler {
	return &EscrowHandler{db: db, kafka: kp}
}

// ─── Request types ───────────────────────────────────────────────────────────

type CreateEscrowRequest struct {
	PurchaseID            string `json:"purchase_id"`
	TotalAmount           int64  `json:"total_amount"`
	Threshold             int64  `json:"threshold"`
	ConfirmationsRequired int    `json:"confirmations_required"`
	IdempotencyKey        string `json:"idempotency_key"`
}

type DepositToEscrowRequest struct {
	WalletID       string `json:"wallet_id"`
	Amount         int64  `json:"amount"`
	Currency       string `json:"currency"`
	IdempotencyKey string `json:"idempotency_key"`
}

// ─── CreateEscrow ────────────────────────────────────────────────────────────

func (h *EscrowHandler) CreateEscrow(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "X-User-ID header required")
		return
	}

	var req CreateEscrowRequest
	if err := decodeBody(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if req.PurchaseID == "" {
		writeError(w, http.StatusBadRequest, "purchase_id required")
		return
	}
	if req.TotalAmount <= 0 {
		writeError(w, http.StatusBadRequest, "total_amount must be positive")
		return
	}
	if req.ConfirmationsRequired <= 0 {
		writeError(w, http.StatusBadRequest, "confirmations_required must be positive")
		return
	}
	if req.IdempotencyKey == "" {
		req.IdempotencyKey = uuid.New().String()
	}

	// Check idempotency by purchase_id uniqueness
	existing, err := h.loadEscrowByPurchaseID(r.Context(), req.PurchaseID)
	if err == nil && existing != nil {
		writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": existing})
		return
	}

	id := uuid.New().String()
	threshold := req.Threshold
	if threshold == 0 {
		threshold = int64(float64(req.ConfirmationsRequired) * 0.8)
	}

	_, err = h.db.Exec(r.Context(),
		`INSERT INTO escrow_accounts (id, purchase_id, total_amount, released_amount, status, threshold, confirmations_required, confirmations_received, created_at, updated_at)
		 VALUES ($1, $2, $3, 0, 'active', $4, $5, 0, NOW(), NOW())`,
		id, req.PurchaseID, req.TotalAmount, threshold, req.ConfirmationsRequired,
	)
	if err != nil {
		log.Printf("CreateEscrow error: %v", err)
		writeError(w, http.StatusInternalServerError, "failed to create escrow account")
		return
	}

	escrow, err := h.loadEscrow(r.Context(), id)
	if err != nil {
		log.Printf("CreateEscrow load error: %v", err)
		writeError(w, http.StatusInternalServerError, "failed to load escrow account")
		return
	}

	h.kafka.Send(r.Context(), "escrow.created", req.PurchaseID, map[string]any{
		"escrowId":              id,
		"purchaseId":            req.PurchaseID,
		"totalAmount":           req.TotalAmount,
		"confirmationsRequired": req.ConfirmationsRequired,
		"userId":                userID,
	})

	writeJSON(w, http.StatusCreated, map[string]any{"success": true, "data": escrow})
}

// ─── GetEscrow ───────────────────────────────────────────────────────────────

func (h *EscrowHandler) GetEscrow(w http.ResponseWriter, r *http.Request) {
	purchaseID := mux.Vars(r)["purchaseId"]
	if purchaseID == "" {
		writeError(w, http.StatusBadRequest, "purchaseId required")
		return
	}

	escrow, err := h.loadEscrowByPurchaseID(r.Context(), purchaseID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			writeError(w, http.StatusNotFound, "escrow account not found")
			return
		}
		log.Printf("GetEscrow error: %v", err)
		writeError(w, http.StatusInternalServerError, "failed to get escrow")
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": escrow})
}

// ─── DepositToEscrow ─────────────────────────────────────────────────────────

func (h *EscrowHandler) DepositToEscrow(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "X-User-ID header required")
		return
	}

	purchaseID := mux.Vars(r)["purchaseId"]
	if purchaseID == "" {
		writeError(w, http.StatusBadRequest, "purchaseId required")
		return
	}

	var req DepositToEscrowRequest
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
	if req.Currency == "" {
		req.Currency = "RUB"
	}

	escrow, err := h.loadEscrowByPurchaseID(r.Context(), purchaseID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			writeError(w, http.StatusNotFound, "escrow account not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "failed to load escrow")
		return
	}
	if escrow.Status != models.EscrowStatusActive {
		writeError(w, http.StatusConflict, fmt.Sprintf("escrow is %s, cannot deposit", escrow.Status))
		return
	}

	// Deduct from buyer's wallet and record escrow_in transaction
	pgTx, err := h.db.Begin(r.Context())
	if err != nil {
		writeError(w, http.StatusInternalServerError, "failed to begin transaction")
		return
	}

	// Deduct from wallet
	walletID := req.WalletID
	tag, err := pgTx.Exec(r.Context(),
		`UPDATE wallets SET balance = balance - $1, version = version + 1, updated_at = NOW()
		 WHERE id = $2 AND (balance - held_amount) >= $1 AND status = 'active'`,
		req.Amount, walletID,
	)
	if err != nil {
		pgTx.Rollback(r.Context())
		writeError(w, http.StatusInternalServerError, "failed to deduct from wallet")
		return
	}
	if tag.RowsAffected() == 0 {
		pgTx.Rollback(r.Context())
		writeError(w, http.StatusPaymentRequired, "insufficient funds or wallet not found")
		return
	}

	// Record escrow_in transaction
	txID := uuid.New().String()
	_, err = pgTx.Exec(r.Context(),
		`INSERT INTO transactions (id, idempotency_key, wallet_id, type, amount, currency, status, purchase_id, description, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())`,
		txID, req.IdempotencyKey, walletID, models.TxTypeEscrowIn, req.Amount,
		req.Currency, models.TxStatusCompleted, purchaseID, "Deposit to escrow",
	)
	if err != nil {
		pgTx.Rollback(r.Context())
		writeError(w, http.StatusInternalServerError, "failed to record transaction")
		return
	}

	// Credit escrow account
	tag, err = pgTx.Exec(r.Context(),
		`UPDATE escrow_accounts SET total_amount = total_amount + $1, updated_at = NOW()
		 WHERE purchase_id = $2 AND status = 'active'`,
		req.Amount, purchaseID,
	)
	if err != nil || tag.RowsAffected() == 0 {
		pgTx.Rollback(r.Context())
		writeError(w, http.StatusInternalServerError, "failed to credit escrow")
		return
	}

	if err := pgTx.Commit(r.Context()); err != nil {
		writeError(w, http.StatusInternalServerError, "failed to commit transaction")
		return
	}

	h.kafka.Send(r.Context(), "escrow.deposited", purchaseID, map[string]any{
		"escrowId":      escrow.ID,
		"purchaseId":    purchaseID,
		"walletId":      walletID,
		"transactionId": txID,
		"amount":        req.Amount,
		"userId":        userID,
	})

	writeJSON(w, http.StatusOK, map[string]any{
		"success":       true,
		"transactionId": txID,
		"escrowId":      escrow.ID,
	})
}

// ─── ConfirmDelivery ─────────────────────────────────────────────────────────

func (h *EscrowHandler) ConfirmDelivery(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "X-User-ID header required")
		return
	}

	purchaseID := mux.Vars(r)["purchaseId"]
	if purchaseID == "" {
		writeError(w, http.StatusBadRequest, "purchaseId required")
		return
	}

	escrow, err := h.loadEscrowByPurchaseID(r.Context(), purchaseID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			writeError(w, http.StatusNotFound, "escrow account not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "failed to load escrow")
		return
	}
	if escrow.Status != models.EscrowStatusActive {
		writeError(w, http.StatusConflict, fmt.Sprintf("escrow is %s, cannot confirm", escrow.Status))
		return
	}

	tag, err := h.db.Exec(r.Context(),
		`UPDATE escrow_accounts SET confirmations_received = confirmations_received + 1, updated_at = NOW()
		 WHERE purchase_id = $1 AND status = 'active' AND confirmations_received < confirmations_required`,
		purchaseID,
	)
	if err != nil {
		log.Printf("ConfirmDelivery error: %v", err)
		writeError(w, http.StatusInternalServerError, "failed to confirm delivery")
		return
	}
	if tag.RowsAffected() == 0 {
		writeError(w, http.StatusConflict, "already fully confirmed or escrow not active")
		return
	}

	// Reload to get updated state
	escrow, _ = h.loadEscrowByPurchaseID(r.Context(), purchaseID)

	h.kafka.Send(r.Context(), "escrow.confirmed", purchaseID, map[string]any{
		"escrowId":              escrow.ID,
		"purchaseId":            purchaseID,
		"confirmationsReceived": escrow.ConfirmationsReceived,
		"confirmationsRequired": escrow.ConfirmationsRequired,
		"canRelease":            escrow.CanRelease(),
		"userId":                userID,
	})

	writeJSON(w, http.StatusOK, map[string]any{
		"success":               true,
		"data":                  escrow,
		"canRelease":            escrow.CanRelease(),
	})
}

// ─── ReleaseEscrow ───────────────────────────────────────────────────────────

type ReleaseEscrowRequest struct {
	RecipientWalletID string `json:"recipient_wallet_id"`
	IdempotencyKey    string `json:"idempotency_key"`
}

func (h *EscrowHandler) ReleaseEscrow(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "X-User-ID header required")
		return
	}

	purchaseID := mux.Vars(r)["purchaseId"]
	if purchaseID == "" {
		writeError(w, http.StatusBadRequest, "purchaseId required")
		return
	}

	var req ReleaseEscrowRequest
	if err := decodeBody(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if req.RecipientWalletID == "" {
		writeError(w, http.StatusBadRequest, "recipient_wallet_id required")
		return
	}
	if req.IdempotencyKey == "" {
		req.IdempotencyKey = uuid.New().String()
	}

	escrow, err := h.loadEscrowByPurchaseID(r.Context(), purchaseID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			writeError(w, http.StatusNotFound, "escrow account not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "failed to load escrow")
		return
	}
	if escrow.Status != models.EscrowStatusActive {
		writeError(w, http.StatusConflict, fmt.Sprintf("escrow is %s, cannot release", escrow.Status))
		return
	}
	if !escrow.CanRelease() {
		writeError(w, http.StatusPreconditionFailed,
			fmt.Sprintf("insufficient confirmations: %d/%d (need 80%%)", escrow.ConfirmationsReceived, escrow.ConfirmationsRequired))
		return
	}

	releaseAmount := escrow.TotalAmount - escrow.ReleasedAmount
	if releaseAmount <= 0 {
		writeError(w, http.StatusConflict, "no funds to release")
		return
	}

	pgTx, err := h.db.Begin(r.Context())
	if err != nil {
		writeError(w, http.StatusInternalServerError, "failed to begin transaction")
		return
	}

	// Mark escrow as released
	tag, err := pgTx.Exec(r.Context(),
		`UPDATE escrow_accounts SET status = 'released', released_amount = total_amount, updated_at = NOW()
		 WHERE purchase_id = $1 AND status = 'active'`,
		purchaseID,
	)
	if err != nil || tag.RowsAffected() == 0 {
		pgTx.Rollback(r.Context())
		writeError(w, http.StatusInternalServerError, "failed to update escrow status")
		return
	}

	// Credit recipient wallet
	tag, err = pgTx.Exec(r.Context(),
		`UPDATE wallets SET balance = balance + $1, version = version + 1, updated_at = NOW()
		 WHERE id = $2 AND status = 'active'`,
		releaseAmount, req.RecipientWalletID,
	)
	if err != nil || tag.RowsAffected() == 0 {
		pgTx.Rollback(r.Context())
		writeError(w, http.StatusInternalServerError, "failed to credit recipient wallet")
		return
	}

	// Record escrow_out transaction
	txID := uuid.New().String()
	_, err = pgTx.Exec(r.Context(),
		`INSERT INTO transactions (id, idempotency_key, wallet_id, type, amount, currency, status, purchase_id, description, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, 'RUB', $6, $7, $8, NOW(), NOW())`,
		txID, req.IdempotencyKey, req.RecipientWalletID, models.TxTypeEscrowOut,
		releaseAmount, models.TxStatusCompleted, purchaseID, "Escrow release to recipient",
	)
	if err != nil {
		pgTx.Rollback(r.Context())
		writeError(w, http.StatusInternalServerError, "failed to record transaction")
		return
	}

	if err := pgTx.Commit(r.Context()); err != nil {
		writeError(w, http.StatusInternalServerError, "failed to commit transaction")
		return
	}

	h.kafka.Send(r.Context(), "escrow.released", purchaseID, map[string]any{
		"escrowId":          escrow.ID,
		"purchaseId":        purchaseID,
		"recipientWalletId": req.RecipientWalletID,
		"transactionId":     txID,
		"amount":            releaseAmount,
		"userId":            userID,
	})

	writeJSON(w, http.StatusOK, map[string]any{
		"success":       true,
		"transactionId": txID,
		"releasedAmount": releaseAmount,
	})
}

// ─── DisputeEscrow ───────────────────────────────────────────────────────────

type DisputeEscrowRequest struct {
	Reason string `json:"reason"`
}

func (h *EscrowHandler) DisputeEscrow(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "X-User-ID header required")
		return
	}

	purchaseID := mux.Vars(r)["purchaseId"]
	if purchaseID == "" {
		writeError(w, http.StatusBadRequest, "purchaseId required")
		return
	}

	var req DisputeEscrowRequest
	if err := decodeBody(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	escrow, err := h.loadEscrowByPurchaseID(r.Context(), purchaseID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			writeError(w, http.StatusNotFound, "escrow account not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "failed to load escrow")
		return
	}
	if escrow.Status != models.EscrowStatusActive {
		writeError(w, http.StatusConflict, fmt.Sprintf("escrow is %s, cannot dispute", escrow.Status))
		return
	}

	tag, err := h.db.Exec(r.Context(),
		`UPDATE escrow_accounts SET status = 'disputed', updated_at = NOW()
		 WHERE purchase_id = $1 AND status = 'active'`,
		purchaseID,
	)
	if err != nil || tag.RowsAffected() == 0 {
		log.Printf("DisputeEscrow error: %v", err)
		writeError(w, http.StatusInternalServerError, "failed to dispute escrow")
		return
	}

	h.kafka.Send(r.Context(), "escrow.disputed", purchaseID, map[string]any{
		"escrowId":   escrow.ID,
		"purchaseId": purchaseID,
		"reason":     req.Reason,
		"amount":     escrow.TotalAmount,
		"userId":     userID,
	})

	escrow.Status = models.EscrowStatusDisputed
	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": escrow})
}

// ─── DB helpers ──────────────────────────────────────────────────────────────

func (h *EscrowHandler) loadEscrow(ctx context.Context, id string) (*models.EscrowAccount, error) {
	row := h.db.QueryRow(ctx,
		`SELECT id, purchase_id, total_amount, released_amount, status, threshold, confirmations_required, confirmations_received, created_at, updated_at
		 FROM escrow_accounts WHERE id = $1`, id)
	return scanEscrow(row)
}

func (h *EscrowHandler) loadEscrowByPurchaseID(ctx context.Context, purchaseID string) (*models.EscrowAccount, error) {
	row := h.db.QueryRow(ctx,
		`SELECT id, purchase_id, total_amount, released_amount, status, threshold, confirmations_required, confirmations_received, created_at, updated_at
		 FROM escrow_accounts WHERE purchase_id = $1`, purchaseID)
	return scanEscrow(row)
}

func scanEscrow(row pgx.Row) (*models.EscrowAccount, error) {
	e := &models.EscrowAccount{}
	err := row.Scan(&e.ID, &e.PurchaseID, &e.TotalAmount, &e.ReleasedAmount,
		&e.Status, &e.Threshold, &e.ConfirmationsRequired, &e.ConfirmationsReceived,
		&e.CreatedAt, &e.UpdatedAt)
	if err != nil {
		return nil, err
	}
	return e, nil
}
