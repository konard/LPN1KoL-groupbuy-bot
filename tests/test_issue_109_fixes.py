"""
Tests for issue #109: docker-compose.monolith.yml startup bugs.

Bug #1: groupbuy-nginx-monolith fails to start with
        "exec /docker-entrypoint-custom.sh: no such file or directory".

        Root cause: docker-compose mounts
            ./infrastructure/nginx/docker-entrypoint.sh:/docker-entrypoint-custom.sh:ro
        and the service uses exec-form ENTRYPOINT
            entrypoint: ["/docker-entrypoint-custom.sh"]

        Docker preserves host file permissions on bind mounts. The host file
        was committed to git with mode 100644 (no executable bit), so the
        kernel's execve() refuses it with ENOENT-style "no such file or
        directory". Without nginx, the whole stack is unreachable, which the
        user perceives as "frontend doesn't start" and "auth doesn't work" —
        the secondary symptoms in this issue.

        Fix: track the script with mode 100755 (executable) in git so the
        bind mount inherits +x.

Bug #2 / #3 (frontend startup, auth flow): nginx is the public entry point
        for both /lk/ (user-frontend) and /api/v1/auth/* (backend-monolith).
        When nginx never starts, requests to / and /api/* fail at the host —
        nothing else is wrong with the user-frontend or backend-monolith
        services themselves. Fixing the entrypoint is therefore the root
        cause; we still keep regression assertions for routing here so the
        chain stays wired the same way as docker-compose.unified.yml.
"""

import os
import pathlib
import re
import stat

import pytest
import yaml

REPO = pathlib.Path(__file__).parent.parent
COMPOSE_MONOLITH = REPO / "docker-compose.monolith.yml"
COMPOSE_UNIFIED = REPO / "docker-compose.unified.yml"
NGINX_ENTRYPOINT = REPO / "infrastructure" / "nginx" / "docker-entrypoint.sh"
NGINX_MONOLITH_CONF = REPO / "infrastructure" / "nginx" / "nginx-monolith.conf"


def _load(path: pathlib.Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Bug #1: nginx entrypoint executable bit
# ---------------------------------------------------------------------------


class TestNginxEntrypointExecutable:
    """The nginx entrypoint script must be executable.

    docker-compose mounts the host file directly into the container with mode
    bits preserved. Using ``entrypoint: ["/docker-entrypoint-custom.sh"]``
    (exec form) bypasses the shell, so the mounted file must have the
    executable bit or execve() fails.
    """

    def test_entrypoint_file_exists(self):
        assert NGINX_ENTRYPOINT.exists(), (
            f"{NGINX_ENTRYPOINT} is missing — the nginx service mounts it as "
            "/docker-entrypoint-custom.sh"
        )

    def test_entrypoint_is_executable_on_disk(self):
        mode = NGINX_ENTRYPOINT.stat().st_mode
        assert mode & stat.S_IXUSR, (
            f"{NGINX_ENTRYPOINT} is not executable for the owner (mode "
            f"{oct(mode & 0o777)}). Docker mounts preserve host permissions; "
            "without +x, nginx fails with "
            "'exec /docker-entrypoint-custom.sh: no such file or directory'."
        )

    def test_entrypoint_is_executable_in_git(self):
        """git must store the script with mode 100755 so fresh clones get +x."""
        import subprocess

        try:
            out = subprocess.check_output(
                ["git", "ls-files", "-s", str(NGINX_ENTRYPOINT.relative_to(REPO))],
                cwd=REPO,
                text=True,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("git not available")
        assert out, f"{NGINX_ENTRYPOINT} is not tracked by git"
        mode = out.split()[0]
        assert mode == "100755", (
            f"{NGINX_ENTRYPOINT} is tracked with git mode {mode}; must be "
            "100755 so the executable bit survives a fresh clone."
        )

    def test_entrypoint_has_shebang(self):
        first_line = NGINX_ENTRYPOINT.read_text().splitlines()[0]
        assert first_line.startswith("#!"), (
            f"{NGINX_ENTRYPOINT} must begin with a shebang line so execve() "
            f"can launch it; first line is {first_line!r}"
        )


# ---------------------------------------------------------------------------
# Bug #1 (config side): both compose files reference the script the same way
# ---------------------------------------------------------------------------


class TestNginxEntrypointWiring:
    """The monolith and unified compose files must mount and exec the script
    the same way so a single fix applies to both."""

    @pytest.mark.parametrize("compose_path", [COMPOSE_MONOLITH, COMPOSE_UNIFIED])
    def test_nginx_entrypoint_pointer(self, compose_path):
        compose = _load(compose_path)
        nginx = compose["services"]["nginx"]
        entrypoint = nginx.get("entrypoint")
        assert entrypoint == ["/docker-entrypoint-custom.sh"], (
            f"{compose_path.name}: nginx entrypoint must be "
            "['/docker-entrypoint-custom.sh'] (exec form). Got: "
            f"{entrypoint!r}"
        )

    @pytest.mark.parametrize("compose_path", [COMPOSE_MONOLITH, COMPOSE_UNIFIED])
    def test_nginx_mounts_entrypoint_script(self, compose_path):
        compose = _load(compose_path)
        nginx = compose["services"]["nginx"]
        volumes = nginx.get("volumes", [])
        target = "./infrastructure/nginx/docker-entrypoint.sh:/docker-entrypoint-custom.sh:ro"
        assert target in volumes, (
            f"{compose_path.name}: nginx must mount the host script at "
            f"/docker-entrypoint-custom.sh. Got volumes: {volumes}"
        )


# ---------------------------------------------------------------------------
# Bug #2: frontend reachability — nginx must be wired to user-frontend
# the same way docker-compose.unified.yml wires nginx to its frontend.
# ---------------------------------------------------------------------------


class TestFrontendStartup:
    """user-frontend must start and be reachable through nginx."""

    @pytest.fixture(scope="class")
    def compose(self):
        return _load(COMPOSE_MONOLITH)

    def test_user_frontend_present(self, compose):
        assert "user-frontend" in compose["services"], (
            "user-frontend service must be defined in docker-compose.monolith.yml"
        )

    def test_nginx_waits_for_user_frontend(self, compose):
        deps = compose["services"]["nginx"].get("depends_on", {})
        assert "user-frontend" in deps, (
            "nginx must depend on user-frontend (mirrors how nginx in "
            "docker-compose.unified.yml depends on frontend-react)"
        )
        cond = (
            deps["user-frontend"].get("condition")
            if isinstance(deps["user-frontend"], dict)
            else None
        )
        assert cond == "service_healthy", (
            "nginx must wait for user-frontend to be service_healthy; "
            f"got condition={cond!r}"
        )

    def test_nginx_routes_root_to_user_frontend(self):
        nginx = NGINX_MONOLITH_CONF.read_text()
        assert "user-frontend:3000" in nginx, (
            "nginx-monolith.conf must proxy user traffic to user-frontend:3000"
        )


# ---------------------------------------------------------------------------
# Bug #3: registration / authorization wiring must match unified.
# In unified, all auth-related services share the same JWT_SECRET and
# admin-backend talks to the same DB as the auth service. Verify the
# monolith mirrors that contract: backend-monolith is the auth source of
# truth, admin-backend trusts the same JWT_SECRET, and nginx exposes the
# same routes (/api/v1/auth/*, /api/users/*, /api/admin/auth/).
# ---------------------------------------------------------------------------


class TestAuthWiringMatchesUnified:
    @pytest.fixture(scope="class")
    def compose(self):
        return _load(COMPOSE_MONOLITH)

    def _env_dict(self, svc):
        env = svc.get("environment", {})
        if isinstance(env, list):
            out = {}
            for item in env:
                if "=" in item:
                    k, v = item.split("=", 1)
                    out[k.strip()] = v.strip()
            return out
        return {str(k): str(v) for k, v in env.items()}

    def test_backend_monolith_has_jwt_secret(self, compose):
        env = self._env_dict(compose["services"]["backend-monolith"])
        assert "JWT_SECRET" in env, (
            "backend-monolith is the auth source of truth and must expose "
            "JWT_SECRET (mirrors auth-service in docker-compose.unified.yml)"
        )

    def test_admin_backend_shares_jwt_secret(self, compose):
        """admin-backend validates JWTs minted by backend-monolith — the
        secret must come from the same env var so tokens verify."""
        env = self._env_dict(compose["services"]["admin-backend"])
        assert "JWT_SECRET" in env, (
            "admin-backend must receive JWT_SECRET so it can validate tokens "
            "issued by backend-monolith (same wiring as auth-service ↔ "
            "django-admin in docker-compose.unified.yml)"
        )
        assert env["JWT_SECRET"] == compose["services"]["backend-monolith"][
            "environment"
        ]["JWT_SECRET"], (
            "admin-backend and backend-monolith must read JWT_SECRET from the "
            "same source so tokens issued by one validate in the other."
        )

    def test_admin_backend_depends_on_backend_monolith(self, compose):
        """Auth-related services must wait for the auth service to be
        healthy before starting, matching unified's auth-service ↔
        notification-service ordering."""
        deps = compose["services"]["admin-backend"].get("depends_on", {})
        assert "backend-monolith" in deps, (
            "admin-backend must wait for backend-monolith (the auth source "
            "of truth) to be healthy before accepting requests."
        )
        cond = (
            deps["backend-monolith"].get("condition")
            if isinstance(deps["backend-monolith"], dict)
            else None
        )
        assert cond == "service_healthy", (
            f"admin-backend must wait for backend-monolith to be healthy; "
            f"got {cond!r}"
        )

    def test_nginx_proxies_auth_routes(self):
        nginx = NGINX_MONOLITH_CONF.read_text()
        # Auth registration/login go through backend-monolith
        assert "/api/v1/auth/" in nginx, (
            "nginx-monolith.conf must expose /api/v1/auth/ so the frontend "
            "can call register/login"
        )
        # Admin auth is rate-limited and routed to admin-backend
        assert "/api/admin/" in nginx, (
            "nginx-monolith.conf must expose /api/admin/ for admin-backend"
        )

    def test_backend_monolith_jwt_settings_match_auth_service(self, compose):
        """The monolith's JWT lifetime envs must exist so the same defaults
        as unified's auth-service apply. The unit names differ on purpose
        (FastAPI uses minutes/days, NestJS uses 15m/7d), but the values must
        line up in seconds."""
        env = self._env_dict(compose["services"]["backend-monolith"])
        assert env.get("JWT_EXPIRES_MINUTES") == "15", (
            "JWT_EXPIRES_MINUTES must be 15 (same as JWT_EXPIRES_IN=15m in "
            "docker-compose.unified.yml's auth-service)"
        )
        assert env.get("JWT_REFRESH_EXPIRES_DAYS") == "7", (
            "JWT_REFRESH_EXPIRES_DAYS must be 7 (same as "
            "JWT_REFRESH_EXPIRES_IN=7d in unified's auth-service)"
        )
        assert env.get("BCRYPT_ROUNDS") == "10", (
            "BCRYPT_ROUNDS must be 10 (same as unified's auth-service)"
        )
