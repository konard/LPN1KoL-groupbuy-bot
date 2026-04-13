#!/bin/sh
# Ensure SSL certificates exist so nginx can start.
# If real certificates are not yet available, generate a temporary self-signed pair.
# This allows the HTTP server (port 80) to work immediately for IP-based access,
# while the HTTPS server (port 443) will use the self-signed cert until
# Let's Encrypt certificates are obtained via init-letsencrypt.sh.

SSL_DIR="/etc/nginx/ssl"
CERT="$SSL_DIR/fullchain.pem"
KEY="$SSL_DIR/privkey.pem"

if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
    echo "[nginx-entrypoint] SSL certificates not found. Generating temporary self-signed certificate..."
    mkdir -p "$SSL_DIR"
    apk add --no-cache openssl >/dev/null 2>&1 || true
    openssl req -x509 -nodes -days 365 \
        -newkey rsa:2048 \
        -keyout "$KEY" \
        -out "$CERT" \
        -subj "/CN=localhost" \
        2>/dev/null
    echo "[nginx-entrypoint] Temporary self-signed certificate created."
    echo "[nginx-entrypoint] Replace with real certificates using: bash scripts/init-letsencrypt.sh"
fi

echo "[nginx-entrypoint] Starting nginx..."
exec nginx -g "daemon off;"
