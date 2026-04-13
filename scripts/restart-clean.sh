#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# restart-clean.sh — Tear down the unified stack, optionally remove volumes,
#                    and bring it back up with real-time logs of problem services.
#
# Usage:
#   bash scripts/restart-clean.sh              # restart, keep volumes
#   bash scripts/restart-clean.sh --purge      # restart, remove ALL volumes
#   bash scripts/restart-clean.sh --logs-only  # show logs of problem services (no restart)
###############################################################################

COMPOSE_FILE="docker-compose.unified.yml"
PROBLEM_SERVICES="bot django-admin centrifugo websocket-server kafka zookeeper"

# ── Debug helpers ────────────────────────────────────────────────────────────
show_debug_logs() {
  echo ""
  echo "==> Debug logs for failed/problematic containers:"
  for svc in groupbuy-bot groupbuy-centrifugo groupbuy-django-admin groupbuy-zookeeper; do
    echo ""
    echo "--- docker logs $svc (last 50 lines) ---"
    docker logs --tail 50 "$svc" 2>&1 || echo "    (container $svc not found)"
  done
}

if [[ "${1:-}" == "--logs-only" ]]; then
  show_debug_logs
  exit 0
fi

# ── Teardown ─────────────────────────────────────────────────────────────────
echo "==> Stopping all services..."
if [[ "${1:-}" == "--purge" ]]; then
  echo "==> Removing named volumes (postgres_data, redis_data, kafka_data, zookeeper_data)..."
  docker compose -f "$COMPOSE_FILE" down --remove-orphans -v
else
  docker compose -f "$COMPOSE_FILE" down --remove-orphans
fi

# Remove any leftover "Created" (never-started) containers from a previous run.
CREATED=$(docker ps -a --filter status=created --format '{{.Names}}' 2>/dev/null || true)
if [[ -n "$CREATED" ]]; then
  echo "==> Removing leftover 'Created' containers: $CREATED"
  # shellcheck disable=SC2086
  docker rm $CREATED
fi

# ── Startup ───────────────────────────────────────────────────────────────────
echo "==> Starting all services..."
docker compose -f "$COMPOSE_FILE" up -d

echo ""
echo "==> Waiting 15 seconds for containers to initialise..."
sleep 15

echo ""
echo "==> Container status:"
docker compose -f "$COMPOSE_FILE" ps

# ── Debug output for problem services ────────────────────────────────────────
show_debug_logs

echo ""
echo "==> Tailing logs for previously-problematic services (Ctrl+C to stop)..."
docker compose -f "$COMPOSE_FILE" logs --tail 50 --follow $PROBLEM_SERVICES
