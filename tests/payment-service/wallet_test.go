package payment_test

import (
	"context"
	"testing"
	"time"

	"github.com/google/uuid"
	"payment-service/handlers"
	"payment-service/models"
)

// ─── In-Memory Store for Testing ──────────────────────────────────────────────
// We test the business logic directly without a real DB by using a mock.

type MockDB struct {
	wallets      map[string]*models.Wallet      // walletId -> wallet
	userWallets  map[string]string              // userId -> walletId
	transactions map[string]*models.Transaction // txId -> tx
	idempotency  map[string]*models.Transaction // key -> tx
}

func newMockDB() *MockDB {
	return &MockDB{
		wallets:      make(map[string]*models.Wallet),
		userWallets:  make(map[string]string),
		transactions: make(map[string]*models.Transaction),
		idempotency:  make(map[string]*models.Transaction),
	}
}

func (m *MockDB) createWallet(userID string) *models.Wallet {
	id := uuid.New().String()
	w := &models.Wallet{
		ID:         id,
		UserID:     userID,
		Balance:    0,
		HeldAmount: 0,
		Currency:   "RUB",
		Status:     models.WalletStatusActive,
		Version:    0,
		CreatedAt:  time.Now(),
		UpdatedAt:  time.Now(),
	}
	m.wallets[id] = w
	m.userWallets[userID] = id
	return w
}

func (m *MockDB) getWalletByUser(userID string) *models.Wallet {
	wid, ok := m.userWallets[userID]
	if !ok {
		return nil
	}
	w := m.wallets[wid]
	if w == nil {
		return nil
	}
	// Return copy
	copy := *w
	return &copy
}

func (m *MockDB) getWallet(id string) *models.Wallet {
	w := m.wallets[id]
	if w == nil {
		return nil
	}
	copy := *w
	return &copy
}

func (m *MockDB) getTransaction(id string) *models.Transaction {
	return m.transactions[id]
}

// ─── Business Logic Under Test ────────────────────────────────────────────────
// We extract pure business logic from the handler to test without HTTP layer.

type WalletService struct {
	db *MockDB
}

func (s *WalletService) topUp(ctx context.Context, userID string, amount int64, idempotencyKey string) (*models.Transaction, error) {
	// Idempotency check
	if existing, ok := s.db.idempotency[idempotencyKey]; ok {
		return existing, nil
	}

	w := s.db.getWalletByUser(userID)
	if w == nil {
		w = s.db.createWallet(userID)
	}

	// Optimistic lock simulation (in real code uses DB version)
	w.Balance += amount
	w.Version++
	w.UpdatedAt = time.Now()
	s.db.wallets[w.ID] = w

	tx := &models.Transaction{
		ID:             uuid.New().String(),
		IdempotencyKey: idempotencyKey,
		WalletID:       w.ID,
		Type:           models.TxTypeTopUp,
		Amount:         amount,
		Currency:       "RUB",
		Status:         models.TxStatusCompleted,
		Description:    "Top up",
		CreatedAt:      time.Now(),
		UpdatedAt:      time.Now(),
	}
	s.db.transactions[tx.ID] = tx
	s.db.idempotency[idempotencyKey] = tx
	return tx, nil
}

func (s *WalletService) hold(ctx context.Context, userID string, amount int64, idempotencyKey string, purchaseID string) (*models.Transaction, error) {
	if existing, ok := s.db.idempotency[idempotencyKey]; ok {
		return existing, nil
	}

	w := s.db.getWalletByUser(userID)
	if w == nil {
		return nil, handlers.ErrInsufficientFunds
	}
	if w.AvailableBalance() < amount {
		return nil, handlers.ErrInsufficientFunds
	}

	w.HeldAmount += amount
	w.Version++
	w.UpdatedAt = time.Now()
	s.db.wallets[w.ID] = w

	tx := &models.Transaction{
		ID:             uuid.New().String(),
		IdempotencyKey: idempotencyKey,
		WalletID:       w.ID,
		Type:           models.TxTypeHold,
		Amount:         amount,
		Currency:       "RUB",
		Status:         models.TxStatusCompleted,
		PurchaseID:     &purchaseID,
		Description:    "Hold for purchase",
		CreatedAt:      time.Now(),
		UpdatedAt:      time.Now(),
	}
	s.db.transactions[tx.ID] = tx
	s.db.idempotency[idempotencyKey] = tx
	return tx, nil
}

func (s *WalletService) commit(ctx context.Context, holdTxID string, idempotencyKey string) (*models.Transaction, error) {
	if existing, ok := s.db.idempotency[idempotencyKey]; ok {
		return existing, nil
	}

	holdTx := s.db.getTransaction(holdTxID)
	if holdTx == nil || holdTx.Type != models.TxTypeHold || holdTx.Status != models.TxStatusCompleted {
		return nil, handlers.ErrOptimisticLock
	}

	w := s.db.getWallet(holdTx.WalletID)
	if w == nil || w.HeldAmount < holdTx.Amount {
		return nil, handlers.ErrInsufficientFunds
	}

	w.Balance -= holdTx.Amount
	w.HeldAmount -= holdTx.Amount
	w.Version++
	w.UpdatedAt = time.Now()
	s.db.wallets[w.ID] = w

	// Mark hold as consumed
	holdTx.Status = models.TxStatusRolledBack
	s.db.transactions[holdTxID] = holdTx

	tx := &models.Transaction{
		ID:             uuid.New().String(),
		IdempotencyKey: idempotencyKey,
		WalletID:       w.ID,
		Type:           models.TxTypeCommit,
		Amount:         holdTx.Amount,
		Currency:       holdTx.Currency,
		Status:         models.TxStatusCompleted,
		RelatedTxID:    &holdTxID,
		PurchaseID:     holdTx.PurchaseID,
		Description:    "Commit",
		CreatedAt:      time.Now(),
		UpdatedAt:      time.Now(),
	}
	s.db.transactions[tx.ID] = tx
	s.db.idempotency[idempotencyKey] = tx
	return tx, nil
}

func (s *WalletService) release(ctx context.Context, holdTxID string, idempotencyKey string) (*models.Transaction, error) {
	if existing, ok := s.db.idempotency[idempotencyKey]; ok {
		return existing, nil
	}

	holdTx := s.db.getTransaction(holdTxID)
	if holdTx == nil || holdTx.Type != models.TxTypeHold || holdTx.Status != models.TxStatusCompleted {
		return nil, handlers.ErrOptimisticLock
	}

	w := s.db.getWallet(holdTx.WalletID)
	if w == nil || w.HeldAmount < holdTx.Amount {
		return nil, handlers.ErrInsufficientFunds
	}

	w.HeldAmount -= holdTx.Amount
	w.Version++
	w.UpdatedAt = time.Now()
	s.db.wallets[w.ID] = w

	holdTx.Status = models.TxStatusRolledBack
	s.db.transactions[holdTxID] = holdTx

	tx := &models.Transaction{
		ID:             uuid.New().String(),
		IdempotencyKey: idempotencyKey,
		WalletID:       w.ID,
		Type:           models.TxTypeRelease,
		Amount:         holdTx.Amount,
		Currency:       holdTx.Currency,
		Status:         models.TxStatusCompleted,
		RelatedTxID:    &holdTxID,
		PurchaseID:     holdTx.PurchaseID,
		Description:    "Release hold",
		CreatedAt:      time.Now(),
		UpdatedAt:      time.Now(),
	}
	s.db.transactions[tx.ID] = tx
	s.db.idempotency[idempotencyKey] = tx
	return tx, nil
}

// ─── Tests ────────────────────────────────────────────────────────────────────

func newService() (*WalletService, *MockDB) {
	db := newMockDB()
	return &WalletService{db: db}, db
}

func TestTopUp_Basic(t *testing.T) {
	svc, db := newService()
	ctx := context.Background()

	tx, err := svc.topUp(ctx, "user-1", 10000, "idem-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if tx.Type != models.TxTypeTopUp {
		t.Errorf("expected tx type top_up, got %s", tx.Type)
	}
	if tx.Amount != 10000 {
		t.Errorf("expected amount 10000, got %d", tx.Amount)
	}

	w := db.getWalletByUser("user-1")
	if w == nil {
		t.Fatal("wallet not found after topup")
	}
	if w.Balance != 10000 {
		t.Errorf("expected balance 10000, got %d", w.Balance)
	}
	if w.AvailableBalance() != 10000 {
		t.Errorf("expected available 10000, got %d", w.AvailableBalance())
	}
}

func TestTopUp_Idempotency(t *testing.T) {
	svc, db := newService()
	ctx := context.Background()
	key := "idem-topup-1"

	tx1, err := svc.topUp(ctx, "user-1", 5000, key)
	if err != nil {
		t.Fatalf("first topup failed: %v", err)
	}

	// Same idempotency key — should return same tx without applying again
	tx2, err := svc.topUp(ctx, "user-1", 5000, key)
	if err != nil {
		t.Fatalf("second topup failed: %v", err)
	}

	if tx1.ID != tx2.ID {
		t.Errorf("idempotency violated: got different tx IDs: %s vs %s", tx1.ID, tx2.ID)
	}

	w := db.getWalletByUser("user-1")
	if w.Balance != 5000 {
		t.Errorf("balance should be 5000 (not doubled), got %d", w.Balance)
	}
}

func TestHold_Success(t *testing.T) {
	svc, db := newService()
	ctx := context.Background()

	_, _ = svc.topUp(ctx, "user-1", 10000, "idem-topup")

	holdTx, err := svc.hold(ctx, "user-1", 3000, "idem-hold-1", "purchase-1")
	if err != nil {
		t.Fatalf("hold failed: %v", err)
	}
	if holdTx.Type != models.TxTypeHold {
		t.Errorf("expected hold tx, got %s", holdTx.Type)
	}

	w := db.getWalletByUser("user-1")
	if w.Balance != 10000 {
		t.Errorf("balance should still be 10000, got %d", w.Balance)
	}
	if w.HeldAmount != 3000 {
		t.Errorf("held should be 3000, got %d", w.HeldAmount)
	}
	if w.AvailableBalance() != 7000 {
		t.Errorf("available should be 7000, got %d", w.AvailableBalance())
	}
}

func TestHold_InsufficientFunds(t *testing.T) {
	svc, _ := newService()
	ctx := context.Background()

	_, _ = svc.topUp(ctx, "user-1", 1000, "idem-topup")

	_, err := svc.hold(ctx, "user-1", 5000, "idem-hold", "purchase-1")
	if err == nil {
		t.Fatal("expected ErrInsufficientFunds, got nil")
	}
	if err != handlers.ErrInsufficientFunds {
		t.Errorf("expected ErrInsufficientFunds, got %v", err)
	}
}

func TestHold_Idempotency(t *testing.T) {
	svc, db := newService()
	ctx := context.Background()

	_, _ = svc.topUp(ctx, "user-1", 10000, "idem-topup")

	key := "idem-hold-1"
	hold1, _ := svc.hold(ctx, "user-1", 3000, key, "purchase-1")
	hold2, _ := svc.hold(ctx, "user-1", 3000, key, "purchase-1")

	if hold1.ID != hold2.ID {
		t.Errorf("idempotency violated for hold: %s vs %s", hold1.ID, hold2.ID)
	}

	// HeldAmount should only be 3000, not 6000
	w := db.getWalletByUser("user-1")
	if w.HeldAmount != 3000 {
		t.Errorf("held should be 3000 (not doubled), got %d", w.HeldAmount)
	}
}

func TestCommit_Success(t *testing.T) {
	svc, db := newService()
	ctx := context.Background()

	_, _ = svc.topUp(ctx, "user-1", 10000, "idem-topup")
	holdTx, _ := svc.hold(ctx, "user-1", 4000, "idem-hold", "purchase-1")

	commitTx, err := svc.commit(ctx, holdTx.ID, "idem-commit-1")
	if err != nil {
		t.Fatalf("commit failed: %v", err)
	}
	if commitTx.Type != models.TxTypeCommit {
		t.Errorf("expected commit tx, got %s", commitTx.Type)
	}
	if *commitTx.RelatedTxID != holdTx.ID {
		t.Errorf("related_tx_id mismatch")
	}

	w := db.getWalletByUser("user-1")
	if w.Balance != 6000 {
		t.Errorf("balance should be 6000 after commit, got %d", w.Balance)
	}
	if w.HeldAmount != 0 {
		t.Errorf("held should be 0 after commit, got %d", w.HeldAmount)
	}
}

func TestCommit_Idempotency(t *testing.T) {
	svc, db := newService()
	ctx := context.Background()

	_, _ = svc.topUp(ctx, "user-1", 10000, "idem-topup")
	holdTx, _ := svc.hold(ctx, "user-1", 4000, "idem-hold", "purchase-1")

	key := "idem-commit"
	c1, _ := svc.commit(ctx, holdTx.ID, key)
	c2, _ := svc.commit(ctx, holdTx.ID, key)

	if c1.ID != c2.ID {
		t.Errorf("idempotency violated for commit: %s vs %s", c1.ID, c2.ID)
	}

	// Balance should only be deducted once
	w := db.getWalletByUser("user-1")
	if w.Balance != 6000 {
		t.Errorf("balance should be 6000, got %d", w.Balance)
	}
}

func TestCommit_CannotCommitTwice(t *testing.T) {
	svc, _ := newService()
	ctx := context.Background()

	_, _ = svc.topUp(ctx, "user-1", 10000, "idem-topup")
	holdTx, _ := svc.hold(ctx, "user-1", 4000, "idem-hold", "purchase-1")

	_, _ = svc.commit(ctx, holdTx.ID, "idem-commit-1")

	// Trying to commit with a DIFFERENT idempotency key should fail
	// because the hold is now in rolled_back state
	_, err := svc.commit(ctx, holdTx.ID, "idem-commit-2")
	if err == nil {
		t.Error("expected error when committing already-committed hold, got nil")
	}
}

func TestRelease_Success(t *testing.T) {
	svc, db := newService()
	ctx := context.Background()

	_, _ = svc.topUp(ctx, "user-1", 10000, "idem-topup")
	holdTx, _ := svc.hold(ctx, "user-1", 5000, "idem-hold", "purchase-1")

	releaseTx, err := svc.release(ctx, holdTx.ID, "idem-release-1")
	if err != nil {
		t.Fatalf("release failed: %v", err)
	}
	if releaseTx.Type != models.TxTypeRelease {
		t.Errorf("expected release tx, got %s", releaseTx.Type)
	}

	w := db.getWalletByUser("user-1")
	if w.Balance != 10000 {
		t.Errorf("balance should be unchanged 10000, got %d", w.Balance)
	}
	if w.HeldAmount != 0 {
		t.Errorf("held should be 0 after release, got %d", w.HeldAmount)
	}
	if w.AvailableBalance() != 10000 {
		t.Errorf("available should be back to 10000, got %d", w.AvailableBalance())
	}
}

func TestRelease_Idempotency(t *testing.T) {
	svc, db := newService()
	ctx := context.Background()

	_, _ = svc.topUp(ctx, "user-1", 10000, "idem-topup")
	holdTx, _ := svc.hold(ctx, "user-1", 5000, "idem-hold", "purchase-1")

	key := "idem-release"
	r1, _ := svc.release(ctx, holdTx.ID, key)
	r2, _ := svc.release(ctx, holdTx.ID, key)

	if r1.ID != r2.ID {
		t.Errorf("idempotency violated for release: %s vs %s", r1.ID, r2.ID)
	}

	// HeldAmount should be 0, not negative
	w := db.getWalletByUser("user-1")
	if w.HeldAmount != 0 {
		t.Errorf("held should be 0, got %d", w.HeldAmount)
	}
}

func TestRelease_CannotReleaseAfterCommit(t *testing.T) {
	svc, _ := newService()
	ctx := context.Background()

	_, _ = svc.topUp(ctx, "user-1", 10000, "idem-topup")
	holdTx, _ := svc.hold(ctx, "user-1", 5000, "idem-hold", "purchase-1")

	_, _ = svc.commit(ctx, holdTx.ID, "idem-commit")

	_, err := svc.release(ctx, holdTx.ID, "idem-release-after-commit")
	if err == nil {
		t.Error("expected error releasing committed hold, got nil")
	}
}

func TestWallet_MultipleHolds(t *testing.T) {
	svc, db := newService()
	ctx := context.Background()

	_, _ = svc.topUp(ctx, "user-1", 10000, "idem-topup")

	_, _ = svc.hold(ctx, "user-1", 3000, "idem-hold-1", "purchase-1")
	_, _ = svc.hold(ctx, "user-1", 3000, "idem-hold-2", "purchase-2")

	w := db.getWalletByUser("user-1")
	if w.HeldAmount != 6000 {
		t.Errorf("total held should be 6000, got %d", w.HeldAmount)
	}
	if w.AvailableBalance() != 4000 {
		t.Errorf("available should be 4000, got %d", w.AvailableBalance())
	}

	// Third hold should fail (only 4000 available, requesting 5000)
	_, err := svc.hold(ctx, "user-1", 5000, "idem-hold-3", "purchase-3")
	if err != handlers.ErrInsufficientFunds {
		t.Errorf("expected ErrInsufficientFunds, got %v", err)
	}
}

func TestWallet_BalanceNeverNegative(t *testing.T) {
	svc, db := newService()
	ctx := context.Background()

	_, _ = svc.topUp(ctx, "user-1", 1000, "idem-topup")
	holdTx, _ := svc.hold(ctx, "user-1", 1000, "idem-hold", "purchase-1")
	_, _ = svc.commit(ctx, holdTx.ID, "idem-commit")

	w := db.getWalletByUser("user-1")
	if w.Balance < 0 {
		t.Errorf("balance went negative: %d", w.Balance)
	}
	if w.HeldAmount < 0 {
		t.Errorf("held amount went negative: %d", w.HeldAmount)
	}
}

func TestTopUp_CreatesWalletIfMissing(t *testing.T) {
	svc, db := newService()
	ctx := context.Background()

	// No prior wallet for user-2
	_, err := svc.topUp(ctx, "user-2", 500, "idem-1")
	if err != nil {
		t.Fatalf("topup failed: %v", err)
	}

	w := db.getWalletByUser("user-2")
	if w == nil {
		t.Fatal("wallet was not created")
	}
	if w.Balance != 500 {
		t.Errorf("expected 500, got %d", w.Balance)
	}
}
