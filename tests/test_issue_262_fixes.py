"""
Tests for issue #262 — 404 on /api/users/by_email/ and /api/users/{id}/balance/.

Root causes and fixes:

1. core-fastapi POST /api/users/ returned 400 when auth-service re-synced a
   user whose UUID already existed as the primary key with a *different*
   (platform, platform_user_id).  The ON CONFLICT clause only targeted
   (platform, platform_user_id) so the duplicate-PK violation was not caught
   and was re-raised as a 400 to the caller.
   Fix: when body.id is supplied, use ON CONFLICT (id) DO UPDATE instead, so
   the row is always upserted by UUID.

2. frontend useStore.js — restoreUserFromToken() parsed coreUserId from
   localStorage with parseInt(..., 10).  Since core now uses UUID primary keys
   (strings), parseInt on "8a7287e1-..." produces NaN, which falls back to
   null.  After a page reload user.coreId is null, so calls like
   /api/users/{coreId}/balance/ use user.id (auth UUID) which may not be in
   core, returning 404.
   Fix: store / restore coreUserId as a plain string, no parseInt conversion.
"""

import os
import re

import pytest


ROOT = os.path.join(os.path.dirname(__file__), "..")

CORE_USERS_ROUTER = os.path.join(ROOT, "core-fastapi", "app", "routers", "users.py")
STORE_JS = os.path.join(ROOT, "frontend-react", "src", "store", "useStore.js")


def read(path: str) -> str:
    with open(path) as f:
        return f.read()


class TestCreateUserUpsertOnId:
    """POST /api/users/ must upsert on id (PK) when body.id is provided."""

    def test_when_id_provided_conflict_target_is_id(self):
        """When body.id is not None, the ON CONFLICT target must be (id) so
        a duplicate PK coming from auth-service re-sync does not raise a 400.

        Previously: ON CONFLICT (platform, platform_user_id) — didn't cover PK.
        Required:   ON CONFLICT (id) DO UPDATE — covers PK re-sync."""
        src = read(CORE_USERS_ROUTER)
        # The id-branch must use ON CONFLICT (id) DO UPDATE
        id_branch = re.search(
            r"if body\.id is not None:(.*?)else:",
            src,
            re.S,
        )
        assert id_branch, "create_user must have an `if body.id is not None:` branch"
        branch_body = id_branch.group(1)
        assert "ON CONFLICT (id) DO UPDATE" in branch_body, (
            "When body.id is provided, the INSERT must conflict on (id) so "
            "a re-sync of the same UUID is idempotent."
        )

    def test_id_conflict_update_sets_email_and_phone(self):
        """The ON CONFLICT (id) DO UPDATE must refresh email and phone so
        GET /api/users/by_email/ and GET /api/users/{id}/balance/ find the
        correct record after a re-sync."""
        src = read(CORE_USERS_ROUTER)
        id_branch = re.search(
            r"ON CONFLICT \(id\) DO UPDATE SET(.*?)RETURNING \*",
            src,
            re.S,
        )
        assert id_branch, "ON CONFLICT (id) DO UPDATE ... RETURNING * not found"
        update_body = id_branch.group(1)
        assert "email=EXCLUDED.email" in update_body, (
            "ON CONFLICT (id) DO UPDATE must set email so by_email lookups work"
        )
        assert "phone=EXCLUDED.phone" in update_body, (
            "ON CONFLICT (id) DO UPDATE must set phone so phone lookups work"
        )

    def test_no_id_branch_still_conflicts_on_platform_user_id(self):
        """When body.id is None (Telegram bot path), the upsert must still
        conflict on (platform, platform_user_id)."""
        src = read(CORE_USERS_ROUTER)
        assert "ON CONFLICT (platform, platform_user_id) DO UPDATE" in src, (
            "The else branch of create_user must still upsert on "
            "(platform, platform_user_id) for Telegram/VK bot callers."
        )


class TestStoreCoreIdNotParsedAsInt:
    """useStore.js must not parseInt() coreUserId from localStorage because
    core now returns UUID strings — parseInt on a UUID yields NaN."""

    def test_restore_user_does_not_call_parseInt_on_core_id(self):
        """restoreUserFromToken must not pass coreUserId through parseInt.

        Previously: coreId: coreId ? parseInt(coreId, 10) : null
        Required:   coreId: coreId || null   (preserve string UUID)"""
        src = read(STORE_JS)
        # Grab restoreUserFromToken body
        fn_match = re.search(
            r"function restoreUserFromToken\(\)\s*\{(.*?)\n\}",
            src,
            re.S,
        )
        assert fn_match, "restoreUserFromToken function not found in useStore.js"
        fn_body = fn_match.group(1)
        assert "parseInt" not in fn_body, (
            "restoreUserFromToken must not call parseInt on coreUserId — "
            "core uses UUID strings; parseInt('8a7287e1-...', 10) returns NaN "
            "and user.coreId becomes null after page reload, causing 404."
        )

    def test_core_id_preserved_as_string(self):
        """The restored coreId must come from localStorage directly (a string)
        without numeric conversion."""
        src = read(STORE_JS)
        fn_match = re.search(
            r"function restoreUserFromToken\(\)\s*\{(.*?)\n\}",
            src,
            re.S,
        )
        assert fn_match, "restoreUserFromToken function not found in useStore.js"
        fn_body = fn_match.group(1)
        # coreId should be set directly from the localStorage value
        assert re.search(r"coreId\s*:\s*coreId\s*([\|\?]|\|\|)", fn_body), (
            "restoreUserFromToken must set coreId directly from the "
            "localStorage string (e.g. `coreId: coreId || null`)"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
