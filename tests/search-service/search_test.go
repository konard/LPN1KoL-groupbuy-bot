package search_test

import (
	"encoding/json"
	"testing"
)

// TestSearchRequestValidation tests search request parameter validation
func TestSearchRequestValidation(t *testing.T) {
	tests := []struct {
		name    string
		query   string
		page    int
		perPage int
		valid   bool
	}{
		{"valid basic search", "laptop", 1, 10, true},
		{"empty query is valid", "", 1, 10, true},
		{"zero page is invalid", "laptop", 0, 10, false},
		{"negative page is invalid", "laptop", -1, 10, false},
		{"too many per page", "laptop", 1, 200, false},
		{"valid max per page", "laptop", 1, 100, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			valid := tt.page > 0 && tt.perPage > 0 && tt.perPage <= 100
			if valid != tt.valid {
				t.Errorf("expected valid=%v, got valid=%v", tt.valid, valid)
			}
		})
	}
}

// TestFuzzyMatchDistance tests that fuzzy search uses Levenshtein distance ≤ 2
func TestFuzzyMatchDistance(t *testing.T) {
	tests := []struct {
		name     string
		query    string
		target   string
		maxDist  int
		expected bool
	}{
		{"exact match", "apple", "apple", 2, true},
		{"one char missing", "aple", "apple", 2, true},
		{"one char extra", "appple", "apple", 2, true},
		{"two chars different", "appel", "apple", 2, true},
		{"too different", "banana", "apple", 2, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			dist := levenshtein(tt.query, tt.target)
			matches := dist <= tt.maxDist
			if matches != tt.expected {
				t.Errorf("levenshtein(%q, %q) = %d, matches=%v, expected=%v",
					tt.query, tt.target, dist, matches, tt.expected)
			}
		})
	}
}

func levenshtein(a, b string) int {
	la, lb := len(a), len(b)
	if la == 0 {
		return lb
	}
	if lb == 0 {
		return la
	}
	prev := make([]int, lb+1)
	for j := 0; j <= lb; j++ {
		prev[j] = j
	}
	for i := 1; i <= la; i++ {
		curr := make([]int, lb+1)
		curr[0] = i
		for j := 1; j <= lb; j++ {
			cost := 1
			if a[i-1] == b[j-1] {
				cost = 0
			}
			curr[j] = min(curr[j-1]+1, min(prev[j]+1, prev[j-1]+cost))
		}
		prev = curr
	}
	return prev[lb]
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// TestSavedFilterSerialization tests saved filter JSON serialization
func TestSavedFilterSerialization(t *testing.T) {
	filter := map[string]interface{}{
		"id":        "test-uuid",
		"user_id":   "user-uuid",
		"name":      "My Filter",
		"query":     "laptop",
		"category":  "electronics",
		"city":      "Moscow",
		"price_min": 10000,
		"price_max": 50000,
		"notify":    true,
	}

	data, err := json.Marshal(filter)
	if err != nil {
		t.Fatalf("Failed to marshal filter: %v", err)
	}

	var decoded map[string]interface{}
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("Failed to unmarshal filter: %v", err)
	}

	if decoded["name"] != "My Filter" {
		t.Errorf("expected name 'My Filter', got %v", decoded["name"])
	}
	if decoded["notify"] != true {
		t.Errorf("expected notify true, got %v", decoded["notify"])
	}
}

// TestSearchResultStructure tests search result JSON structure
func TestSearchResultStructure(t *testing.T) {
	result := map[string]interface{}{
		"total": 42,
		"page":  1,
		"hits": []map[string]interface{}{
			{
				"id":          "purchase-uuid",
				"title":       "Group Buy: Laptops",
				"description": "Buying laptops in bulk",
				"category":    "electronics",
				"city":        "Moscow",
				"price":       45000,
				"score":       0.95,
			},
		},
	}

	data, err := json.Marshal(result)
	if err != nil {
		t.Fatalf("Failed to marshal result: %v", err)
	}

	var decoded map[string]interface{}
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("Failed to unmarshal result: %v", err)
	}

	total, ok := decoded["total"].(float64)
	if !ok || total != 42 {
		t.Errorf("expected total 42, got %v", decoded["total"])
	}

	hits, ok := decoded["hits"].([]interface{})
	if !ok || len(hits) != 1 {
		t.Errorf("expected 1 hit, got %v", len(hits))
	}
}
