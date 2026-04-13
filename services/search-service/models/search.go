package models

import "time"

type SearchRequest struct {
	Query    string  `json:"query"`
	Category string  `json:"category,omitempty"`
	City     string  `json:"city,omitempty"`
	PriceMin float64 `json:"price_min,omitempty"`
	PriceMax float64 `json:"price_max,omitempty"`
	Page     int     `json:"page,omitempty"`
	PerPage  int     `json:"per_page,omitempty"`
}

type SearchResult struct {
	ID          string            `json:"id"`
	Title       string            `json:"title"`
	Description string            `json:"description"`
	Category    string            `json:"category"`
	City        string            `json:"city"`
	Price       float64           `json:"price"`
	Organizer   string            `json:"organizer"`
	Score       float64           `json:"score"`
	Highlights  map[string]string `json:"highlights,omitempty"`
}

type SearchResponse struct {
	Results    []SearchResult `json:"results"`
	Total      int64          `json:"total"`
	Page       int            `json:"page"`
	PerPage    int            `json:"per_page"`
	TotalPages int            `json:"total_pages"`
}

type SavedFilter struct {
	ID        string    `json:"id"`
	UserID    string    `json:"user_id"`
	Name      string    `json:"name"`
	Query     string    `json:"query,omitempty"`
	Category  string    `json:"category,omitempty"`
	City      string    `json:"city,omitempty"`
	PriceMin  float64   `json:"price_min,omitempty"`
	PriceMax  float64   `json:"price_max,omitempty"`
	Notify    bool      `json:"notify"`
	CreatedAt time.Time `json:"created_at"`
}

type SearchHistoryEntry struct {
	Query     string    `json:"query"`
	Category  string    `json:"category,omitempty"`
	City      string    `json:"city,omitempty"`
	Timestamp time.Time `json:"timestamp"`
}

type PurchaseEvent struct {
	ID          string  `json:"id"`
	Title       string  `json:"title"`
	Description string  `json:"description"`
	Category    string  `json:"category"`
	City        string  `json:"city"`
	Price       float64 `json:"price"`
	Organizer   string  `json:"organizer"`
	Status      string  `json:"status"`
}
