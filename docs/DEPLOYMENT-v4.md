# Deployment Guide v4.0 — GroupBuy Service

Complete deployment instructions for the GroupBuy microservices platform.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Infrastructure Setup](#2-infrastructure-setup)
3. [Database Setup](#3-database-setup)
4. [Configuration](#4-configuration)
5. [Docker Compose Deployment (Dev/Staging)](#5-docker-compose-deployment)
6. [Kubernetes Deployment (Production)](#6-kubernetes-deployment)
7. [Service Verification](#7-service-verification)
8. [Monitoring Setup](#8-monitoring-setup)
9. [CI/CD Pipeline](#9-cicd-pipeline)
10. [Scaling Guide](#10-scaling-guide)
11. [Backup & Recovery](#11-backup--recovery)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Prerequisites

### Hardware Requirements (Production)

| Component | Min Spec | Recommended |
|-----------|----------|-------------|
| Kubernetes nodes | 3 nodes, 4 CPU / 16GB RAM | 6+ nodes, 8 CPU / 32GB RAM |
| PostgreSQL | 4 CPU / 16GB RAM / 200GB SSD | 8 CPU / 32GB RAM / 500GB NVMe |
| Elasticsearch | 4 CPU / 8GB RAM / 100GB SSD | 8 CPU / 16GB RAM / 500GB NVMe |
| Redis | 2 CPU / 8GB RAM | 4 CPU / 16GB RAM |
| Kafka | 4 CPU / 8GB RAM / 500GB SSD | 8 CPU / 16GB RAM / 1TB SSD |

### Software Requirements

- Docker 24.0+ and Docker Compose v2.20+
- Kubernetes 1.28+ (for production)
- kubectl, helm 3.13+
- Go 1.22+, Node.js 20+, Python 3.11+
- PostgreSQL 16, Redis 7, Kafka 3.5+
- Elasticsearch 8.12+
- Argo Rollouts (for canary deployments)

### Accounts & Credentials

- Stripe API keys (for payment processing)
- YooKassa credentials (for Russian payment processing)
- Telegram Bot Token (from @BotFather)
- WhatsApp Business API access token
- SMTP credentials for email notifications
- S3/MinIO credentials for file storage
- SSL certificates for your domain

---

## 2. Infrastructure Setup

### 2.1 Clone Repository

```bash
git clone https://github.com/MixaByk1996/groupbuy-bot.git
cd groupbuy-bot
```

### 2.2 Environment Configuration

```bash
cp .env.example .env
```

Edit `.env` with your actual credentials:

```env
# Database
POSTGRES_PASSWORD=your_secure_password_here

# JWT
JWT_SECRET=generate_with_openssl_rand_base64_64
JWT_REFRESH_SECRET=generate_another_secret

# Payments
STRIPE_SECRET_KEY=sk_live_...
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret

# Telegram Bot
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-...

# WhatsApp
WHATSAPP_API_URL=https://graph.facebook.com/v18.0
WHATSAPP_ACCESS_TOKEN=your_access_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id

# SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASS=your_app_password

# S3 / MinIO
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
```

---

## 3. Database Setup

### 3.1 PostgreSQL Databases

The system uses separate databases per service:

| Service | Database | User |
|---------|----------|------|
| Auth | auth_db | auth_user |
| Purchase | purchase_db | purchase_user |
| Payment | payment_db | payment_user |
| Chat | chat_db | chat_user |
| Reputation | reputation_db | reputation_user |

Each service auto-runs migrations on startup. No manual migration needed.

### 3.2 ClickHouse (Analytics/Chat History)

ClickHouse is used for chat message archival and analytics. The chat-service creates tables on startup.

### 3.3 Elasticsearch (Search)

The search-service auto-creates the `purchases` index with proper mapping on startup.

### 3.4 Redis

Used for:
- JWT token blacklist (auth)
- Rate limiting (gateway)
- Session cache
- Search history (search-service)
- Voting rate limits

---

## 4. Configuration

### 4.1 Service Ports

| Service | Port | Protocol |
|---------|------|----------|
| Gateway | 3000 | HTTP |
| Auth Service | 4001 | HTTP |
| Purchase Service | 4002 | HTTP |
| Payment Service | 4003 | HTTP |
| Chat Service | 4004 | HTTP |
| Notification Service | 4005 | HTTP |
| Analytics Service | 4006 | HTTP |
| Search Service | 4007 | HTTP |
| Reputation Service | 4008 | HTTP |
| Frontend | 3001 | HTTP |
| Centrifugo (WebSocket) | 8000 | HTTP/WS |
| Kafka | 9092 | TCP |
| Kafka UI | 8090 | HTTP |
| Prometheus | 9090 | HTTP |
| Grafana | 3001 | HTTP |

### 4.2 Kafka Topics

All topics are auto-created. Key topics:

**Purchase events:** `purchase.created`, `purchase.voting.started`, `purchase.voting.closed`, `purchase.voting.tie`, `purchase.vote.cast`, `purchase.vote.changed`, `purchase.candidate.added`, `purchase.cancelled`

**Payment events:** `payment.topup.completed`, `payment.hold.created`, `payment.committed`, `payment.released`

**Commission events:** `commission.held`, `commission.committed`, `commission.released`

**Escrow events:** `escrow.created`, `escrow.deposited`, `escrow.confirmed`, `escrow.released`, `escrow.disputed`

**Reputation events:** `review.created`, `complaint.filed`, `complaint.resolved`, `user.auto_blocked`

**Search events:** `search.query`, `search.new_match`

### 4.3 Commission Configuration

- Range: 0-10% (step 0.5%)
- Configured per purchase by the organizer
- Validated at API level and database level (CHECK constraint)

### 4.4 Escrow Configuration

- Default threshold: $10,000 (configurable)
- Release requires 80%+ buyer confirmations
- Disputes trigger admin arbitration

### 4.5 2FA Configuration

- TOTP-based (Google Authenticator compatible)
- Mandatory for organizer and supplier roles
- 10 one-time backup codes per user

---

## 5. Docker Compose Deployment

### 5.1 Development Environment

```bash
# Start all microservices with infrastructure
docker compose -f docker-compose.microservices.yml up -d

# Check all services are running
docker compose -f docker-compose.microservices.yml ps

# View logs for a specific service
docker compose -f docker-compose.microservices.yml logs -f gateway
```

### 5.2 Production Docker Compose

```bash
# Build all images
docker compose -f docker-compose.microservices.yml build

# Start with production settings
docker compose -f docker-compose.prod.yml up -d
```

### 5.3 Service Build Order

Infrastructure starts first (postgres, redis, kafka, elasticsearch), then services:

1. PostgreSQL instances (auth, purchase, payment, chat, reputation)
2. Redis, Kafka, Zookeeper, ClickHouse, MinIO, Elasticsearch
3. Centrifugo
4. Auth Service
5. All other services (purchase, payment, chat, search, reputation, notification, analytics)
6. Gateway
7. Frontend

### 5.4 Verify Deployment

```bash
# Check all health endpoints
for port in 3000 4001 4002 4003 4004 4005 4006 4007 4008; do
  echo "Port $port: $(curl -s http://localhost:$port/health | jq -r '.status')"
done
```

---

## 6. Kubernetes Deployment

### 6.1 Prerequisites

```bash
# Install Argo Rollouts for canary deployments
kubectl apply -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

# Install kubectl argo rollouts plugin
curl -LO https://github.com/argoproj/argo-rollouts/releases/latest/download/kubectl-argo-rollouts-linux-amd64
chmod +x kubectl-argo-rollouts-linux-amd64
sudo mv kubectl-argo-rollouts-linux-amd64 /usr/local/bin/kubectl-argo-rollouts
```

### 6.2 Create Namespace

```bash
kubectl create namespace groupbuy
kubectl config set-context --current --namespace=groupbuy
```

### 6.3 Create Secrets

```bash
# Database secrets
kubectl create secret generic auth-db-secret \
  --from-literal=url="postgresql://auth_user:PASSWORD@postgres-auth:5432/auth_db"

kubectl create secret generic purchase-db-secret \
  --from-literal=url="postgresql://purchase_user:PASSWORD@postgres-purchase:5432/purchase_db"

kubectl create secret generic payment-db-secret \
  --from-literal=url="postgresql://payment_user:PASSWORD@postgres-payment:5432/payment_db"

kubectl create secret generic chat-db-secret \
  --from-literal=url="postgresql://chat_user:PASSWORD@postgres-chat:5432/chat_db"

kubectl create secret generic reputation-db-secret \
  --from-literal=url="postgresql://reputation_user:PASSWORD@postgres-reputation:5432/reputation_db"

# Redis secret
kubectl create secret generic redis-secret \
  --from-literal=url="redis://:PASSWORD@redis:6379"

# JWT secret
kubectl create secret generic jwt-secret \
  --from-literal=secret="your_jwt_secret_here" \
  --from-literal=refresh-secret="your_refresh_secret_here"

# Payment secrets
kubectl create secret generic payment-secrets \
  --from-literal=stripe-key="sk_live_..." \
  --from-literal=yookassa-shop-id="your_shop_id" \
  --from-literal=yookassa-secret="your_secret"

# Telegram/WhatsApp
kubectl create secret generic messenger-secrets \
  --from-literal=telegram-token="your_telegram_token" \
  --from-literal=whatsapp-token="your_whatsapp_token"
```

### 6.4 Deploy Infrastructure

```bash
# Apply infrastructure manifests
kubectl apply -f infrastructure/k8s/postgres.yaml
kubectl apply -f infrastructure/k8s/redis.yaml
kubectl apply -f infrastructure/k8s/kafka.yaml
kubectl apply -f infrastructure/k8s/clickhouse.yaml
kubectl apply -f infrastructure/k8s/elasticsearch.yaml
kubectl apply -f infrastructure/k8s/centrifugo.yaml

# Wait for infrastructure to be ready
kubectl wait --for=condition=ready pod -l app=postgres-auth --timeout=120s
kubectl wait --for=condition=ready pod -l app=redis --timeout=60s
kubectl wait --for=condition=ready pod -l app=elasticsearch --timeout=180s
```

### 6.5 Deploy Application Services

```bash
# Deploy all services
kubectl apply -f infrastructure/k8s/auth-service.yaml
kubectl apply -f infrastructure/k8s/purchase-service.yaml
kubectl apply -f infrastructure/k8s/payment-service.yaml
kubectl apply -f infrastructure/k8s/chat-service.yaml
kubectl apply -f infrastructure/k8s/notification-service.yaml
kubectl apply -f infrastructure/k8s/analytics-service.yaml
kubectl apply -f infrastructure/k8s/search-service.yaml
kubectl apply -f infrastructure/k8s/reputation-service.yaml
kubectl apply -f infrastructure/k8s/gateway.yaml

# Verify
kubectl get pods
```

### 6.6 Enable Canary Deployments with Auto-Rollback

```bash
# Apply Argo Rollouts configurations
kubectl apply -f infrastructure/k8s/argo-rollouts/

# Check rollout status
kubectl argo rollouts get rollout purchase-service
kubectl argo rollouts get rollout payment-service
kubectl argo rollouts get rollout gateway
```

The auto-rollback triggers when:
- 5xx error rate > 0.5% during canary (5% traffic) for 2 minutes
- p95 latency > 500ms during canary

### 6.7 Geo-Distribution (Multi-Region)

For 3-region deployment (US, EU, APAC):

```bash
# Each region gets full service set
# US-East: Master for writes
# EU: Sync replica for reads
# APAC: Async replica for reads

# Use Global Load Balancer (GCP GLB / AWS Global Accelerator)
# with latency-based routing
```

---

## 7. Service Verification

### 7.1 Health Checks

```bash
# Gateway
curl http://localhost:3000/health

# Auth (register + login)
curl -X POST http://localhost:3000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"securepass123","role":"USER"}'

# Login (returns JWT + optional 2FA prompt)
curl -X POST http://localhost:3000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"securepass123"}'

# Search
curl -X POST http://localhost:3000/api/v1/search/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"test product","page":1,"per_page":10}'

# Reputation
curl http://localhost:3000/api/v1/reputation/user-id-here \
  -H "Authorization: Bearer $TOKEN"
```

### 7.2 WebSocket Test

```javascript
// Test WebSocket via Centrifugo
const ws = new WebSocket('ws://localhost:8000/connection/websocket');
ws.onopen = () => {
  ws.send(JSON.stringify({
    connect: { token: "JWT_TOKEN" },
    id: 1
  }));
};
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

### 7.3 Voting Test

```bash
# Create voting session
curl -X POST http://localhost:3000/api/v1/voting/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"purchaseId":"uuid","votingDuration":24}'

# Add candidate
curl -X POST http://localhost:3000/api/v1/voting/sessions/$SESSION_ID/candidates \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"supplierName":"Supplier A","pricePerUnit":100}'

# Cast vote
curl -X POST http://localhost:3000/api/v1/voting/sessions/$SESSION_ID/votes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"candidateId":"uuid"}'
```

---

## 8. Monitoring Setup

### 8.1 Prometheus

Already configured in `monitoring/prometheus.yml`. Scrapes all 9 services + infrastructure.

### 8.2 Grafana

Access at `http://localhost:3001` (admin/admin_password).

Key dashboards:
- **Service Health**: All services uptime, error rates, latencies
- **Active Purchases**: Status distribution, voting timeline
- **Payment Flow**: Hold/commit/release pipeline
- **Escrow**: Total held, confirmations, disputes
- **Reputation**: Rating distribution, complaint trends
- **Search**: Query volume, latency, popular terms

### 8.3 Alerting

Alert rules defined in `monitoring/alert_rules.yml`:

| Alert | Severity | Condition |
|-------|----------|-----------|
| ServiceDown | Critical | Any service down >1min |
| HighErrorRate | Warning | 5xx >5% for 2min |
| CanaryHighErrorRate | Critical | Canary 5xx >0.5% for 2min (triggers rollback) |
| AutoRollbackPerformed | Critical | Rollback event detected |
| EscrowDisputeRate | Warning | >5% disputes |
| SearchHighLatency | Warning | p95 >1s for 5min |
| ElasticsearchClusterRed | Critical | ES health red |
| PaymentHoldFailureRate | Warning | >10% failures |

### 8.4 Tracing (Jaeger)

For request tracing across services, deploy Jaeger:

```bash
kubectl apply -f https://raw.githubusercontent.com/jaegertracing/jaeger-operator/main/deploy/crds/jaegertracing.io_jaegers_crd.yaml
kubectl apply -f https://raw.githubusercontent.com/jaegertracing/jaeger-operator/main/deploy/operator.yaml
```

All services propagate `X-Request-ID` headers for correlation.

---

## 9. CI/CD Pipeline

### 9.1 Build Pipeline

Each service has its own Dockerfile. Build with:

```bash
# Build all service images
for svc in gateway auth-service purchase-service payment-service \
  chat-service notification-service analytics-service \
  search-service reputation-service; do
  docker build -t groupbuy/$svc:latest ./services/$svc/
done

# Build frontend
docker build -t groupbuy/frontend:latest ./frontend-react/
```

### 9.2 Deployment Pipeline

```yaml
# .github/workflows/deploy.yml (example)
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build and push images
        run: |
          for svc in gateway auth-service purchase-service ...; do
            docker build -t $REGISTRY/$svc:${{ github.sha }} ./services/$svc/
            docker push $REGISTRY/$svc:${{ github.sha }}
          done
      - name: Update rollout image
        run: |
          kubectl argo rollouts set image purchase-service \
            purchase-service=$REGISTRY/purchase-service:${{ github.sha }}
```

---

## 10. Scaling Guide

### 10.1 Recommended Replicas (>10M Users)

| Service | Replicas | HPA Min/Max |
|---------|----------|-------------|
| Gateway | 10 | 10/50 |
| Auth | 5 | 5/20 |
| User | 5 | 5/15 |
| Purchase | 15 | 15/60 |
| Payment | 10 | 10/40 |
| Chat (+ Centrifugo) | 20 | 20/80 |
| Analytics | 5 | 5/15 |
| Notification | 5 | 5/20 |
| Search | 5 | 5/30 |
| Reputation | 3 | 3/10 |

### 10.2 Database Scaling

- PostgreSQL: 10 shards by purchase_id and user_id
- ClickHouse: 6-node cluster with 90-day TTL
- Redis Cluster: 12 nodes
- Elasticsearch: 6 nodes (3 master, 3 data)
- Kafka: 3 brokers, 12 partitions for hot topics

### 10.3 Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: purchase-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: purchase-service
  minReplicas: 15
  maxReplicas: 60
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

---

## 11. Backup & Recovery

### 11.1 PostgreSQL Backup

```bash
# Automated daily backup (all databases)
for db in auth purchase payment chat reputation; do
  pg_dump -h postgres-$db -U ${db}_user ${db}_db | gzip > \
    /backups/postgres/${db}_$(date +%Y%m%d_%H%M%S).sql.gz
done

# Point-in-time recovery with WAL archiving
# Configure postgresql.conf:
# archive_mode = on
# archive_command = 'aws s3 cp %p s3://backups/wal/%f'
```

### 11.2 Elasticsearch Backup

```bash
# Register snapshot repository
curl -X PUT "localhost:9200/_snapshot/backup" \
  -H "Content-Type: application/json" \
  -d '{"type":"s3","settings":{"bucket":"es-backups"}}'

# Create snapshot
curl -X PUT "localhost:9200/_snapshot/backup/snap_$(date +%Y%m%d)"
```

### 11.3 Redis Backup

Redis AOF is enabled. RDB snapshots are auto-saved.

```bash
# Manual backup
redis-cli -a $REDIS_PASSWORD BGSAVE
cp /data/dump.rdb /backups/redis/dump_$(date +%Y%m%d).rdb
```

### 11.4 Recovery Procedures

**RTO: 15 minutes, RPO: 1 minute**

PostgreSQL master failure:
```bash
# Promote sync replica to master
pg_ctl promote -D /var/lib/postgresql/data
# Update connection strings in secrets
kubectl edit secret purchase-db-secret
# Rolling restart of affected services
kubectl rollout restart deployment purchase-service
```

---

## 12. Troubleshooting

### Common Issues

**Service can't connect to database:**
```bash
# Check database pods
kubectl get pods -l app=postgres-purchase
# Check connection from service pod
kubectl exec -it purchase-service-xxx -- nc -zv postgres-purchase 5432
```

**Kafka consumer lag:**
```bash
# Check consumer group lag
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --group notification-group --describe
# If lag >10000: increase consumer replicas
```

**Elasticsearch cluster red:**
```bash
# Check cluster health
curl localhost:9200/_cluster/health?pretty
# Check unassigned shards
curl localhost:9200/_cat/shards?v&h=index,shard,prirep,state,unassigned.reason
```

**High payment hold failure rate:**
```bash
# Check wallet balances
curl -H "X-User-ID: $USER_ID" http://payment-service:4003/wallet
# Check transaction log
kubectl logs -l app=payment-service --tail=100 | grep "Hold error"
```

**Voting tie not resolved:**
```bash
# Check voting session status
curl http://purchase-service:4002/voting/sessions/$SESSION_ID/results
# Manually resolve
curl -X POST http://purchase-service:4002/voting/sessions/$SESSION_ID/resolve-tie \
  -H "Content-Type: application/json" \
  -d '{"candidateId":"winner-uuid"}'
```

**Auto-rollback triggered:**
```bash
# Check rollout status
kubectl argo rollouts get rollout purchase-service
# View analysis runs
kubectl get analysisrun -l rollouts-pod-template-hash
# Check Prometheus for error spike
# Visit Grafana dashboard: http://grafana:3000/d/service-health
```

---

## Appendix: Architecture Diagram

```
                    ┌──────────────────┐
                    │  Global Load     │
                    │  Balancer        │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │    Gateway       │
                    │  (Go/Fiber)      │
                    │  Rate Limit,JWT  │
                    └────────┬─────────┘
           ┌─────────┬──────┴──────┬──────────┐
           │         │            │           │
     ┌─────▼──┐ ┌────▼───┐ ┌─────▼──┐ ┌──────▼──┐
     │  Auth  │ │Purchase│ │Payment │ │  Chat   │
     │Service │ │Service │ │Service │ │Service  │
     │(Go)   │ │(NestJS)│ │  (Go)  │ │  (Go)   │
     └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
         │          │          │           │
         │     ┌────┴────┐    │      ┌────┴────┐
         │     │  Kafka  │◄───┘      │Centrifugo│
         │     └────┬────┘           └─────────┘
         │          │
    ┌────┴──┐  ┌───┴────┐  ┌────────┐  ┌──────────┐
    │Search │  │Notif.  │  │Analyt. │  │Reputation│
    │Service│  │Service │  │Service │  │ Service  │
    │(Go+ES)│  │(Node)  │  │(Python)│  │(NestJS)  │
    └───────┘  └────────┘  └────────┘  └──────────┘
```

---

*Version: 4.0 | Date: 2026-04-03*
