package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"github.com/gorilla/mux"
)

func main() {
	r := mux.NewRouter()
	protected := r.PathPrefix("/api/v1").Subrouter()
	
	protected.PathPrefix("/purchases").HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		fmt.Fprintf(w, "purchases handler, path: %s", req.URL.Path)
	})
	
	// Test 1: Request to /api/v1/purchases/123
	req := httptest.NewRequest("GET", "/api/v1/purchases/123", nil)
	rr := httptest.NewRecorder()
	r.ServeHTTP(rr, req)
	fmt.Printf("Test 1 - /api/v1/purchases/123 -> path seen by handler: %s\n", rr.Body.String())
	
	// Now test with StripPrefix
	r2 := mux.NewRouter()
	protected2 := r2.PathPrefix("/api/v1").Subrouter()
	
	protected2.PathPrefix("/purchases").Handler(
		http.StripPrefix("/api/v1/purchases", http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
			fmt.Fprintf(w, "path seen after StripPrefix: %s", req.URL.Path)
		})),
	)
	
	req2 := httptest.NewRequest("GET", "/api/v1/purchases/123", nil)
	rr2 := httptest.NewRecorder()
	r2.ServeHTTP(rr2, req2)
	fmt.Printf("Test 2 - /api/v1/purchases/123 with StripPrefix('/api/v1/purchases') -> %s\n", rr2.Body.String())
}
