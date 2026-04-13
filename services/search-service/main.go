package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gorilla/mux"
	"github.com/olivere/elastic/v7"
	"github.com/redis/go-redis/v9"

	"search-service/handlers"
	"search-service/indexer"
)

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func initElasticsearch() (*elastic.Client, error) {
	url := getEnv("ELASTICSEARCH_URL", "")
	if url == "" {
		log.Printf("Warning: ELASTICSEARCH_URL not configured, search functionality will be degraded")
		return nil, nil
	}

	client, err := elastic.NewClient(
		elastic.SetURL(url),
		elastic.SetSniff(false),
		elastic.SetHealthcheck(true),
		elastic.SetHealthcheckInterval(30*time.Second),
		elastic.SetRetrier(elastic.NewBackoffRetrier(elastic.NewExponentialBackoff(100*time.Millisecond, 5*time.Second))),
	)
	if err != nil {
		return nil, err
	}

	return client, nil
}

func initRedis() *redis.Client {
	url := getEnv("REDIS_URL", "redis://localhost:6379")

	opts, err := redis.ParseURL(url)
	if err != nil {
		log.Fatalf("Invalid REDIS_URL: %v", err)
	}

	opts.PoolSize = 20
	opts.MinIdleConns = 5
	opts.ReadTimeout = 3 * time.Second
	opts.WriteTimeout = 3 * time.Second

	return redis.NewClient(opts)
}

func main() {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	esClient, err := initElasticsearch()
	if err != nil {
		log.Printf("Warning: Elasticsearch init failed: %v — search will be degraded", err)
	}

	rdb := initRedis()
	defer rdb.Close()

	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Printf("Warning: Redis ping failed: %v", err)
	}

	if esClient != nil {
		idx := indexer.NewIndexer(esClient)
		defer idx.Close()

		if err := idx.EnsureIndex(ctx); err != nil {
			log.Printf("Warning: failed to ensure Elasticsearch index: %v", err)
		}

		go idx.Start(ctx)
	} else {
		log.Printf("Elasticsearch disabled — indexer not started")
	}

	h := handlers.NewSearchHandler(esClient, rdb)

	r := mux.NewRouter()
	r.HandleFunc("/health", h.Health).Methods(http.MethodGet)
	r.HandleFunc("/search", h.Search).Methods(http.MethodPost)
	r.HandleFunc("/filters", h.GetSavedFilters).Methods(http.MethodGet)
	r.HandleFunc("/filters", h.CreateSavedFilter).Methods(http.MethodPost)
	r.HandleFunc("/filters/{id}", h.DeleteSavedFilter).Methods(http.MethodDelete)
	r.HandleFunc("/history", h.GetSearchHistory).Methods(http.MethodGet)

	port := getEnv("PORT", "4007")
	srv := &http.Server{
		Addr:         ":" + port,
		Handler:      r,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	go func() {
		sigCh := make(chan os.Signal, 1)
		signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
		<-sigCh
		log.Println("Shutting down gracefully...")
		cancel()

		shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer shutdownCancel()
		if err := srv.Shutdown(shutdownCtx); err != nil {
			log.Printf("HTTP server shutdown error: %v", err)
		}
	}()

	log.Printf("Search service starting on :%s", port)
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Server error: %v", err)
	}
	log.Println("Search service stopped")
}
