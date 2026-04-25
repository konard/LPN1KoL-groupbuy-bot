# EventFlow Backend

FastAPI ticketing demo with PostgreSQL, Redis caching, RabbitMQ/Celery workers, JWT roles, Stripe mock payments, health checks, rate limits, and Alembic migrations.

Run: `cp .env.example .env && docker compose up --build`.
Migrate: `alembic upgrade head`.
Tests: `python -m pytest`.

Use `POST /auth/token` to issue a demo organizer or user token. The API exposes `/health`, paginated `GET /events?page=&size=&date_from=`, ticket purchase, task status, and ticket return endpoints.
