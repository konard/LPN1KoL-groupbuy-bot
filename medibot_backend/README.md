# MediBot Backend

Telegram appointment demo with PostgreSQL, Redis state, RabbitMQ/Celery reminders, ConversationHandler flows, inline clinic and time buttons, Google Calendar mock, structured logs, rate limits, and Alembic migrations.

Run: `cp .env.example .env && docker compose up --build`.
Migrate: `alembic upgrade head`.
Tests: `python -m pytest`.

Use `/start`, `/clinics`, `/appointment`, and `/appointments` in Telegram. Appointment creation schedules `send_appointment_reminder` with an ETA one hour before the selected time.
