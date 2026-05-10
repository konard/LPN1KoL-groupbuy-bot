"""Regression coverage for issue #230: "Cannot POST /auth/register" not fixed.

Issue #228 described that POST /auth/register from the browser returned
"Cannot POST /auth/register".  Issue #230 confirms the fix is still incomplete.

Root cause analysis:
  1. Development mode (Vite dev server): ``vite.config.js`` was missing a proxy
     rule for ``/auth/*`` requests. The Vite server does not handle POST routes,
     so unproxied ``/auth/register`` fell through and returned "Cannot POST".

  2. The gateway's ``legacy_auth_proxy`` handles ``/auth/{path}`` but only if
     those paths are listed in ``PUBLIC_PATHS`` (no JWT required). Registration
     and login must be public so unauthenticated users can call them.

  3. The ``frontend-react`` nginx container must proxy ``/auth/*`` to the
     gateway, otherwise direct container access skips the gateway entirely.

Verification: all three layers are tested here.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
VITE_CONFIG = ROOT / "frontend-react" / "vite.config.js"
FRONTEND_NGINX = ROOT / "frontend-react" / "nginx.conf"
GATEWAY_MAIN = ROOT / "services" / "gateway" / "main.py"


def _exact_auth_block(content: str) -> re.Match | None:
    """Return the proxy block for the exact '/auth' key (not '/api/v1/auth')."""
    return re.search(r"['\"]\/auth['\"][\s]*:\s*\{([^}]+)\}", content, re.DOTALL)


# ── Layer 1: Vite dev-server proxy ────────────────────────────────────────────


class TestViteDevServerAuthProxy:
    """Vite proxy must forward /auth/* to the gateway so POST requests work."""

    def test_auth_proxy_entry_exists(self):
        content = VITE_CONFIG.read_text()
        assert "'/auth'" in content or '"/auth"' in content, (
            "vite.config.js is missing a proxy entry for '/auth'. "
            "POST /auth/register hits the Vite dev server directly which cannot "
            "handle POST routes, causing 'Cannot POST /auth/register'."
        )

    def test_auth_proxy_target_is_gateway(self):
        content = VITE_CONFIG.read_text()
        m = _exact_auth_block(content)
        assert m is not None, (
            "vite.config.js has no '/auth' proxy block. "
            "Add one to forward /auth/* to the gateway."
        )
        block_text = m.group(1)
        assert "localhost:3001" in block_text or "gateway" in block_text, (
            "The '/auth' proxy in vite.config.js should target the gateway "
            "(http://localhost:3001 in dev). Found: " + block_text.strip()
        )

    def test_auth_proxy_does_not_strip_path_prefix(self):
        """
        The '/auth' proxy must NOT rewrite the /auth prefix away. The gateway
        route is /auth/{path:path} and expects the full URI, e.g. /auth/register.
        A rewrite stripping '/auth' would deliver '/register' to the wrong path.
        """
        content = VITE_CONFIG.read_text()
        m = _exact_auth_block(content)
        if m is None:
            return  # caught by test_auth_proxy_entry_exists
        block_text = m.group(1)
        if "rewrite" not in block_text:
            return  # no rewrite: path is forwarded unchanged, which is correct
        # A rewrite is only acceptable if it does not strip the /auth prefix.
        # Wrong pattern: path.replace(/^\/auth/, '')
        # That would turn /auth/register → /register (missing the /auth segment).
        bad_strip = re.search(r"replace\s*\(.*?\\\/auth.*?,\s*['\"][\s]*['\"]", block_text)
        assert bad_strip is None, (
            "The '/auth' proxy rewrite in vite.config.js strips the /auth "
            "prefix. The gateway route is /auth/{path:path} and must receive "
            "the full URI. Remove the rewrite or keep /auth in the replacement."
        )

    def test_auth_proxy_is_ordered_before_api_proxy(self):
        """
        The '/auth' entry should come before the generic '/api' entry so
        specificity-first ordering matches nginx convention.
        """
        content = VITE_CONFIG.read_text()
        auth_pos = content.find("'/auth'")
        if auth_pos == -1:
            auth_pos = content.find('"/auth"')
        api_pos = content.find("'/api'")
        if api_pos == -1:
            api_pos = content.find('"/api"')
        if auth_pos == -1 or api_pos == -1:
            return  # other tests will catch missing entries
        assert auth_pos < api_pos, (
            "In vite.config.js, the '/auth' proxy entry should appear before "
            "the generic '/api' entry to follow the same specificity-first "
            "ordering used in nginx."
        )


# ── Layer 2: Gateway public paths ─────────────────────────────────────────────


class TestGatewayLegacyAuthPublicPaths:
    """Gateway must treat /auth/register (and related OTP paths) as public."""

    def _gateway_source(self):
        return GATEWAY_MAIN.read_text()

    def test_legacy_auth_route_exists(self):
        src = self._gateway_source()
        assert '"/auth/{path:path}"' in src, (
            "gateway/main.py is missing the legacy /auth/{path:path} route. "
            "Requests from nginx 'location /auth/' will get 404."
        )

    def test_register_is_in_public_paths(self):
        src = self._gateway_source()
        assert '"auth/register"' in src or "'auth/register'" in src, (
            "gateway/main.py PUBLIC_PATHS does not include 'auth/register'. "
            "POST /auth/register will be rejected with 401 Unauthorized "
            "because unauthenticated users cannot yet have a token."
        )

    def test_login_is_in_public_paths(self):
        src = self._gateway_source()
        assert '"auth/login"' in src or "'auth/login'" in src, (
            "gateway/main.py PUBLIC_PATHS does not include 'auth/login'. "
            "POST /auth/login will be rejected with 401."
        )

    def test_register_confirm_is_in_public_paths(self):
        src = self._gateway_source()
        assert '"auth/register/confirm"' in src or "'auth/register/confirm'" in src, (
            "gateway/main.py PUBLIC_PATHS does not include 'auth/register/confirm'. "
            "OTP confirmation step will fail with 401."
        )

    def test_legacy_auth_proxy_proxies_to_auth_service(self):
        src = self._gateway_source()
        assert '_proxy_request(request, "auth", path)' in src or \
               "_proxy_request(request, 'auth', path)" in src, (
            "gateway/main.py legacy_auth_proxy must call "
            "_proxy_request(request, 'auth', path) to forward to auth-service."
        )


# ── Layer 3: Frontend-react nginx container ───────────────────────────────────


class TestFrontendReactNginxAuthProxy:
    """frontend-react nginx must proxy /auth/* to gateway, not serve as SPA."""

    def _nginx_conf(self):
        return FRONTEND_NGINX.read_text()

    def test_auth_location_block_exists(self):
        conf = self._nginx_conf()
        assert "location /auth/" in conf, (
            "frontend-react/nginx.conf is missing 'location /auth/'. "
            "When the React container is accessed directly, POST /auth/register "
            "falls through to the SPA try_files rule which cannot handle POST "
            "requests — causing 'Cannot POST /auth/register'."
        )

    def test_auth_location_proxies_to_gateway(self):
        conf = self._nginx_conf()
        auth_block = re.search(
            r"location /auth/\s*\{([^}]+)\}",
            conf,
            re.DOTALL,
        )
        assert auth_block is not None, (
            "frontend-react/nginx.conf has no 'location /auth/' block."
        )
        block = auth_block.group(1)
        assert "proxy_pass" in block, (
            "The 'location /auth/' block in frontend-react/nginx.conf must "
            "contain a proxy_pass directive to forward requests to the gateway."
        )
        assert "gateway" in block, (
            "The 'location /auth/' block in frontend-react/nginx.conf must "
            "proxy to the gateway upstream. "
            "Found block: " + block.strip()
        )

    def test_auth_location_before_spa_fallback(self):
        """
        The /auth/ location must appear BEFORE the SPA try_files fallback so
        nginx does not serve index.html for POST /auth/register.
        """
        conf = self._nginx_conf()
        auth_pos = conf.find("location /auth/")
        spa_fallback_pos = conf.find("try_files")
        assert auth_pos != -1, (
            "frontend-react/nginx.conf is missing 'location /auth/'."
        )
        assert spa_fallback_pos != -1, (
            "frontend-react/nginx.conf is missing the SPA try_files fallback."
        )
        assert auth_pos < spa_fallback_pos, (
            "In frontend-react/nginx.conf, 'location /auth/' must appear "
            "before the SPA try_files fallback so nginx proxies /auth/register "
            "to the gateway rather than serving index.html."
        )
