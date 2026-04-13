"""
Unit tests for Mattermost adapter
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp.test_utils import TestClient, TestServer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_ENV = {
    "MATTERMOST_TOKEN": "test_token",
    "MATTERMOST_WEBHOOK_URL": "http://mattermost.local/hooks/xxx",
}

BASE_ENV_WITH_REST = {
    **BASE_ENV,
    "MATTERMOST_URL": "http://mattermost.local",
    "MATTERMOST_BOT_TOKEN": "bot_personal_token",
}


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initialization():
    """Adapter initialises correctly when required env vars are present."""
    with patch.dict("os.environ", BASE_ENV, clear=True):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()
        assert adapter.token == "test_token"
        assert adapter.webhook_url == "http://mattermost.local/hooks/xxx"
        assert adapter.bot_service_url == "http://bot:8001"
        assert isinstance(adapter.message_queue, asyncio.Queue)
        assert adapter.is_running is False


@pytest.mark.asyncio
async def test_initialization_no_token():
    """Adapter raises ValueError when MATTERMOST_TOKEN is missing."""
    with patch.dict(
        "os.environ", {"MATTERMOST_WEBHOOK_URL": "http://x/hooks/y"}, clear=True
    ):
        from adapters.mattermost.adapter import MattermostAdapter

        with pytest.raises(ValueError, match="MATTERMOST_TOKEN is not set"):
            MattermostAdapter()


@pytest.mark.asyncio
async def test_initialization_no_webhook_url():
    """Adapter raises ValueError when MATTERMOST_WEBHOOK_URL is missing."""
    with patch.dict("os.environ", {"MATTERMOST_TOKEN": "tok"}, clear=True):
        from adapters.mattermost.adapter import MattermostAdapter

        with pytest.raises(ValueError, match="MATTERMOST_WEBHOOK_URL is not set"):
            MattermostAdapter()


# ---------------------------------------------------------------------------
# Message standardisation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_standardize_message_basic():
    """Outgoing-webhook payload is converted to the standardised format."""
    with patch.dict("os.environ", BASE_ENV, clear=True):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()
        data = {
            "token": "test_token",
            "user_id": "user123",
            "user_name": "alice",
            "text": "hello world",
            "channel_id": "chan456",
            "channel_name": "town-square",
            "post_id": "post789",
            "team_id": "team1",
            "team_domain": "acme",
            "trigger_word": "",
        }
        result = adapter._standardize_message(data)

        assert result["platform"] == "mattermost"
        assert result["user_id"] == "user123"
        assert result["chat_id"] == "chan456"
        assert result["text"] == "hello world"
        assert result["message_id"] == "post789"
        assert result["type"] == "message"
        assert result["user_info"]["username"] == "alice"
        assert result["user_info"]["team_id"] == "team1"
        assert result["user_info"]["team_domain"] == "acme"


@pytest.mark.asyncio
async def test_standardize_message_strips_trigger_word():
    """Trigger word is stripped from the message text."""
    with patch.dict("os.environ", BASE_ENV, clear=True):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()
        data = {
            "token": "test_token",
            "user_id": "u1",
            "user_name": "bob",
            "text": "!buy some item",
            "channel_id": "c1",
            "channel_name": "general",
            "post_id": "p1",
            "team_id": "t1",
            "team_domain": "corp",
            "trigger_word": "!buy",
        }
        result = adapter._standardize_message(data)
        assert result["text"] == "some item"


# ---------------------------------------------------------------------------
# Slash-command standardisation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_standardize_slash():
    """Slash-command payload is standardised with type=slash_command."""
    with patch.dict("os.environ", BASE_ENV, clear=True):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()
        data = {
            "token": "test_token",
            "user_id": "u2",
            "user_name": "carol",
            "command": "/groupbuy",
            "text": "list",
            "channel_id": "c2",
            "channel_name": "direct",
            "team_id": "t2",
            "team_domain": "startup",
        }
        result = adapter._standardize_slash(data)

        assert result["platform"] == "mattermost"
        assert result["user_id"] == "u2"
        assert result["type"] == "slash_command"
        assert result["text"] == "/groupbuy list"
        assert result["user_info"]["username"] == "carol"


@pytest.mark.asyncio
async def test_standardize_slash_no_args():
    """Slash command without extra text uses command name only."""
    with patch.dict("os.environ", BASE_ENV, clear=True):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()
        data = {
            "token": "test_token",
            "user_id": "u3",
            "user_name": "dave",
            "command": "/help",
            "text": "",
            "channel_id": "c3",
            "channel_name": "town-square",
            "team_id": "t3",
            "team_domain": "example",
        }
        result = adapter._standardize_slash(data)
        assert result["text"] == "/help"


# ---------------------------------------------------------------------------
# Interactive-action standardisation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_standardize_action():
    """Interactive button payload is standardised with type=callback."""
    with patch.dict("os.environ", BASE_ENV, clear=True):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()
        data = {
            "user_id": "u4",
            "user_name": "eve",
            "channel_id": "c4",
            "channel_name": "direct",
            "post_id": "p4",
            "team_id": "t4",
            "team_domain": "org",
            "context": {"action": "join_procurement:42"},
        }
        result = adapter._standardize_action(data)

        assert result["platform"] == "mattermost"
        assert result["user_id"] == "u4"
        assert result["callback_data"] == "join_procurement:42"
        assert result["type"] == "callback"
        assert result["message_id"] == "p4"


# ---------------------------------------------------------------------------
# Keyboard conversion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_convert_keyboard_to_attachments():
    """Standardised keyboard is converted to Mattermost attachment actions."""
    with patch.dict("os.environ", BASE_ENV, clear=True):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()
        keyboard = {
            "buttons": [
                [
                    {"text": "Профиль", "callback_data": "profile"},
                    {"text": "Баланс", "callback_data": "balance"},
                ],
                [{"text": "Открыть сайт", "url": "https://example.com"}],
            ]
        }
        attachments = adapter._convert_keyboard_to_attachments(keyboard, "Выберите:")

        assert len(attachments) == 1
        actions = attachments[0]["actions"]
        assert len(actions) == 3

        assert actions[0]["name"] == "Профиль"
        assert actions[0]["integration"]["context"]["action"] == "profile"
        assert actions[1]["name"] == "Баланс"
        assert actions[2]["name"] == "Открыть сайт"
        assert actions[2]["integration"]["context"]["url"] == "https://example.com"


# ---------------------------------------------------------------------------
# Sending messages – webhook fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_via_webhook():
    """send_message posts to the incoming webhook when no bot token is set."""
    with patch.dict("os.environ", BASE_ENV, clear=True):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)

            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session_cls.return_value = mock_session

            result = await adapter.send_message("user123", "Hello!")
            assert result is True
            mock_session.post.assert_called_once()
            call_kwargs = mock_session.post.call_args
            assert "Hello!" in json.dumps(call_kwargs[1].get("json", {}))


@pytest.mark.asyncio
async def test_send_message_webhook_failure():
    """send_message returns False when the webhook returns a non-200 status."""
    with patch.dict("os.environ", BASE_ENV, clear=True):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_response = MagicMock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Internal Server Error")
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)

            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session_cls.return_value = mock_session

            result = await adapter.send_message("user123", "Hello!")
            assert result is False


# ---------------------------------------------------------------------------
# Sending messages – REST API path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_via_rest():
    """send_message uses REST API when bot token and URL are available."""
    with patch.dict("os.environ", BASE_ENV_WITH_REST, clear=True):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()

        # Patch _send_via_rest directly; its internals are tested separately
        adapter._send_via_rest = AsyncMock(return_value=True)

        result = await adapter.send_message("user456", "Hi via REST")
        assert result is True
        adapter._send_via_rest.assert_called_once()


@pytest.mark.asyncio
async def test_send_message_with_keyboard_via_webhook():
    """send_message_with_keyboard posts attachments via webhook without bot token."""
    with patch.dict("os.environ", BASE_ENV, clear=True):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)

            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session_cls.return_value = mock_session

            keyboard = {"buttons": [[{"text": "OK", "callback_data": "ok"}]]}
            result = await adapter.send_message_with_keyboard(
                "user123", "Pick one:", keyboard
            )
            assert result is True
            mock_session.post.assert_called_once()
            payload = mock_session.post.call_args[1].get("json", {})
            assert "attachments" in payload


# ---------------------------------------------------------------------------
# get_user_info
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_info_success():
    """get_user_info returns parsed user dict on 200 response."""
    with patch.dict("os.environ", BASE_ENV_WITH_REST, clear=True):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()

        mock_user_data = {
            "id": "abc123",
            "first_name": "Иван",
            "last_name": "Иванов",
            "username": "ivan",
            "email": "ivan@example.com",
            "nickname": "vanya",
        }

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_user_data)
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)

            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session_cls.return_value = mock_session

            result = await adapter.get_user_info("abc123")

        assert result is not None
        assert result["id"] == "abc123"
        assert result["first_name"] == "Иван"
        assert result["last_name"] == "Иванов"
        assert result["username"] == "ivan"


@pytest.mark.asyncio
async def test_get_user_info_no_credentials():
    """get_user_info returns None when REST API creds are not configured."""
    with patch.dict("os.environ", BASE_ENV, clear=True):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()
        result = await adapter.get_user_info("abc123")
        assert result is None


@pytest.mark.asyncio
async def test_get_user_info_api_error():
    """get_user_info returns None on non-200 REST response."""
    with patch.dict("os.environ", BASE_ENV_WITH_REST, clear=True):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_response = MagicMock()
            mock_response.status = 404
            mock_response.text = AsyncMock(return_value="Not Found")
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)

            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session_cls.return_value = mock_session

            result = await adapter.get_user_info("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# Message routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_route_message():
    """_route_message POSTs the standardised message to the bot service."""
    with patch.dict("os.environ", BASE_ENV, clear=True):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)

            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session_cls.return_value = mock_session

            test_message = {
                "platform": "mattermost",
                "user_id": "u1",
                "chat_id": "c1",
                "text": "test",
                "type": "message",
            }
            await adapter._route_message(test_message)
            mock_session.post.assert_called_once()
            call_url = mock_session.post.call_args[0][0]
            assert call_url.endswith("/message")


# ---------------------------------------------------------------------------
# HTTP handler tests (using aiohttp TestClient)
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter_env(monkeypatch):
    monkeypatch.setenv("MATTERMOST_TOKEN", "test_token")
    monkeypatch.setenv("MATTERMOST_WEBHOOK_URL", "http://mattermost.local/hooks/xxx")
    monkeypatch.delenv("MATTERMOST_URL", raising=False)
    monkeypatch.delenv("MATTERMOST_BOT_TOKEN", raising=False)


@pytest.mark.asyncio
async def test_health_endpoint(adapter_env):
    """GET /health returns {"status": "ok"}."""
    from adapters.mattermost.adapter import MattermostAdapter

    adapter = MattermostAdapter()
    async with TestClient(TestServer(adapter.app)) as client:
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_webhook_endpoint_valid_token(adapter_env):
    """POST /webhook with valid token enqueues message and returns 200."""
    from adapters.mattermost.adapter import MattermostAdapter

    adapter = MattermostAdapter()
    payload = {
        "token": "test_token",
        "user_id": "u1",
        "user_name": "alice",
        "text": "hello",
        "channel_id": "c1",
        "channel_name": "general",
        "post_id": "p1",
        "team_id": "t1",
        "team_domain": "acme",
        "trigger_word": "",
    }
    async with TestClient(TestServer(adapter.app)) as client:
        resp = await client.post("/webhook", data=payload)
        assert resp.status == 200
    assert adapter.message_queue.qsize() == 1
    msg = await adapter.message_queue.get()
    assert msg["user_id"] == "u1"
    assert msg["type"] == "message"


@pytest.mark.asyncio
async def test_webhook_endpoint_invalid_token(adapter_env):
    """POST /webhook with wrong token returns 403."""
    from adapters.mattermost.adapter import MattermostAdapter

    adapter = MattermostAdapter()
    payload = {
        "token": "wrong_token",
        "user_id": "u1",
        "user_name": "alice",
        "text": "hello",
        "channel_id": "c1",
    }
    async with TestClient(TestServer(adapter.app)) as client:
        resp = await client.post("/webhook", data=payload)
        assert resp.status == 403
    assert adapter.message_queue.qsize() == 0


@pytest.mark.asyncio
async def test_slash_endpoint_valid(adapter_env):
    """POST /slash with valid token enqueues slash command and returns ephemeral reply."""
    from adapters.mattermost.adapter import MattermostAdapter

    adapter = MattermostAdapter()
    payload = {
        "token": "test_token",
        "user_id": "u2",
        "user_name": "bob",
        "command": "/groupbuy",
        "text": "status",
        "channel_id": "c2",
        "channel_name": "direct",
        "team_id": "t2",
        "team_domain": "startup",
    }
    async with TestClient(TestServer(adapter.app)) as client:
        resp = await client.post("/slash", data=payload)
        assert resp.status == 200
        data = await resp.json()
        assert data.get("response_type") == "ephemeral"

    assert adapter.message_queue.qsize() == 1
    msg = await adapter.message_queue.get()
    assert msg["type"] == "slash_command"
    assert "/groupbuy" in msg["text"]


@pytest.mark.asyncio
async def test_slash_endpoint_invalid_token(adapter_env):
    """POST /slash with wrong token returns 403."""
    from adapters.mattermost.adapter import MattermostAdapter

    adapter = MattermostAdapter()
    payload = {
        "token": "bad",
        "user_id": "u2",
        "user_name": "bob",
        "command": "/groupbuy",
        "text": "",
        "channel_id": "c2",
    }
    async with TestClient(TestServer(adapter.app)) as client:
        resp = await client.post("/slash", data=payload)
        assert resp.status == 403


@pytest.mark.asyncio
async def test_action_endpoint(adapter_env):
    """POST /mattermost_action enqueues callback and returns update response."""
    from adapters.mattermost.adapter import MattermostAdapter

    adapter = MattermostAdapter()
    payload = {
        "user_id": "u3",
        "user_name": "carol",
        "channel_id": "c3",
        "channel_name": "direct",
        "post_id": "p3",
        "team_id": "t3",
        "team_domain": "corp",
        "context": {"action": "join_procurement:99"},
    }
    async with TestClient(TestServer(adapter.app)) as client:
        resp = await client.post("/mattermost_action", json=payload)
        assert resp.status == 200
        data = await resp.json()
        assert "update" in data

    assert adapter.message_queue.qsize() == 1
    msg = await adapter.message_queue.get()
    assert msg["type"] == "callback"
    assert msg["callback_data"] == "join_procurement:99"


# ---------------------------------------------------------------------------
# reply_url in standardised messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_standardize_message_includes_reply_url(adapter_env):
    """Outgoing-webhook standardised message must include a reply_url."""
    from adapters.mattermost.adapter import MattermostAdapter

    adapter = MattermostAdapter()
    data = {
        "token": "test_token",
        "user_id": "u1",
        "user_name": "alice",
        "text": "/start",
        "channel_id": "c1",
        "channel_name": "general",
        "post_id": "p1",
        "team_id": "t1",
        "team_domain": "acme",
        "trigger_word": "",
    }
    result = adapter._standardize_message(data)
    assert "reply_url" in result, "reply_url must be present so bot service can reply"
    assert result["reply_url"].endswith("/send"), "reply_url must point to the /send endpoint"


@pytest.mark.asyncio
async def test_standardize_slash_includes_reply_url(adapter_env):
    """Slash-command standardised message must include a reply_url."""
    from adapters.mattermost.adapter import MattermostAdapter

    adapter = MattermostAdapter()
    data = {
        "token": "test_token",
        "user_id": "u2",
        "user_name": "bob",
        "command": "/help",
        "text": "",
        "channel_id": "c2",
        "channel_name": "direct",
        "team_id": "t2",
        "team_domain": "example",
    }
    result = adapter._standardize_slash(data)
    assert "reply_url" in result, "reply_url must be present in slash command messages"
    assert result["reply_url"].endswith("/send")


# ---------------------------------------------------------------------------
# /send endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_endpoint_delivers_message(adapter_env):
    """POST /send must forward the text to Mattermost and return 200."""
    from adapters.mattermost.adapter import MattermostAdapter

    adapter = MattermostAdapter()
    # Patch send_message so no real HTTP call is made
    adapter.send_message = AsyncMock(return_value=True)

    async with TestClient(TestServer(adapter.app)) as client:
        resp = await client.post(
            "/send", json={"user_id": "u1", "text": "Hello from bot!"}
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"

    adapter.send_message.assert_called_once_with("u1", "Hello from bot!")


@pytest.mark.asyncio
async def test_send_endpoint_missing_fields(adapter_env):
    """POST /send returns 400 when user_id or text is missing."""
    from adapters.mattermost.adapter import MattermostAdapter

    adapter = MattermostAdapter()
    async with TestClient(TestServer(adapter.app)) as client:
        resp = await client.post("/send", json={"user_id": "u1"})
        assert resp.status == 400


@pytest.mark.asyncio
async def test_send_endpoint_mattermost_failure(adapter_env):
    """POST /send returns 502 when the Mattermost delivery fails."""
    from adapters.mattermost.adapter import MattermostAdapter

    adapter = MattermostAdapter()
    adapter.send_message = AsyncMock(return_value=False)

    async with TestClient(TestServer(adapter.app)) as client:
        resp = await client.post(
            "/send", json={"user_id": "u1", "text": "Hi"}
        )
        assert resp.status == 502


@pytest.mark.asyncio
async def test_send_endpoint_invalid_json(adapter_env):
    """POST /send returns 400 for non-JSON bodies."""
    from adapters.mattermost.adapter import MattermostAdapter

    adapter = MattermostAdapter()
    async with TestClient(TestServer(adapter.app)) as client:
        resp = await client.post(
            "/send",
            data=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400


# ---------------------------------------------------------------------------
# MATTERMOST_ADAPTER_URL configuration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adapter_url_default():
    """When MATTERMOST_ADAPTER_URL is not set the default points to the internal Docker hostname."""
    with patch.dict("os.environ", BASE_ENV, clear=True):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()
        assert adapter.adapter_url == "http://mattermost-adapter:8002"


@pytest.mark.asyncio
async def test_adapter_url_custom():
    """When MATTERMOST_ADAPTER_URL is set it overrides the default."""
    custom_url = "http://192.168.1.10:8002"
    with patch.dict(
        "os.environ",
        {**BASE_ENV, "MATTERMOST_ADAPTER_URL": custom_url},
        clear=True,
    ):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()
        assert adapter.adapter_url == custom_url


@pytest.mark.asyncio
async def test_adapter_url_trailing_slash_stripped():
    """Trailing slash in MATTERMOST_ADAPTER_URL is stripped."""
    with patch.dict(
        "os.environ",
        {**BASE_ENV, "MATTERMOST_ADAPTER_URL": "http://192.168.1.10:8002/"},
        clear=True,
    ):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()
        assert adapter.adapter_url == "http://192.168.1.10:8002"


@pytest.mark.asyncio
async def test_reply_url_uses_adapter_url():
    """reply_url in standardised messages is built from MATTERMOST_ADAPTER_URL."""
    custom_url = "http://203.0.113.42:8002"
    with patch.dict(
        "os.environ",
        {**BASE_ENV, "MATTERMOST_ADAPTER_URL": custom_url},
        clear=True,
    ):
        from adapters.mattermost.adapter import MattermostAdapter

        adapter = MattermostAdapter()
        data = {
            "token": "test_token",
            "user_id": "u1",
            "user_name": "alice",
            "text": "/start",
            "channel_id": "c1",
            "channel_name": "general",
            "post_id": "p1",
            "team_id": "t1",
            "team_domain": "acme",
            "trigger_word": "",
        }
        msg = adapter._standardize_message(data)
        assert msg["reply_url"] == f"{custom_url}/send", (
            "reply_url must use MATTERMOST_ADAPTER_URL so the bot service can "
            "POST replies back to the adapter on a different server"
        )

        slash_data = {
            "token": "test_token",
            "user_id": "u2",
            "user_name": "bob",
            "command": "/help",
            "text": "",
            "channel_id": "c2",
            "channel_name": "direct",
            "team_id": "t2",
            "team_domain": "example",
        }
        slash_msg = adapter._standardize_slash(slash_data)
        assert slash_msg["reply_url"] == f"{custom_url}/send", (
            "reply_url in slash commands must also use MATTERMOST_ADAPTER_URL"
        )
