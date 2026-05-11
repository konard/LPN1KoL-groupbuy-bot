#!/bin/sh
# entrypoint.sh — Django admin container startup script
#
# Runs Django migrations and, when DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_PASSWORD
# are set, automatically creates a superuser on first start (idempotent — skipped if the
# user already exists).
#
# Required environment variables:
#   DATABASE_URL           – PostgreSQL connection string
#   SECRET_KEY             – Django secret key
#
# Optional environment variables (auto-superuser creation):
#   DJANGO_SUPERUSER_USERNAME  – admin username  (default: admin)
#   DJANGO_SUPERUSER_PASSWORD  – admin password  (required for auto-creation)
#   DJANGO_SUPERUSER_EMAIL     – admin email     (default: admin@localhost)

set -e

# Ensure the django_admin_db database exists before attempting migrations.
# init-databases.sh only runs on the very first postgres volume creation, so on
# existing deployments where the volume was provisioned without this database the
# container would crash at the migration step.  Running a CREATE DATABASE …
# idempotently here guarantees the database is always present.
if [ -n "${DATABASE_URL:-}" ]; then
    # Extract host, port, user, password and database from DATABASE_URL.
    # Expected format: postgresql://user:pass@host:port/dbname
    DB_URL_STRIPPED="${DATABASE_URL#postgresql://}"
    DB_USERPASS="${DB_URL_STRIPPED%%@*}"
    DB_HOSTPORTDB="${DB_URL_STRIPPED#*@}"
    DB_USER_ONLY="${DB_USERPASS%%:*}"
    DB_PASS_ONLY="${DB_USERPASS#*:}"
    DB_HOST="${DB_HOSTPORTDB%%:*}"
    DB_PORT_DB="${DB_HOSTPORTDB#*:}"
    DB_PORT="${DB_PORT_DB%%/*}"
    DB_NAME="${DB_PORT_DB#*/}"

    echo "==> Ensuring database '${DB_NAME}' exists on ${DB_HOST}:${DB_PORT}..."
    PGPASSWORD="${DB_PASS_ONLY}" psql \
        -h "${DB_HOST}" -p "${DB_PORT}" \
        -U "${DB_USER_ONLY}" \
        -d postgres \
        -tc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" \
        | grep -q 1 || \
    PGPASSWORD="${DB_PASS_ONLY}" psql \
        -h "${DB_HOST}" -p "${DB_PORT}" \
        -U "${DB_USER_ONLY}" \
        -d postgres \
        -c "CREATE DATABASE \"${DB_NAME}\""
    echo "==> Database '${DB_NAME}' is ready."
fi

echo "==> Generating any pending model migrations..."
python manage.py makemigrations --noinput

echo "==> Running Django migrations..."
# --fake-initial records already-applied initial migrations as done without
# re-executing them.  This prevents "relation '...' already exists" crashes
# when the container restarts against a database that was initialised during
# a previous run (issue #182).
python manage.py migrate --noinput --fake-initial

echo "==> Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "==> Loading initial data fixtures..."
python manage.py loaddata initial_categories --app procurements 2>/dev/null && \
    echo "    Categories loaded." || echo "    Categories already loaded or fixture skipped."

# Auto-create superuser when credentials are provided via environment variables.
# Uses django.contrib.auth.models.User explicitly — the admin panel authenticates
# against Django's built-in auth system, not the custom users.User model.
if [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    SUPERUSER_USERNAME="${DJANGO_SUPERUSER_USERNAME:-admin}"
    SUPERUSER_EMAIL="${DJANGO_SUPERUSER_EMAIL:-admin@localhost}"

    echo "==> Ensuring superuser '${SUPERUSER_USERNAME}' exists..."
    python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='${SUPERUSER_USERNAME}').exists():
    User.objects.create_superuser(
        username='${SUPERUSER_USERNAME}',
        email='${SUPERUSER_EMAIL}',
        password='${DJANGO_SUPERUSER_PASSWORD}',
    )
    print('Superuser created: ${SUPERUSER_USERNAME}')
else:
    print('Superuser already exists: ${SUPERUSER_USERNAME}')
"
else
    echo "==> DJANGO_SUPERUSER_PASSWORD not set — skipping auto-superuser creation."
    echo "    To create a superuser manually, run:"
    echo "      bash scripts/create-superuser.sh"
    echo "    Or set DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_PASSWORD / DJANGO_SUPERUSER_EMAIL"
    echo "    in your .env file and restart the django-admin container."
fi

echo "==> Starting Gunicorn..."
# GUNICORN_WORKERS defaults to 2 to stay within memory limits on 3GB hosts.
# Set GUNICORN_WORKERS in .env to override (e.g. 4 for hosts with more RAM).
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers "${GUNICORN_WORKERS:-2}"
