#!/bin/bash
# init-databases.sh — creates all required databases in a single PostgreSQL instance
# Used by docker-compose.unified.yml and docker-compose.light.yml as an init script.
# Runs automatically on first container start (when the data volume is empty).
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE auth_db'      WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'auth_db')\gexec
    SELECT 'CREATE DATABASE purchase_db'  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'purchase_db')\gexec
    SELECT 'CREATE DATABASE payment_db'   WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'payment_db')\gexec
    SELECT 'CREATE DATABASE chat_db'      WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'chat_db')\gexec
    SELECT 'CREATE DATABASE reputation_db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'reputation_db')\gexec
EOSQL

echo "All databases created successfully."
