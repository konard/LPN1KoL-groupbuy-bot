# GroupBuy Highload Demo

This folder is an isolated multi-container demo for issue #7. It keeps the
current repository intact while providing a launchable high-load architecture
with an async REST backend, horizontally scalable WebSocket workers, Redis
Pub/Sub fan-out, PgBouncer, PostgreSQL 15, Django admin, React/Vite frontend,
and nginx as the public entry point.

## Quick Start

```bash
cd project-highload
cp .env.example .env
docker compose up --build --scale websocket=3
```

Open:

- Frontend: http://localhost:8080/
- REST API: http://localhost:8080/api/items
- WebSocket: ws://localhost:8080/ws/items
- Django admin: http://localhost:8080/admin/ (`admin` / `admin` by default)
- nginx health: http://localhost:8080/healthz
- backend readiness: http://localhost:8080/backend/readyz
- websocket readiness: http://localhost:8080/websocket/readyz

Create an item from another terminal:

```bash
curl -X POST http://localhost:8080/api/items \
  -H 'Content-Type: application/json' \
  -d '{"name":"Demo item","description":"Published through Redis Pub/Sub"}'
```

Every connected browser receives the event from its local WebSocket worker.

## Architecture

```text
Browser
  | HTTP / WebSocket
  v
nginx
  |-- /                 -> frontend (React/Vite static build)
  |-- /api/*            -> backend replicas (FastAPI async, stateless)
  |-- /ws/*             -> websocket replicas (aiohttp, sticky sessions)
  |-- /admin/*          -> admin (Django via Gunicorn + Uvicorn worker)

backend -- SQLAlchemy async + asyncpg pool --> PgBouncer --> PostgreSQL 15
backend -- publish items:new -------------> Redis Pub/Sub
websocket replicas -- subscribe items:new -> Redis Pub/Sub
```

The backend is stateless and can be scaled independently:

```bash
docker compose up --build --scale backend=3 --scale websocket=3
```

WebSocket workers keep only local in-memory connection sets. Cross-instance
delivery happens through Redis Pub/Sub on the `items:new` channel, so any
backend replica can create an item and every WebSocket replica receives it.

## Sticky Sessions

nginx uses a `SERVER_ID` cookie as the sticky key for `/ws/` traffic:

```nginx
hash $sticky_key consistent;
add_header Set-Cookie "SERVER_ID=$sticky_key; Path=/; HttpOnly; SameSite=Lax" always;
```

The first WebSocket upgrade receives a cookie. Later reconnects use that cookie
so the client is routed back to the same upstream worker when the worker is
healthy. If a worker disappears, consistent hashing remaps the client to another
replica.

## Service Responsibilities

| Service | Role | High-load behavior |
| --- | --- | --- |
| `frontend` | React/Vite UI | Reads `VITE_API_URL` and `VITE_WS_URL` at build time |
| `backend` | FastAPI REST API | Async SQLAlchemy/asyncpg, pooled DB access, stateless replicas |
| `websocket` | aiohttp WebSocket fan-out | Local connection registry, Redis Pub/Sub subscription, graceful shutdown |
| `admin` | Django admin | Gunicorn + Uvicorn worker, same PostgreSQL database through PgBouncer |
| `db` | PostgreSQL 15 | Persistent volume plus baseline high-load settings |
| `pgbouncer` | Connection pooler | Transaction pooling in front of PostgreSQL |
| `redis` | Event broker | Pub/Sub for `items:new`; persistence disabled for local demo |
| `nginx` | Public entry point | API load balancing, WebSocket proxying, sticky sessions |

## Health, Readiness, And Metrics

Container healthchecks are defined for every runtime service. HTTP endpoints:

- `backend`: `/healthz`, `/readyz`, `/metrics`
- `websocket`: `/healthz`, `/readyz`, `/metrics`
- `admin`: `/healthz`
- `nginx`: `/healthz`

The readiness endpoints are suitable for Kubernetes liveness/readiness probes.
The metrics endpoints return Prometheus-style text so they can be scraped by a
Prometheus sidecar or service monitor later.

## Load Testing

REST API with `wrk`:

```bash
wrk -t8 -c512 -d60s http://localhost:8080/api/items
```

REST API with `k6`:

```bash
k6 run - <<'EOF'
import http from 'k6/http';
import { sleep } from 'k6';

export const options = {
  vus: 200,
  duration: '1m',
};

export default function () {
  http.get('http://localhost:8080/api/items');
  sleep(0.1);
}
EOF
```

For WebSocket load, use `k6/ws` or a purpose-built tool such as `thor`, then
increase `--scale websocket=N` and watch `groupbuy_websocket_connections` on
each worker. For tens of thousands of WebSocket connections, raise host
`ulimit -n`, tune nginx `worker_connections`, and spread workers across nodes.

## Failure Handling

- Backend failure: nginx routes new REST requests to remaining healthy backend
  replicas. The service is stateless, so no in-process session is lost.
- WebSocket worker restart: the worker closes sockets with `GOING_AWAY` during
  graceful shutdown. The frontend reconnects and receives a fresh `connected`
  event.
- Redis outage: WebSocket workers mark readiness as failed and retry Redis
  subscription with backoff. Backend item creation returns 503 if the database
  commit succeeds but publishing to Redis fails, making the partial failure
  visible to callers.
- PostgreSQL connection spike: PgBouncer absorbs client connection bursts and
  keeps PostgreSQL `max_connections` bounded.
- Container crash: every runtime service uses `restart: unless-stopped`.

## Production Notes

- Replace the local PgBouncer `auth_type = trust` with SCRAM or md5
  authentication before exposing it outside the private network.
- Replace Redis Pub/Sub with Kafka, NATS JetStream, or Redis Streams if events
  must be durably replayed after subscriber downtime. Redis Pub/Sub is fast and
  simple, but it does not guarantee delivery to disconnected subscribers.
- Move to Kubernetes when the deployment needs node-level scaling. The same
  service split maps directly to Deployments for `backend`, `websocket`,
  `frontend`, and `admin`; StatefulSets or managed services should host
  PostgreSQL, PgBouncer, and Redis.
- Use an ingress controller with cookie affinity or consistent-hash routing for
  WebSocket sticky sessions.
- Use Alembic/Django migrations for schema evolution. The demo creates the
  `items` table on backend startup to make local launch immediate.
