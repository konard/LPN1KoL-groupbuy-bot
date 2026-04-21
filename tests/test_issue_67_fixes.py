"""
Tests for issue #67 fix:
  1. Bot restart loop when TELEGRAM_TOKEN is not set:
     - bot/main.py called sys.exit(1) immediately, causing Docker restart loops.
     - Fixed: adapter server starts regardless; bot logs a warning and keeps
       running without Telegram so platform adapters (Mattermost, VK) still work.

  2. Container groupbuy-bot-user-frontend-1 error — dependency user-frontend
     failed to start:
     - The bot service had no healthcheck, so dependent services (telegram-adapter,
       mattermost-adapter) used service_started and could race.
     - Fixed: bot service now has a healthcheck on port 8001 (/health), and
       telegram-adapter / mattermost-adapter now depend on service_healthy.

  3. docker-compose.monolith.yml thorough review:
     - TELEGRAM_TOKEN and MATTERMOST_* env vars now default to empty string
       (${VAR:-}) so Docker Compose does not warn about unset variables.
"""
import ast
import os

import pytest
import yaml

ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_monolith_compose():
    path = os.path.join(ROOT, "docker-compose.monolith.yml")
    with open(path) as f:
        return yaml.safe_load(f)


class TestBotNoTokenGracefulDegradation:
    """Bot must not sys.exit(1) when TELEGRAM_TOKEN is missing."""

    def test_bot_does_not_exit_on_missing_token(self):
        """
        bot/main.py must NOT call sys.exit(1) at the top level of main()
        when TELEGRAM_TOKEN is absent — that causes Docker restart loops.
        """
        path = os.path.join(ROOT, "bot", "main.py")
        with open(path) as f:
            source = f.read()

        tree = ast.parse(source)

        # Find the main() coroutine
        main_func = None
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "main":
                main_func = node
                break

        assert main_func is not None, "main() coroutine not found in bot/main.py"

        # Collect all sys.exit calls inside main()
        exit_calls = []
        for node in ast.walk(main_func):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "exit"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "sys"
            ):
                exit_calls.append(node)

        assert len(exit_calls) == 0, (
            "bot/main.py main() must not call sys.exit() when TELEGRAM_TOKEN is "
            "missing — this causes Docker to restart the container in an infinite "
            "loop because the token is still missing after each restart. "
            "Instead, log a warning and keep the adapter server running."
        )

    def test_bot_starts_adapter_server_before_token_check(self):
        """
        The adapter message server (port 8001) must be started before the
        TELEGRAM_TOKEN check so Mattermost/VK adapters always have an endpoint
        to talk to, even when Telegram is not configured.
        """
        path = os.path.join(ROOT, "bot", "main.py")
        with open(path) as f:
            source = f.read()

        tree = ast.parse(source)

        main_func = None
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "main":
                main_func = node
                break

        assert main_func is not None

        # Walk the body in order and record positions of adapter server call
        # and token check
        adapter_server_line = None
        token_check_line = None

        for node in ast.walk(main_func):
            # Detect "await start_adapter_server()"
            if (
                isinstance(node, ast.Await)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "start_adapter_server"
            ):
                adapter_server_line = node.lineno

            # Detect "if not config.telegram_token:"
            if (
                isinstance(node, ast.If)
                and isinstance(node.test, ast.UnaryOp)
                and isinstance(node.test.op, ast.Not)
            ):
                # Check that the operand accesses config.telegram_token
                operand = node.test.operand
                if (
                    isinstance(operand, ast.Attribute)
                    and operand.attr == "telegram_token"
                ):
                    token_check_line = node.lineno

        assert adapter_server_line is not None, (
            "start_adapter_server() must be called in main() before the "
            "TELEGRAM_TOKEN check."
        )
        assert token_check_line is not None, (
            "TELEGRAM_TOKEN check (if not config.telegram_token) not found in main()."
        )
        assert adapter_server_line < token_check_line, (
            f"start_adapter_server() is called on line {adapter_server_line} but "
            f"TELEGRAM_TOKEN check is on line {token_check_line}. "
            "Adapter server must start BEFORE the token check."
        )


class TestBotHealthcheck:
    """Bot service in docker-compose.monolith.yml must have a healthcheck."""

    def test_bot_has_healthcheck(self):
        """
        The bot service must define a healthcheck so that telegram-adapter and
        mattermost-adapter can depend on condition: service_healthy and avoid
        starting before the adapter HTTP server is ready.
        """
        compose = load_monolith_compose()
        bot = compose["services"]["bot"]
        assert "healthcheck" in bot, (
            "bot service in docker-compose.monolith.yml must define a healthcheck "
            "so dependent services can use condition: service_healthy."
        )

    def test_bot_healthcheck_uses_health_endpoint(self):
        """
        Bot healthcheck must probe the /health endpoint on port 8001.
        """
        compose = load_monolith_compose()
        bot = compose["services"]["bot"]
        hc = bot.get("healthcheck", {})
        test_cmd = " ".join(hc.get("test", [])) if isinstance(hc.get("test"), list) else str(hc.get("test", ""))
        assert "8001" in test_cmd, (
            "Bot healthcheck must probe port 8001 (the adapter HTTP server)."
        )
        assert "health" in test_cmd, (
            "Bot healthcheck must probe the /health endpoint."
        )


class TestAdapterDependsOnBotHealthy:
    """telegram-adapter and mattermost-adapter must wait for bot to be healthy."""

    @pytest.mark.parametrize("adapter", ["telegram-adapter", "mattermost-adapter"])
    def test_adapter_depends_on_bot_healthy(self, adapter):
        """
        Adapters must use condition: service_healthy for the bot dependency
        so they do not start before the bot's adapter server is ready.
        """
        compose = load_monolith_compose()
        service = compose["services"][adapter]
        depends_on = service.get("depends_on", {})

        assert "bot" in depends_on, (
            f"{adapter} must list 'bot' in depends_on."
        )
        condition = depends_on["bot"].get("condition")
        assert condition == "service_healthy", (
            f"{adapter} must depend on bot with condition: service_healthy "
            f"(currently '{condition}'). This ensures the adapter server is "
            "ready before the adapter tries to connect."
        )


class TestEnvVarDefaults:
    """Optional env vars must have empty-string defaults to avoid Docker warnings."""

    @pytest.mark.parametrize("service,var", [
        ("bot", "TELEGRAM_TOKEN"),
        ("telegram-adapter", "TELEGRAM_TOKEN"),
        ("mattermost-adapter", "MATTERMOST_URL"),
        ("mattermost-adapter", "MATTERMOST_TOKEN"),
        ("mattermost-adapter", "MATTERMOST_WEBHOOK_URL"),
    ])
    def test_optional_env_var_has_default(self, service, var):
        """
        Optional env vars must use ${VAR:-} syntax so Docker Compose does not
        print warnings about unset variables when no .env file is present.
        """
        compose = load_monolith_compose()
        svc = compose["services"][service]
        env = svc.get("environment", [])

        # environment can be a list of "KEY=VALUE" strings or a dict
        if isinstance(env, list):
            env_str = "\n".join(env)
        else:
            env_str = "\n".join(f"{k}={v}" for k, v in env.items())

        assert f"{var}=${{" in env_str and ":-}" in env_str.split(var)[-1].split("\n")[0], (
            f"Service '{service}': {var} must use empty-string default "
            f"syntax (${{VAR:-}}) so Docker Compose doesn't warn about unset "
            "variables when no .env file is present."
        )
