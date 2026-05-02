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
