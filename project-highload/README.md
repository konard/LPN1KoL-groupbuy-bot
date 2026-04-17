# GroupBuy High-Load Architecture

A multi-container, high-load ready platform built with Docker Compose.

## Architecture Diagram

```
                        ┌──────────────────────────────────────────────┐
                        │                    nginx                      │
                        │  :80  (entry point, load balancer, WS proxy) │
                        └───┬───────────┬──────────────┬───────────────┘
                            │           │              │
              ┌─────────────┘     ┌─────┘         ┌───┘
              ▼                   ▼               ▼
       ┌────────────┐    ┌──────────────┐  ┌───────────────┐
       │  frontend  │    │   backend    │  │   websocket   │
       │  (React /  │    │  (FastAPI)   │  │   (aiohttp)   │
       │  nginx)    │    │  replicas    │  │   replicas    │
       └────────────┘    └──────┬───────┘  └──────┬────────┘
                                │   publish        │ subscribe
                                ▼                  │
                         ┌──────────┐              │
                         │  Redis   │◄─────────────┘
                         │  Pub/Sub │
                         └──────────┘
                                │
                         ┌──────▼──────┐
                         │  PgBouncer  │ (connection pool)
                         └──────┬──────┘
                                │
                         ┌──────▼──────┐
                         │ PostgreSQL  │
                         │     15      │
                         └─────────────┘
                                ▲
                         ┌──────┴──────┐
                         │   admin     │
                         │  (Django)   │
                         └─────────────┘
```

### Data Flow for Real-Time Updates

1. Client POSTs to `POST /api/items` → nginx → any backend replica
2. Backend writes item to PostgreSQL (via PgBouncer)
3. Backend publishes JSON to Redis `items:new` channel
4. **Every** WebSocket replica subscribes to `items:new` and forwards the event to its local clients
5. Clients receive the event regardless of which WebSocket server they are connected to

## Quick Start

```bash
cp .env.example .env
# Edit .env if needed

# Start full stack with 3 WebSocket replicas
docker compose up --build --scale websocket=3

# Open http://localhost in a browser
```

## Services

| Service      | Technology                  | Port (internal) | Exposed via nginx |
|--------------|-----------------------------|-----------------|-------------------|
| frontend     | React 18 + Vite + nginx     | 80              | `/`               |
| backend      | FastAPI + asyncpg           | 8000            | `/api/`           |
| websocket    | aiohttp + redis Pub/Sub     | 8001            | `/ws`             |
| admin        | Django + Gunicorn/Uvicorn   | 8002            | `/admin/`         |
| nginx        | nginx 1.27                  | 80 (host)       | —                 |
| db           | PostgreSQL 15               | 5432            | —                 |
| pgbouncer    | PgBouncer 1.22              | 5432            | —                 |
| redis        | Redis 7                     | 6379            | —                 |

## Scaling

```bash
# Scale WebSocket servers
docker compose up --scale websocket=5

# Scale backend replicas
docker compose up --scale backend=4
```

Nginx uses `ip_hash` for WebSocket upstream to provide sticky sessions — connections from the same IP always reach the same WebSocket instance (important for upgrade handshake).

## Load Testing

### REST API with wrk

```bash
# Install wrk, then:
wrk -t8 -c400 -d30s http://localhost/api/items

# POST load test (requires wrk with Lua script)
cat > post.lua <<'EOF'
wrk.method = "POST"
wrk.body   = '{"name":"load-test","description":"bench"}'
wrk.headers["Content-Type"] = "application/json"
EOF
wrk -t4 -c200 -d30s -s post.lua http://localhost/api/items
```

### WebSocket with k6

```js
// ws_test.js
import ws from 'k6/ws';
import { check } from 'k6';

export let options = { vus: 500, duration: '30s' };

export default function () {
  ws.connect('ws://localhost/ws', {}, (socket) => {
    socket.on('open', () => socket.setTimeout(() => socket.close(), 25000));
  });
}
```

```bash
k6 run ws_test.js
```

## Failure Handling

| Failure Scenario        | Behavior                                                         |
|-------------------------|------------------------------------------------------------------|
| Backend replica crash   | nginx routes to surviving replicas; Docker restarts the crashed one |
| WebSocket replica crash | Clients reconnect (3s backoff in frontend) to another replica   |
| Redis disconnection     | WebSocket service logs error; reconnects automatically on next message; REST API unaffected |
| PostgreSQL unavailable  | Backend returns 500; PgBouncer queues connections up to pool limit |
| PgBouncer restart       | Backend retries via SQLAlchemy pool pre-ping                     |

## Further Scaling Recommendations

### Kubernetes

Replace `docker compose up --scale` with a Kubernetes `Deployment` + HPA:

```yaml
# backend Deployment with HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
```

Kubernetes manifests are provided under `k8s/` as a starting point.

### Replace Redis Pub/Sub with Kafka

For **guaranteed delivery** (Redis Pub/Sub is fire-and-forget):

- Use **Apache Kafka** or **Redpanda** as the message broker.
- Backend → `items` Kafka topic.
- WebSocket service → consumer group per replica.
- Each message is delivered at least once even if a replica was briefly offline.

### CDN + Static Assets

Serve the built React bundle from a CDN (CloudFront, Cloudflare). Only dynamic requests hit nginx.

### Database Read Replicas

Add PostgreSQL streaming replicas and configure SQLAlchemy to route read queries to replicas using `asyncpg` connection strings.
