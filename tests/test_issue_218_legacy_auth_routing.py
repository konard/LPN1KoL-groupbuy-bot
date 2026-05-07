"""Regression coverage for issue #218: Docker must route /auth/* login calls."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
GATEWAY_DIR = ROOT / "services" / "gateway"
NGINX_API_CONF = ROOT / "infrastructure" / "nginx" / "nginx-api.conf"
FRONTEND_NGINX_CONF = ROOT / "frontend-react" / "nginx.conf"


def test_unified_nginx_routes_legacy_auth_to_gateway():
    conf = NGINX_API_CONF.read_text()

    assert conf.count("location /auth/") >= 2, (
        "nginx-api.conf must route legacy /auth/* requests in both HTTP and HTTPS "
        "server blocks so Docker traffic does not fall through to the frontend."
    )
    assert "proxy_pass http://gateway;" in conf
    assert "proxy_pass http://frontend;" in conf


def test_frontend_container_routes_legacy_auth_to_gateway():
    conf = FRONTEND_NGINX_CONF.read_text()

    assert "location /auth/" in conf, (
        "frontend-react nginx must proxy legacy /auth/* requests to the gateway "
        "when the frontend container is accessed directly."
    )
    assert "proxy_pass $gateway_upstream;" in conf


def test_gateway_exposes_legacy_auth_alias_without_compose_only_dependencies():
    source = (GATEWAY_DIR / "main.py").read_text()

    assert '"/auth/{path:path}"' in source
    assert "legacy_auth_proxy" in source
    assert 'return await _proxy_request(request, "auth", path)' in source
