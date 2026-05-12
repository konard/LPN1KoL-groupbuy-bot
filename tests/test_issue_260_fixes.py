"""
Tests for issue #260 fixes (Russian: «найти и исправить 404 на /api/users и
добавить Swagger-документацию ко всем эндпоинтам»).

The issue had three parts:

  1. The frontend reportedly hit 404s on /api/users.  We audited the entire
     request path (nginx → core-fastapi → app.include_router) and confirmed
     the routes are wired correctly via /api/users/* — the only behaviour the
     reporter likely misread was FastAPI's 307 redirect from /api/users to
     /api/users/ (default ``redirect_slashes=True``).  This test pins down the
     route prefix wiring so a future refactor cannot silently move it.

  2. Add Swagger/OpenAPI documentation to *every* endpoint in core-fastapi.
     The router decorators were missing ``response_model``, rich
     ``description`` strings, per-route ``responses``, and per-Query
     descriptions/examples.  This test asserts each users.py route now has
     the expected metadata so the /api/docs page is genuinely useful.

  3. Provide a final report — see PR description.

The checks are intentionally static (regex over file contents) to match the
style of ``tests/test_issue_256_fixes.py`` and ``tests/test_issue_258_fixes.py``
— they do not require Postgres / Redis / a running service.
"""

import os
import re

import pytest


ROOT = os.path.join(os.path.dirname(__file__), "..")

CORE_MAIN = os.path.join(ROOT, "core-fastapi", "main.py")
CORE_USERS_ROUTER = os.path.join(ROOT, "core-fastapi", "app", "routers", "users.py")
CORE_SCHEMAS = os.path.join(ROOT, "core-fastapi", "app", "schemas.py")

NGINX_API_CONF = os.path.join(ROOT, "infrastructure", "nginx", "nginx-api.conf")
UNIFIED_COMPOSE = os.path.join(ROOT, "docker-compose.unified.yml")


def read(path: str) -> str:
    with open(path) as f:
        return f.read()


# ─── 1. /api/users routing is correctly wired end-to-end ─────────────────────


class TestApiUsersRouting:
    def test_nginx_routes_api_to_core(self):
        """nginx must proxy /api/ to the core-fastapi upstream (called
        ``core_api`` in the unified compose config)."""
        conf = read(NGINX_API_CONF)
        assert "upstream core_api" in conf, "nginx-api.conf must declare core_api upstream"
        assert "core:8000" in conf, "core_api upstream must point at core:8000 (docker hostname)"
        assert re.search(r"location\s+/api/\s*\{", conf), "nginx must have a location /api/ block"
        assert re.search(r"proxy_pass\s+http://core_api;", conf), (
            "the /api/ location must proxy to the core_api upstream"
        )

    def test_unified_compose_mounts_nginx_api_conf(self):
        """The unified compose stack must mount nginx-api.conf (not
        nginx.conf) so the /api/ → core_api routing is actually active."""
        compose = read(UNIFIED_COMPOSE)
        assert "./infrastructure/nginx/nginx-api.conf:/etc/nginx/nginx.conf:ro" in compose, (
            "docker-compose.unified.yml must mount nginx-api.conf at /etc/nginx/nginx.conf"
        )

    def test_core_main_includes_users_router_under_api_prefix(self):
        """core-fastapi must include the users router behind /api so the
        public path becomes /api/users/*."""
        src = read(CORE_MAIN)
        assert re.search(
            r'app\.include_router\(\s*users\.router\s*,\s*prefix\s*=\s*["\']/api["\']\s*\)',
            src,
        ), "main.py must include users.router with prefix='/api'"

    def test_users_router_prefix_and_tag(self):
        """The users APIRouter must keep prefix='/users' and tag 'users' so
        the final routes resolve at /api/users/* and group under the same
        Swagger tag."""
        src = read(CORE_USERS_ROUTER)
        assert re.search(r'prefix\s*=\s*["\']/users["\']', src), (
            "APIRouter must declare prefix='/users'"
        )
        assert re.search(r'tags\s*=\s*\[\s*["\']users["\']\s*\]', src), (
            "APIRouter must declare tags=['users']"
        )

    def test_users_router_default_error_responses(self):
        """Router-level default ``responses`` should advertise the 400/404
        envelope so Swagger renders error shapes for every route."""
        src = read(CORE_USERS_ROUTER)
        # Slice the APIRouter(...) construction call.
        m = re.search(r"router\s*=\s*APIRouter\((?P<args>.*?)\n\)\s*\n", src, re.S)
        assert m, "APIRouter(...) construction not found"
        args = m.group("args")
        assert "responses=" in args, "APIRouter must pass responses="
        assert re.search(r"400:\s*\{[^}]*ErrorDetail", args), (
            "APIRouter must declare default 400 → ErrorDetail"
        )
        assert re.search(r"404:\s*\{[^}]*ErrorDetail", args), (
            "APIRouter must declare default 404 → ErrorDetail"
        )


# ─── 2. Swagger annotations on every /api/users endpoint ──────────────────────


# Expected (route_path, response_model_class_or_None, http_method)
# response_model=None means we don't enforce one (e.g. raw dict endpoints).
USER_ROUTES = [
    ("/",                          "list[UserResponse]",   "get"),
    ("/",                          "UserResponse",         "post"),
    ("/by_platform/",              "UserResponse",         "get"),
    ("/by_email/",                 "UserResponse",         "get"),
    ("/by_phone/",                 "UserResponse",         "get"),
    ("/check_exists/",             "ExistsResponse",       "get"),
    ("/search/",                   "list[UserResponse]",   "get"),
    ("/sessions/clear_state/",     "MessageResponse",      "post"),
    ("/{user_id}/",                "UserResponse",         "get"),
    ("/{user_id}/",                "UserResponse",         "put"),
    ("/{user_id}/",                "UserResponse",         "patch"),
    ("/{user_id}/balance/",        "UserBalanceResponse",  "get"),
    ("/{user_id}/update_balance/", "BalanceUpdateResponse", "post"),
    ("/{user_id}/role/",           "UserRoleResponse",     "get"),
    ("/{user_id}/ws_token/",       "WsTokenResponse",      "get"),
]


class TestUsersRouterSwaggerAnnotations:
    @pytest.mark.parametrize("path,response_model,method", USER_ROUTES)
    def test_route_has_response_model(self, path, response_model, method):
        """Every documented route must declare its response_model so
        clients can generate typed bindings from the OpenAPI schema."""
        src = read(CORE_USERS_ROUTER)
        # Match the decorator block for this (method, path) combo:
        # @router.<method>(\n   "<path>",\n   response_model=<X>,\n   ...
        # We tolerate arbitrary whitespace between fields.
        decorator_pattern = (
            r"@router\." + re.escape(method) + r"\(\s*"
            r"[\"']" + re.escape(path) + r"[\"']"
            r"(?P<body>.*?)\)\s*\n"
        )
        m = re.search(decorator_pattern, src, re.S)
        assert m, f"decorator for {method.upper()} {path} not found"
        body = m.group("body")
        assert (
            f"response_model={response_model}" in body
            or f"response_model=  {response_model}" in body
        ), f"{method.upper()} {path} must declare response_model={response_model}"

    @pytest.mark.parametrize("path,response_model,method", USER_ROUTES)
    def test_route_has_summary_and_description(self, path, response_model, method):
        """Every route needs a human-readable summary AND description so
        the rendered Swagger entry is actually useful."""
        src = read(CORE_USERS_ROUTER)
        decorator_pattern = (
            r"@router\." + re.escape(method) + r"\(\s*"
            r"[\"']" + re.escape(path) + r"[\"']"
            r"(?P<body>.*?)\)\s*\n"
        )
        m = re.search(decorator_pattern, src, re.S)
        assert m, f"decorator for {method.upper()} {path} not found"
        body = m.group("body")
        assert re.search(r"summary\s*=\s*[\"']", body), (
            f"{method.upper()} {path} missing summary="
        )
        assert re.search(r"description\s*=\s*[\(\"']", body), (
            f"{method.upper()} {path} missing description="
        )

    def test_schemas_define_response_envelopes(self):
        """All response_model classes referenced from the router must exist
        in app/schemas.py — otherwise the OpenAPI schema would 500 at boot."""
        schemas = read(CORE_SCHEMAS)
        for klass in [
            "ErrorDetail",
            "ExistsResponse",
            "MessageResponse",
            "BalanceUpdateResponse",
            "UserRoleResponse",
            "WsTokenResponse",
            "UserResponse",
            "UserBalanceResponse",
        ]:
            assert re.search(rf"\nclass {klass}\(BaseModel\):", schemas), (
                f"schemas.py is missing class {klass}(BaseModel)"
            )


# ─── 3. App-level OpenAPI metadata (tags, custom paths) ──────────────────────


class TestAppOpenApiMetadata:
    def test_openapi_paths_under_api(self):
        """Swagger / ReDoc / openapi.json must be served under /api so
        nginx's /api/ proxy reaches them."""
        src = read(CORE_MAIN)
        assert 'docs_url="/api/docs"' in src
        assert 'redoc_url="/api/redoc"' in src
        assert 'openapi_url="/api/schema/openapi.json"' in src

    def test_openapi_tags_metadata_declared(self):
        """The FastAPI app must declare openapi_tags with descriptions for
        each tag so the rendered docs group routes meaningfully."""
        src = read(CORE_MAIN)
        assert "openapi_tags=" in src, "main.py must pass openapi_tags= to FastAPI()"
        # Tag names that must appear in the metadata list.
        for tag in [
            "users",
            "procurements",
            "payments",
            "chat",
            "buyer-requests",
            "news",
            "polls",
            "suppliers",
            "invitations",
            "health",
        ]:
            assert re.search(rf'"name":\s*"{re.escape(tag)}"', src), (
                f"openapi_tags must include a metadata entry for tag '{tag}'"
            )


# ─── 4. Schema imports / consistency in the users router ─────────────────────


class TestUsersRouterImports:
    def test_router_imports_all_response_models(self):
        """The users router must import every response model it references."""
        src = read(CORE_USERS_ROUTER)
        for klass in [
            "BalanceUpdateResponse",
            "ErrorDetail",
            "ExistsResponse",
            "MessageResponse",
            "UserBalanceResponse",
            "UserResponse",
            "UserRoleResponse",
            "WsTokenResponse",
        ]:
            assert re.search(rf"\b{klass}\b", src), (
                f"users.py must import / reference {klass}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
