"""
Tests for issue #182 fix:
  "docker compose -f docker-compose.unified.yml up -d" on a 3 GB host causes:
  1. Kafka OutOfMemoryError: Java heap space (JVM heap must be bounded within
     the container memory limit).
  2. django-admin crash loop due to "relation 'users' already exists" when the
     database already contains tables from a previous run (--fake-initial must
     be used so that already-applied initial migrations are skipped).
  3. telegram-adapter exit 137 (OOM-killed) because 64 MB is not enough for a
     Python aiohttp/aiogram process.

Root causes and fixes:
  1. Kafka KAFKA_HEAP_OPTS must use asymmetric -Xms/-Xmx so the initial heap
     is small but the JVM is still capped below the container memory limit.
     The recommended setting for 256 M container: -Xmx128m -Xms64m.
  2. core/entrypoint.sh must run  migrate --fake-initial  (not bare migrate)
     so that migrations whose tables already exist are recorded as applied
     without trying to re-create those tables.
  3. telegram-adapter deploy.resources.limits.memory must be raised to at least
     128 M to avoid OOM-kills on Python aiohttp workers.
"""
import os
import re

import pytest
import yaml


ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_unified_compose():
    """Load docker-compose.unified.yml as a dict."""
    path = os.path.join(ROOT, "docker-compose.unified.yml")
    with open(path) as f:
        return yaml.safe_load(f)


def load_entrypoint():
    """Return the text of core/entrypoint.sh."""
    path = os.path.join(ROOT, "core", "entrypoint.sh")
    with open(path) as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1. Kafka heap configuration
# ---------------------------------------------------------------------------

class TestKafkaHeapOpts:
    """
    Kafka must have KAFKA_HEAP_OPTS set so the JVM heap is bounded below
    the container memory limit, preventing OutOfMemoryError: Java heap space
    on hosts with limited RAM (issue #182, log excerpt: java.lang.OutOfMemoryError:
    Java heap space).
    """

    def test_kafka_heap_opts_present(self):
        """KAFKA_HEAP_OPTS must be defined in the kafka service environment."""
        compose = load_unified_compose()
        kafka_env = compose["services"]["kafka"].get("environment", {})
        assert "KAFKA_HEAP_OPTS" in kafka_env, (
            "Kafka service must set KAFKA_HEAP_OPTS to bound JVM heap size. "
            "Without it the JVM uses up to 25 % of host RAM and causes "
            "OutOfMemoryError on 3 GB hosts."
        )

    def test_kafka_heap_opts_has_xmx(self):
        """KAFKA_HEAP_OPTS must include a -Xmx flag to cap maximum heap."""
        compose = load_unified_compose()
        heap_opts = compose["services"]["kafka"]["environment"]["KAFKA_HEAP_OPTS"]
        assert re.search(r"-Xmx\d+[mMgG]", heap_opts), (
            f"KAFKA_HEAP_OPTS='{heap_opts}' must include -Xmx<size> to cap the "
            f"maximum JVM heap and prevent OutOfMemoryError."
        )

    def test_kafka_heap_opts_xmx_within_container_limit(self):
        """
        The -Xmx value must be smaller than the container memory limit so
        the JVM heap alone does not exhaust the container's RAM budget.
        """
        compose = load_unified_compose()
        kafka = compose["services"]["kafka"]
        heap_opts = kafka["environment"]["KAFKA_HEAP_OPTS"]

        # Parse -Xmx value in MB
        m = re.search(r"-Xmx(\d+)([mMgG])", heap_opts)
        assert m, f"Cannot parse -Xmx from KAFKA_HEAP_OPTS='{heap_opts}'"
        xmx_mb = int(m.group(1)) * (1024 if m.group(2).lower() == "g" else 1)

        # Parse container memory limit in MB (may be under deploy.resources or mem_limit)
        mem_limit_raw = (
            kafka.get("deploy", {})
                 .get("resources", {})
                 .get("limits", {})
                 .get("memory")
            or kafka.get("mem_limit")
        )
        assert mem_limit_raw, (
            "kafka service must define a memory limit (deploy.resources.limits.memory)"
        )
        m2 = re.match(r"(\d+)([mMgG]?)", str(mem_limit_raw))
        limit_mb = int(m2.group(1)) * (1024 if m2.group(2).lower() == "g" else 1)

        assert xmx_mb < limit_mb, (
            f"Kafka -Xmx{xmx_mb}m must be strictly less than the container "
            f"memory limit {limit_mb}m.  The JVM also needs overhead beyond the "
            f"heap (metaspace, threads, off-heap buffers), so the container limit "
            f"must be higher than -Xmx."
        )

    def test_kafka_heap_opts_xms_lte_xmx(self):
        """
        -Xms (initial heap) must be ≤ -Xmx (maximum heap).
        Having Xms > Xmx causes the JVM to fail at startup.
        """
        compose = load_unified_compose()
        heap_opts = compose["services"]["kafka"]["environment"]["KAFKA_HEAP_OPTS"]

        xms_m = re.search(r"-Xms(\d+)([mMgG])", heap_opts)
        xmx_m = re.search(r"-Xmx(\d+)([mMgG])", heap_opts)

        if xms_m:
            xms_mb = int(xms_m.group(1)) * (1024 if xms_m.group(2).lower() == "g" else 1)
            xmx_mb = int(xmx_m.group(1)) * (1024 if xmx_m.group(2).lower() == "g" else 1)
            assert xms_mb <= xmx_mb, (
                f"Kafka -Xms{xms_mb}m must be ≤ -Xmx{xmx_mb}m. "
                f"A larger initial heap than maximum heap is invalid."
            )


# ---------------------------------------------------------------------------
# 2. Django migration —fake-initial
# ---------------------------------------------------------------------------

class TestDjangoMigrateFakeInitial:
    """
    core/entrypoint.sh must use  migrate --fake-initial  so that when the
    database already contains tables (e.g. after a previous run), initial
    migrations are recorded as applied without trying to re-create those
    tables.

    Without --fake-initial Django raises:
      django.db.utils.ProgrammingError: relation "users" already exists
    which crashes the container and causes a restart loop.
    """

    def test_entrypoint_uses_fake_initial(self):
        """
        entrypoint.sh migrate command must include --fake-initial.
        """
        content = load_entrypoint()
        assert "--fake-initial" in content, (
            "core/entrypoint.sh must run 'python manage.py migrate --fake-initial' "
            "(not bare 'migrate --noinput') to handle databases that already contain "
            "tables from a previous run. Without this flag Django raises "
            "ProgrammingError: relation '...' already exists and the container "
            "crashes in a restart loop."
        )

    def test_entrypoint_migrate_command_structure(self):
        """
        The migrate command in entrypoint.sh must keep --noinput (non-interactive)
        and add --fake-initial. Both flags are required.
        """
        content = load_entrypoint()
        # Accept either order of flags
        assert re.search(
            r"manage\.py\s+migrate\s+.*--fake-initial",
            content,
        ), (
            "entrypoint.sh must call 'python manage.py migrate ... --fake-initial'. "
            "Found no such pattern."
        )

    def test_entrypoint_migrate_still_noinput(self):
        """
        --noinput must still be present so migrations don't block waiting for
        user confirmation in non-interactive container startup.
        """
        content = load_entrypoint()
        assert "--noinput" in content, (
            "core/entrypoint.sh migrate command must keep --noinput so that "
            "Django does not wait for interactive input during container startup."
        )


# ---------------------------------------------------------------------------
# 3. telegram-adapter memory limit
# ---------------------------------------------------------------------------

class TestTelegramAdapterMemory:
    """
    telegram-adapter was being OOM-killed (exit 137) with a 64 M container
    limit. A Python aiohttp/aiogram process needs at least 128 M.
    """

    def test_telegram_adapter_memory_limit_at_least_128m(self):
        """
        telegram-adapter deploy.resources.limits.memory must be >= 128 M
        to avoid OOM-kills (exit 137).
        """
        compose = load_unified_compose()
        svc = compose["services"]["telegram-adapter"]

        mem_raw = (
            svc.get("deploy", {})
               .get("resources", {})
               .get("limits", {})
               .get("memory")
            or svc.get("mem_limit")
        )
        assert mem_raw, (
            "telegram-adapter must define a memory limit so it is not "
            "killed by the kernel OOM-killer (observed as exit 137)."
        )

        m = re.match(r"(\d+)([mMgG]?)", str(mem_raw))
        limit_mb = int(m.group(1)) * (1024 if m.group(2).lower() == "g" else 1)

        assert limit_mb >= 128, (
            f"telegram-adapter memory limit is {limit_mb} M but must be at "
            f"least 128 M. The previous 64 M limit caused the Python "
            f"aiohttp/aiogram process to be OOM-killed (exit 137)."
        )
