"""
Tests for issue #264 — three production problems on the unified stack.

1. **/admin-panel returns 404**.  nginx-api.conf had a prefix-only
   ``location /admin`` block that proxied to django-admin.  nginx prefix
   matches are greedy, so ``/admin-panel/foo`` also matched and was sent to
   django-admin, which has no such route.  Fix: split into ``location = /admin``
   (exact match) plus ``location /admin/`` (with trailing slash) so
   ``/admin-panel/*`` falls through to the React SPA via ``location /``.

2. **/api/users/{id}/... returns 404 in the Cabinet**.  After login,
   ``user.coreId`` was fetched via a fire-and-forget ``getUserByEmail`` call.
   If the user opened the Cabinet before that completed (or if the auth-service
   sync to core had failed silently during registration), Cabinet fell back to
   ``user.id`` — the auth-service UUID — and asked core for
   ``/api/users/{auth_uuid}/balance/`` which didn't exist.  Fix: in
   ``useStore.js`` the post-login and post-registration handlers now ``await``
   the by-email lookup, and ``Cabinet.jsx`` re-fetches the core record on
   demand instead of falling back to the auth UUID.

3. **Registration data loss**.  ``_sync_user_to_core`` in auth-service
   ``app.py`` swallowed every error from the core POST, so a transient core
   outage during registration produced an auth-service user with no matching
   core record — breaking every later ``/api/users/{id}/…`` call.  Fix:
   ``_sync_user_to_core`` now accepts ``raise_on_error=True`` and
   ``confirm_registration`` rolls back the auth row on sync failure so both
   sides stay consistent.  Default role changed from ``"user"`` to ``"buyer"``
   to align with the Cabinet's role-based UX.
"""

import os
import re

import pytest


ROOT = os.path.join(os.path.dirname(__file__), "..")

NGINX_API_CONF = os.path.join(ROOT, "infrastructure", "nginx", "nginx-api.conf")
AUTH_APP = os.path.join(ROOT, "services", "auth-service", "app.py")
STORE_JS = os.path.join(ROOT, "frontend-react", "src", "store", "useStore.js")
CABINET_JSX = os.path.join(ROOT, "frontend-react", "src", "components", "Cabinet.jsx")


def read(path: str) -> str:
    with open(path) as f:
        return f.read()


# ─── 1. nginx /admin-panel routing ────────────────────────────────────────────

class TestAdminPanelNginxRouting:
    """nginx-api.conf must NOT swallow /admin-panel/* via a greedy /admin
    prefix match."""

    def setup_method(self):
        self.conf = read(NGINX_API_CONF)

    def test_no_unscoped_location_admin_prefix(self):
        """A bare ``location /admin {`` prefix block is the bug: it also
        matches /admin-panel/foo.  It must be replaced by an exact match
        (``location = /admin``) and a trailing-slash prefix (``location
        /admin/``)."""
        # Allow location = /admin (exact) and location /admin/ (trailing-slash
        # prefix), but reject the bare prefix.
        matches = re.findall(r"location\s+/admin\s*\{", self.conf)
        assert not matches, (
            "nginx-api.conf must not contain `location /admin {` (bare prefix). "
            "It matches /admin-panel/* and proxies to django-admin (404). "
            "Use `location = /admin` plus `location /admin/` instead."
        )

    def test_exact_admin_match_present(self):
        """``location = /admin`` must exist so the bare path still reaches
        django-admin."""
        # Must appear in both HTTP and HTTPS server blocks
        count = len(re.findall(r"location\s+=\s+/admin\s*\{", self.conf))
        assert count >= 2, (
            f"Expected `location = /admin` in both HTTP and HTTPS server blocks; "
            f"found {count}"
        )

    def test_admin_slash_prefix_present(self):
        """``location /admin/`` (with trailing slash) must exist so
        /admin/login/, /admin/users/, … reach django-admin."""
        count = len(re.findall(r"location\s+/admin/\s*\{", self.conf))
        assert count >= 2, (
            f"Expected `location /admin/` in both HTTP and HTTPS server blocks; "
            f"found {count}"
        )

    def test_admin_blocks_proxy_to_django_admin(self):
        """The /admin exact and /admin/ prefix blocks must proxy to
        django-admin via the deferred-DNS variable pattern."""
        # Pull every block that targets /admin or /admin/
        blocks = re.findall(
            r"location\s+(?:=\s+/admin|/admin/)\s*\{([^}]+)\}",
            self.conf,
            re.S,
        )
        assert blocks, "No /admin or /admin/ location blocks found"
        for block in blocks:
            assert "django_admin_backend" in block, (
                "/admin and /admin/ blocks must use $django_admin_backend so "
                "DNS is resolved at request time via Docker's resolver"
            )
            assert "proxy_pass" in block, (
                "/admin and /admin/ blocks must contain a proxy_pass directive"
            )

    def test_api_admin_still_routes_to_django_admin(self):
        """The /api/admin/ block must remain unchanged — it serves the Django
        admin's REST API used by the admin frontend."""
        blocks = re.findall(
            r"location\s+/api/admin/\s*\{([^}]+)\}",
            self.conf,
            re.S,
        )
        assert blocks, "No /api/admin/ location block found"
        for block in blocks:
            assert "django_admin_backend" in block, (
                "/api/admin/ block must proxy to django-admin"
            )


# ─── 2. Cabinet must not fall back to auth-service UUID ───────────────────────

class TestCabinetCoreIdResolution:
    """Cabinet.jsx must resolve a real core id before /api/users/{id}/* calls,
    never falling back to the auth-service UUID (issue #264 problem 1)."""

    def setup_method(self):
        self.src = read(CABINET_JSX)

    def test_loadStats_does_not_fallback_to_user_id_for_balance(self):
        """The fallback ``user.coreId || user.id`` inside loadStats is the
        bug: when coreId is missing, the auth UUID is used, which produces
        404s on /api/users/{auth_uuid}/balance/."""
        # The "loadStats" callback must not contain `user.coreId || user.id`
        # immediately before calling getUserBalance/getUserProcurements.
        load_stats = re.search(
            r"const loadStats\s*=\s*useCallback\(.*?\}\s*,\s*\[user\]\);",
            self.src,
            re.S,
        )
        assert load_stats, "loadStats useCallback not found in Cabinet.jsx"
        body = load_stats.group(0)
        # Specifically: the local `coreId` resolved here must NOT use the
        # `user.coreId || user.id` pattern — that's what produced 404s.
        assert "user.coreId || user.id" not in body, (
            "Cabinet.loadStats must not fall back to user.id when "
            "user.coreId is missing — it must re-fetch via getUserByEmail "
            "(issue #264)."
        )

    def test_loadStats_refetches_by_email_when_coreid_missing(self):
        """When ``user.coreId`` is missing, loadStats must call
        ``api.getUserByEmail(user.email)`` to recover it before proceeding."""
        load_stats = re.search(
            r"const loadStats\s*=\s*useCallback\(.*?\}\s*,\s*\[user\]\);",
            self.src,
            re.S,
        )
        assert load_stats, "loadStats useCallback not found in Cabinet.jsx"
        body = load_stats.group(0)
        assert "api.getUserByEmail" in body, (
            "Cabinet.loadStats must re-fetch the core user by email when "
            "user.coreId is missing (issue #264)."
        )


# ─── 2b. Store must await coreId resolution before navigation ─────────────────

class TestStoreAwaitCoreIdOnLogin:
    """useStore.js must await getUserByEmail in confirmLogin and
    confirmRegistration so the Cabinet doesn't render with coreId=null."""

    def setup_method(self):
        self.src = read(STORE_JS)

    def _extract_fn(self, name: str) -> str:
        m = re.search(
            rf"{name}\s*:\s*async\s*\(.*?\)\s*=>\s*\{{(.*?)\n\s*\}},",
            self.src,
            re.S,
        )
        assert m, f"function {name} not found in useStore.js"
        return m.group(1)

    def test_confirm_login_awaits_by_email(self):
        """confirmLogin must ``await`` the by-email lookup, not fire-and-forget."""
        body = self._extract_fn("confirmLogin")
        assert "await api.getUserByEmail" in body, (
            "confirmLogin must await api.getUserByEmail so user.coreId is "
            "populated before the user lands in the Cabinet (issue #264)."
        )

    def test_confirm_registration_awaits_by_email(self):
        """confirmRegistration must ``await`` the by-email lookup too."""
        body = self._extract_fn("confirmRegistration")
        assert "await api.getUserByEmail" in body, (
            "confirmRegistration must await api.getUserByEmail so user.coreId "
            "is populated before the user lands in the Cabinet (issue #264)."
        )


# ─── 3. auth-service must fail loudly when core sync fails ────────────────────

class TestAuthServiceCoreSyncFailsLoudly:
    """`_sync_user_to_core` must support raising on error; registration must
    use that path so the auth row is not persisted without a core record."""

    def setup_method(self):
        self.src = read(AUTH_APP)

    def test_sync_helper_supports_raise_on_error(self):
        """The helper signature must accept a `raise_on_error` flag."""
        assert "raise_on_error" in self.src, (
            "_sync_user_to_core must accept a raise_on_error flag so the "
            "registration endpoint can fail loudly on core outage (issue #264)."
        )
        # The signature must declare the parameter
        assert re.search(
            r"async def _sync_user_to_core\([^)]*raise_on_error[^)]*\)",
            self.src,
        ), "_sync_user_to_core signature must declare raise_on_error"

    def test_register_confirm_uses_raise_on_error(self):
        """`confirm_registration` must call `_sync_user_to_core` with
        raise_on_error=True so a sync failure aborts the registration."""
        # Find the confirm_registration function body
        fn = re.search(
            r"async def confirm_registration\(.*?\)(.*?)\n@app\.",
            self.src,
            re.S,
        )
        assert fn, "confirm_registration function not found"
        body = fn.group(1)
        assert "_sync_user_to_core" in body, (
            "confirm_registration must still call _sync_user_to_core"
        )
        assert "raise_on_error=True" in body, (
            "confirm_registration must pass raise_on_error=True to "
            "_sync_user_to_core so registration fails loudly when core is "
            "unreachable (issue #264)."
        )

    def test_register_confirm_rolls_back_auth_row_on_sync_failure(self):
        """When the core sync fails, the auth-service row inserted moments
        earlier must be DELETE'd so the two stores stay consistent."""
        fn = re.search(
            r"async def confirm_registration\(.*?\)(.*?)\n@app\.",
            self.src,
            re.S,
        )
        assert fn, "confirm_registration function not found"
        body = fn.group(1)
        assert re.search(
            r"DELETE FROM users WHERE id=\$1",
            body,
        ), (
            "On core-sync failure, confirm_registration must DELETE the just-"
            "inserted auth-service user so the two stores remain consistent."
        )

    def test_register_confirm_default_role_is_buyer(self):
        """Default role for new registrations is ``"buyer"`` (a business role)
        — not the literal ``"user"`` which has no display label in core."""
        fn = re.search(
            r"async def confirm_registration\(.*?\)(.*?)\n@app\.",
            self.src,
            re.S,
        )
        assert fn, "confirm_registration function not found"
        body = fn.group(1)
        # The role default must read pending.get("role") or "buyer"
        assert re.search(
            r'pending\.get\(\s*"role"\s*\)\s*or\s*"buyer"',
            body,
        ), (
            "confirm_registration default role must be 'buyer' (issue #264)."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
