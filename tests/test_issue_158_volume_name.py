"""
Tests for issue #158 fix:
  "password authentication failed for user postgres" when running
  docker compose -f docker-compose.unified.yml up -d

Root cause: setup-prod.sh was using a hardcoded VOLUME_NAME="groupbuy_postgres_data"
while Docker Compose derives the volume name from the project directory name.
When the working directory is "groupbuy-bot", Docker creates:
  groupbuy-bot_postgres_data
but the script tried to inspect/remove "groupbuy_postgres_data" — a mismatch
that meant the stale-volume detection was silently skipped, and the old volume
(initialized with a different password) was reused, causing authentication failure.

Fix: setup-prod.sh now computes the project name dynamically from the working
directory basename using the same transformation Docker Compose applies.
"""
import re
import subprocess
import os
import pytest


def docker_compose_project_name(directory_name: str) -> str:
    """
    Replicate Docker Compose's project name derivation from a directory name.
    Docker lowercases the basename and replaces non-alphanumeric chars with hyphens.
    This matches the transformation in setup-prod.sh:
        PROJECT_NAME=$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g')
    """
    lowered = directory_name.lower()
    return re.sub(r'[^a-z0-9]', '-', lowered)


def expected_volume_name(directory_name: str) -> str:
    """Return the expected Docker volume name for postgres_data."""
    return f"{docker_compose_project_name(directory_name)}_postgres_data"


class TestVolumeNameDerivation:
    """Verify the volume name derivation logic matches Docker Compose behaviour."""

    def test_standard_repo_name(self):
        """groupbuy-bot directory → groupbuy-bot_postgres_data."""
        assert expected_volume_name("groupbuy-bot") == "groupbuy-bot_postgres_data"

    def test_uppercase_directory(self):
        """Uppercase chars are lowercased."""
        assert expected_volume_name("GroupBuy-Bot") == "groupbuy-bot_postgres_data"

    def test_underscore_directory(self):
        """Underscores become hyphens (non-alphanumeric replacement)."""
        assert expected_volume_name("groupbuy_bot") == "groupbuy-bot_postgres_data"

    def test_hardcoded_name_was_wrong(self):
        """
        Regression: the old hardcoded VOLUME_NAME="groupbuy_postgres_data" does NOT
        match the volume Docker actually creates when running from the 'groupbuy-bot'
        directory — demonstrating the original bug.
        """
        old_hardcoded = "groupbuy_postgres_data"
        actual = expected_volume_name("groupbuy-bot")
        assert old_hardcoded != actual, (
            f"Old hardcoded name '{old_hardcoded}' should differ from "
            f"Docker-derived name '{actual}' — the fix is needed."
        )

    def test_setup_script_uses_dynamic_volume_name(self):
        """
        setup-prod.sh must compute VOLUME_NAME dynamically, not use a hardcoded value.
        """
        script_path = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "setup-prod.sh"
        )
        with open(script_path) as f:
            content = f.read()

        # Must NOT have the old hardcoded wrong value
        assert 'VOLUME_NAME="groupbuy_postgres_data"' not in content, (
            "setup-prod.sh still contains hardcoded VOLUME_NAME='groupbuy_postgres_data'. "
            "This is the bug from issue #158 — the script fails to detect the stale "
            "postgres volume because the name doesn't match what Docker actually created."
        )

        # Must derive project name dynamically from the working directory
        assert 'PROJECT_NAME=$(basename "$(pwd)"' in content, (
            "setup-prod.sh must derive PROJECT_NAME from the working directory basename "
            "to correctly compute the Docker Compose volume name."
        )

        # VOLUME_NAME must be built from PROJECT_NAME
        assert 'VOLUME_NAME="${PROJECT_NAME}_postgres_data"' in content, (
            "setup-prod.sh must set VOLUME_NAME as '${PROJECT_NAME}_postgres_data' "
            "to match the volume name Docker Compose actually creates."
        )

    def test_setup_script_warning_mentions_password_mismatch(self):
        """
        The stale-volume warning in setup-prod.sh must explain that the
        DB_PASSWORD in .env must match what was used to initialise the volume.
        """
        script_path = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "setup-prod.sh"
        )
        with open(script_path) as f:
            content = f.read()

        assert "password authentication failed" in content, (
            "setup-prod.sh should mention 'password authentication failed' in its "
            "stale-volume warning so users understand why the error occurs."
        )
