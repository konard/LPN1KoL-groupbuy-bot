#!/bin/sh
set -eu

: "${DB_HOST:=db}"
: "${DB_PORT:=5432}"
: "${DB_NAME:=groupbuy}"
: "${DB_USER:=groupbuy}"
: "${DB_PASSWORD:=groupbuy}"
: "${POOL_MODE:=transaction}"
: "${MAX_CLIENT_CONN:=10000}"
: "${DEFAULT_POOL_SIZE:=80}"
: "${RESERVE_POOL_SIZE:=20}"

cat > /etc/pgbouncer/pgbouncer.ini <<EOF
[databases]
${DB_NAME} = host=${DB_HOST} port=${DB_PORT} dbname=${DB_NAME} user=${DB_USER} password=${DB_PASSWORD}
* = host=${DB_HOST} port=${DB_PORT} user=${DB_USER} password=${DB_PASSWORD}

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = trust
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = ${POOL_MODE}
max_client_conn = ${MAX_CLIENT_CONN}
default_pool_size = ${DEFAULT_POOL_SIZE}
reserve_pool_size = ${RESERVE_POOL_SIZE}
server_reset_query = DISCARD ALL
ignore_startup_parameters = extra_float_digits
admin_users = ${DB_USER}
stats_users = ${DB_USER}
log_connections = 0
log_disconnections = 0
EOF

printf '"%s" ""\n' "${DB_USER}" > /etc/pgbouncer/userlist.txt
chown -R pgbouncer:pgbouncer /etc/pgbouncer /var/log/pgbouncer /var/run/pgbouncer

exec su-exec pgbouncer pgbouncer /etc/pgbouncer/pgbouncer.ini
