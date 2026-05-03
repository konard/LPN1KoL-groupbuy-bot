"""
Tests for issue #150: docker-compose.python.yml init-databases.sh failure
("/bin/bash^M: bad interpreter") and downstream postgres "skipping
initialization" message.

Previous PRs (#139 / #143 / #145 / #147) addressed:
  - .gitattributes enforcing LF for *.sh
  - executable bits on init-databases.sh
  - :ro mount of init-databases.sh
  - postgres healthcheck start_period >= 30s for first-boot init

This issue (#150) explicitly names docker-compose.python.yml as the failing
compose file, but our CI (.github/workflows/ci.yml) historically did NOT run
`docker compose -f docker-compose.python.yml config --quiet`, so a regression
in that file would not have been caught. It also did not run pytest, so the
prior issue tests were never executed in CI.

This test module locks in the prevention layer:

  1. docker-compose.python.yml is structurally valid (parses, has the postgres
     service with the right healthcheck, mount, and dependency wiring).
  2. The init script mounted by docker-compose.python.yml exists with LF
     endings and the executable bit.
  3. CI explicitly validates docker-compose.python.yml (the file from the
     issue logs) and the other previously-unvalidated compose files.
  4. CI runs the docker-compose / shell-script regression tests so
     regressions surface on PRs instead of in production logs.
"""

from __future__ import annotations

import pathlib
import stat

import yaml

REPO = pathlib.Path(__file__).parent.parent

COMPOSE_PYTHON = REPO / "docker-compose.python.yml"
INIT_SCRIPT = REPO / "scripts" / "init-databases.sh"
CI_WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"


def _parse_duration(value) -> float:
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


def _load_python_compose() -> dict:
    with open(COMPOSE_PYTHON) as f:
        return yaml.safe_load(f)


class TestPythonComposePostgresService:
    """The postgres service in docker-compose.python.yml — the file named in the
    issue logs — must be configured so init-databases.sh can succeed on first
    boot and so the orchestrator does not mark it unhealthy prematurely."""

    def test_compose_file_exists(self):
        assert COMPOSE_PYTHON.exists(), (
            f"{COMPOSE_PYTHON.relative_to(REPO)} is missing — issue #150 logs "
            "reference it directly."
        )

    def test_postgres_service_present(self):
        compose = _load_python_compose()
        assert "postgres" in compose["services"], (
            "docker-compose.python.yml must define a 'postgres' service."
        )

    def test_postgres_mounts_init_script_readonly(self):
        postgres = _load_python_compose()["services"]["postgres"]
        volumes = postgres.get("volumes", [])
        init_mounts = [v for v in volumes if "init-databases.sh" in v]
        assert init_mounts, (
            "docker-compose.python.yml postgres must mount scripts/"
            "init-databases.sh into /docker-entrypoint-initdb.d/."
        )
        for mount in init_mounts:
            assert mount.endswith(":ro"), (
                f"init-databases.sh must be mounted read-only (`:ro`) so "
                f"postgres cannot rewrite or chmod it. Found: {mount!r}"
            )
            assert "/docker-entrypoint-initdb.d/" in mount, (
                f"init-databases.sh must be mounted under "
                f"/docker-entrypoint-initdb.d/. Found: {mount!r}"
            )

    def test_postgres_healthcheck_start_period_is_at_least_30s(self):
        hc = _load_python_compose()["services"]["postgres"]["healthcheck"]
        seconds = _parse_duration(hc.get("start_period", "0s"))
        assert seconds >= 30, (
            f"docker-compose.python.yml postgres start_period must be >= 30s "
            f"to cover first-boot initdb + creating five extra databases. "
            f"Currently: {hc.get('start_period')}."
        )

    def test_postgres_healthcheck_total_grace_at_least_100s(self):
        hc = _load_python_compose()["services"]["postgres"]["healthcheck"]
        retries = int(hc.get("retries", 1))
        interval_s = _parse_duration(hc.get("interval", "30s"))
        window = retries * interval_s
        assert window >= 100, (
            f"docker-compose.python.yml postgres retries * interval = {window}s, "
            f"must be >= 100s. retries={retries}, interval={hc.get('interval')}."
        )


class TestPythonComposeInitScriptOnDisk:
    """The init script mounted by docker-compose.python.yml must be LF-only and
    executable, otherwise the container fails with /bin/bash^M: bad interpreter
    or the entrypoint sources it under `set -e`."""

    def test_init_script_exists(self):
        assert INIT_SCRIPT.exists(), (
            f"{INIT_SCRIPT.relative_to(REPO)} is missing."
        )

    def test_init_script_has_no_crlf(self):
        raw = INIT_SCRIPT.read_bytes()
        assert b"\r\n" not in raw, (
            f"{INIT_SCRIPT.relative_to(REPO)} has CRLF line endings — "
            "this is exactly the failure shown in issue #150 logs "
            "('/bin/bash^M: bad interpreter')."
        )

    def test_init_script_is_executable(self):
        mode = INIT_SCRIPT.stat().st_mode
        assert mode & stat.S_IXUSR, (
            f"{INIT_SCRIPT.relative_to(REPO)} must have the user-executable bit "
            f"so the postgres entrypoint runs it instead of sourcing it. "
            f"Current mode: {oct(mode & 0o777)}."
        )
        assert mode & stat.S_IXOTH, (
            f"{INIT_SCRIPT.relative_to(REPO)} should be world-executable so it "
            f"runs under any UID. Current mode: {oct(mode & 0o777)}."
        )


class TestCiValidatesPythonCompose:
    """CI must validate docker-compose.python.yml. Without this step a future
    edit to the file from the issue logs could break it without anyone noticing
    until users run docker compose up locally."""

    def test_ci_workflow_exists(self):
        assert CI_WORKFLOW.exists(), (
            f"{CI_WORKFLOW.relative_to(REPO)} is missing — without CI, "
            "regressions in compose files are not caught."
        )

    def test_ci_validates_python_compose(self):
        text = CI_WORKFLOW.read_text()
        assert "docker-compose.python.yml" in text, (
            "CI workflow must validate docker-compose.python.yml — the file "
            "named in issue #150 logs. Add a 'docker compose -f "
            "docker-compose.python.yml config --quiet' step."
        )

    def test_ci_runs_compose_regression_tests(self):
        text = CI_WORKFLOW.read_text()
        assert "pytest" in text, (
            "CI workflow must run pytest so the docker-compose regression "
            "tests (test_issue_137_*, test_issue_139_*, test_issue_143_*, "
            "test_issue_145_*, test_issue_147_*, test_issue_150_*) actually "
            "execute on every PR."
        )

    def test_ci_guards_against_crlf_in_shell_scripts(self):
        text = CI_WORKFLOW.read_text()
        # Either an explicit grep guard or running pytest covers this; assert
        # at least one mechanism exists.
        has_grep_guard = "find" in text and ".sh" in text and "\\r" in text
        has_pytest = "pytest" in text
        assert has_grep_guard or has_pytest, (
            "CI must guard against CRLF in shell scripts — either via an "
            "explicit `find ... | xargs grep -l $'\\r'` step or by running "
            "the pytest regression suite."
        )
