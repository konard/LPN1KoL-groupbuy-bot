"""Regression coverage for issue #220 frontend-to-backend auth routing.

The React bundles in this repository have used both `/api/v1/auth/*` and
legacy `/api/auth/*` URLs.  In the unified stack those POST requests must reach
the FastAPI gateway/auth-service instead of falling through to the static
frontend or the wrong backend, otherwise browsers surface "Cannot POST" style
errors.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
NGINX_API_CONF = ROOT / "infrastructure" / "nginx" / "nginx-api.conf"
FRONTEND_NGINX_CONF = ROOT / "frontend" / "nginx.conf"
GATEWAY_MAIN = ROOT / "services" / "gateway" / "main.py"
AUTH_APP = ROOT / "services" / "auth-service" / "app.py"
SERVICE_RUNTIME_FILES = [
    ROOT / "gateway" / "main.py",
    ROOT / "services" / "gateway" / "main.py",
    ROOT / "services" / "auth-service" / "app.py",
    ROOT / "services" / "purchase-service" / "app.py",
    ROOT / "services" / "payment-service" / "app.py",
    ROOT / "services" / "chat-service" / "app.py",
    ROOT / "services" / "notification-service" / "app.py",
    ROOT / "services" / "search-service" / "app.py",
    ROOT / "services" / "reputation-service" / "app.py",
    ROOT / "services" / "backend-monolith" / "app" / "main.py",
    ROOT / "services" / "shared-lib" / "groupbuy_shared" / "middleware.py",
]


def test_unified_edge_routes_legacy_api_auth_to_gateway():
    conf = NGINX_API_CONF.read_text()

    assert conf.count("location /api/auth/") >= 2, (
        "nginx-api.conf must route /api/auth/* in both HTTP and HTTPS blocks "
        "so legacy React auth POSTs do not fall through to /api/."
    )
    assert "rewrite ^/api/auth/(.*)$ /api/v1/auth/$1 break;" in conf
    assert "proxy_pass http://gateway;" in conf


def test_gateway_accepts_legacy_api_auth_alias_directly():
    source = GATEWAY_MAIN.read_text()

    assert '"/api/auth/{path:path}"' in source
    assert "legacy_api_auth_proxy" in source
    assert 'return await _proxy_request(request, "auth", path)' in source


def test_direct_frontend_container_proxies_api_post_requests():
    conf = FRONTEND_NGINX_CONF.read_text()

    assert "location /api/" in conf, (
        "frontend/nginx.conf must proxy /api/* when the React container is "
        "exposed directly, as in docker-compose.4services.yml."
    )
    assert "proxy_pass $backend_upstream;" in conf
    assert "try_files $uri $uri/ /index.html;" in conf


def test_wildcard_cors_does_not_enable_credentials_on_auth_path():
    gateway = GATEWAY_MAIN.read_text()
    auth = AUTH_APP.read_text()

    assert 'CORS_ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS' in gateway
    assert 'allow_credentials=CORS_ALLOW_CREDENTIALS' in gateway
    assert 'CORS_ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS' in auth
    assert 'allow_credentials=CORS_ALLOW_CREDENTIALS' in auth


def test_service_runtimes_do_not_force_credentials_with_wildcard_cors():
    offenders = []

    for path in SERVICE_RUNTIME_FILES:
        source = path.read_text()
        if "allow_credentials=True" in source or "allow_credentials = True" in source:
            offenders.append(path.relative_to(ROOT).as_posix())

    assert not offenders, (
        "Service CORS middleware must not force credentials on wildcard origins: "
        + ", ".join(offenders)
    )
