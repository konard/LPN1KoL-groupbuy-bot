"""
Tests for issue #139: "groupbuy-postgres is unhealthy" caused by CRLF line endings
and missing executable bit on shell scripts mounted into Docker containers.

Root causes fixed:

1. No .gitattributes enforcing LF line endings for *.sh files.  On Windows with
   git autocrlf=true (the default), shell scripts are checked out with CRLF line
   endings.  When these files are bind-mounted into a Linux container the shebang
   line becomes "#!/bin/bash\r", which the kernel rejects with:
       /bin/bash^M: bad interpreter: No such file or directory
   The init script fails silently, the extra databases are never created, and on
   the next container restart (when Postgres skips re-initialization) all services
   that depend on those databases fail to start.

2. infrastructure/postgres/init-databases.sh lacked the executable bit (0o644).
   The official postgres image's docker-entrypoint sources non-executable .sh
   files instead of executing them.  Sourcing inherits `set -e`, so any psql
   failure aborts the entire entrypoint and postgres exits before the healthcheck
   can ever pass.

3. infrastructure/postgres/init-databases.sh only created auth_db.  The full
   microservices stack needs auth_db, purchase_db, payment_db, chat_db, and
   reputation_db — exactly what scripts/init-databases.sh already creates.

4. docker-compose.yml postgres healthcheck lacked start_period.  Without it the
   orchestrator starts probing immediately; on first boot (initdb + creating five
   extra databases) postgres routinely takes > 10 s before accepting connections,
   causing spurious "unhealthy" marks that cascade to every dependent service.
"""

import pathlib
import stat

import yaml

REPO = pathlib.Path(__file__).parent.parent

COMPOSE_PYTHON = REPO / "docker-compose.python.yml"
COMPOSE_MAIN = REPO / "docker-compose.yml"
INIT_INFRA = REPO / "infrastructure" / "postgres" / "init-databases.sh"
INIT_SCRIPTS = REPO / "scripts" / "init-databases.sh"
GITATTRIBUTES = REPO / ".gitattributes"

REQUIRED_DATABASES = [
    "auth_db",
    "purchase_db",
    "payment_db",
    "chat_db",
    "reputation_db",
]


def _parse_duration(value) -> float:
    """Parse a docker-compose duration string (e.g. '30s', '1m') to seconds."""
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if s.endswith("ms"):
        return float(s[:-2]) / 1000.0
    if s.endswith("s"):
        return float(s[:-1])
    if s.endswith("m"):
        return float(s[:-1]) * 60
    if s.endswith("h"):
        return float(s[:-1]) * 3600
    return float(s)


class TestGitAttributesEnforcesLF:
    """A .gitattributes file must enforce LF line endings for shell scripts
    so Windows clients never check out .sh files with CRLF endings."""

    def test_gitattributes_exists(self):
        assert GITATTRIBUTES.exists(), (
            ".gitattributes is missing.  Without it, Windows git clients with "
            "autocrlf=true check out *.sh files with CRLF endings, which causes "
            "/bin/bash^M: bad interpreter errors inside Linux containers."
        )

    def test_gitattributes_covers_sh_files(self):
        text = GITATTRIBUTES.read_text()
        assert "*.sh" in text, (
            ".gitattributes must contain a rule for *.sh files to force LF "
            "line endings (e.g. '*.sh  text eol=lf')."
        )

    def test_gitattributes_sh_rule_uses_eol_lf(self):
        for line in GITATTRIBUTES.read_text().splitlines():
            if "*.sh" in line and not line.strip().startswith("#"):
                assert "eol=lf" in line, (
                    f"The *.sh rule in .gitattributes must include 'eol=lf'. "
                    f"Found: {line!r}"
                )
                return
        raise AssertionError(
            "No non-comment *.sh rule with 'eol=lf' found in .gitattributes."
        )

    def test_gitattributes_has_no_crlf(self):
        raw = GITATTRIBUTES.read_bytes()
        assert b"\r\n" not in raw, (
            ".gitattributes itself must not have CRLF line endings."
        )


class TestInfraPostgresInitScript:
    """infrastructure/postgres/init-databases.sh must be executable and
    create all databases needed by the microservices stack."""

    def test_init_script_exists(self):
        assert INIT_INFRA.exists(), (
            f"{INIT_INFRA} is missing — docker-compose.yml references it."
        )

    def test_init_script_is_executable(self):
        mode = INIT_INFRA.stat().st_mode
        assert mode & stat.S_IXUSR, (
            f"{INIT_INFRA.name} must have the user-executable bit set so the "
            f"postgres docker-entrypoint runs it instead of sourcing it. "
            f"Current mode: {oct(mode & 0o777)}."
        )
        assert mode & stat.S_IXOTH, (
            f"{INIT_INFRA.name} should be world-executable so it works under "
            f"any UID the postgres image uses. "
            f"Current mode: {oct(mode & 0o777)}."
        )

    def test_init_script_has_no_crlf(self):
        raw = INIT_INFRA.read_bytes()
        assert b"\r\n" not in raw, (
            f"{INIT_INFRA.name} has CRLF line endings — this causes "
            f"'/bin/bash^M: bad interpreter' inside Alpine-based containers."
        )

    def test_init_script_uses_alpine_available_shell(self):
        first_line = INIT_INFRA.read_bytes().split(b"\n")[0]
        assert first_line == b"#!/bin/sh", (
            f"{INIT_INFRA.relative_to(REPO)} is mounted into postgres:16-alpine, "
            "which includes /bin/sh but not bash. Use '#!/bin/sh' so the "
            "PostgreSQL init script can run in the Alpine image."
        )

    def test_init_script_creates_all_required_databases(self):
        text = INIT_INFRA.read_text()
        for db in REQUIRED_DATABASES:
            assert db in text, (
                f"{INIT_INFRA.name} must create {db!r} but it does not appear "
                f"in the script.  All five extra databases are needed by the "
                f"microservices stack: {REQUIRED_DATABASES}."
            )


class TestScriptsInitScript:
    """scripts/init-databases.sh (used by docker-compose.python.yml) must also
    be free of CRLF and executable."""

    def test_scripts_init_script_has_no_crlf(self):
        raw = INIT_SCRIPTS.read_bytes()
        assert b"\r\n" not in raw, (
            f"{INIT_SCRIPTS.name} has CRLF line endings — this causes "
            f"'/bin/bash^M: bad interpreter' inside Alpine-based containers."
        )

    def test_scripts_init_script_is_executable(self):
        mode = INIT_SCRIPTS.stat().st_mode
        assert mode & stat.S_IXUSR, (
            f"{INIT_SCRIPTS.name} must have the user-executable bit. "
            f"Current mode: {oct(mode & 0o777)}."
        )


class TestMainComposePostgresHealthcheck:
    """docker-compose.yml postgres healthcheck must be robust enough to survive
    first-boot initialization (initdb + creating five extra databases)."""

    def _load(self):
        with open(COMPOSE_MAIN) as f:
            return yaml.safe_load(f)

    def test_postgres_has_healthcheck(self):
        compose = self._load()
        assert "healthcheck" in compose["services"]["postgres"], (
            "docker-compose.yml postgres service must define a healthcheck."
        )

    def test_postgres_start_period_is_at_least_30s(self):
        hc = self._load()["services"]["postgres"]["healthcheck"]
        start_period = hc.get("start_period", "0s")
        seconds = _parse_duration(start_period)
        assert seconds >= 30, (
            f"docker-compose.yml postgres healthcheck.start_period must be at "
            f"least 30s to cover first-boot init. Currently: {start_period}."
        )

    def test_postgres_retries_grant_at_least_100s_after_start_period(self):
        hc = self._load()["services"]["postgres"]["healthcheck"]
        retries = int(hc.get("retries", 1))
        interval_s = _parse_duration(hc.get("interval", "30s"))
        window = retries * interval_s
        assert window >= 100, (
            f"docker-compose.yml postgres healthcheck retries * interval = "
            f"{window}s; must be ≥ 100s. Currently retries={retries}, "
            f"interval={hc.get('interval')}."
        )

    def test_postgres_healthcheck_uses_pg_isready(self):
        hc = self._load()["services"]["postgres"]["healthcheck"]
        test_cmd = hc["test"]
        cmd_str = " ".join(test_cmd) if isinstance(test_cmd, list) else str(test_cmd)
        assert "pg_isready" in cmd_str, (
            f"postgres healthcheck must use pg_isready; got: {cmd_str}"
        )


class TestAllShellScriptsHaveNoEmbeddedCRLF:
    """Every shell script in the repo must be free of CRLF line endings.
    This is a belt-and-suspenders check: .gitattributes prevents new
    violations from being committed, this test catches any that slip through."""

    SHELL_FILES = [
        REPO / "scripts" / "init-databases.sh",
        REPO / "infrastructure" / "postgres" / "init-databases.sh",
        REPO / "infrastructure" / "nginx" / "docker-entrypoint.sh",
        REPO / "core" / "entrypoint.sh",
        REPO / "services" / "purchase-service" / "entrypoint.sh",
    ]

    def test_no_crlf_in_shell_scripts(self):
        bad = []
        for path in self.SHELL_FILES:
            if path.exists() and b"\r\n" in path.read_bytes():
                bad.append(str(path.relative_to(REPO)))
        assert not bad, (
            f"These shell scripts have CRLF line endings and will fail with "
            f"'/bin/bash^M: bad interpreter' inside Alpine containers:\n"
            + "\n".join(f"  {p}" for p in bad)
        )
