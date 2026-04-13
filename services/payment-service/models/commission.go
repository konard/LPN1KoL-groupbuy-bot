package models

import "time"

type CommissionStatus string

const (
	CommissionStatusHeld      CommissionStatus = "held"
	CommissionStatusCommitted CommissionStatus = "committed"
	CommissionStatusReleased  CommissionStatus = "released"
)

// CommissionHold represents a commission held from an organizer's wallet for a purchase.
type CommissionHold struct {
	ID                string           `json:"id" db:"id"`
	PurchaseID        string           `json:"purchase_id" db:"purchase_id"`
	OrganizerWalletID string           `json:"organizer_wallet_id" db:"organizer_wallet_id"`
	Amount            int64            `json:"amount" db:"amount"`
	Percent           float64          `json:"percent" db:"percent"`
	Status            CommissionStatus `json:"status" db:"status"`
	CreatedAt         time.Time        `json:"created_at" db:"created_at"`
	UpdatedAt         time.Time        `json:"updated_at" db:"updated_at"`
}
