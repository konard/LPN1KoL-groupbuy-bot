package models

import "time"

type EscrowStatus string

const (
	EscrowStatusActive   EscrowStatus = "active"
	EscrowStatusReleased EscrowStatus = "released"
	EscrowStatusDisputed EscrowStatus = "disputed"
	EscrowStatusRefunded EscrowStatus = "refunded"
)

// EscrowAccount holds funds in escrow for a purchase until delivery is confirmed.
type EscrowAccount struct {
	ID                    string       `json:"id" db:"id"`
	PurchaseID            string       `json:"purchase_id" db:"purchase_id"`
	TotalAmount           int64        `json:"total_amount" db:"total_amount"`
	ReleasedAmount        int64        `json:"released_amount" db:"released_amount"`
	Status                EscrowStatus `json:"status" db:"status"`
	Threshold             int64        `json:"threshold" db:"threshold"`
	ConfirmationsRequired int          `json:"confirmations_required" db:"confirmations_required"`
	ConfirmationsReceived int          `json:"confirmations_received" db:"confirmations_received"`
	CreatedAt             time.Time    `json:"created_at" db:"created_at"`
	UpdatedAt             time.Time    `json:"updated_at" db:"updated_at"`
}

// ConfirmationPercent returns the percentage of confirmations received.
func (e *EscrowAccount) ConfirmationPercent() float64 {
	if e.ConfirmationsRequired == 0 {
		return 0
	}
	return float64(e.ConfirmationsReceived) / float64(e.ConfirmationsRequired) * 100
}

// CanRelease returns true if confirmations have reached the 80% threshold.
func (e *EscrowAccount) CanRelease() bool {
	if e.ConfirmationsRequired == 0 {
		return false
	}
	return float64(e.ConfirmationsReceived) >= float64(e.ConfirmationsRequired)*0.8
}
