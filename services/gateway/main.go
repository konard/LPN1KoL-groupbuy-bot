package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/gorilla/mux"
	"github.com/redis/go-redis/v9"
	"github.com/rs/cors"
	"golang.org/x/time/rate"
)

// ─── Configuration ────────────────────────────────────────────────────────────

type Config struct {
	Port                string
	JWTSecret           string
	AuthServiceURL      string
	PurchaseServiceURL  string
	PaymentServiceURL   string
	ChatServiceURL      string
	SearchServiceURL    string
	ReputationServiceURL string
	AnalyticsServiceURL string
	NotificationServiceURL string
	RedisAddr           string
	RedisPassword       string
	RateLimitRPM        int
	VotingRateLimitRPM  int // Higher limit for voting during hot hour
	CORSOrigins         []string
}

func loadConfig() *Config {
	rpm := 60
	if v := os.Getenv("RATE_LIMIT_RPM"); v != "" {
		fmt.Sscanf(v, "%d", &rpm)
	}
	votingRPM := 120
	if v := os.Getenv("VOTING_RATE_LIMIT_RPM"); v != "" {
		fmt.Sscanf(v, "%d", &votingRPM)
	}
	origins := strings.Split(getEnv("CORS_ORIGINS", "http://localhost:3001"), ",")
	return &Config{
		Port:                   getEnv("PORT", "3000"),
		JWTSecret:              getEnv("JWT_SECRET", "change_me"),
		AuthServiceURL:         getEnv("AUTH_SERVICE_URL", "http://localhost:4001"),
		PurchaseServiceURL:     getEnv("PURCHASE_SERVICE_URL", "http://localhost:4002"),
		PaymentServiceURL:      getEnv("PAYMENT_SERVICE_URL", "http://localhost:4003"),
		ChatServiceURL:         getEnv("CHAT_SERVICE_URL", "http://localhost:4004"),
		SearchServiceURL:       getEnv("SEARCH_SERVICE_URL", "http://localhost:4007"),
		ReputationServiceURL:   getEnv("REPUTATION_SERVICE_URL", "http://localhost:4008"),
		AnalyticsServiceURL:    getEnv("ANALYTICS_SERVICE_URL", "http://localhost:4006"),
		NotificationServiceURL: getEnv("NOTIFICATION_SERVICE_URL", "http://localhost:4005"),
		RedisAddr:              getEnv("REDIS_ADDR", "localhost:6379"),
		RedisPassword:          getEnv("REDIS_PASSWORD", ""),
		RateLimitRPM:           rpm,
		VotingRateLimitRPM:     votingRPM,
		CORSOrigins:            origins,
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// ─── JWT Claims ───────────────────────────────────────────────────────────────

type Claims struct {
	UserID string `json:"sub"`
	Email  string `json:"email"`
	Role   string `json:"role"`
	jwt.RegisteredClaims
}

// ─── Rate Limiter ─────────────────────────────────────────────────────────────

type IPRateLimiter struct {
	mu       sync.Mutex
	limiters map[string]*rate.Limiter
	rpm      int
}

func newIPRateLimiter(rpm int) *IPRateLimiter {
	return &IPRateLimiter{
		limiters: make(map[string]*rate.Limiter),
		rpm:      rpm,
	}
}

func (l *IPRateLimiter) getLimiter(ip string) *rate.Limiter {
	l.mu.Lock()
	defer l.mu.Unlock()
	if lim, ok := l.limiters[ip]; ok {
		return lim
	}
	lim := rate.NewLimiter(rate.Every(time.Minute/time.Duration(l.rpm)), l.rpm)
	l.limiters[ip] = lim
	return lim
}

// ─── Gateway Server ───────────────────────────────────────────────────────────

type Gateway struct {
	cfg        *Config
	rdb        *redis.Client
	rateLimiter *IPRateLimiter
	proxies    map[string]*httputil.ReverseProxy
}

func newGateway(cfg *Config) *Gateway {
	rdb := redis.NewClient(&redis.Options{
		Addr:     cfg.RedisAddr,
		Password: cfg.RedisPassword,
		DB:       0,
	})

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Printf("Warning: Redis connection failed: %v", err)
	}

	proxies := map[string]*httputil.ReverseProxy{}
	for name, rawURL := range map[string]string{
		"auth":         cfg.AuthServiceURL,
		"purchase":     cfg.PurchaseServiceURL,
		"payment":      cfg.PaymentServiceURL,
		"chat":         cfg.ChatServiceURL,
		"search":       cfg.SearchServiceURL,
		"reputation":   cfg.ReputationServiceURL,
		"analytics":    cfg.AnalyticsServiceURL,
		"notification": cfg.NotificationServiceURL,
	} {
		u, err := url.Parse(rawURL)
		if err != nil {
			log.Fatalf("Invalid URL for %s: %v", name, err)
		}
		proxy := httputil.NewSingleHostReverseProxy(u)
		proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
			log.Printf("Proxy error for %s: %v", name, err)
			http.Error(w, "Service temporarily unavailable", http.StatusBadGateway)
		}
		proxies[name] = proxy
	}

	return &Gateway{
		cfg:         cfg,
		rdb:         rdb,
		rateLimiter: newIPRateLimiter(cfg.RateLimitRPM),
		proxies:     proxies,
	}
}

// ─── Middleware ────────────────────────────────────────────────────────────────

func (g *Gateway) rateLimitMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ip := realIP(r)
		if !g.rateLimiter.getLimiter(ip).Allow() {
			http.Error(w, `{"error":"rate limit exceeded"}`, http.StatusTooManyRequests)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func (g *Gateway) jwtMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		authHeader := r.Header.Get("Authorization")
		if authHeader == "" {
			http.Error(w, `{"error":"authorization header required"}`, http.StatusUnauthorized)
			return
		}
		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) != 2 || strings.ToLower(parts[0]) != "bearer" {
			http.Error(w, `{"error":"invalid authorization format"}`, http.StatusUnauthorized)
			return
		}
		tokenStr := parts[1]

		// Check Redis blacklist
		ctx := r.Context()
		blacklisted, err := g.rdb.Exists(ctx, "jwt:blacklist:"+tokenStr).Result()
		if err == nil && blacklisted > 0 {
			http.Error(w, `{"error":"token revoked"}`, http.StatusUnauthorized)
			return
		}

		claims := &Claims{}
		token, err := jwt.ParseWithClaims(tokenStr, claims, func(t *jwt.Token) (interface{}, error) {
			if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
				return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
			}
			return []byte(g.cfg.JWTSecret), nil
		})
		if err != nil || !token.Valid {
			http.Error(w, `{"error":"invalid or expired token"}`, http.StatusUnauthorized)
			return
		}

		// Forward user info to downstream
		r.Header.Set("X-User-ID", claims.UserID)
		r.Header.Set("X-User-Email", claims.Email)
		r.Header.Set("X-User-Role", claims.Role)
		next.ServeHTTP(w, r)
	})
}

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		lrw := &loggingResponseWriter{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(lrw, r)
		log.Printf("[%s] %s %s %d %v", realIP(r), r.Method, r.URL.Path, lrw.status, time.Since(start))
	})
}

type loggingResponseWriter struct {
	http.ResponseWriter
	status int
}

func (l *loggingResponseWriter) WriteHeader(status int) {
	l.status = status
	l.ResponseWriter.WriteHeader(status)
}

func realIP(r *http.Request) string {
	if ip := r.Header.Get("X-Real-IP"); ip != "" {
		return ip
	}
	if ip := r.Header.Get("X-Forwarded-For"); ip != "" {
		return strings.Split(ip, ",")[0]
	}
	return strings.Split(r.RemoteAddr, ":")[0]
}

// ─── WebSocket Upgrade ────────────────────────────────────────────────────────

func (g *Gateway) wsProxyHandler(target *httputil.ReverseProxy) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// For WebSocket, just pass through (httputil handles upgrade detection)
		target.ServeHTTP(w, r)
	}
}

// ─── Proxy Handlers ───────────────────────────────────────────────────────────

func (g *Gateway) proxyTo(service string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		proxy, ok := g.proxies[service]
		if !ok {
			http.Error(w, "unknown service", http.StatusInternalServerError)
			return
		}
		proxy.ServeHTTP(w, r)
	}
}

// ─── Health ───────────────────────────────────────────────────────────────────

func (g *Gateway) healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, `{"status":"ok","service":"gateway","time":"%s"}`, time.Now().Format(time.RFC3339))
}

// ─── Router ───────────────────────────────────────────────────────────────────

func (g *Gateway) buildRouter() http.Handler {
	r := mux.NewRouter()

	// Public routes (no JWT required)
	r.HandleFunc("/health", g.healthHandler).Methods(http.MethodGet)
	// /api/v1/auth/* → backend-monolith /auth/*
	r.PathPrefix("/api/v1/auth/").Handler(
		http.StripPrefix("/api/v1", g.proxyTo("auth")),
	).Methods(http.MethodPost, http.MethodGet)

	// Protected routes
	protected := r.PathPrefix("/api/v1").Subrouter()
	protected.Use(g.jwtMiddleware)

	// /api/v1/purchases/* → backend-monolith /purchases/*
	protected.PathPrefix("/purchases").Handler(
		http.StripPrefix("/api/v1", g.proxyTo("purchase")),
	)
	// /api/v1/voting/* → backend-monolith /purchases/* (voting is part of purchases)
	protected.PathPrefix("/voting").Handler(
		http.StripPrefix("/api/v1/voting", g.proxyTo("purchase")),
	)
	// /api/v1/payments/* → backend-monolith /wallets/*
	protected.PathPrefix("/payments").Handler(
		http.StripPrefix("/api/v1/payments", g.proxyTo("payment")),
	)
	// /api/v1/wallets/* → backend-monolith /wallets/*
	protected.PathPrefix("/wallets").Handler(
		http.StripPrefix("/api/v1", g.proxyTo("payment")),
	)
	// /api/v1/escrow/* → backend-monolith /escrow/*
	protected.PathPrefix("/escrow").Handler(
		http.StripPrefix("/api/v1", g.proxyTo("payment")),
	)
	// /api/v1/commission/* → backend-monolith /commission/* (future use)
	protected.PathPrefix("/commission").Handler(
		http.StripPrefix("/api/v1", g.proxyTo("payment")),
	)
	protected.PathPrefix("/chat").Handler(
		http.StripPrefix("/api/v1/chat", g.proxyTo("chat")),
	)
	protected.PathPrefix("/search").Handler(
		http.StripPrefix("/api/v1/search", g.proxyTo("search")),
	)
	// /api/v1/reputation/* → backend-monolith /reputation/*
	protected.PathPrefix("/reputation").Handler(
		http.StripPrefix("/api/v1", g.proxyTo("reputation")),
	)
	// /api/v1/reviews/* → backend-monolith /reputation/reviews/*
	protected.PathPrefix("/reviews").Handler(
		http.StripPrefix("/api/v1/reviews", g.proxyTo("reputation")),
	)
	protected.PathPrefix("/complaints").Handler(
		http.StripPrefix("/api/v1", g.proxyTo("reputation")),
	)
	protected.PathPrefix("/analytics").Handler(
		http.StripPrefix("/api/v1/analytics", g.proxyTo("analytics")),
	)

	// WebSocket endpoint (centrifugo is proxied via chat-service for auth)
	r.PathPrefix("/ws").Handler(g.wsProxyHandler(g.proxies["chat"]))

	// Webhook routes (no JWT, validated by provider signature)
	r.PathPrefix("/webhooks/").Handler(
		http.StripPrefix("/webhooks", g.proxyTo("payment")),
	)

	corsHandler := cors.New(cors.Options{
		AllowedOrigins:   g.cfg.CORSOrigins,
		AllowedMethods:   []string{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"Authorization", "Content-Type", "X-Requested-With"},
		ExposedHeaders:   []string{"X-Request-ID"},
		AllowCredentials: true,
		MaxAge:           300,
	})

	chain := loggingMiddleware(g.rateLimitMiddleware(corsHandler.Handler(r)))
	return chain
}

// ─── Main ─────────────────────────────────────────────────────────────────────

func main() {
	cfg := loadConfig()
	gw := newGateway(cfg)

	srv := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      gw.buildRouter(),
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 60 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	log.Printf("Gateway starting on :%s", cfg.Port)
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Server error: %v", err)
	}
}
