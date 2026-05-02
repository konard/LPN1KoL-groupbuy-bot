#!/bin/sh
set -e

echo "==> Running database migrations..."
for migration in /app/migrations/*.sql; do
  echo "Applying $migration..."
  psql "$DATABASE_URL" -f "$migration"
done
echo "==> Migrations complete. Starting application..."
exec node dist/main
