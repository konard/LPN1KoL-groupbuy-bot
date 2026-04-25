# LogiTrack Backend

FastAPI tracking demo with PostgreSQL, Redis, REST order workflows, token-protected WebSockets, GraphQL order history, GeoJSON track output, health checks, rate limits, and Alembic migrations.

Run: `cp .env.example .env && docker compose up --build`.
Migrate: `alembic upgrade head`.
Tests: `python -m pytest`.

Send `X-API-Token` on REST requests and `?token=` on `/ws/orders/{order_id}`. The API exposes `/health`, `/orders`, `/orders/{order_id}/courier`, and `/graphql`.
