#!/bin/bash
# reset-kafka.sh — wipe Kafka and Zookeeper volumes to fix InconsistentClusterIdException
#
# Use this when Kafka fails to start with:
#   kafka.common.InconsistentClusterIdException: The Cluster ID ... doesn't match stored clusterId
#
# Root cause: Zookeeper stores a cluster ID in its data volume. Kafka stores the
# same cluster ID in its own data volume (meta.properties). When one volume is
# wiped (e.g. docker compose down -v) but not the other, the IDs diverge and
# Kafka refuses to start.
#
# This script stops Kafka and Zookeeper, removes BOTH data volumes, then prompts
# you to restart. All Kafka topics, offsets, and consumer group state are lost.
#
# Usage:
#   bash scripts/reset-kafka.sh                           # uses docker-compose.yml
#   bash scripts/reset-kafka.sh docker-compose.light.yml  # specify compose file

set -e

COMPOSE_FILE="${1:-docker-compose.yml}"

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "ERROR: compose file '$COMPOSE_FILE' not found."
  echo "Usage: bash scripts/reset-kafka.sh [docker-compose-file]"
  exit 1
fi

echo "==> Stopping Kafka and Zookeeper..."
docker compose -f "$COMPOSE_FILE" stop kafka zookeeper 2>/dev/null || true
docker compose -f "$COMPOSE_FILE" stop kafka-ui 2>/dev/null || true

echo "==> Removing Kafka and Zookeeper containers..."
docker compose -f "$COMPOSE_FILE" rm -f kafka zookeeper 2>/dev/null || true
docker compose -f "$COMPOSE_FILE" rm -f kafka-ui 2>/dev/null || true

echo "==> Removing Kafka and Zookeeper volumes..."
# docker compose down --volumes scoped to specific services is not supported,
# so we derive the project-scoped volume names and remove them directly.
PROJECT_DIR="$(basename "$(cd "$(dirname "$COMPOSE_FILE")" && pwd)")"
PROJECT_NAME="$(echo "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-')"

for VOL_SUFFIX in kafka_data zookeeper_data zookeeper_log_data; do
  CANDIDATE="${PROJECT_NAME}_${VOL_SUFFIX}"
  if docker volume inspect "$CANDIDATE" >/dev/null 2>&1; then
    echo "    Removing volume: $CANDIDATE"
    docker volume rm "$CANDIDATE"
  else
    echo "    Volume not found (skipping): $CANDIDATE"
  fi
done

echo ""
echo "==> Done. Both Kafka and Zookeeper volumes have been wiped."
echo "    Restart with:"
echo "    docker compose -f $COMPOSE_FILE up -d"
