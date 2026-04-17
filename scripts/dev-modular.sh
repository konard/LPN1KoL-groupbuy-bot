#!/usr/bin/env bash
# Local development startup (no Docker required).
# Runs all 4 services with hot-reload. Requires:
#   - Python 3.11+  (backend, socket, admin)
#   - Node.js 20+   (frontend)
#   - SQLite is used by default (no Postgres needed locally)
#
# Usage:
#   cp .env.modular.example .env.modular
#   # Edit .env.modular if needed
#   chmod +x scripts/dev-modular.sh
#   ./scripts/dev-modular.sh

set -e

# Load env file if present
if [ -f .env.modular ]; then
  export $(grep -v '^#' .env.modular | xargs)
fi

export SECRET_KEY="${SECRET_KEY:-dev-secret-key}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///./dev.db}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:5173,http://localhost:5174}"
export BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
export VITE_BACKEND_URL="${VITE_BACKEND_URL:-http://localhost:8000}"
export VITE_SOCKET_URL="${VITE_SOCKET_URL:-ws://localhost:8001}"

PIDS=()
cleanup() {
  echo ""
  echo "Stopping all services..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  exit 0
}
trap cleanup SIGINT SIGTERM

echo "Installing Python dependencies..."

(cd backend && python -m venv .venv 2>/dev/null || true && \
  .venv/bin/pip install -q -r requirements.txt)

(cd socket && python -m venv .venv 2>/dev/null || true && \
  .venv/bin/pip install -q -r requirements.txt)

(cd admin && python -m venv .venv 2>/dev/null || true && \
  .venv/bin/pip install -q -r requirements.txt)

echo "Installing frontend dependencies..."
(cd frontend && npm install --silent)

echo ""
echo "Starting services:"
echo "  Backend  → http://localhost:8000   (API docs: http://localhost:8000/docs)"
echo "  Socket   → ws://localhost:8001     (http://localhost:8001/docs)"
echo "  Admin    → http://localhost:8002"
echo "  Frontend → http://localhost:5173"
echo ""

# Backend
(cd backend && \
  DATABASE_URL="$DATABASE_URL" SECRET_KEY="$SECRET_KEY" CORS_ORIGINS="$CORS_ORIGINS" \
  .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload) &
PIDS+=($!)

sleep 1  # Give backend a moment to init the DB

# Socket
(cd socket && \
  SECRET_KEY="$SECRET_KEY" BACKEND_URL="$BACKEND_URL" CORS_ORIGINS="$CORS_ORIGINS" \
  .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8001 --reload) &
PIDS+=($!)

# Admin
(cd admin && \
  BACKEND_URL="$BACKEND_URL" \
  .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8002 --reload) &
PIDS+=($!)

# Frontend
(cd frontend && \
  VITE_BACKEND_URL="$VITE_BACKEND_URL" VITE_SOCKET_URL="$VITE_SOCKET_URL" \
  npm run dev) &
PIDS+=($!)

echo "All services started. Press Ctrl+C to stop."
wait
