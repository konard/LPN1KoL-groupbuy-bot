"""
Tests for issue #152: docker-compose.python.yml postgres init-databases.sh
failure due to CRLF line endings ("/bin/bash^M: bad interpreter").

The issue reports:
  groupbuy-postgres | /docker-entrypoint-initdb.d/init-databases.sh: /bin/bash^M:
    bad interpreter: No such file or directory

Root causes addressed by this repository:
  1. scripts/init-databases.sh must use LF (Unix) line endings, not CRLF (Windows).
  2. scripts/init-databases.sh must have the executable bit set.
  3. scripts/init-databases.sh must use /bin/sh because postgres:16-alpine
     does not include bash.
  4. docker-compose.python.yml must mount the script read-only at the correct path.
  5. .gitattributes must enforce LF for *.sh to prevent Windows clients from
     checking out the file with CRLF endings.

These tests lock in the fix so it cannot regress silently.
"""

from __future__ import annotations

import pathlib
import stat

import yaml

REPO = pathlib.Path(__file__).parent.parent

INIT_SCRIPT = REPO / "scripts" / "init-databases.sh"
COMPOSE_PYTHON = REPO / "docker-compose.python.yml"
GITATTRIBUTES = REPO / ".gitattributes"


class TestInitScriptLineEndings:
    """scripts/init-databases.sh must use LF line endings.

    The issue error '/bin/bash^M: bad interpreter' is caused by CRLF
    endings in the shebang line — the \\r becomes ^M and the OS cannot
    find the interpreter '/bin/bash\\r'.
    """

    def test_init_script_exists(self):
        assert INIT_SCRIPT.exists(), (
            f"{INIT_SCRIPT.relative_to(REPO)} is missing — "
            "docker-compose.python.yml mounts this file into the postgres container."
        )

    def test_init_script_has_no_crlf(self):
        raw = INIT_SCRIPT.read_bytes()
        assert b"\r\n" not in raw, (
            f"{INIT_SCRIPT.relative_to(REPO)} contains CRLF line endings (\\r\\n). "
            "This is the exact cause of the error in issue #152: "
            "'/bin/bash^M: bad interpreter: No such file or directory'. "
            "Fix with: sed -i 's/\\r$//' scripts/init-databases.sh"
        )

    def test_init_script_shebang_has_no_carriage_return(self):
        raw = INIT_SCRIPT.read_bytes()
        first_line = raw.split(b"\n")[0]
        assert b"\r" not in first_line, (
            f"The shebang line of {INIT_SCRIPT.relative_to(REPO)} contains "
            "a carriage return (\\r). This makes the interpreter path "
            "'/bin/bash\\r' which the OS cannot find."
        )

    def test_init_script_uses_alpine_available_shell(self):
        raw = INIT_SCRIPT.read_bytes()
        first_line = raw.split(b"\n")[0]
        assert first_line == b"#!/bin/sh", (
            f"{INIT_SCRIPT.relative_to(REPO)} is mounted into postgres:16-alpine, "
            "which includes /bin/sh but not bash. Use '#!/bin/sh' so the "
            "PostgreSQL init script can run in the Alpine image."
        )


class TestInitScriptPermissions:
    """scripts/init-databases.sh must have the executable bit set.

    Without the executable bit the postgres entrypoint sources the script
    rather than executing it. Under set -e any error in the sourced script
    silently aborts the init run.
    """

    def test_init_script_is_user_executable(self):
        mode = INIT_SCRIPT.stat().st_mode
        assert mode & stat.S_IXUSR, (
            f"{INIT_SCRIPT.relative_to(REPO)} is missing the user-executable bit. "
            "Fix with: chmod +x scripts/init-databases.sh"
        )

    def test_init_script_is_world_executable(self):
        mode = INIT_SCRIPT.stat().st_mode
        assert mode & stat.S_IXOTH, (
            f"{INIT_SCRIPT.relative_to(REPO)} is missing the world-executable bit. "
            "The postgres container may run as a non-root UID. "
            "Fix with: chmod +x scripts/init-databases.sh"
        )


class TestDockerComposePythonPostgresMount:
    """docker-compose.python.yml must mount init-databases.sh correctly.

    The script must be mounted at /docker-entrypoint-initdb.d/ so postgres
    picks it up on first boot, and with :ro so the container cannot modify it.
    """

    def _load_compose(self) -> dict:
        with open(COMPOSE_PYTHON) as f:
            return yaml.safe_load(f)

    def test_postgres_service_mounts_init_script(self):
        compose = self._load_compose()
        postgres = compose["services"]["postgres"]
        volumes = postgres.get("volumes", [])
        init_mounts = [v for v in volumes if "init-databases.sh" in str(v)]
        assert init_mounts, (
            "docker-compose.python.yml postgres service does not mount "
            "scripts/init-databases.sh. Add: "
            "- ./scripts/init-databases.sh:/docker-entrypoint-initdb.d/init-databases.sh:ro"
        )

    def test_init_script_mounted_at_correct_path(self):
        compose = self._load_compose()
        postgres = compose["services"]["postgres"]
        volumes = postgres.get("volumes", [])
        init_mounts = [v for v in volumes if "init-databases.sh" in str(v)]
        assert init_mounts, "No init-databases.sh mount found in postgres service."
        for mount in init_mounts:
            assert "/docker-entrypoint-initdb.d/" in str(mount), (
                f"init-databases.sh mount target must be under "
                f"/docker-entrypoint-initdb.d/ for postgres to pick it up. "
                f"Found: {mount!r}"
            )

    def test_init_script_mounted_readonly(self):
        compose = self._load_compose()
        postgres = compose["services"]["postgres"]
        volumes = postgres.get("volumes", [])
        init_mounts = [v for v in volumes if "init-databases.sh" in str(v)]
        assert init_mounts, "No init-databases.sh mount found in postgres service."
        for mount in init_mounts:
            assert str(mount).endswith(":ro"), (
                f"init-databases.sh must be mounted read-only (:ro). "
                f"Found: {mount!r}"
            )


class TestGitAttributesPreventsRegressions:
    """.gitattributes must enforce LF endings for shell scripts.

    This prevents Windows users cloning with core.autocrlf=true from getting
    CRLF-encoded .sh files that break inside Linux containers.
    """

    def test_gitattributes_exists(self):
        assert GITATTRIBUTES.exists(), (
            ".gitattributes is missing. Without it, Windows git clients may "
            "check out .sh files with CRLF endings, causing "
            "'/bin/bash^M: bad interpreter' errors in Docker containers."
        )

    def test_gitattributes_enforces_lf_for_shell_scripts(self):
        text = GITATTRIBUTES.read_text()
        assert "*.sh" in text and "eol=lf" in text, (
            ".gitattributes does not enforce LF endings for *.sh files. "
            "Add: *.sh text eol=lf"
        )

    def test_gitattributes_has_no_crlf(self):
        raw = GITATTRIBUTES.read_bytes()
        assert b"\r\n" not in raw, (
            ".gitattributes itself has CRLF endings — it must use LF."
        )
