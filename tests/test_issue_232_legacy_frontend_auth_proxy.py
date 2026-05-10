"""Regression coverage for issue #232: "Cannot POST /auth/register".

Issues #228 and #230 fixed the unified compose stack (``frontend-react`` →
gateway → auth-service).  Issue #232 reports the same browser error coming
from the *other* compose stacks that build the legacy ``./frontend``
directory: ``docker-compose.4services.yml`` and ``docker-compose.modular.yml``.

Root cause analysis (legacy frontend):
  1. ``frontend/src/api.js`` calls ``POST /auth/register`` (and ``/auth/login``)
     directly — the bundled SPA expects a proxy at ``/auth/*``.

  2. ``frontend/nginx.conf`` only had ``location /api/`` plus the SPA
     ``try_files`` fallback. Unproxied ``/auth/register`` fell through to the
     fallback which serves ``index.html`` for any URI; on POST that returns
     405/200 garbage and breaks registration.

  3. ``frontend/vite.config.js`` only proxied ``/api``; the dev server has no
     POST handler, so unproxied ``/auth/register`` returned the literal
     "Cannot POST /auth/register" Express-style 404 message.

The fix mirrors what was done for ``frontend-react``: add a ``/auth/`` proxy
in BOTH the production ``nginx.conf`` and the dev ``vite.config.js`` so the
legacy SPA's POST requests reach the backend.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
LEGACY_NGINX = ROOT / "frontend" / "nginx.conf"
LEGACY_VITE = ROOT / "frontend" / "vite.config.js"
LEGACY_API = ROOT / "frontend" / "src" / "api.js"


# ── Confirm the SPA actually posts to /auth/register ──────────────────────────


def test_legacy_frontend_api_posts_to_auth_register():
    """The legacy SPA's api.js must keep calling /auth/register; this test
    documents the exact URL that nginx and vite have to proxy."""
    src = LEGACY_API.read_text()
    assert "'/auth/register'" in src or '"/auth/register"' in src, (
        "frontend/src/api.js no longer posts to /auth/register. "
        "If you removed that endpoint, also remove the /auth/ proxy from "
        "frontend/nginx.conf and frontend/vite.config.js."
    )


# ── Layer 1: Legacy nginx production build ────────────────────────────────────


class TestLegacyFrontendNginxAuthProxy:
    """frontend/nginx.conf must proxy /auth/* before the SPA fallback."""

    def _conf(self) -> str:
        return LEGACY_NGINX.read_text()

    def test_auth_location_block_exists(self):
        conf = self._conf()
        assert "location /auth/" in conf, (
            "frontend/nginx.conf is missing 'location /auth/'. "
            "POST /auth/register from the bundled SPA would otherwise fall "
            "through to the SPA try_files rule, which cannot handle POST — "
            "resulting in 'Cannot POST /auth/register' in the browser."
        )

    def test_auth_location_proxies_to_backend(self):
        conf = self._conf()
        match = re.search(
            r"location /auth/\s*\{([^}]+)\}",
            conf,
            re.DOTALL,
        )
        assert match is not None, (
            "frontend/nginx.conf has no 'location /auth/' block."
        )
        block = match.group(1)
        assert "proxy_pass" in block, (
            "The 'location /auth/' block in frontend/nginx.conf must proxy "
            "to the backend. Found: " + block.strip()
        )
        assert "$backend_upstream" in block or "backend-api" in block, (
            "The 'location /auth/' block in frontend/nginx.conf must point "
            "at the backend upstream (backend-api). Found: " + block.strip()
        )

    def test_auth_location_appears_before_spa_fallback(self):
        conf = self._conf()
        auth_pos = conf.find("location /auth/")
        spa_pos = conf.find("try_files")
        assert auth_pos != -1, "frontend/nginx.conf is missing 'location /auth/'."
        assert spa_pos != -1, "frontend/nginx.conf is missing the SPA try_files fallback."
        assert auth_pos < spa_pos, (
            "In frontend/nginx.conf, 'location /auth/' must appear before "
            "the SPA try_files fallback so POST /auth/register is proxied to "
            "the backend rather than served as index.html."
        )


# ── Layer 2: Legacy Vite dev-server ───────────────────────────────────────────


class TestLegacyFrontendViteAuthProxy:
    """frontend/vite.config.js must forward /auth/* to the backend."""

    def _conf(self) -> str:
        return LEGACY_VITE.read_text()

    def test_auth_proxy_entry_exists(self):
        conf = self._conf()
        assert "'/auth'" in conf or '"/auth"' in conf, (
            "frontend/vite.config.js is missing a proxy entry for '/auth'. "
            "POST /auth/register hits the Vite dev server which cannot handle "
            "POST routes, returning 'Cannot POST /auth/register'."
        )

    def test_auth_proxy_targets_backend(self):
        conf = self._conf()
        match = re.search(
            r"['\"]\/auth['\"]\s*:\s*\{([^}]+)\}",
            conf,
            re.DOTALL,
        )
        assert match is not None, (
            "frontend/vite.config.js has no '/auth' proxy block."
        )
        block = match.group(1)
        # Allow either explicit backend URL or the VITE_BACKEND_URL fallback
        # which defaults to localhost:8000 (the Python core API).
        assert "VITE_BACKEND_URL" in block or "localhost:8000" in block, (
            "The '/auth' proxy in frontend/vite.config.js must target the "
            "backend (process.env.VITE_BACKEND_URL || 'http://localhost:8000'). "
            "Found: " + block.strip()
        )

    def test_auth_proxy_does_not_strip_path_prefix(self):
        """A rewrite that strips /auth would deliver /register to the backend
        instead of /auth/register, breaking the contract."""
        conf = self._conf()
        match = re.search(
            r"['\"]\/auth['\"]\s*:\s*\{([^}]+)\}",
            conf,
            re.DOTALL,
        )
        if match is None:
            return  # caught by test_auth_proxy_entry_exists
        block = match.group(1)
        if "rewrite" not in block:
            return  # no rewrite is the safe default
        bad_strip = re.search(r"replace\s*\(.*?\\\/auth.*?,\s*['\"][\s]*['\"]", block)
        assert bad_strip is None, (
            "The '/auth' proxy rewrite in frontend/vite.config.js strips the "
            "/auth prefix. The backend expects the full URI (e.g. "
            "/auth/register). Remove the rewrite or keep /auth in it."
        )

    def test_auth_proxy_appears_before_api_proxy(self):
        """Specificity-first ordering: '/auth' before '/api' so the more
        specific path wins (matches nginx convention)."""
        conf = self._conf()
        auth_pos = conf.find("'/auth'")
        if auth_pos == -1:
            auth_pos = conf.find('"/auth"')
        api_pos = conf.find("'/api'")
        if api_pos == -1:
            api_pos = conf.find('"/api"')
        if auth_pos == -1 or api_pos == -1:
            return  # other tests will catch missing entries
        assert auth_pos < api_pos, (
            "In frontend/vite.config.js, the '/auth' proxy entry should "
            "appear before the generic '/api' entry to follow specificity-"
            "first ordering."
        )
