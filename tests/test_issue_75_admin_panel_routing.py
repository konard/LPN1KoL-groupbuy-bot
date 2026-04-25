"""
Tests for issue #75 fix:

  ``docker-compose.monolith.yml up`` does not start the personal account
  (личный кабинет) and admin panel.

  Root cause: ``infrastructure/nginx/nginx-monolith.conf`` defined an
  ``admin_frontend`` upstream (``server admin-frontend:80``) but never used
  it — there was no ``location /admin-panel/`` block routing browser traffic
  to the admin-frontend container.  As a result, navigating to
  ``http://<host>/admin-panel/`` fell through to the ``location /`` block
  which served the user-frontend instead, and the admin panel was
  inaccessible.

  Additionally, ``admin-frontend/vite.config.js`` had no ``base`` option set.
  When Vite builds without a ``base`` the generated ``index.html`` references
  all JS/CSS assets from ``/assets/…``.  When the admin-frontend is mounted
  under ``/admin-panel/`` (outer nginx strips the prefix and proxies to the
  container's root), asset requests like ``/admin-panel/assets/index.js``
  are correctly forwarded.  However without ``base: '/admin-panel/'`` set
  the references in ``index.html`` would be relative to ``/``, so browsers
  would request ``/assets/index.js`` which falls through to user-frontend —
  breaking the page.

  Fix:
  1. Add ``location /admin-panel/`` blocks (HTTP + HTTPS) in
     ``nginx-monolith.conf`` that ``proxy_pass`` to ``admin_frontend`` with a
     trailing slash so the ``/admin-panel/`` prefix is stripped.
  2. Set ``base: '/admin-panel/'`` in ``admin-frontend/vite.config.js`` so
     all built asset URLs are prefixed with ``/admin-panel/``.
"""
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")

NGINX_MONOLITH_CONF = os.path.join(ROOT, "infrastructure", "nginx", "nginx-monolith.conf")
VITE_CONFIG = os.path.join(ROOT, "admin-frontend", "vite.config.js")


def read(path):
    with open(path) as f:
        return f.read()


class TestAdminPanelNginxRouting:
    """nginx-monolith.conf must route /admin-panel/ to admin_frontend."""

    def setup_method(self):
        self.conf = read(NGINX_MONOLITH_CONF)

    def test_admin_panel_location_exists(self):
        assert "location /admin-panel/" in self.conf, (
            "nginx-monolith.conf is missing a 'location /admin-panel/' block. "
            "Without it the admin panel is unreachable through nginx."
        )

    def test_admin_panel_proxies_to_a_frontend(self):
        """The /admin-panel/ location must proxy to a frontend service.

        Issue #75 originally required admin_frontend.  Issue #105 updated this
        to user-frontend so that a single Next.js container serves both /lk/
        and /admin-panel/ (mirroring docker-compose.unified.yml).  Either
        upstream is acceptable; what matters is that a proxy_pass is present.
        """
        blocks = re.findall(
            r"location\s+/admin-panel/\s*\{([^}]+)\}",
            self.conf,
            re.DOTALL,
        )
        assert blocks, "No /admin-panel/ location block found"
        for block in blocks:
            assert "proxy_pass" in block, (
                "location /admin-panel/ block must contain a proxy_pass directive"
            )

    def test_admin_frontend_upstream_defined(self):
        """admin_frontend upstream must reference admin-frontend container."""
        assert "upstream admin_frontend" in self.conf, (
            "admin_frontend upstream is not defined in nginx-monolith.conf"
        )
        assert "server admin-frontend:80" in self.conf, (
            "admin_frontend upstream does not point to admin-frontend:80"
        )

    def test_admin_panel_location_count(self):
        """Both HTTP (port 80) and HTTPS (port 443) server blocks must have
        the /admin-panel/ location so the admin panel is reachable on both."""
        count = self.conf.count("location /admin-panel/")
        assert count >= 2, (
            f"Expected /admin-panel/ location in both HTTP and HTTPS server blocks, "
            f"found only {count} occurrence(s)"
        )

    def test_admin_panel_has_proxy_pass_directive(self):
        """proxy_pass for /admin-panel/ must be present.

        Issue #75 originally required a trailing slash on admin_frontend/.
        Issue #105 changed the upstream to user-frontend (via a $upstream
        variable), so the trailing-slash rule no longer applies.  The essential
        invariant is that a proxy_pass directive exists in the block.
        """
        blocks = re.findall(
            r"location\s+/admin-panel/\s*\{([^}]+)\}",
            self.conf,
            re.DOTALL,
        )
        assert blocks, "No /admin-panel/ location block found"
        for block in blocks:
            assert "proxy_pass" in block, (
                "location /admin-panel/ must contain a proxy_pass directive"
            )

    def test_admin_api_still_routes_to_admin_backend(self):
        """/api/admin/* must still route to admin_backend, not admin_frontend."""
        blocks = re.findall(
            r"location\s+/api/admin/\s*\{([^}]+)\}",
            self.conf,
            re.DOTALL,
        )
        assert blocks, "No /api/admin/ location block found"
        for block in blocks:
            assert "admin_backend" in block, (
                "location /api/admin/ must proxy to admin_backend"
            )


class TestAdminFrontendViteBase:
    """admin-frontend/vite.config.js must set base to /admin-panel/."""

    def setup_method(self):
        self.config = read(VITE_CONFIG)

    def test_base_is_set_to_admin_panel(self):
        assert "base: '/admin-panel/'" in self.config, (
            "admin-frontend/vite.config.js is missing base: '/admin-panel/'. "
            "Without this, built asset URLs are relative to /, so browsers "
            "request /assets/… which falls through to user-frontend instead "
            "of being served by the admin-frontend container."
        )
