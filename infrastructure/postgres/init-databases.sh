#!/bin/bash
# Creates additional databases required by microservices on the same PostgreSQL instance.
# This script is run automatically by the official postgres image when placed in
# /docker-entrypoint-initdb.d/.  It runs as the postgres superuser.

set -e

DB_USER="${POSTGRES_USER:-postgres}"

psql -v ON_ERROR_STOP=1 --username "$DB_USER" <<-EOSQL
    SELECT 'CREATE DATABASE auth_db'       WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'auth_db')\gexec
    SELECT 'CREATE DATABASE purchase_db'   WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'purchase_db')\gexec
    SELECT 'CREATE DATABASE payment_db'    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'payment_db')\gexec
    SELECT 'CREATE DATABASE chat_db'       WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'chat_db')\gexec
    SELECT 'CREATE DATABASE reputation_db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'reputation_db')\gexec
EOSQL

echo "All databases created successfully."
