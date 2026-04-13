"""
Tests for the bot adapter message server (port 8001) and APIClient session fix.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from aiohttp.test_utils import TestClient, TestServer
from aiohttp import web


# ---------------------------------------------------------------------------
# Adapter message HTTP server
# ---------------------------------------------------------------------------

async def _make_test_app():
    """Create a minimal aiohttp app mirroring the bot's adapter server."""
    # Import at function level so the module-level env patching takes effect
    with patch.dict("os.environ", {"TELEGRAM_TOKEN": "tok"}):
        with patch("aiogram.Bot"):
            # We only need the route handlers, not a full bot start
            from bot.main import handle_adapter_message, handle_health

            app = web.Application()
            app.router.add_post("/message", handle_adapter_message)
            app.router.add_get("/health", handle_health)
            return app


@pytest.mark.asyncio
async def test_health_endpoint():
    """/health returns 200 with {status: ok}"""
    app = await _make_test_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_adapter_message_endpoint_valid():
    """/message accepts a valid adapter payload and returns {status: ok}"""
    app = await _make_test_app()
    async with TestClient(TestServer(app)) as client:
        payload = {
            "platform": "vk",
            "user_id": "123",
            "text": "Привет",
            "type": "message",
        }
        resp = await client.post("/message", json=payload)
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_adapter_message_endpoint_invalid_json():
    """/message returns 400 for malformed JSON"""
    app = await _make_test_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.post(
            "/message",
            data=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400
        data = await resp.json()
        assert "error" in data


# ---------------------------------------------------------------------------
# APIClient persistent session
# ---------------------------------------------------------------------------

class TestAPIClientSession:
    """Tests for the persistent session in APIClient"""

    @pytest.mark.asyncio
    async def test_session_created_lazily(self):
        """Session is None on init, created on first _request call"""
        from bot.api_client import APIClient
        import aiohttp

        client = APIClient(base_url="http://localhost:8000/api")
        assert client._session is None

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"exists": True})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request = MagicMock(return_value=mock_response)

        with patch("aiohttp.ClientSession", return_value=mock_session) as mock_cls:
            await client._request("GET", "/users/check_exists/")
            # Session created once
            mock_cls.assert_called_once()
            assert client._session is mock_session

    @pytest.mark.asyncio
    async def test_session_reused_across_requests(self):
        """The same session is reused for multiple requests"""
        from bot.api_client import APIClient

        client = APIClient(base_url="http://localhost:8000/api")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"ok": True})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request = MagicMock(return_value=mock_response)

        with patch("aiohttp.ClientSession", return_value=mock_session) as mock_cls:
            await client._request("GET", "/users/1/")
            await client._request("GET", "/users/2/")
            await client._request("GET", "/users/3/")

            # aiohttp.ClientSession constructed only once
            mock_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_invalidated_on_connection_error(self):
        """On ClientError the session is reset so the next call opens a fresh one"""
        from bot.api_client import APIClient
        import aiohttp

        client = APIClient(base_url="http://localhost:8000/api")

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request = MagicMock(
            side_effect=aiohttp.ClientConnectionError("connection refused")
        )
        client._session = mock_session

        result = await client._request("GET", "/users/1/")

        assert result is None
        # Session reset so next call creates a new one
        assert client._session is None

    @pytest.mark.asyncio
    async def test_close_closes_session(self):
        """close() closes the underlying aiohttp session"""
        from bot.api_client import APIClient

        client = APIClient(base_url="http://localhost:8000/api")

        mock_session = AsyncMock()
        mock_session.closed = False
        client._session = mock_session

        await client.close()

        mock_session.close.assert_called_once()


# ---------------------------------------------------------------------------
# Command dispatch and reply forwarding
# ---------------------------------------------------------------------------


def _make_mock_http_session(posted_payloads: list) -> MagicMock:
    """
    Build a mock aiohttp.ClientSession that records POST calls.

    ``posted_payloads`` is a shared list that each POST call appends to so the
    test can inspect what was sent.
    """
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value="")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    def _post(url, json=None, **kwargs):
        posted_payloads.append({"url": url, "json": json})
        return mock_resp

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.post = MagicMock(side_effect=_post)
    return mock_session


@pytest.mark.asyncio
async def test_mattermost_start_command_sends_reply():
    """
    When a /start command arrives from a Mattermost adapter with a reply_url,
    the bot must POST a non-empty reply back to that reply_url.

    This is the core regression test for issue #106: the bot was silently
    discarding all messages from the Mattermost adapter instead of processing
    commands and sending replies.
    """
    app = await _make_test_app()
    posted_payloads: list = []
    mock_session = _make_mock_http_session(posted_payloads)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        async with TestClient(TestServer(app)) as client:
            payload = {
                "platform": "mattermost",
                "user_id": "user123",
                "chat_id": "chan456",
                "text": "/start",
                "type": "message",
                "reply_url": "http://mattermost-adapter:8002/send",
            }
            resp = await client.post("/message", json=payload)
            assert resp.status == 200

    # The bot must have POSTed a reply to the reply_url
    reply_calls = [p for p in posted_payloads if p["url"] == "http://mattermost-adapter:8002/send"]
    assert reply_calls, (
        "Bot did not POST any reply to the adapter reply_url. "
        "The Mattermost bot ignores all commands — this is the bug from issue #106."
    )
    reply_body = reply_calls[0]["json"]
    assert reply_body.get("text"), "Reply text must not be empty"
    assert reply_body.get("user_id") == "user123"


@pytest.mark.asyncio
async def test_mattermost_help_command_sends_reply():
    """/help from a Mattermost adapter must trigger a reply back to reply_url."""
    app = await _make_test_app()
    posted_payloads: list = []
    mock_session = _make_mock_http_session(posted_payloads)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        async with TestClient(TestServer(app)) as client:
            payload = {
                "platform": "mattermost",
                "user_id": "user999",
                "chat_id": "chan001",
                "text": "/help",
                "type": "message",
                "reply_url": "http://mattermost-adapter:8002/send",
            }
            resp = await client.post("/message", json=payload)
            assert resp.status == 200

    reply_calls = [p for p in posted_payloads if p["url"] == "http://mattermost-adapter:8002/send"]
    assert reply_calls, "Bot must reply to /help command via reply_url"
    assert reply_calls[0]["json"].get("text")


@pytest.mark.asyncio
async def test_non_mattermost_message_no_reply_url_still_ok():
    """Messages without a reply_url (e.g. non-Mattermost) still return 200."""
    app = await _make_test_app()
    async with TestClient(TestServer(app)) as client:
        payload = {
            "platform": "vk",
            "user_id": "789",
            "text": "/help",
            "type": "message",
        }
        resp = await client.post("/message", json=payload)
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"
