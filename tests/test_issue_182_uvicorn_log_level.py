"""
Tests for issue #182 fix: uvicorn --log-level rejects uppercase values.

Error observed:
  Error: Invalid value for '--log-level': 'INFO' is not one of
  'critical', 'error', 'warning', 'info', 'debug', 'trace'.

Root cause:
  1. docker-compose.yml sets LOG_LEVEL=${LOG_LEVEL:-INFO} (uppercase default).
  2. core-fastapi/Dockerfile CMD passed ${LOG_LEVEL:-info} directly to uvicorn
     without lowercasing, so when LOG_LEVEL=INFO the container failed to start.
  3. core-fastapi/app/config.py stored log_level as uppercase (.upper()), which
     would also cause uvicorn.run() to fail when called via `python main.py`.

Fix:
  1. Dockerfile CMD now pipes through `tr '[:upper:]' '[:lower:]'`.
  2. config.py now calls .lower() so the in-process uvicorn.run() path also works.
"""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
CORE_FASTAPI_DIR = os.path.join(ROOT, "core-fastapi")
DOCKERFILE_PATH = os.path.join(CORE_FASTAPI_DIR, "Dockerfile")
CONFIG_PATH = os.path.join(CORE_FASTAPI_DIR, "app", "config.py")

UVICORN_VALID_LEVELS = {"critical", "error", "warning", "info", "debug", "trace"}


class TestCoreDockerfileLoglevel:
    """Verify core-fastapi/Dockerfile passes a lowercase log-level to uvicorn."""

    def _read_dockerfile(self):
        with open(DOCKERFILE_PATH) as f:
            return f.read()

    def test_dockerfile_exists(self):
        assert os.path.isfile(DOCKERFILE_PATH), (
            f"core-fastapi/Dockerfile not found at {DOCKERFILE_PATH}"
        )

    def test_cmd_lowercases_log_level(self):
        """
        The CMD in core-fastapi/Dockerfile must ensure LOG_LEVEL is lowercased
        before it is passed to uvicorn --log-level, because uvicorn only accepts
        lowercase values ('critical', 'error', 'warning', 'info', 'debug', 'trace').
        """
        content = self._read_dockerfile()
        # Must have a CMD that uses tr or similar to lowercase the value
        assert re.search(r"tr\s+'\[:upper:\]'\s+'\[:lower:\]'", content) or \
               re.search(r"\$\(.*lower.*LOG_LEVEL.*\)", content) or \
               re.search(r"tr\s+A-Z\s+a-z", content), (
            "core-fastapi/Dockerfile CMD must lowercase LOG_LEVEL before passing "
            "it to uvicorn --log-level. Uvicorn rejects uppercase values. "
            "Expected a shell expression like: "
            "$(echo ${LOG_LEVEL:-info} | tr '[:upper:]' '[:lower:]')"
        )

    def test_cmd_does_not_pass_uppercase_log_level_directly(self):
        """
        The CMD must not pass ${LOG_LEVEL} directly to --log-level without
        a lowercase conversion.
        """
        content = self._read_dockerfile()
        # Find the CMD line
        cmd_lines = [l.strip() for l in content.splitlines() if l.strip().startswith("CMD")]
        assert cmd_lines, "Dockerfile must have a CMD instruction"
        cmd = cmd_lines[-1]
        # Should not have a bare ${LOG_LEVEL} passed straight to --log-level
        assert not re.search(r"--log-level\s+\$\{LOG_LEVEL[^}]*\}\s*\"", cmd), (
            "CMD must not pass ${LOG_LEVEL} directly to --log-level without "
            "lowercasing. Add: $(echo ${LOG_LEVEL:-info} | tr '[:upper:]' '[:lower:]')"
        )


class TestCoreConfigLoglevel:
    """Verify core-fastapi/app/config.py stores log_level in lowercase."""

    def _read_config(self):
        with open(CONFIG_PATH) as f:
            return f.read()

    def test_config_exists(self):
        assert os.path.isfile(CONFIG_PATH), (
            f"core-fastapi/app/config.py not found at {CONFIG_PATH}"
        )

    def test_config_lowercases_log_level(self):
        """
        Settings.log_level must call .lower() (not .upper()) so that when
        uvicorn.run() is called directly (e.g. `python main.py`), it receives
        a valid lowercase log-level string.
        """
        content = self._read_config()
        # Must use .lower() for log_level
        assert re.search(r'log_level.*\.lower\(\)', content), (
            "core-fastapi/app/config.py Settings.log_level must call .lower() "
            "to ensure the value is lowercase. Uvicorn only accepts lowercase "
            "log-level values: 'critical', 'error', 'warning', 'info', 'debug', 'trace'."
        )

    def test_config_does_not_uppercase_log_level(self):
        """
        Settings.log_level must not call .upper(), as that would produce a
        value that uvicorn rejects.
        """
        content = self._read_config()
        assert not re.search(r'log_level.*\.upper\(\)', content), (
            "core-fastapi/app/config.py Settings.log_level must not call .upper(). "
            "Uvicorn only accepts lowercase log-level values."
        )
