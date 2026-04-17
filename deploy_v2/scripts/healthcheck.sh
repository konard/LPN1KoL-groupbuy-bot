#!/bin/sh
# Check health of all services
set -e

echo "=== Backend ==="
curl -sf http://localhost/api/health || echo "FAIL"

echo ""
echo "=== Socket Service ==="
curl -sf http://localhost/socket/health || echo "FAIL"

echo ""
echo "=== Admin Panel ==="
curl -sf http://localhost/admin-panel/health || echo "FAIL"

echo ""
echo "=== Frontend ==="
curl -sf -o /dev/null -w "HTTP %{http_code}" http://localhost/ || echo "FAIL"
echo ""
