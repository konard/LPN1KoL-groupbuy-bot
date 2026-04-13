package models

import (
	"time"
)

type WalletStatus string

const (
	WalletStatusActive   WalletStatus = "active"
	WalletStatusFrozen   WalletStatus = "frozen"
	WalletStatusClosed   WalletStatus = "closed"
)

// Wallet represents a user's wallet with optimistic locking via version.
type Wallet struct {
	ID        string       `json:"id" db:"id"`
	UserID    string       `json:"user_id" db:"user_id"`
	Balance   int64        `json:"balance" db:"balance"`   // stored in minor units (kopecks)
	HeldAmount int64       `json:"held_amount" db:"held_amount"`
	Currency  string       `json:"currency" db:"currency"`
	Status    WalletStatus `json:"status" db:"status"`
	Version   int64        `json:"version" db:"version"` // optimistic lock
	CreatedAt time.Time    `json:"created_at" db:"created_at"`
	UpdatedAt time.Time    `json:"updated_at" db:"updated_at"`
}

// AvailableBalance returns balance minus held amount.
func (w *Wallet) AvailableBalance() int64 {
	return w.Balance - w.HeldAmount
}
