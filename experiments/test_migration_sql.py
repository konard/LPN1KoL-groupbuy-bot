"""Syntax-check the migration SQL using pglast (libpg_query)."""

import sys
from pathlib import Path

import pglast

# Load db.py and extract MIGRATIONS by importing it
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core-fastapi"))

# Avoid importing dependencies (asyncpg, etc.) by reading the file directly.
db_path = Path(__file__).resolve().parent.parent / "core-fastapi" / "app" / "db.py"
src = db_path.read_text()

# Find the MIGRATIONS list start and grab the first migration string (000)
start = src.index("MIGRATIONS = [")
# Find first triple-quoted string after that
first_quote = src.index('"""', start)
end_quote = src.index('"""', first_quote + 3)
migration_000 = src[first_quote + 3 : end_quote]

print(f"Migration 000 length: {len(migration_000)} chars")
print(f"First 200 chars: {migration_000[:200]}")

# Parse it.
try:
    tree = pglast.parse_sql(migration_000)
    print(f"\n✓ Parsed OK: {len(tree)} top-level statements")
    for i, stmt in enumerate(tree):
        # Get statement type
        stmt_type = type(stmt.stmt).__name__ if stmt.stmt else "unknown"
        print(f"  [{i}] {stmt_type}")
except pglast.parser.ParseError as e:
    print(f"\n✗ Parse error: {e}")
    sys.exit(1)
