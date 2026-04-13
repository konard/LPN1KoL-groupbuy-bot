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

type CommissionHandler struct {
	db    *pgxpool.Pool
	kafka *kafka.Producer
}

func NewCommissionHandler(db *pgxpool.Pool, kp *kafka.Producer) *CommissionHandler {
	return &CommissionHandler{db: db, kafka: kp}
}

// ─── Request types ───────────────────────────────────────────────────────────

type HoldCommissionRequest struct {
	PurchaseID        string  `json:"purchase_id"`
	OrganizerWalletID string  `json:"organizer_wallet_id"`
	Amount            int64   `json:"amount"`
	Percent           float64 `json:"percent"`
	IdempotencyKey    string  `json:"idempotency_key"`
}

type CommitCommissionRequest struct {
	PurchaseID     string `json:"purchase_id"`
	IdempotencyKey string `json:"idempotency_key"`
}

type ReleaseCommissionRequest struct {
	PurchaseID     string `json:"purchase_id"`
	IdempotencyKey string `json:"idempotency_key"`
}

// ─── HoldCommission ──────────────────────────────────────────────────────────

func (h *CommissionHandler) HoldCommission(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "X-User-ID header required")
		return
	}

	var req HoldCommissionRequest
	if err := decodeBody(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if req.PurchaseID == "" {
		writeError(w, http.StatusBadRequest, "purchase_id required")
		return
	}
	if req.OrganizerWalletID == "" {
		writeError(w, http.StatusBadRequest, "organizer_wallet_id required")
		return
	}
	if req.Amount <= 0 {
		writeError(w, http.StatusBadRequest, "amount must be positive")
		return
	}
	if req.Percent <= 0 || req.Percent > 100 {
		writeError(w, http.StatusBadRequest, "percent must be between 0 and 100")
		return
	}
	if req.IdempotencyKey == "" {
		req.IdempotencyKey = uuid.New().String()
	}

	// Check idempotency: if commission already exists for this purchase, return it
	existing, err := h.loadCommissionByPurchaseID(r.Context(), req.PurchaseID)
	if err == nil && existing != nil {
		writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": existing})
		return
	}

	pgTx, err := h.db.Begin(r.Context())
	if err != nil {
		writeError(w, http.StatusInternalServerError, "failed to begin transaction")
		return
	}

	// Hold funds on organizer's wallet
	tag, err := pgTx.Exec(r.Context(),
		`UPDATE wallets SET held_amount = held_amount + $1, version = version + 1, updated_at = NOW()
		 WHERE id = $2 AND (balance - held_amount) >= $1 AND status = 'active'`,
		req.Amount, req.OrganizerWalletID,
	)
	if err != nil {
		pgTx.Rollback(r.Context())
		writeError(w, http.StatusInternalServerError, "failed to hold funds")
		return
	}
	if tag.RowsAffected() == 0 {
		pgTx.Rollback(r.Context())
		writeError(w, http.StatusPaymentRequired, "insufficient funds in organizer wallet")
		return
	}

	// Record commission transaction
	txID := uuid.New().String()
	_, err = pgTx.Exec(r.Context(),
		`INSERT INTO transactions (id, idempotency_key, wallet_id, type, amount, currency, status, purchase_id, description, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, 'RUB', $6, $7, $8, NOW(), NOW())`,
		txID, req.IdempotencyKey, req.OrganizerWalletID, models.TxTypeCommission,
		req.Amount, models.TxStatusCompleted, req.PurchaseID, "Commission hold",
	)
	if err != nil {
		pgTx.Rollback(r.Context())
		writeError(w, http.StatusInternalServerError, "failed to record transaction")
		return
	}

	// Create commission hold record
	commissionID := uuid.New().String()
	_, err = pgTx.Exec(r.Context(),
		`INSERT INTO commission_holds (id, purchase_id, organizer_wallet_id, amount, percent, status, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, 'held', NOW(), NOW())`,
		commissionID, req.PurchaseID, req.OrganizerWalletID, req.Amount, req.Percent,
	)
	if err != nil {
		pgTx.Rollback(r.Context())
		writeError(w, http.StatusInternalServerError, "failed to create commission hold")
		return
	}

	if err := pgTx.Commit(r.Context()); err != nil {
		writeError(w, http.StatusInternalServerError, "failed to commit transaction")
		return
	}

	commission, _ := h.loadCommission(r.Context(), commissionID)

	h.kafka.Send(r.Context(), "commission.held", req.PurchaseID, map[string]any{
		"commissionId":      commissionID,
		"purchaseId":        req.PurchaseID,
		"organizerWalletId": req.OrganizerWalletID,
		"amount":            req.Amount,
		"percent":           req.Percent,
		"transactionId":     txID,
		"userId":            userID,
	})

	writeJSON(w, http.StatusCreated, map[string]any{"success": true, "data": commission})
}

// ─── CommitCommission ────────────────────────────────────────────────────────

func (h *CommissionHandler) CommitCommission(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "X-User-ID header required")
		return
	}

	var req CommitCommissionRequest
	if err := decodeBody(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if req.PurchaseID == "" {
		writeError(w, http.StatusBadRequest, "purchase_id required")
		return
	}
	if req.IdempotencyKey == "" {
		req.IdempotencyKey = uuid.New().String()
	}

	commission, err := h.loadCommissionByPurchaseID(r.Context(), req.PurchaseID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			writeError(w, http.StatusNotFound, "commission hold not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "failed to load commission")
		return
	}
	if commission.Status != models.CommissionStatusHeld {
		writeError(w, http.StatusConflict, fmt.Sprintf("commission is %s, cannot commit", commission.Status))
		return
	}

	pgTx, err := h.db.Begin(r.Context())
	if err != nil {
		writeError(w, http.StatusInternalServerError, "failed to begin transaction")
		return
	}

	// Deduct held amount and balance from organizer's wallet (commit the hold)
	tag, err := pgTx.Exec(r.Context(),
		`UPDATE wallets SET balance = balance - $1, held_amount = held_amount - $1, version = version + 1, updated_at = NOW()
		 WHERE id = $2 AND held_amount >= $1`,
		commission.Amount, commission.OrganizerWalletID,
	)
	if err != nil || tag.RowsAffected() == 0 {
		pgTx.Rollback(r.Context())
		writeError(w, http.StatusInternalServerError, "failed to commit held funds")
		return
	}

	// Update commission status
	_, err = pgTx.Exec(r.Context(),
		`UPDATE commission_holds SET status = 'committed', updated_at = NOW()
		 WHERE id = $1 AND status = 'held'`,
		commission.ID,
	)
	if err != nil {
		pgTx.Rollback(r.Context())
		writeError(w, http.StatusInternalServerError, "failed to update commission status")
		return
	}

	// Record commission commit transaction
	txID := uuid.New().String()
	_, err = pgTx.Exec(r.Context(),
		`INSERT INTO transactions (id, idempotency_key, wallet_id, type, amount, currency, status, purchase_id, description, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, 'RUB', $6, $7, $8, NOW(), NOW())`,
		txID, req.IdempotencyKey, commission.OrganizerWalletID, models.TxTypeCommission,
		commission.Amount, models.TxStatusCompleted, req.PurchaseID, "Commission committed",
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

	commission.Status = models.CommissionStatusCommitted

	h.kafka.Send(r.Context(), "commission.committed", req.PurchaseID, map[string]any{
		"commissionId":      commission.ID,
		"purchaseId":        req.PurchaseID,
		"organizerWalletId": commission.OrganizerWalletID,
		"amount":            commission.Amount,
		"transactionId":     txID,
		"userId":            userID,
	})

	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": commission})
}

// ─── ReleaseCommission ───────────────────────────────────────────────────────

func (h *CommissionHandler) ReleaseCommission(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "X-User-ID header required")
		return
	}

	var req ReleaseCommissionRequest
	if err := decodeBody(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if req.PurchaseID == "" {
		writeError(w, http.StatusBadRequest, "purchase_id required")
		return
	}
	if req.IdempotencyKey == "" {
		req.IdempotencyKey = uuid.New().String()
	}

	commission, err := h.loadCommissionByPurchaseID(r.Context(), req.PurchaseID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			writeError(w, http.StatusNotFound, "commission hold not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "failed to load commission")
		return
	}
	if commission.Status != models.CommissionStatusHeld {
		writeError(w, http.StatusConflict, fmt.Sprintf("commission is %s, cannot release", commission.Status))
		return
	}

	pgTx, err := h.db.Begin(r.Context())
	if err != nil {
		writeError(w, http.StatusInternalServerError, "failed to begin transaction")
		return
	}

	// Release held amount back to organizer's wallet
	tag, err := pgTx.Exec(r.Context(),
		`UPDATE wallets SET held_amount = held_amount - $1, version = version + 1, updated_at = NOW()
		 WHERE id = $2 AND held_amount >= $1`,
		commission.Amount, commission.OrganizerWalletID,
	)
	if err != nil || tag.RowsAffected() == 0 {
		pgTx.Rollback(r.Context())
		writeError(w, http.StatusInternalServerError, "failed to release held funds")
		return
	}

	// Update commission status
	_, err = pgTx.Exec(r.Context(),
		`UPDATE commission_holds SET status = 'released', updated_at = NOW()
		 WHERE id = $1 AND status = 'held'`,
		commission.ID,
	)
	if err != nil {
		pgTx.Rollback(r.Context())
		writeError(w, http.StatusInternalServerError, "failed to update commission status")
		return
	}

	// Record release transaction
	txID := uuid.New().String()
	_, err = pgTx.Exec(r.Context(),
		`INSERT INTO transactions (id, idempotency_key, wallet_id, type, amount, currency, status, purchase_id, description, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, 'RUB', $6, $7, $8, NOW(), NOW())`,
		txID, req.IdempotencyKey, commission.OrganizerWalletID, models.TxTypeCommission,
		commission.Amount, models.TxStatusCompleted, req.PurchaseID, "Commission released",
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

	commission.Status = models.CommissionStatusReleased

	h.kafka.Send(r.Context(), "commission.released", req.PurchaseID, map[string]any{
		"commissionId":      commission.ID,
		"purchaseId":        req.PurchaseID,
		"organizerWalletId": commission.OrganizerWalletID,
		"amount":            commission.Amount,
		"transactionId":     txID,
		"userId":            userID,
	})

	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": commission})
}

// ─── GetCommission ───────────────────────────────────────────────────────────

func (h *CommissionHandler) GetCommission(w http.ResponseWriter, r *http.Request) {
	purchaseID := mux.Vars(r)["purchaseId"]
	if purchaseID == "" {
		writeError(w, http.StatusBadRequest, "purchaseId required")
		return
	}

	commission, err := h.loadCommissionByPurchaseID(r.Context(), purchaseID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			writeError(w, http.StatusNotFound, "commission hold not found")
			return
		}
		log.Printf("GetCommission error: %v", err)
		writeError(w, http.StatusInternalServerError, "failed to get commission")
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": commission})
}

// ─── DB helpers ──────────────────────────────────────────────────────────────

func (h *CommissionHandler) loadCommission(ctx context.Context, id string) (*models.CommissionHold, error) {
	row := h.db.QueryRow(ctx,
		`SELECT id, purchase_id, organizer_wallet_id, amount, percent, status, created_at, updated_at
		 FROM commission_holds WHERE id = $1`, id)
	return scanCommission(row)
}

func (h *CommissionHandler) loadCommissionByPurchaseID(ctx context.Context, purchaseID string) (*models.CommissionHold, error) {
	row := h.db.QueryRow(ctx,
		`SELECT id, purchase_id, organizer_wallet_id, amount, percent, status, created_at, updated_at
		 FROM commission_holds WHERE purchase_id = $1`, purchaseID)
	return scanCommission(row)
}

func scanCommission(row pgx.Row) (*models.CommissionHold, error) {
	c := &models.CommissionHold{}
	err := row.Scan(&c.ID, &c.PurchaseID, &c.OrganizerWalletID, &c.Amount,
		&c.Percent, &c.Status, &c.CreatedAt, &c.UpdatedAt)
	if err != nil {
		return nil, err
	}
	return c, nil
}
