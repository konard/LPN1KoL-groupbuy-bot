// Gateway routing experiment: verifies that the StripPrefix behavior is correct
// Run: go run experiments/test_gateway_routing.go (from services/gateway directory)
package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"

	"github.com/gorilla/mux"
)

func recordPath(label string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintf(w, "[%s] path=%s", label, r.URL.Path)
	}
}

func buildRouter() *mux.Router {
	r := mux.NewRouter()

	// Public routes
	r.PathPrefix("/api/v1/auth/").Handler(
		http.StripPrefix("/api/v1/auth", recordPath("auth")),
	).Methods(http.MethodPost, http.MethodGet)

	// Protected subrouter
	protected := r.PathPrefix("/api/v1").Subrouter()

	// purchase-service: @Controller() (no prefix after fix)
	protected.PathPrefix("/purchases").Handler(
		http.StripPrefix("/api/v1/purchases", recordPath("purchase")),
	)
	// voting in purchase-service: @Controller() (no prefix after fix)
	protected.PathPrefix("/voting").Handler(
		http.StripPrefix("/api/v1/voting", recordPath("voting")),
	)
	// payment-service
	protected.PathPrefix("/payments").Handler(
		http.StripPrefix("/api/v1/payments", recordPath("payment")),
	)
	// escrow/commission in payment-service: strip only /api/v1
	protected.PathPrefix("/escrow").Handler(
		http.StripPrefix("/api/v1", recordPath("escrow")),
	)
	protected.PathPrefix("/commission").Handler(
		http.StripPrefix("/api/v1", recordPath("commission")),
	)
	// chat-service
	protected.PathPrefix("/chat").Handler(
		http.StripPrefix("/api/v1/chat", recordPath("chat")),
	)
	// reputation-service: strip only /api/v1 so service gets /reviews/... /reputation/... /complaints/...
	protected.PathPrefix("/reputation").Handler(
		http.StripPrefix("/api/v1", recordPath("reputation")),
	)
	protected.PathPrefix("/reviews").Handler(
		http.StripPrefix("/api/v1", recordPath("reviews")),
	)
	protected.PathPrefix("/complaints").Handler(
		http.StripPrefix("/api/v1", recordPath("complaints")),
	)

	return r
}

func test(r *mux.Router, method, path, expected string) {
	req := httptest.NewRequest(method, path, nil)
	rr := httptest.NewRecorder()
	r.ServeHTTP(rr, req)
	got := rr.Body.String()
	status := "PASS"
	if got != expected {
		status = "FAIL"
	}
	fmt.Printf("[%s] %s %s\n  expected: %q\n  got:      %q\n", status, method, path, expected, got)
}

func main() {
	r := buildRouter()

	fmt.Println("=== Auth routes ===")
	test(r, "POST", "/api/v1/auth/register", "[auth] path=/register")
	test(r, "POST", "/api/v1/auth/login", "[auth] path=/login")
	test(r, "POST", "/api/v1/auth/login/confirm", "[auth] path=/login/confirm")

	fmt.Println("\n=== Purchase routes (@Controller() - no prefix) ===")
	test(r, "GET", "/api/v1/purchases", "[purchase] path=")
	test(r, "GET", "/api/v1/purchases/", "[purchase] path=/")
	test(r, "GET", "/api/v1/purchases/abc-123", "[purchase] path=/abc-123")
	test(r, "GET", "/api/v1/purchases/abc-123/editors", "[purchase] path=/abc-123/editors")

	fmt.Println("\n=== Voting routes (@Controller() - no prefix) ===")
	test(r, "POST", "/api/v1/voting/sessions", "[voting] path=/sessions")
	test(r, "GET", "/api/v1/voting/sessions/sess-1/results", "[voting] path=/sessions/sess-1/results")

	fmt.Println("\n=== Payment routes ===")
	test(r, "GET", "/api/v1/payments/wallet", "[payment] path=/wallet")
	test(r, "POST", "/api/v1/payments/wallet/topup", "[payment] path=/wallet/topup")

	fmt.Println("\n=== Escrow routes (StripPrefix /api/v1) ===")
	test(r, "GET", "/api/v1/escrow/purchase-1", "[escrow] path=/escrow/purchase-1")
	test(r, "POST", "/api/v1/escrow/purchase-1/deposit", "[escrow] path=/escrow/purchase-1/deposit")

	fmt.Println("\n=== Commission routes (StripPrefix /api/v1) ===")
	test(r, "POST", "/api/v1/commission/hold", "[commission] path=/commission/hold")

	fmt.Println("\n=== Chat routes ===")
	test(r, "POST", "/api/v1/chat/rooms", "[chat] path=/rooms")
	test(r, "GET", "/api/v1/chat/media/upload", "[chat] path=/media/upload")

	fmt.Println("\n=== Reputation routes (StripPrefix /api/v1) ===")
	test(r, "GET", "/api/v1/reputation/user-1", "[reputation] path=/reputation/user-1")
	test(r, "GET", "/api/v1/reputation/user-1/ratings-by-role", "[reputation] path=/reputation/user-1/ratings-by-role")

	fmt.Println("\n=== Reviews routes (StripPrefix /api/v1) ===")
	test(r, "POST", "/api/v1/reviews", "[reviews] path=/reviews")
	test(r, "GET", "/api/v1/reviews/user/user-1", "[reviews] path=/reviews/user/user-1")

	fmt.Println("\n=== Complaints routes (StripPrefix /api/v1) ===")
	test(r, "POST", "/api/v1/complaints", "[complaints] path=/complaints")
	test(r, "GET", "/api/v1/complaints/user/user-1", "[complaints] path=/complaints/user/user-1")
}
