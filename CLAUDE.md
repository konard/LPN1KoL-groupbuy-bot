# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GroupBuy Bot is a microservices platform for organizing group purchases, supporting Telegram, VK, Mattermost, and WebSocket-based chat. The system uses a multi-language stack with multiple deployment configurations.

## Architecture

The system has three layers:

**Core API (Rust)** — `core-rust/` — Actix-web REST API with PostgreSQL (sqlx) and JWT auth. This is the primary backend. Modules: `src/handlers/`, `src/models/`, `src/db/`. Migrations in `core-rust/migrations/`.

**Legacy Django Core** — `core/` — Django + DRF backend with apps: `users`, `procurements`, `chat`, `payments`, `admin_api`, `ml`. Settings in `core/config/settings.py`. Still used for admin API and ML analytics.

**Bot Service** — `bot/` — Telegram bot using aiogram 3.x + aiohttp web server. Handles user commands, procurements, chat, broadcasts. Communicates with Core API via HTTP.

**Platform Adapters** — `adapters/telegram/`, `adapters/vk/`, `adapters/mattermost/` — Translate platform-specific events to/from the bot service's HTTP API.

**Go Microservices** — `services/`:
- `gateway/` — Go (gorilla/mux) API gateway with JWT validation, rate limiting, CORS
- `auth-service/` — NestJS JWT auth with 2FA
- `purchase-service/` — NestJS + Kafka for purchase sagas
- `payment-service/` — Go wallets/escrow
- `chat-service/`, `search-service/`, `reputation-service/`, `notification-service/`, `analytics-service/`

**Frontend** — `frontend-react/` — React 18 + Vite + Zustand + WASM integration. Dev: `npm run dev`, Build: `npm run build`, Lint: `npm run lint`.

**Infrastructure** — `infrastructure/k8s/` (Kubernetes manifests), `infrastructure/nginx/`, `infrastructure/websocket/` (Python WebSocket server). Monitoring in `monitoring/`.

## Common Commands

### Python Tests (Core + Bot)
```bash
# Run all tests (uses SQLite in-memory, no Postgres needed)
pytest

# Run a single test file
pytest tests/test_core_api.py

# Run a specific test
pytest tests/test_core_api.py::TestClassName::test_method -v
```
Tests are configured in `pytest.ini` with `asyncio_mode = auto`. The `conftest.py` sets up Django with SQLite and adds `core/` and `bot/` to sys.path.

### Rust Core
```bash
cd core-rust
cargo build --release
cargo test
```

### Python Linting (CI uses these)
```bash
ruff check bot/ adapters/
ruff format --check bot/ adapters/
```

### NestJS Services (auth, purchase, reputation)
```bash
cd services/auth-service  # or purchase-service, reputation-service
npm install
npm run build
npm test
```

### Docker
```bash
# Development (full stack)
docker compose up -d

# Production
docker compose -f docker-compose.prod.yml up -d

# Microservices mode
docker compose -f docker-compose.microservices.yml up -d

# Unified (single-server)
docker compose -f docker-compose.unified.yml up -d
```

## Key Technical Details

- Python 3.11, Django 4.2, aiogram 3.x
- Rust edition 2021, Actix-web 4, sqlx 0.8 with PostgreSQL
- Go services use gorilla/mux, go-redis, golang-jwt
- NestJS services use TypeScript
- Frontend uses Vite 6, React 18, vitest for tests
- CI runs on GitHub Actions: Python lint (ruff), Rust build+test, and more (`.github/workflows/ci.yml`)
- Environment variables documented in `.env.example`
- The project is bilingual (English code, Russian user-facing strings and documentation)
