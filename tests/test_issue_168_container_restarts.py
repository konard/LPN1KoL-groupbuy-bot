"""
Tests for issue #168 fix:
  "docker compose -f docker-compose.unified.yml up -d" causes some containers
  to restart themselves in a loop.

Root causes identified and fixed:
  1. Centrifugo Redis password mismatch: centrifugo.json had "redis_password"
     while Redis is configured with "redis_secret" (the default), causing
     Centrifugo to crash on startup.
  2. Kafka has no healthcheck: services depending on Kafka via service_started
     could start before the broker was ready, causing connection failures and
     crash loops.
  3. Search service crashes on missing Elasticsearch: the search-service called
     log.Fatalf when Elasticsearch was unavailable, but Elasticsearch is not
     included in docker-compose.unified.yml.
  4. Notification service crashes on Kafka failure without retries: a single
     Kafka connection failure caused process.exit(1) with no retry logic.
"""
import json
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


def load_centrifugo_config():
    """Load the centrifugo configuration JSON."""
    path = os.path.join(ROOT, "services", "chat-service", "centrifugo", "centrifugo.json")
    with open(path) as f:
        return json.load(f)


class TestCentrifugoRedisPassword:
    """Verify Centrifugo's Redis password matches the default Redis password."""

    def test_centrifugo_redis_password_matches_default(self):
        """
        Centrifugo config must use 'redis_secret' (the default REDIS_PASSWORD
        in docker-compose.unified.yml) so it can authenticate to Redis out
        of the box without a custom .env file.

        centrifugo.json uses the flat Centrifugo v5 key 'redis_password'
        (not nested redis.password), so we check both locations.
        """
        config = load_centrifugo_config()
        # Centrifugo v5 uses flat 'redis_password' key; fall back to nested for safety
        redis_password = config.get("redis_password") or config.get("redis", {}).get("password", "")
        assert redis_password == "redis_secret", (
            f"centrifugo.json has redis password '{redis_password}' but "
            f"docker-compose.unified.yml defaults REDIS_PASSWORD to 'redis_secret'. "
            f"This mismatch causes Centrifugo to crash on startup."
        )

    def test_centrifugo_redis_password_not_placeholder(self):
        """
        Regression: the old placeholder value 'redis_password' (as a string value,
        not a key) should not be present — it never matched any Docker Compose default.
        """
        config = load_centrifugo_config()
        # Centrifugo v5 uses flat 'redis_password' key; fall back to nested for safety
        redis_password = config.get("redis_password") or config.get("redis", {}).get("password", "")
        assert redis_password != "redis_password", (
            "centrifugo.json still contains the placeholder value 'redis_password' "
            "which does not match any Docker Compose default."
        )


class TestKafkaHealthcheck:
    """Verify Kafka has a healthcheck and dependent services use service_healthy."""

    def test_kafka_has_healthcheck(self):
        """
        Kafka must define a healthcheck so dependent services can use
        condition: service_healthy and avoid connecting before the broker
        is ready.
        """
        compose = load_unified_compose()
        kafka = compose["services"]["kafka"]
        assert "healthcheck" in kafka, (
            "Kafka service must define a healthcheck so that dependent services "
            "can wait for the broker to be ready before starting."
        )
        assert "test" in kafka["healthcheck"], (
            "Kafka healthcheck must include a test command."
        )

    @pytest.mark.parametrize("service_name", [
        "purchase-service",
        "payment-service",
        "notification-service",
        "analytics-service",
        "search-service",
        "reputation-service",
    ])
    def test_kafka_dependent_services_use_service_healthy(self, service_name):
        """
        Services that depend on Kafka must use condition: service_healthy
        (not service_started) to avoid connecting before the broker is ready.
        """
        compose = load_unified_compose()
        service = compose["services"][service_name]
        depends_on = service.get("depends_on", {})

        # depends_on can be a list (short form) or dict (long form)
        if isinstance(depends_on, list):
            pytest.fail(
                f"{service_name} uses short-form depends_on for Kafka, "
                f"which defaults to service_started. Must use long form "
                f"with condition: service_healthy."
            )

        if "kafka" in depends_on:
            condition = depends_on["kafka"].get("condition", "service_started")
            assert condition == "service_healthy", (
                f"{service_name} depends on Kafka with condition '{condition}'. "
                f"Must use 'service_healthy' to wait for broker readiness."
            )


class TestSearchServiceGracefulDegradation:
    """Verify search-service handles missing Elasticsearch gracefully."""

    def test_search_service_does_not_fatalf_on_missing_elasticsearch(self):
        """
        search-service main.go must not call log.Fatalf when Elasticsearch
        is unavailable — it should log a warning and continue running in
        degraded mode.
        """
        main_go = os.path.join(ROOT, "services", "search-service", "main.go")
        with open(main_go) as f:
            content = f.read()

        # Must not have log.Fatalf for Elasticsearch init
        assert 'log.Fatalf("Elasticsearch init failed' not in content, (
            "search-service main.go must not call log.Fatalf on Elasticsearch "
            "init failure — this causes the container to crash and restart "
            "when Elasticsearch is not available."
        )

    def test_search_service_handles_empty_elasticsearch_url(self):
        """
        When ELASTICSEARCH_URL is empty or unset, search-service should
        start in degraded mode instead of crashing.
        """
        main_go = os.path.join(ROOT, "services", "search-service", "main.go")
        with open(main_go) as f:
            content = f.read()

        # The initElasticsearch function should handle empty URL gracefully
        assert 'return nil, nil' in content, (
            "initElasticsearch() should return nil client (not an error) "
            "when ELASTICSEARCH_URL is empty, allowing graceful degradation."
        )

    def test_search_handler_nil_checks_for_elasticsearch(self):
        """
        Search handler must check for nil Elasticsearch client to avoid
        nil pointer panics when running in degraded mode.
        """
        handler_go = os.path.join(
            ROOT, "services", "search-service", "handlers", "search_handler.go"
        )
        with open(handler_go) as f:
            content = f.read()

        assert "h.es != nil" in content or "h.es == nil" in content, (
            "Search handler must check whether Elasticsearch client is nil "
            "before using it, to avoid panics in degraded mode."
        )


class TestNotificationServiceRetry:
    """Verify notification-service retries Kafka connection."""

    def test_notification_service_has_kafka_retry_logic(self):
        """
        notification-service must retry Kafka connections before giving up,
        instead of crashing immediately on the first failure.
        """
        index_js = os.path.join(
            ROOT, "services", "notification-service", "src", "index.js"
        )
        with open(index_js) as f:
            content = f.read()

        assert "startConsumerWithRetry" in content, (
            "notification-service must wrap Kafka consumer startup with retry "
            "logic (startConsumerWithRetry) to handle transient Kafka "
            "unavailability during startup."
        )

    def test_notification_service_retry_has_backoff(self):
        """
        Kafka retry logic should use increasing delays (backoff) to avoid
        overwhelming the broker during startup.
        """
        index_js = os.path.join(
            ROOT, "services", "notification-service", "src", "index.js"
        )
        with open(index_js) as f:
            content = f.read()

        # Should have some form of increasing delay
        assert re.search(r'baseDelay\s*\*\s*attempt|delay\s*\*\s*2', content), (
            "notification-service Kafka retry logic should use backoff "
            "(increasing delay between attempts) to avoid overwhelming the broker."
        )
