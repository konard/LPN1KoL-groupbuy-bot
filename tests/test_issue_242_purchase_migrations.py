"""Regression coverage for issue #242.

The purchase-service container failed to start because two divergent schemas
were applied against the same database:

1. ``services/purchase-service/entrypoint.sh`` ran the SQL files in
   ``services/purchase-service/migrations/`` which create ``candidates`` and
   ``votes`` with a ``voting_session_id`` foreign key.
2. ``services/purchase-service/app.py`` then ran an inline ``MIGRATIONS``
   block in its FastAPI ``lifespan`` that defined the same tables with a
   ``session_id`` column and tried ``CREATE INDEX ... ON votes(session_id)``.

Because ``CREATE TABLE IF NOT EXISTS`` is a no-op on the already-created
table, the trailing ``CREATE INDEX`` referenced a column that did not exist
on the canonical schema, raising::

    asyncpg.exceptions.UndefinedColumnError: column "session_id" does not exist

The fix removes the redundant inline ``MIGRATIONS`` from ``app.py`` (the
entrypoint already provisions the schema) and aligns the endpoint SQL with
the canonical column names from the migration files.

These tests guard against re-introducing either side of the regression.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
PURCHASE = ROOT / "services" / "purchase-service"
APP_PY = PURCHASE / "app.py"
MIGRATIONS_DIR = PURCHASE / "migrations"
ENTRYPOINT = PURCHASE / "entrypoint.sh"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ─── Schema source of truth ───────────────────────────────────────────────────


def test_migration_files_use_voting_session_id():
    """Canonical migrations create candidates/votes with voting_session_id."""
    sql = _read(MIGRATIONS_DIR / "001_create_purchases.sql")
    assert "voting_session_id" in sql
    # And NOT the alternative "session_id" column name on candidates/votes
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("session_id") or stripped.startswith("session_id "):
            pytest.fail(
                f"Canonical migration defines a bare 'session_id' column: {line!r}"
            )


def test_entrypoint_runs_migration_files():
    """entrypoint.sh must apply the SQL files from migrations/."""
    sh = _read(ENTRYPOINT)
    assert "/app/migrations/" in sh
    assert "psql" in sh


# ─── app.py must not run a second, conflicting MIGRATIONS block ──────────────


def test_app_does_not_define_inline_migrations_constant():
    """The inline MIGRATIONS string in app.py was the source of the conflict.

    After the fix, there must not be a top-level ``MIGRATIONS = "..."`` block
    that gets executed in ``lifespan`` and clashes with the SQL files.
    """
    src = _read(APP_PY)
    assert not re.search(r"^MIGRATIONS\s*=\s*['\"]{3}", src, re.MULTILINE), (
        "app.py still defines an inline MIGRATIONS string; the entrypoint "
        "already applies SQL files from migrations/. Two sources of schema "
        "truth caused issue #242."
    )


def test_app_lifespan_does_not_execute_inline_migrations():
    """lifespan() must not run ``conn.execute(MIGRATIONS)``."""
    src = _read(APP_PY)
    assert "conn.execute(MIGRATIONS)" not in src, (
        "lifespan() still executes inline MIGRATIONS, which conflicts with "
        "the file-based migrations applied by entrypoint.sh."
    )


# ─── Endpoint SQL must match the canonical schema ─────────────────────────────


@pytest.mark.parametrize(
    "bad_column",
    [
        # candidates/votes use voting_session_id, not session_id
        "FROM votes WHERE session_id",
        "FROM candidates WHERE session_id",
        "INTO votes(session_id",
        "INTO candidates(session_id",
        # purchases uses min_participants / commission_percent, not the inline
        # MIGRATIONS aliases that caused drift
        "INTO purchases(organizer_id, title, description, category, min_quantity",
        "min_quantity, commission_pct",
        # voting_sessions uses winner_candidate_id, not winner_id
        "voting_sessions SET status=$1, winner_id=",
        "voting_sessions SET winner_id=",
    ],
)
def test_app_endpoints_do_not_reference_legacy_column_names(bad_column):
    src = _read(APP_PY)
    assert bad_column not in src, (
        f"app.py contains legacy column reference {bad_column!r}; this "
        "would fail against the canonical schema."
    )


def test_app_endpoints_use_canonical_column_names():
    """Spot-check that endpoint SQL targets the canonical columns."""
    src = _read(APP_PY)
    assert "voting_session_id" in src
    assert "min_participants" in src
    assert "commission_percent" in src


# ─── voting_sessions.closes_at must be provided on insert ─────────────────────


def test_start_voting_provides_closes_at():
    """voting_sessions.closes_at is NOT NULL in the canonical schema (001).

    The endpoint must supply a value or the INSERT raises NotNullViolation.
    """
    src = _read(APP_PY)
    assert "INSERT INTO voting_sessions" in src
    # Find the INSERT and verify closes_at is part of the column list
    m = re.search(r"INSERT INTO voting_sessions\s*\(([^)]+)\)", src)
    assert m, "Could not locate INSERT INTO voting_sessions statement"
    columns = m.group(1)
    assert "closes_at" in columns, (
        "start_voting must pass closes_at; the column is NOT NULL in the "
        "canonical migration but has no default."
    )


# ─── No duplicate migration in app.py ─────────────────────────────────────────


def test_no_create_table_in_app_py():
    """Schema DDL belongs in migrations/, never in app.py."""
    src = _read(APP_PY)
    assert "CREATE TABLE" not in src, (
        "app.py contains CREATE TABLE DDL; schema must live only in "
        "services/purchase-service/migrations/*.sql."
    )
