#!/bin/bash
# reset-kafka.sh — wipe Kafka and Zookeeper volumes to fix InconsistentClusterIdException
#
# Use this when Kafka fails to start with:
#   kafka.common.InconsistentClusterIdException: The Cluster ID ... doesn't match stored clusterId
#
# This removes all Kafka and Zookeeper data (topics, offsets, consumer groups).
# After running, restart with: docker compose -f docker-compose.monolith.yml up -d

set -e

COMPOSE_FILE="${1:-docker-compose.monolith.yml}"

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "ERROR: compose file '$COMPOSE_FILE' not found."
  echo "Usage: bash scripts/reset-kafka.sh [docker-compose-file]"
  exit 1
fi

echo "==> Stopping Kafka and Zookeeper..."
docker compose -f "$COMPOSE_FILE" stop kafka kafka-ui zookeeper 2>/dev/null || true

echo "==> Removing Kafka and Zookeeper volumes..."
docker compose -f "$COMPOSE_FILE" rm -f kafka kafka-ui zookeeper 2>/dev/null || true
docker volume rm "$(docker compose -f "$COMPOSE_FILE" config --volumes | grep -E 'kafka_data|zookeeper_data|zookeeper_log_data' | xargs -I{} sh -c 'basename $(pwd)_{}' 2>/dev/null)" 2>/dev/null || \
  docker volume ls -q | grep -E 'kafka_data|zookeeper_data|zookeeper_log_data' | xargs docker volume rm 2>/dev/null || true

echo "==> Done. Restart with:"
echo "    docker compose -f $COMPOSE_FILE up -d"
