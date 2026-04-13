"""
Tests for issue #186 fix:
  1. Kafka OutOfMemoryError during LogCleaner startup on a 3GB RAM system.
     Fixed by increasing KAFKA_HEAP_OPTS, adding KAFKA_JVM_PERFORMANCE_OPTS,
     disabling KAFKA_LOG_CLEANER_ENABLE, and raising the container memory limit
     to 512M.

  2. Django Admin DisallowedHost for 'localhost:8000' and missing CORS settings.
     Fixed by adding extra hosts (localhost:8000, 0.0.0.0, gateway, nginx) to
     ALLOWED_HOSTS and adding CORS_ALLOW_ALL_ORIGINS=True.
"""
import os

import yaml


ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_unified_compose():
    """Load docker-compose.unified.yml as a dict."""
    path = os.path.join(ROOT, "docker-compose.unified.yml")
    with open(path) as f:
        return yaml.safe_load(f)


def get_service_env(compose, service):
    """Return the environment dict/list for a service."""
    return compose["services"][service].get("environment", [])


def parse_env_var(env_list, key):
    """Return the value string for KEY=VALUE in env_list, or None."""
    for entry in env_list:
        if isinstance(entry, str) and entry.startswith(key + "="):
            return entry[len(key) + 1 :]
        if isinstance(entry, dict) and key in entry:
            return str(entry[key])
    return None


def get_env_value(env, key):
    """Get env var value from either list or dict style environment."""
    if isinstance(env, list):
        return parse_env_var(env, key)
    if isinstance(env, dict):
        return str(env.get(key, "")) if key in env else None
    return None


# ---------------------------------------------------------------------------
# 1. Kafka — HEAP_OPTS increased to prevent OOM
# ---------------------------------------------------------------------------


class TestKafkaHeapOpts:
    """
    Kafka crashed with OutOfMemoryError during LogCleaner startup.
    KAFKA_HEAP_OPTS must be set to at least -Xmx256m to give the JVM
    enough room for the log cleaner and broker operations on a 3GB host.
    """

    def test_kafka_heap_opts_xmx_at_least_256m(self):
        compose = load_unified_compose()
        env = get_service_env(compose, "kafka")
        heap_opts = get_env_value(env, "KAFKA_HEAP_OPTS")
        assert heap_opts is not None, "KAFKA_HEAP_OPTS must be set"
        assert "-Xmx256m" in heap_opts or "-Xmx512m" in heap_opts, (
            f"KAFKA_HEAP_OPTS='{heap_opts}' must set -Xmx to at least 256m "
            f"to prevent OutOfMemoryError during LogCleaner startup."
        )

    def test_kafka_heap_opts_xms_set(self):
        compose = load_unified_compose()
        env = get_service_env(compose, "kafka")
        heap_opts = get_env_value(env, "KAFKA_HEAP_OPTS")
        assert heap_opts is not None, "KAFKA_HEAP_OPTS must be set"
        assert "-Xms" in heap_opts, (
            f"KAFKA_HEAP_OPTS='{heap_opts}' should set -Xms for predictable "
            f"initial heap allocation."
        )


# ---------------------------------------------------------------------------
# 2. Kafka — JVM Performance Opts for MetaspaceSize
# ---------------------------------------------------------------------------


class TestKafkaJvmPerformanceOpts:
    """
    KAFKA_JVM_PERFORMANCE_OPTS should set MetaspaceSize and MaxMetaspaceSize
    to prevent class metadata from consuming too much memory on low-RAM hosts.
    """

    def test_kafka_jvm_performance_opts_present(self):
        compose = load_unified_compose()
        env = get_service_env(compose, "kafka")
        jvm_opts = get_env_value(env, "KAFKA_JVM_PERFORMANCE_OPTS")
        assert jvm_opts is not None, (
            "KAFKA_JVM_PERFORMANCE_OPTS must be set to control MetaspaceSize "
            "on memory-constrained hosts."
        )

    def test_kafka_jvm_performance_opts_metaspace(self):
        compose = load_unified_compose()
        env = get_service_env(compose, "kafka")
        jvm_opts = get_env_value(env, "KAFKA_JVM_PERFORMANCE_OPTS")
        if jvm_opts is None:
            return  # covered by previous test
        assert "MetaspaceSize" in jvm_opts, (
            f"KAFKA_JVM_PERFORMANCE_OPTS='{jvm_opts}' should set MetaspaceSize."
        )
        assert "MaxMetaspaceSize" in jvm_opts, (
            f"KAFKA_JVM_PERFORMANCE_OPTS='{jvm_opts}' should set MaxMetaspaceSize."
        )


# ---------------------------------------------------------------------------
# 3. Kafka — Log cleaner disabled
# ---------------------------------------------------------------------------


class TestKafkaLogCleanerDisabled:
    """
    On a 3GB host Kafka's LogCleaner thread is the direct trigger for the
    OutOfMemoryError.  Disabling it avoids the OOM while keeping the broker
    functional (log retention by time/size still works).
    """

    def test_kafka_log_cleaner_disabled(self):
        compose = load_unified_compose()
        env = get_service_env(compose, "kafka")
        value = get_env_value(env, "KAFKA_LOG_CLEANER_ENABLE")
        assert value is not None, "KAFKA_LOG_CLEANER_ENABLE must be set"
        assert value.lower() == "false", (
            f"KAFKA_LOG_CLEANER_ENABLE='{value}' must be 'false' to prevent "
            f"OutOfMemoryError from the LogCleaner thread on low-RAM hosts."
        )


# ---------------------------------------------------------------------------
# 4. Kafka — container memory limit raised to 512M
# ---------------------------------------------------------------------------


class TestKafkaMemoryLimit:
    """
    With KAFKA_HEAP_OPTS -Xmx256m the container needs at least 512M
    to accommodate JVM heap + metaspace + OS overhead.
    """

    def test_kafka_memory_limit_at_least_512m(self):
        compose = load_unified_compose()
        kafka = compose["services"]["kafka"]
        mem = kafka.get("deploy", {}).get("resources", {}).get("limits", {}).get("memory")
        assert mem is not None, "kafka service must have a memory limit"
        # Parse the memory string (e.g. '512M', '1G')
        mem_str = str(mem).upper()
        if mem_str.endswith("G"):
            mem_mb = int(mem_str[:-1]) * 1024
        elif mem_str.endswith("M"):
            mem_mb = int(mem_str[:-1])
        else:
            mem_mb = int(mem_str) // (1024 * 1024)
        assert mem_mb >= 512, (
            f"Kafka container memory limit is {mem} but must be at least 512M "
            f"to accommodate -Xmx256m heap + metaspace + OS overhead."
        )


# ---------------------------------------------------------------------------
# 5. Django — ALLOWED_HOSTS includes additional required hosts
# ---------------------------------------------------------------------------


class TestDjangoAllowedHostsExtended:
    """
    ALLOWED_HOSTS must include localhost:8000, 0.0.0.0, and inter-service
    hostnames (gateway, nginx) so that health probes and browser access
    from various origins are not rejected with DisallowedHost.
    """

    def test_allowed_hosts_includes_localhost_with_port(self):
        compose = load_unified_compose()
        env = get_service_env(compose, "django-admin")
        value = parse_env_var(env, "ALLOWED_HOSTS")
        assert value is not None, "ALLOWED_HOSTS must be set"
        assert "localhost:8000" in value, (
            f"ALLOWED_HOSTS='{value}' must include 'localhost:8000' to accept "
            f"requests with the Host header 'localhost:8000'."
        )

    def test_allowed_hosts_includes_zero_addr(self):
        compose = load_unified_compose()
        env = get_service_env(compose, "django-admin")
        value = parse_env_var(env, "ALLOWED_HOSTS")
        assert value is not None
        assert "0.0.0.0" in value, (
            f"ALLOWED_HOSTS='{value}' must include '0.0.0.0'."
        )

    def test_allowed_hosts_includes_gateway(self):
        compose = load_unified_compose()
        env = get_service_env(compose, "django-admin")
        value = parse_env_var(env, "ALLOWED_HOSTS")
        assert value is not None
        assert "gateway" in value, (
            f"ALLOWED_HOSTS='{value}' must include 'gateway' for inter-service access."
        )

    def test_allowed_hosts_includes_nginx(self):
        compose = load_unified_compose()
        env = get_service_env(compose, "django-admin")
        value = parse_env_var(env, "ALLOWED_HOSTS")
        assert value is not None
        assert "nginx" in value, (
            f"ALLOWED_HOSTS='{value}' must include 'nginx' for reverse proxy access."
        )


# ---------------------------------------------------------------------------
# 6. Django — CORS_ALLOW_ALL_ORIGINS set to True
# ---------------------------------------------------------------------------


class TestDjangoCorsAllowAllOrigins:
    """
    CORS_ALLOW_ALL_ORIGINS=True must be set so that the admin panel is
    accessible from any browser origin without CORS errors.
    """

    def test_cors_allow_all_origins_present(self):
        compose = load_unified_compose()
        env = get_service_env(compose, "django-admin")
        value = parse_env_var(env, "CORS_ALLOW_ALL_ORIGINS")
        assert value is not None, (
            "CORS_ALLOW_ALL_ORIGINS must be defined in django-admin environment."
        )

    def test_cors_allow_all_origins_default_true(self):
        compose = load_unified_compose()
        env = get_service_env(compose, "django-admin")
        value = parse_env_var(env, "CORS_ALLOW_ALL_ORIGINS")
        if value is None:
            return  # covered by previous test
        # The value may be ${CORS_ALLOW_ALL_ORIGINS:-True} — check for 'True'
        assert "True" in value or "true" in value, (
            f"CORS_ALLOW_ALL_ORIGINS='{value}' default should be True."
        )


# ---------------------------------------------------------------------------
# 7. Django — CORS_ALLOWED_ORIGINS includes localhost:3000
# ---------------------------------------------------------------------------


class TestDjangoCorsAllowedOrigins:
    """
    CORS_ALLOWED_ORIGINS should include http://localhost:3000 (the gateway
    port) and http://localhost:8000 (django-admin) as defaults.
    """

    def test_cors_allowed_origins_includes_localhost_3000(self):
        compose = load_unified_compose()
        env = get_service_env(compose, "django-admin")
        value = parse_env_var(env, "CORS_ALLOWED_ORIGINS")
        assert value is not None, "CORS_ALLOWED_ORIGINS must be set"
        assert "http://localhost:3000" in value, (
            f"CORS_ALLOWED_ORIGINS='{value}' should include http://localhost:3000."
        )

    def test_cors_allowed_origins_includes_localhost_8000(self):
        compose = load_unified_compose()
        env = get_service_env(compose, "django-admin")
        value = parse_env_var(env, "CORS_ALLOWED_ORIGINS")
        assert value is not None
        assert "http://localhost:8000" in value, (
            f"CORS_ALLOWED_ORIGINS='{value}' should include http://localhost:8000."
        )


# ---------------------------------------------------------------------------
# 8. settings.py — CORS_ALLOW_ALL_ORIGINS env var is respected
# ---------------------------------------------------------------------------


class TestSettingsCorsAllowAllOrigins:
    """
    settings.py must honour the CORS_ALLOW_ALL_ORIGINS environment variable
    so that operators can explicitly enable or disable it from docker-compose.
    """

    def test_settings_reads_cors_allow_all_origins_env(self):
        path = os.path.join(ROOT, "core", "config", "settings.py")
        with open(path) as f:
            src = f.read()
        assert "CORS_ALLOW_ALL_ORIGINS" in src, (
            "settings.py must reference CORS_ALLOW_ALL_ORIGINS."
        )
        assert "os.getenv" in src and "CORS_ALLOW_ALL_ORIGINS" in src, (
            "settings.py must read CORS_ALLOW_ALL_ORIGINS from environment."
        )
