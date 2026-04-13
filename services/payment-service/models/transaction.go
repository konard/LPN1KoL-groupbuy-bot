package models

import "time"

type TransactionType string
type TransactionStatus string

const (
	TxTypeTopUp    TransactionType = "top_up"
	TxTypeHold     TransactionType = "hold"
	TxTypeCommit   TransactionType = "commit"
	TxTypeRelease  TransactionType = "release"
	TxTypeWithdraw  TransactionType = "withdraw"
	TxTypeRefund    TransactionType = "refund"
	TxTypeEscrowIn  TransactionType = "escrow_in"
	TxTypeEscrowOut TransactionType = "escrow_out"
	TxTypeCommission TransactionType = "commission"

	TxStatusPending   TransactionStatus = "pending"
	TxStatusCompleted TransactionStatus = "completed"
	TxStatusFailed    TransactionStatus = "failed"
	TxStatusRolledBack TransactionStatus = "rolled_back"
)

// Transaction records a financial operation.
type Transaction struct {
	ID              string            `json:"id" db:"id"`
	IdempotencyKey  string            `json:"idempotency_key" db:"idempotency_key"`
	WalletID        string            `json:"wallet_id" db:"wallet_id"`
	Type            TransactionType   `json:"type" db:"type"`
	Amount          int64             `json:"amount" db:"amount"`   // minor units
	Currency        string            `json:"currency" db:"currency"`
	Status          TransactionStatus `json:"status" db:"status"`
	RelatedTxID     *string           `json:"related_tx_id,omitempty" db:"related_tx_id"`
	PurchaseID      *string           `json:"purchase_id,omitempty" db:"purchase_id"`
	Description     string            `json:"description" db:"description"`
	ExternalRef     *string           `json:"external_ref,omitempty" db:"external_ref"`
	Metadata        map[string]any    `json:"metadata,omitempty"`
	CreatedAt       time.Time         `json:"created_at" db:"created_at"`
	UpdatedAt       time.Time         `json:"updated_at" db:"updated_at"`
}
