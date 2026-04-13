"""
Tests for issue #328 fix:

  Frontend fails to load — page is blank after issue #326 is fixed.

  Two root causes identified:

  ROOT CAUSE 1 — Render-blocking Google Fonts (Material Symbols) in index.html
  ----------------------------------------------------------------------------
  ``frontend-react/index.html`` contains a ``<link rel="stylesheet">`` tag that
  loads Material Symbols (icon font) from ``fonts.googleapis.com``.

  Problems:
  • This request is RENDER-BLOCKING: the browser must download the CSS before it
    can paint the page.  If the network is slow or the request hangs (e.g., because
    Google servers are unreachable — common in Russia, the primary target market),
    the page stays blank until the request either succeeds or the browser times out.
  • Material Symbols is not referenced anywhere in the React source code
    (``src/**/*.{jsx,js,css}``), so the font is dead code with zero benefit.

  Fix: remove the ``<link rel="stylesheet" href="https://fonts.googleapis.com/...">``
  line from ``frontend-react/index.html``.

  ROOT CAUSE 2 — No React ErrorBoundary
  --------------------------------------
  The React application tree has no ErrorBoundary component.  In production mode
  (``npm run build`` output served by nginx), React does not render any fallback
  when an uncaught error is thrown during rendering — it simply unmounts the
  entire tree, leaving a blank ``<div id="root"></div>``.

  Fix: add an ``<ErrorBoundary>`` wrapper around the top-level ``<App>`` in
  ``frontend-react/src/main.jsx``.  The ErrorBoundary must be a class component
  (React's requirement) and should render a user-visible error message instead
  of nothing.
"""
import os
import re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")

INDEX_HTML = os.path.join(ROOT, "frontend-react", "index.html")
MAIN_JSX = os.path.join(ROOT, "frontend-react", "src", "main.jsx")


def read(path):
    with open(path) as f:
        return f.read()


# ─── Root cause 1: render-blocking Google Fonts ──────────────────────────────

class TestNoRenderBlockingExternalFonts:
    def test_no_google_fonts_link(self):
        """
        ``index.html`` must not contain a Google Fonts stylesheet link.

        A ``<link rel="stylesheet" href="https://fonts.googleapis.com/...">`` is
        render-blocking: the browser cannot paint the page until the stylesheet is
        downloaded.  When Google Fonts is unreachable (e.g. in Russia where the
        app is primarily used), the browser waits for the request to time out —
        often tens of seconds — before rendering anything.  The perceived result
        is a blank page.

        Material Symbols is not referenced in any React source file, so the link
        is also dead code.
        """
        content = read(INDEX_HTML)
        assert "fonts.googleapis.com" not in content, (
            "frontend-react/index.html contains a <link> to fonts.googleapis.com. "
            "This is render-blocking and will cause a blank page when Google servers "
            "are unreachable (common in Russia, the primary target market). "
            "Remove the unused Material Symbols / Google Fonts link."
        )

    def test_no_material_symbols_import(self):
        """
        ``index.html`` must not load Material Symbols.

        The icon font is not used anywhere in the React source code; it only adds
        a render-blocking round-trip to an external CDN.
        """
        content = read(INDEX_HTML)
        assert "Material+Symbols" not in content and "material-symbols" not in content.lower(), (
            "frontend-react/index.html still loads Material Symbols from Google CDN. "
            "This font is unused in the source code and creates an unnecessary "
            "render-blocking request. Remove it."
        )

    def test_no_render_blocking_external_stylesheets(self):
        """
        ``index.html`` must not contain render-blocking external stylesheet links.

        Any ``<link rel="stylesheet" href="https://...">`` pointing to an external
        host is render-blocking in most browsers.  Such resources should be hosted
        locally (self-hosted), loaded asynchronously, or removed if unused.
        """
        content = read(INDEX_HTML)
        # Find all external stylesheet links
        external_css = re.findall(
            r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']https?://[^"\']+["\']',
            content,
            re.IGNORECASE,
        ) + re.findall(
            r'<link[^>]+href=["\']https?://[^"\']+["\'][^>]+rel=["\']stylesheet["\']',
            content,
            re.IGNORECASE,
        )
        assert external_css == [], (
            f"frontend-react/index.html contains render-blocking external stylesheets: "
            f"{external_css}. "
            "Move them to local assets or load them non-blocking."
        )


# ─── Root cause 2: missing React ErrorBoundary ───────────────────────────────

class TestReactErrorBoundary:
    def test_error_boundary_in_main_jsx(self):
        """
        ``main.jsx`` must wrap the top-level ``<App>`` in an ErrorBoundary.

        Without an ErrorBoundary, any uncaught render-time error in production
        causes React to unmount the entire component tree, leaving the user with
        a completely blank page and no feedback.

        The fix is to add a class component ErrorBoundary (React's requirement)
        and wrap ``<App>`` with it in ``ReactDOM.createRoot(...).render()``.
        """
        content = read(MAIN_JSX)
        assert "ErrorBoundary" in content, (
            "frontend-react/src/main.jsx does not use an ErrorBoundary. "
            "Without an ErrorBoundary, any uncaught render error in production "
            "causes React to unmount the whole tree, showing a blank page. "
            "Add a class-based ErrorBoundary and wrap <App> with it."
        )

    def test_error_boundary_wraps_app(self):
        """
        The ErrorBoundary component must wrap ``<App>``.

        Defining ErrorBoundary without using it provides no protection.
        """
        content = read(MAIN_JSX)
        # Check that ErrorBoundary is used as a component wrapper (not just defined/imported)
        assert re.search(r"<ErrorBoundary[^/]", content), (
            "frontend-react/src/main.jsx defines or imports ErrorBoundary "
            "but does not use it to wrap <App>. "
            "Wrap the <App> render call with <ErrorBoundary> to protect against "
            "blank page on render errors."
        )

    def test_error_boundary_component_exists(self):
        """
        The ErrorBoundary component should be defined or imported in main.jsx.
        """
        content = read(MAIN_JSX)
        has_class_definition = "class ErrorBoundary" in content
        has_import = "import" in content and "ErrorBoundary" in content
        assert has_class_definition or has_import, (
            "frontend-react/src/main.jsx has no ErrorBoundary class definition "
            "and no import of ErrorBoundary. "
            "Add a class-based ErrorBoundary component (React's requirement for error boundaries) "
            "and wrap <App> with it."
        )
