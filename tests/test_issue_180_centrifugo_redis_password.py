"""
Tests for issue #180 fix:
  Deployment failure — Centrifugo exits because its Redis password does not
  match the default Redis password configured in docker-compose.unified.yml.

Root cause:
  centrifugo.json had "redis_password": "" (empty string) while Redis is
  started with --requirepass redis_secret (the default REDIS_PASSWORD).
  Centrifugo cannot authenticate to Redis and crashes immediately, which
  causes every service that depends on Centrifugo (chat-service) to stay
  in "Created" state and never start.

Fix:
  Set "redis_password": "redis_secret" in centrifugo.json so it matches
  the Docker Compose default out of the box.
"""
import json
import os

import yaml

ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_unified_compose():
    path = os.path.join(ROOT, "docker-compose.unified.yml")
    with open(path) as f:
        return yaml.safe_load(f)


def load_centrifugo_config():
    path = os.path.join(ROOT, "services", "chat-service", "centrifugo", "centrifugo.json")
    with open(path) as f:
        return json.load(f)


class TestCentrifugoRedisPasswordIssue180:
    """Regression tests ensuring centrifugo.json redis_password matches compose default."""

    def test_centrifugo_json_redis_password_not_empty(self):
        """
        centrifugo.json must not have an empty redis_password.
        An empty password causes authentication failure against a Redis
        instance that was started with --requirepass redis_secret.
        """
        config = load_centrifugo_config()
        redis_password = config.get("redis", {}).get("password", config.get("redis_password", ""))
        assert redis_password != "", (
            "centrifugo.json has an empty redis_password. Redis requires "
            "'redis_secret' by default (REDIS_PASSWORD in docker-compose.unified.yml). "
            "An empty password causes Centrifugo to crash on startup."
        )

    def test_centrifugo_json_redis_password_matches_compose_default(self):
        """
        The redis_password in centrifugo.json must equal the default value of
        REDIS_PASSWORD used in docker-compose.unified.yml so the stack works
        out of the box without a custom .env file.
        """
        compose = load_unified_compose()
        redis_service = compose["services"]["redis"]
        # Extract default from the redis-server command, e.g. --requirepass ${REDIS_PASSWORD:-redis_secret}
        redis_cmd = " ".join(redis_service.get("command", "").split())
        import re
        match = re.search(r"--requirepass \$\{REDIS_PASSWORD:-(\w+)\}", redis_cmd)
        assert match, "Could not find --requirepass in redis service command."
        compose_default_password = match.group(1)

        config = load_centrifugo_config()
        # Support both flat key and nested redis.password
        redis_password = config.get("redis_password") or config.get("redis", {}).get("password", "")

        assert redis_password == compose_default_password, (
            f"centrifugo.json redis_password is '{redis_password}' but "
            f"docker-compose.unified.yml defaults REDIS_PASSWORD to '{compose_default_password}'. "
            f"This mismatch causes Centrifugo to fail to authenticate to Redis "
            f"and exit immediately, leaving dependent services stuck in 'Created' state."
        )

    def test_centrifugo_compose_env_override_present(self):
        """
        docker-compose.unified.yml must pass CENTRIFUGO_REDIS_PASSWORD so that
        users who override REDIS_PASSWORD in their .env file also get the correct
        password injected into Centrifugo at runtime.
        """
        compose = load_unified_compose()
        centrifugo = compose["services"]["centrifugo"]
        env = centrifugo.get("environment", {})
        assert "CENTRIFUGO_REDIS_PASSWORD" in env, (
            "centrifugo service in docker-compose.unified.yml must set "
            "CENTRIFUGO_REDIS_PASSWORD so that a custom REDIS_PASSWORD in .env "
            "is forwarded to Centrifugo at runtime."
        )
