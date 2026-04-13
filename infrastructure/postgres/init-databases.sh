#!/bin/bash
# Creates additional databases required by microservices on the same PostgreSQL instance.
# This script is run automatically by the official postgres image when placed in
# /docker-entrypoint-initdb.d/.  It runs as the postgres superuser.

set -e

DB_USER="${POSTGRES_USER:-postgres}"

# Create auth_db for the auth microservice
psql -v ON_ERROR_STOP=1 --username "$DB_USER" <<-EOSQL
    SELECT 'CREATE DATABASE auth_db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'auth_db')\gexec
EOSQL
