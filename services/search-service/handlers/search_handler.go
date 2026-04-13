package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
	"github.com/olivere/elastic/v7"
	"github.com/redis/go-redis/v9"

	"search-service/models"
)

const (
	indexName         = "purchases"
	savedFiltersKey   = "search:filters:"
	searchHistoryKey  = "search:history:"
	searchHistoryTTL  = 7 * 24 * time.Hour
	defaultPage       = 1
	defaultPerPage    = 20
	maxPerPage        = 100
	fuzzyMaxEdits     = 2
)

type SearchHandler struct {
	es    *elastic.Client
	redis *redis.Client
}

func NewSearchHandler(es *elastic.Client, rdb *redis.Client) *SearchHandler {
	return &SearchHandler{es: es, redis: rdb}
}

// ─── Request / Response helpers ──────────────────────────────────────────────

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}

func decodeBody(r *http.Request, dst any) error {
	if err := json.NewDecoder(r.Body).Decode(dst); err != nil {
		return fmt.Errorf("invalid JSON: %w", err)
	}
	return nil
}

// ─── Health ──────────────────────────────────────────────────────────────────

func (h *SearchHandler) Health(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	esHealthy := true
	redisHealthy := true

	if h.es != nil {
		_, err := h.es.ClusterHealth().Do(ctx)
		if err != nil {
			esHealthy = false
		}
	} else {
		esHealthy = false
	}

	if err := h.redis.Ping(ctx).Err(); err != nil {
		redisHealthy = false
	}

	status := "ok"
	if !esHealthy || !redisHealthy {
		status = "degraded"
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"status":        status,
		"service":       "search-service",
		"elasticsearch": esHealthy,
		"redis":         redisHealthy,
	})
}

// ─── Search ──────────────────────────────────────────────────────────────────

func (h *SearchHandler) Search(w http.ResponseWriter, r *http.Request) {
	var req models.SearchRequest
	if err := decodeBody(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	if req.Page < 1 {
		req.Page = defaultPage
	}
	if req.PerPage < 1 {
		req.PerPage = defaultPerPage
	}
	if req.PerPage > maxPerPage {
		req.PerPage = maxPerPage
	}

	if h.es == nil {
		writeError(w, http.StatusServiceUnavailable, "search is temporarily unavailable — Elasticsearch not configured")
		return
	}

	query := h.buildSearchQuery(req)

	from := (req.Page - 1) * req.PerPage
	searchResult, err := h.es.Search().
		Index(indexName).
		Query(query).
		From(from).
		Size(req.PerPage).
		Highlight(elastic.NewHighlight().
			Field("title").
			Field("description").
			PreTags("<em>").
			PostTags("</em>")).
		Do(r.Context())
	if err != nil {
		log.Printf("Elasticsearch search error: %v", err)
		writeError(w, http.StatusInternalServerError, "search failed")
		return
	}

	results := make([]models.SearchResult, 0, len(searchResult.Hits.Hits))
	for _, hit := range searchResult.Hits.Hits {
		var sr models.SearchResult
		if err := json.Unmarshal(hit.Source, &sr); err != nil {
			log.Printf("Failed to unmarshal search hit: %v", err)
			continue
		}
		sr.ID = hit.Id
		if hit.Score != nil {
			sr.Score = *hit.Score
		}

		if hit.Highlight != nil {
			sr.Highlights = make(map[string]string)
			for field, fragments := range hit.Highlight {
				if len(fragments) > 0 {
					sr.Highlights[field] = fragments[0]
				}
			}
		}
		results = append(results, sr)
	}

	totalHits := searchResult.TotalHits()
	totalPages := int(math.Ceil(float64(totalHits) / float64(req.PerPage)))

	resp := models.SearchResponse{
		Results:    results,
		Total:      totalHits,
		Page:       req.Page,
		PerPage:    req.PerPage,
		TotalPages: totalPages,
	}

	// Record search history asynchronously
	userID := r.Header.Get("X-User-ID")
	if userID != "" && req.Query != "" {
		go h.recordSearchHistory(userID, req)
	}

	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": resp})
}

func (h *SearchHandler) buildSearchQuery(req models.SearchRequest) elastic.Query {
	must := make([]elastic.Query, 0)
	filter := make([]elastic.Query, 0)

	if req.Query != "" {
		must = append(must, elastic.NewMultiMatchQuery(req.Query, "title", "description", "organizer").
			Type("best_fields").
			Fuzziness("AUTO").
			MaxExpansions(50).
			PrefixLength(1))
	}

	if req.Category != "" {
		filter = append(filter, elastic.NewTermQuery("category.keyword", req.Category))
	}

	if req.City != "" {
		filter = append(filter, elastic.NewTermQuery("city.keyword", req.City))
	}

	if req.PriceMin > 0 || req.PriceMax > 0 {
		rangeQ := elastic.NewRangeQuery("price")
		if req.PriceMin > 0 {
			rangeQ.Gte(req.PriceMin)
		}
		if req.PriceMax > 0 {
			rangeQ.Lte(req.PriceMax)
		}
		filter = append(filter, rangeQ)
	}

	if len(must) == 0 && len(filter) == 0 {
		return elastic.NewMatchAllQuery()
	}

	boolQ := elastic.NewBoolQuery()
	if len(must) > 0 {
		boolQ.Must(must...)
	}
	if len(filter) > 0 {
		boolQ.Filter(filter...)
	}
	return boolQ
}

func (h *SearchHandler) recordSearchHistory(userID string, req models.SearchRequest) {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	entry := models.SearchHistoryEntry{
		Query:     req.Query,
		Category:  req.Category,
		City:      req.City,
		Timestamp: time.Now().UTC(),
	}

	data, err := json.Marshal(entry)
	if err != nil {
		log.Printf("Failed to marshal search history entry: %v", err)
		return
	}

	key := searchHistoryKey + userID
	pipe := h.redis.Pipeline()
	pipe.LPush(ctx, key, data)
	pipe.LTrim(ctx, key, 0, 99) // Keep last 100 entries
	pipe.Expire(ctx, key, searchHistoryTTL)
	if _, err := pipe.Exec(ctx); err != nil {
		log.Printf("Failed to record search history for user %s: %v", userID, err)
	}
}

// ─── Saved Filters ──────────────────────────────────────────────────────────

func (h *SearchHandler) GetSavedFilters(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "X-User-ID header required")
		return
	}

	key := savedFiltersKey + userID
	data, err := h.redis.HGetAll(r.Context(), key).Result()
	if err != nil {
		log.Printf("Failed to get saved filters for user %s: %v", userID, err)
		writeError(w, http.StatusInternalServerError, "failed to retrieve saved filters")
		return
	}

	filters := make([]models.SavedFilter, 0, len(data))
	for _, raw := range data {
		var f models.SavedFilter
		if err := json.Unmarshal([]byte(raw), &f); err != nil {
			log.Printf("Failed to unmarshal saved filter: %v", err)
			continue
		}
		filters = append(filters, f)
	}

	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": filters})
}

func (h *SearchHandler) CreateSavedFilter(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "X-User-ID header required")
		return
	}

	var f models.SavedFilter
	if err := decodeBody(r, &f); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	if f.Name == "" {
		writeError(w, http.StatusBadRequest, "name is required")
		return
	}

	f.ID = uuid.New().String()
	f.UserID = userID
	f.CreatedAt = time.Now().UTC()

	data, err := json.Marshal(f)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "failed to serialize filter")
		return
	}

	key := savedFiltersKey + userID
	if err := h.redis.HSet(r.Context(), key, f.ID, data).Err(); err != nil {
		log.Printf("Failed to save filter for user %s: %v", userID, err)
		writeError(w, http.StatusInternalServerError, "failed to save filter")
		return
	}

	writeJSON(w, http.StatusCreated, map[string]any{"success": true, "data": f})
}

func (h *SearchHandler) DeleteSavedFilter(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "X-User-ID header required")
		return
	}

	filterID := mux.Vars(r)["id"]
	if filterID == "" {
		writeError(w, http.StatusBadRequest, "filter id is required")
		return
	}

	key := savedFiltersKey + userID
	deleted, err := h.redis.HDel(r.Context(), key, filterID).Result()
	if err != nil {
		log.Printf("Failed to delete filter %s for user %s: %v", filterID, userID, err)
		writeError(w, http.StatusInternalServerError, "failed to delete filter")
		return
	}

	if deleted == 0 {
		writeError(w, http.StatusNotFound, "filter not found")
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{"success": true, "message": "filter deleted"})
}

// ─── Search History ──────────────────────────────────────────────────────────

func (h *SearchHandler) GetSearchHistory(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "X-User-ID header required")
		return
	}

	key := searchHistoryKey + userID
	entries, err := h.redis.LRange(r.Context(), key, 0, 49).Result()
	if err != nil {
		log.Printf("Failed to get search history for user %s: %v", userID, err)
		writeError(w, http.StatusInternalServerError, "failed to retrieve search history")
		return
	}

	history := make([]models.SearchHistoryEntry, 0, len(entries))
	for _, raw := range entries {
		var entry models.SearchHistoryEntry
		if err := json.Unmarshal([]byte(raw), &entry); err != nil {
			log.Printf("Failed to unmarshal search history entry: %v", err)
			continue
		}
		history = append(history, entry)
	}

	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": history})
}
