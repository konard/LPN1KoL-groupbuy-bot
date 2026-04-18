# GroupBuy v2 — Dockerized Microservice Architecture

## Architecture

4 isolated services in a single `docker-compose.yml`, communicating through Docker's internal network:

```
┌────────────────────────────────────────────────────────────────┐
│                     Nginx (port 80)                            │
│  /           → frontend-client  (React SPA)                    │
│  /api/       → backend          (FastAPI REST)                 │
│  /socket/    → socket-broker    (FastAPI WebSocket)            │
│  /admin-panel/ → frontend-admin (FastAPI + Jinja2)             │
└──────┬─────────────┬──────────────┬──────────────┬─────────────┘
       │             │              │              │
  ┌────▼────┐  ┌─────▼─────┐  ┌────▼────┐  ┌─────▼──────┐
  │frontend │  │  backend   │  │ socket  │  │   admin    │
  │ client  │  │   API      │  │ broker  │  │   panel    │
  │ :80     │  │  :8000     │  │ :8001   │  │  :8002     │
  └─────────┘  └──┬────┬───┘  └────┬────┘  └────────────┘
                  │    │           │
              ┌───▼┐ ┌─▼───────────▼──┐
              │ DB │ │     Redis       │
              │5432│ │  (Pub/Sub)      │
              └────┘ └────────────────┘
```

### How Socket Communication Works

1. Client (frontend) connects to **socket-broker** via WebSocket
2. Admin panel connects to **socket-broker** via WebSocket
3. When **backend** needs to notify users (e.g., new order, status change), it **publishes** an event to Redis Pub/Sub (`redis_client.publish("room:admin", event)`)
4. **socket-broker** **subscribes** to Redis channels and relays messages to the correct WebSocket clients
5. Restarting `backend` does NOT break WebSocket connections — they are held by `socket-broker`

### Directory Structure

```
deploy_v2/
├── docker-compose.yml
├── .env.example
├── services/
│   ├── backend/          # Service 2: FastAPI REST API
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── create_admin.py
│   │   └── app/
│   │       └── main.py
│   ├── socket-service/   # Service 4: WebSocket broker
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── main.py
│   ├── frontend-client/  # Service 1: React SPA
│   │   ├── Dockerfile
│   │   ├── nginx.conf
│   │   ├── package.json
│   │   ├── index.html
│   │   ├── vite.config.js
│   │   └── src/
│   └── frontend-admin/   # Service 3: Admin panel
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── main.py
│       └── templates/
├── nginx/
│   └── default.conf
└── scripts/
    ├── create-admin.sh
    └── healthcheck.sh
```

## Deployment on a Clean Machine

### 1. Clone the repository

```bash
git clone <repo-url>
cd <repo>/deploy_v2
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set SECRET_KEY, DB_PASSWORD, DOMAIN for production
```

### 3. Build and start

```bash
docker compose build
docker compose up -d
```

### 4. Create admin user

```bash
./scripts/create-admin.sh admin admin@example.com your-password
```

### 5. Verify

```bash
./scripts/healthcheck.sh
```

Then open:
- **Frontend**: http://localhost/
- **Admin panel**: http://localhost/admin-panel/
- **API docs**: http://localhost/api/docs

### Production

For production, only change `.env`:

```env
SECRET_KEY=<long-random-string>
DB_PASSWORD=<strong-password>
DOMAIN=yourdomain.com
CORS_ORIGINS=https://yourdomain.com
```

No code or config changes needed. `docker compose up -d` works identically.

### Data persistence

- `docker compose down` stops containers but preserves the `postgres_data` volume
- `docker compose down -v` removes volumes (database data will be lost)
- `docker compose up -d` recreates containers with existing data

## Stress-test checklist

Manual verification steps to confirm the architecture behaves as designed:

- [ ] Client dashboard opens at `http://localhost/` with no CORS errors in the
      browser console (same-origin thanks to the nginx reverse proxy).
- [ ] Admin panel opens at `http://localhost/admin-panel/` and reads live data
      from the shared Postgres through the backend API.
- [ ] Creating an order (or any `publish_event` trigger) in the client
      dashboard delivers a WebSocket notification to the admin panel via the
      `room:admin` Redis channel.
- [ ] `docker compose restart backend` does **not** drop active client or admin
      WebSocket connections — the `socket-broker` owns the sockets and merely
      re-subscribes when backend resumes publishing.
- [ ] `docker compose down` (without `-v`) keeps the `postgres_data` volume; a
      subsequent `docker compose up -d` recreates all containers with the same
      data intact. Only `docker compose down -v` destroys the volume.

## Mapping to issue requirements

| Requirement                               | Where it lives                                        |
|-------------------------------------------|-------------------------------------------------------|
| Service 1 — frontend-client (React+Nginx) | `services/frontend-client/`                           |
| Service 2 — backend (Python/FastAPI)      | `services/backend/`                                   |
| Service 3 — frontend-admin                | `services/frontend-admin/`                            |
| Service 4 — socket broker                 | `services/socket-service/`                            |
| Single `docker-compose.yml`               | `docker-compose.yml` (root of `deploy_v2/`)           |
| Redis Pub/Sub between backend and sockets | `publish_event()` in backend, `psubscribe("room:*")` in socket-broker |
| Shared internal network                   | Default Docker bridge network created by compose      |
| `.env.example` for production overrides   | `deploy_v2/.env.example`                              |
| Reverse proxy / single public port        | `nginx/default.conf` on port 80                       |
