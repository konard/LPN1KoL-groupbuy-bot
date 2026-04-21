"""
Tests for issue #63 fix:

  Frontend (user lk + admin panel) cannot reach backend when the app is
  launched via ``docker-compose.monolith.yml``.  Direct requests to the
  backend's Swagger UI work; only frontend requests fail.  Example symptom:
  ``/api/procurements/`` is not in Swagger but the frontend actively calls
  it.

  Root cause: the React client uses legacy, domain-style URLs
  (``/api/procurements/*``, ``/api/users/*``, ``/api/chat/*``,
  ``/api/payments/*``, ``/api/v1/auth/*``) while ``backend-monolith``'s
  FastAPI routers mount prefixes that differ from each of those shapes
  (``/purchases``, ``/api/users``, ``/api/v1/chat``, ``/wallets``,
  ``/auth``).  The previous nginx had a single strip-``/api``/-preserve-
  ``/api/v1`` pair that worked only for a subset of endpoints, leaving
  several 404/500 holes.

  Fix: expand ``frontend-react/nginx.conf`` with explicit location blocks
  that bridge each client path to the correct backend router prefix.
"""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
NGINX_CONF = os.path.join(ROOT, "frontend-react", "nginx.conf")
BACKEND_MAIN = os.path.join(ROOT, "backend-monolith", "app", "main.py")


def read(path):
    with open(path) as f:
        return f.read()


def _parse_nginx_api_rules(conf_text):
    """Return list of {prefix, rewrite_pattern, rewrite_replacement,
    upstream_var} for every ``location /api…`` block, sorted by prefix
    length descending (longest-prefix wins in nginx)."""
    blocks = re.findall(
        r"location\s+(\S+)\s*\{([^}]*)\}",
        conf_text,
        re.DOTALL,
    )
    rules = []
    for prefix, body in blocks:
        if not prefix.startswith("/api"):
            continue
        rw = re.search(r"rewrite\s+(\S+)\s+(\S+)\s+break", body)
        upstream_m = re.search(r"proxy_pass\s+\$(\w+)", body)
        rules.append(
            {
                "prefix": prefix,
                "rewrite_pattern": rw.group(1) if rw else None,
                "rewrite_replacement": rw.group(2) if rw else None,
                "upstream_var": upstream_m.group(1) if upstream_m else None,
            }
        )
    rules.sort(key=lambda r: len(r["prefix"]), reverse=True)
    return rules


def _route(path, rules):
    """Simulate nginx's longest-prefix match + optional rewrite."""
    for r in rules:
        if path.startswith(r["prefix"]):
            if r["rewrite_pattern"]:
                replacement = re.sub(r"\$(\d+)", r"\\\1", r["rewrite_replacement"])
                new_path = re.sub(r["rewrite_pattern"], replacement, path)
            else:
                new_path = path
            return r["upstream_var"], new_path
    return None, path


class TestNginxMappingForIssue63:
    """Every legacy frontend path must be bridged to the backend's actual
    router prefix."""

    def setup_method(self):
        self.rules = _parse_nginx_api_rules(read(NGINX_CONF))

    def test_procurements_rewrites_to_purchases(self):
        upstream, path = _route("/api/procurements/?status=active", self.rules)
        assert upstream == "monolith_upstream"
        assert path == "/purchases/?status=active"

    def test_procurements_action_endpoint(self):
        upstream, path = _route("/api/procurements/abc/join/", self.rules)
        assert upstream == "monolith_upstream"
        assert path == "/purchases/abc/join/"

    def test_users_prefix_is_preserved(self):
        """users_router is mounted at /api/users, so nginx must NOT strip
        the /api prefix here."""
        upstream, path = _route("/api/users/123/balance/", self.rules)
        assert upstream == "monolith_upstream"
        assert path == "/api/users/123/balance/"

    def test_v1_auth_strips_api_v1(self):
        """auth_router is mounted at /auth (no /api/v1); nginx must strip."""
        upstream, path = _route("/api/v1/auth/login", self.rules)
        assert upstream == "monolith_upstream"
        assert path == "/auth/login"

    def test_v1_auth_refresh(self):
        upstream, path = _route("/api/v1/auth/refresh", self.rules)
        assert upstream == "monolith_upstream"
        assert path == "/auth/refresh"

    def test_v1_chat_media_is_preserved(self):
        upstream, path = _route("/api/v1/chat/media/upload", self.rules)
        assert upstream == "monolith_upstream"
        assert path == "/api/v1/chat/media/upload"

    def test_legacy_chat_rewrites_to_v1(self):
        upstream, path = _route("/api/chat/messages/?procurement=1", self.rules)
        assert upstream == "monolith_upstream"
        assert path == "/api/v1/chat/messages/?procurement=1"

    def test_legacy_payments_rewrites_to_wallets(self):
        upstream, path = _route("/api/payments/pay1/status/", self.rules)
        assert upstream == "monolith_upstream"
        assert path == "/wallets/pay1/status/"

    def test_reputation_still_strips_api(self):
        upstream, path = _route("/api/reputation/foo", self.rules)
        assert upstream == "monolith_upstream"
        assert path == "/reputation/foo"

    def test_escrow_still_strips_api(self):
        upstream, path = _route("/api/escrow/bar", self.rules)
        assert upstream == "monolith_upstream"
        assert path == "/escrow/bar"

    def test_admin_api_goes_to_admin_backend(self):
        upstream, path = _route("/api/admin/health", self.rules)
        assert upstream == "admin_upstream"
        assert path == "/api/admin/health"

    def test_categories_preserved(self):
        """categories_router uses prefix /api/v1/categories."""
        upstream, path = _route("/api/v1/categories", self.rules)
        assert upstream == "monolith_upstream"
        assert path == "/api/v1/categories"

    def test_authorization_header_forwarded_everywhere(self):
        """Every /api location must forward the Authorization header so
        JWT auth works.  Without this admins and users see 401s even
        though the token is valid."""
        conf = read(NGINX_CONF)
        blocks = re.findall(
            r"location\s+(/api\S*)\s*\{([^}]*)\}",
            conf,
            re.DOTALL,
        )
        missing = [p for p, body in blocks if "Authorization" not in body]
        assert not missing, (
            f"location blocks without Authorization header forwarding: "
            f"{missing}"
        )


class TestCorsConfigForIssue63:
    """CORS spec forbids ``Access-Control-Allow-Origin: *`` with
    credentials.  The backend must not send both together or browsers
    will drop the response."""

    def test_wildcard_origin_disables_credentials(self):
        content = read(BACKEND_MAIN)
        # Accept any formulation that conditions allow_credentials on the
        # origins not being ["*"].
        has_guard = (
            re.search(r"allow_credentials\s*=\s*[^\n]*cors_origins\s*!=\s*\[\"\*\"\]", content)
            or re.search(
                r"allow_credentials\s*=\s*(?:True|False)\s*\n?\s*if\s+cors_origins",
                content,
            )
            or (
                "allow_credentials=allow_credentials" in content
                and "allow_credentials = cors_origins != [\"*\"]" in content
            )
        )
        assert has_guard, (
            "backend-monolith/app/main.py still passes a hard-coded "
            "allow_credentials=True alongside a potentially wildcard "
            "allow_origins, which browsers reject."
        )


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
