# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GroupBuy Bot is a Python + FastAPI microservices platform for organizing group purchases across Telegram, VK, Mattermost, a web cabinet, and WebSocket-based chat. The unified stack builds local Python services with healthchecks and environment-driven configuration.

## Architecture

The main deployable layers are:

**Core API** — `core-fastapi/` — FastAPI service for legacy `/api/*` endpoints used by the frontend, bot, and adapters. Routers live in `core-fastapi/app/routers/`; schema and connection setup live in `core-fastapi/app/schemas.py` and `core-fastapi/app/db.py`.

**Gateway** — `services/gateway/` — FastAPI API gateway for `/api/v1/*`, `/auth/*`, payment webhooks, JWT validation, user-context forwarding, rate limiting, and CORS.

**Microservices** — `services/`:
- `auth-service/` — OTP registration/login, refresh/logout, token validation.
- `purchase-service/` — purchases, participants, voting, invitations, Kafka events.
- `payment-service/` — wallets, transactions, holds, escrow, commissions, payment webhooks.
- `chat-service/` — rooms, messages, media metadata, Centrifugo publishing.
- `notification-service/` — OTP email and notification dispatch.
- `analytics-service/` — event aggregation and report generation.
- `search-service/` — search/indexing with Elasticsearch or Redis fallback.
- `reputation-service/` — reviews, complaints, reputation scores.

Each FastAPI service exposes `GET /health`, is configured by environment variables, and is started by uvicorn from its Dockerfile.

**Bot and Platform Adapters** — `bot/`, `adapters/telegram/`, `adapters/vk/`, `adapters/mattermost/` — Python services that translate platform events to the bot command flow and call the core/gateway APIs.

**Frontend and Infrastructure** — `frontend-react/`, `infrastructure/nginx/`, `infrastructure/websocket/`, `monitoring/`, and `infrastructure/k8s/`.

## Common Commands

### Python Tests
```bash
pytest
pytest tests/test_issue_236_unified_fastapi_stack.py -v
```

Tests are configured in `pytest.ini` with `asyncio_mode = auto`. The `conftest.py` file sets up Django-compatible test support for older tests and adds service paths where needed.

### Service Runs
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
uvicorn services.gateway.main:app --host 0.0.0.0 --port 3000
```

For a service directory that keeps implementation in `app.py`, use the local `main.py` shim:

```bash
cd services/auth-service
uvicorn main:app --host 0.0.0.0 --port 4001
```

### Python Linting
```bash
ruff check bot/ adapters/
ruff format --check bot/ adapters/
```

### Docker
```bash
docker compose up -d
docker compose -f docker-compose.unified.yml up --build
docker compose -f docker-compose.microservices.yml up -d
docker compose -f docker-compose.python.yml up -d
```

## Development Rules

- Keep service configuration in environment variables with sensible defaults.
- Preserve `GET /health` on every FastAPI service and keep compose healthchecks pointed at that endpoint.
- Gateway-facing endpoints should keep legacy aliases where existing frontend or bot clients depend on them.
- Add retries/timeouts around inter-service HTTP calls with `httpx.AsyncClient`.
- Prefer the existing FastAPI router/service patterns before adding new abstractions.
- Keep user-facing Russian strings intact unless the task explicitly changes copy.

## Key Technical Details

- Python 3.11 is the service runtime baseline.
- FastAPI + uvicorn are used for the core API, gateway, and microservices.
- PostgreSQL, Redis, Kafka/Zookeeper, and Centrifugo are shared infrastructure in compose stacks.
- CI includes Python linting, compose regression tests, docker compose validation, and service image builds.
- Environment variables are documented in `.env.example` and README sections for each stack.
