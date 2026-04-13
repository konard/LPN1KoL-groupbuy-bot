"""
Tests for issue #326 fix:

  Frontend fails to load — browser gets 404 on JS and CSS files, main page is blank.

  Root cause: ``vite.config.js`` set ``assetsDir: 'static'``, which caused Vite to
  place all built JS/CSS bundles under ``dist/static/`` and reference them from
  ``index.html`` as ``/static/main-HASH.js``.

  However, the main nginx (``infrastructure/nginx/nginx.conf``) has a dedicated
  ``location /static/`` block that serves Django's collected static files
  (``alias /static/``).  When the browser requests ``/static/main-HASH.js``, nginx
  matches that block first and looks in the Django static directory — the file is
  not there — so nginx returns a 404.  The frontend container never receives the
  request.

  Fix: change ``assetsDir`` from ``'static'`` to ``'assets'`` (Vite's default).
  Built assets are now served as ``/assets/main-HASH.js``, which does not conflict
  with the ``/static/`` block reserved for Django static files.  The matching
  ``location /static/`` block in ``frontend-react/nginx.conf`` is updated to
  ``location /assets/`` accordingly.
"""
import os
import re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")

VITE_CONFIG = os.path.join(ROOT, "frontend-react", "vite.config.js")
FRONTEND_NGINX = os.path.join(ROOT, "frontend-react", "nginx.conf")
INFRA_NGINX = os.path.join(ROOT, "infrastructure", "nginx", "nginx.conf")


def read(path):
    with open(path) as f:
        return f.read()


class TestViteAssetsDir:
    def test_assets_dir_is_not_static(self):
        """
        ``assetsDir`` must not be 'static' — that name clashes with the
        ``/static/`` location block in the main nginx which serves Django files.
        """
        content = read(VITE_CONFIG)
        assert "assetsDir: 'static'" not in content, (
            "vite.config.js sets assetsDir to 'static', which conflicts with "
            "the /static/ nginx location reserved for Django static files."
        )

    def test_assets_dir_is_assets(self):
        """
        ``assetsDir`` should be 'assets' (Vite's default) to avoid the
        ``/static/`` conflict.
        """
        content = read(VITE_CONFIG)
        assert "assetsDir: 'assets'" in content, (
            "vite.config.js should set assetsDir to 'assets' to avoid "
            "conflicting with the /static/ nginx location."
        )


class TestFrontendNginxConf:
    def test_no_static_location_for_frontend_assets(self):
        """
        The frontend nginx should not use ``location /static/`` for caching
        built Vite assets — that path is claimed by Django in the main nginx.
        """
        content = read(FRONTEND_NGINX)
        # If /static/ is present it should not be for built Vite assets.
        # After the fix the caching block should use /assets/ instead.
        if "location /static/" in content:
            pytest.fail(
                "frontend-react/nginx.conf still caches /static/ — "
                "update the location block to /assets/ to match the new assetsDir."
            )

    def test_assets_location_present(self):
        """
        The frontend nginx must have a caching ``location /assets/`` block for
        the built Vite bundles.
        """
        content = read(FRONTEND_NGINX)
        assert "location /assets/" in content, (
            "frontend-react/nginx.conf is missing a 'location /assets/' block. "
            "Add one to cache the built Vite assets efficiently."
        )


class TestInfraNginxStaticDoesNotInterfereWithFrontend:
    def test_infra_nginx_static_location_present(self):
        """
        The main nginx must keep its ``/static/`` location for Django.
        This test ensures we did not accidentally remove it.
        """
        content = read(INFRA_NGINX)
        assert "location /static/" in content, (
            "infrastructure/nginx/nginx.conf lost its /static/ location block. "
            "Django needs this to serve collected static files."
        )

    def test_infra_nginx_has_no_assets_location(self):
        """
        The main nginx should not define a ``/assets/`` location — requests for
        frontend assets must fall through to the ``location /`` proxy block
        which forwards them to the frontend container where they are served
        correctly.
        """
        content = read(INFRA_NGINX)
        assert "location /assets/" not in content, (
            "infrastructure/nginx/nginx.conf defines a /assets/ location block, "
            "which would intercept frontend bundle requests before they reach "
            "the frontend container."
        )
