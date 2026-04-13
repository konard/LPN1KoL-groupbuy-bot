"""
Tests for issue #212 fixes — three bugs reported from production logs:

  1. Django Admin DisallowedHost — '95.81.123.52' rejected because
     docker-compose.prod.yml ALLOWED_HOSTS only included ${DOMAIN} and
     ${EXTERNAL_IP:-} (empty fallback).  Fix: hard-code 95.81.123.52 as
     a default fallback so it is always present.

  2. purchase-service Scheduler error — relation "voting_sessions" does not
     exist.  Cause: the Dockerfile CMD starts the app without running the SQL
     migrations in src/migrations/*.  Fix: add an entrypoint.sh that runs all
     migration files via psql before launching node.

  3. Rust core-api JSON deserialisation error — POST /api/chat/messages/
     returned 400 "missing field `procurement`".  Cause: the React frontend
     sent keys `procurement_id` and `user_id` but the Rust CreateMessage
     struct expects `procurement` and `user`.  Same mismatch for GET query
     params: frontend used `procurement_id=` / `user_id=` but the Rust
     MessageQuery / NotificationQuery structs use `procurement` / `user`.
     Fix: align frontend field names with the Rust API contract.
"""
import os
import yaml

ROOT = os.path.join(os.path.dirname(__file__), "..")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_prod_compose():
    path = os.path.join(ROOT, "docker-compose.prod.yml")
    with open(path) as f:
        return yaml.safe_load(f)


def parse_env_var(env_list, key):
    """Return the value string for KEY=VALUE entries, or None."""
    for entry in env_list:
        if isinstance(entry, str) and entry.startswith(key + "="):
            return entry[len(key) + 1:]
        if isinstance(entry, dict) and key in entry:
            return str(entry[key])
    return None


def read_file(relpath):
    with open(os.path.join(ROOT, relpath)) as f:
        return f.read()


# ===========================================================================
# Fix 1 — docker-compose.prod.yml ALLOWED_HOSTS includes 95.81.123.52
# ===========================================================================

class TestProdAllowedHostsExternalIp:
    """
    docker-compose.prod.yml ALLOWED_HOSTS must include 95.81.123.52 so
    Django does not reject requests from the external server IP.
    """

    def test_allowed_hosts_includes_external_ip(self):
        compose = load_prod_compose()
        env = compose["services"]["django-admin"].get("environment", [])
        value = parse_env_var(env, "ALLOWED_HOSTS")
        assert value is not None, "ALLOWED_HOSTS must be set in django-admin service"
        assert "95.81.123.52" in value, (
            f"docker-compose.prod.yml ALLOWED_HOSTS='{value}' must include "
            f"'95.81.123.52' so Django accepts requests from the external IP."
        )

    def test_allowed_hosts_no_trailing_empty_entry(self):
        """
        When EXTERNAL_IP env var is unset, the old value '${EXTERNAL_IP:-}'
        produced a trailing comma that Django would parse as an empty-string
        host, allowing any host.  The new default must not be empty.
        """
        compose = load_prod_compose()
        env = compose["services"]["django-admin"].get("environment", [])
        value = parse_env_var(env, "ALLOWED_HOSTS")
        assert value is not None
        # Expand the value as if no env vars are set (replace ${VAR:-default} with default)
        import re
        expanded = re.sub(r'\$\{[^}]+:-([^}]*)\}', r'\1', value)
        hosts = [h.strip() for h in expanded.split(",") if h.strip()]
        assert "95.81.123.52" in hosts, (
            f"After expanding env-var defaults, ALLOWED_HOSTS must contain "
            f"'95.81.123.52'.  Expanded value: '{expanded}'"
        )


# ===========================================================================
# Fix 2 — purchase-service Dockerfile runs migrations before starting app
# ===========================================================================

class TestPurchaseServiceDockerfileRunsMigrations:
    """
    The purchase-service Dockerfile must run SQL migrations before the
    application starts, so that voting_sessions and related tables exist.
    """

    def test_dockerfile_copies_migrations(self):
        dockerfile = read_file("services/purchase-service/Dockerfile")
        assert "migrations" in dockerfile, (
            "Dockerfile must copy the migrations directory into the image "
            "so they can be applied at startup."
        )

    def test_dockerfile_has_entrypoint_or_migration_command(self):
        dockerfile = read_file("services/purchase-service/Dockerfile")
        has_entrypoint = "entrypoint" in dockerfile.lower()
        has_psql = "psql" in dockerfile or "migrate" in dockerfile.lower()
        assert has_entrypoint or has_psql, (
            "Dockerfile must use an entrypoint script or include a migration "
            "command (psql/migrate) so the DB schema is created before the "
            "NestJS application starts."
        )

    def test_entrypoint_script_runs_migrations(self):
        entrypoint_path = os.path.join(ROOT, "services/purchase-service/entrypoint.sh")
        assert os.path.exists(entrypoint_path), (
            "services/purchase-service/entrypoint.sh must exist to run "
            "migrations before starting the application."
        )
        content = open(entrypoint_path).read()
        assert "psql" in content or "migrate" in content.lower(), (
            "entrypoint.sh must call psql (or a migration tool) to apply "
            "SQL migrations before starting node."
        )
        assert "node" in content or "npm" in content, (
            "entrypoint.sh must start the Node.js application after migrations."
        )

    def test_migration_files_exist(self):
        migrations_dir = os.path.join(
            ROOT, "services/purchase-service/src/migrations"
        )
        assert os.path.isdir(migrations_dir), (
            "services/purchase-service/src/migrations/ must exist and contain "
            "the SQL migration files."
        )
        sql_files = [f for f in os.listdir(migrations_dir) if f.endswith(".sql")]
        assert len(sql_files) >= 1, (
            "At least one .sql migration file must exist in "
            "services/purchase-service/src/migrations/"
        )

    def test_migration_creates_voting_sessions_table(self):
        migrations_dir = os.path.join(
            ROOT, "services/purchase-service/src/migrations"
        )
        all_sql = ""
        for fname in sorted(os.listdir(migrations_dir)):
            if fname.endswith(".sql"):
                with open(os.path.join(migrations_dir, fname)) as f:
                    all_sql += f.read()
        assert "voting_sessions" in all_sql, (
            "SQL migrations must create the 'voting_sessions' table so the "
            "Scheduler no longer throws 'relation does not exist'."
        )


# ===========================================================================
# Fix 3 — Frontend uses correct field names for Rust chat API
# ===========================================================================

class TestFrontendChatApiFieldNames:
    """
    The React frontend must use the field names expected by the Rust core API:
      - GET /api/chat/messages/?procurement=<id>   (not procurement_id)
      - POST /api/chat/messages/ body: {procurement: ..., user: ...}
        (not procurement_id / user_id)
      - GET /api/chat/notifications/?user=<id>     (not user_id)
    """

    def _read_api_js(self):
        return read_file("frontend-react/src/services/api.js")

    def _read_store_js(self):
        return read_file("frontend-react/src/store/useStore.js")

    # -- GET messages query param --

    def test_get_messages_uses_procurement_param(self):
        src = self._read_api_js()
        assert "procurement=" in src or "procurement`" in src or "?procurement" in src, (
            "api.js getMessages() must use 'procurement' query param "
            "(not 'procurement_id') to match the Rust MessageQuery struct."
        )

    def test_get_messages_does_not_use_procurement_id_param(self):
        src = self._read_api_js()
        # Allow procurement_id only in comments, not in actual URL construction
        import re
        url_uses = re.findall(r'procurement_id=\$\{', src) + re.findall(r'procurement_id=\$', src)
        assert len(url_uses) == 0, (
            "api.js getMessages() must not use 'procurement_id=' in the URL; "
            "use 'procurement=' instead."
        )

    # -- GET notifications query param --

    def test_get_notifications_uses_user_param(self):
        src = self._read_api_js()
        assert "notifications/?user=" in src or "notifications/?user`" in src or "?user=${" in src, (
            "api.js getNotifications() must use 'user' query param "
            "(not 'user_id') to match the Rust NotificationQuery struct."
        )

    def test_get_notifications_does_not_use_user_id_param(self):
        src = self._read_api_js()
        import re
        # Find notification URL construction with user_id
        matches = re.findall(r'notifications/\?user_id=', src)
        assert len(matches) == 0, (
            "api.js getNotifications() must not use 'user_id=' in the URL; "
            "use 'user=' instead."
        )

    # -- POST message body --

    def test_send_message_uses_procurement_field(self):
        src = self._read_store_js()
        assert "procurement:" in src, (
            "useStore.js sendMessage() must send field 'procurement' "
            "(not 'procurement_id') to match the Rust CreateMessage struct."
        )

    def test_send_message_does_not_use_procurement_id_field(self):
        src = self._read_store_js()
        assert "procurement_id:" not in src, (
            "useStore.js sendMessage() must not use 'procurement_id:'; "
            "use 'procurement:' instead."
        )

    def test_send_message_uses_user_field(self):
        src = self._read_store_js()
        # Ensure the sendMessage call uses `user:` not `user_id:`
        # Allow user_id elsewhere (like login), only check sendMessage context
        import re
        send_block = re.search(
            r'sendMessage.*?api\.sendMessage\(\{(.*?)\}\)', src, re.DOTALL
        )
        assert send_block is not None, (
            "useStore.js must contain a sendMessage call with api.sendMessage()"
        )
        block = send_block.group(1)
        assert "user_id:" not in block, (
            "sendMessage payload must use 'user:' not 'user_id:' "
            "to match the Rust CreateMessage struct."
        )
        assert "user:" in block, (
            "sendMessage payload must include 'user:' field "
            "to match the Rust CreateMessage struct."
        )
