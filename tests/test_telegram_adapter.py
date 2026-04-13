"""
Unit tests for Telegram adapter fixes:
- Proxy support via TELEGRAM_PROXY_URL env var
- Retry logic on network errors
- Persistent aiohttp session for message routing
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestTelegramAdapterInit:
    """Tests for adapter initialisation"""

    def test_initialization_with_token(self):
        """Adapter initialises correctly when TELEGRAM_TOKEN is set"""
        with patch.dict("os.environ", {"TELEGRAM_TOKEN": "test_token"}):
            with patch("adapters.telegram.adapter.AiohttpSession") as mock_session_cls:
                mock_session = MagicMock()
                mock_session_cls.return_value = mock_session
                with patch("adapters.telegram.adapter.Bot"):
                    from adapters.telegram.adapter import TelegramAdapter

                    adapter = TelegramAdapter()

                    assert adapter.token == "test_token"
                    assert adapter.bot_service_url == "http://bot:8001"
                    assert adapter.proxy_url == ""
                    assert isinstance(adapter.message_queue, asyncio.Queue)
                    assert adapter.is_running is False

    def test_initialization_raises_without_token(self):
        """Adapter raises ValueError when TELEGRAM_TOKEN is missing"""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="TELEGRAM_TOKEN is not set"):
                from adapters.telegram.adapter import TelegramAdapter

                TelegramAdapter()

    def test_proxy_url_passed_to_session(self):
        """When TELEGRAM_PROXY_URL is set the session is created with it"""
        env = {"TELEGRAM_TOKEN": "tok", "TELEGRAM_PROXY_URL": "socks5://proxy:1080"}
        with patch.dict("os.environ", env):
            with patch("adapters.telegram.adapter.AiohttpSession") as mock_session_cls:
                mock_session_cls.return_value = MagicMock()
                with patch("adapters.telegram.adapter.Bot"):
                    from adapters.telegram.adapter import TelegramAdapter

                    TelegramAdapter()

                    mock_session_cls.assert_called_once_with(proxy="socks5://proxy:1080")

    def test_no_proxy_uses_default_session(self):
        """When TELEGRAM_PROXY_URL is absent the session is created without proxy"""
        with patch.dict("os.environ", {"TELEGRAM_TOKEN": "tok"}):
            with patch("adapters.telegram.adapter.AiohttpSession") as mock_session_cls:
                mock_session_cls.return_value = MagicMock()
                with patch("adapters.telegram.adapter.Bot"):
                    from adapters.telegram.adapter import TelegramAdapter

                    TelegramAdapter()

                    mock_session_cls.assert_called_once_with()

    def test_builtin_proxy_via_use_proxy_flag(self):
        """When TELEGRAM_USE_PROXY=true the built-in SOCKS5 proxy is used"""
        env = {"TELEGRAM_TOKEN": "tok", "TELEGRAM_USE_PROXY": "true"}
        with patch.dict("os.environ", env, clear=True):
            with patch("adapters.telegram.adapter.AiohttpSession") as mock_session_cls:
                mock_session_cls.return_value = MagicMock()
                with patch("adapters.telegram.adapter.Bot"):
                    with patch("adapters.telegram.adapter.TelegramAdapter._check_proxy_reachable", return_value=True):
                        from adapters.telegram.adapter import TelegramAdapter

                        adapter = TelegramAdapter()

                        assert adapter.proxy_url == "socks5://telegram-proxy:1080"
                        mock_session_cls.assert_called_once_with(
                            proxy="socks5://telegram-proxy:1080"
                        )

    def test_explicit_proxy_overrides_use_proxy_flag(self):
        """TELEGRAM_PROXY_URL takes priority over TELEGRAM_USE_PROXY"""
        env = {
            "TELEGRAM_TOKEN": "tok",
            "TELEGRAM_PROXY_URL": "http://my-proxy:8080",
            "TELEGRAM_USE_PROXY": "true",
        }
        with patch.dict("os.environ", env, clear=True):
            with patch("adapters.telegram.adapter.AiohttpSession") as mock_session_cls:
                mock_session_cls.return_value = MagicMock()
                with patch("adapters.telegram.adapter.Bot"):
                    from adapters.telegram.adapter import TelegramAdapter

                    adapter = TelegramAdapter()

                    assert adapter.proxy_url == "http://my-proxy:8080"
                    mock_session_cls.assert_called_once_with(proxy="http://my-proxy:8080")

    def test_use_proxy_false_means_direct(self):
        """TELEGRAM_USE_PROXY=false results in direct connection"""
        env = {"TELEGRAM_TOKEN": "tok", "TELEGRAM_USE_PROXY": "false"}
        with patch.dict("os.environ", env, clear=True):
            with patch("adapters.telegram.adapter.AiohttpSession") as mock_session_cls:
                mock_session_cls.return_value = MagicMock()
                with patch("adapters.telegram.adapter.Bot"):
                    from adapters.telegram.adapter import TelegramAdapter

                    adapter = TelegramAdapter()

                    assert adapter.proxy_url == ""
                    mock_session_cls.assert_called_once_with()


# ---------------------------------------------------------------------------
# Proxy URL resolution
# ---------------------------------------------------------------------------

class TestResolveProxyUrl:
    """Tests for _resolve_proxy_url static method"""

    def test_empty_when_nothing_set(self):
        with patch.dict("os.environ", {}, clear=True):
            from adapters.telegram.adapter import TelegramAdapter

            assert TelegramAdapter._resolve_proxy_url() == ""

    def test_explicit_proxy_url(self):
        env = {"TELEGRAM_PROXY_URL": "socks5://ext:1080"}
        with patch.dict("os.environ", env, clear=True):
            from adapters.telegram.adapter import TelegramAdapter

            assert TelegramAdapter._resolve_proxy_url() == "socks5://ext:1080"

    def test_builtin_proxy_with_true(self):
        env = {"TELEGRAM_USE_PROXY": "true"}
        with patch.dict("os.environ", env, clear=True):
            from adapters.telegram.adapter import TelegramAdapter

            with patch.object(TelegramAdapter, "_check_proxy_reachable", return_value=True):
                assert TelegramAdapter._resolve_proxy_url() == "socks5://telegram-proxy:1080"

    def test_builtin_proxy_with_1(self):
        env = {"TELEGRAM_USE_PROXY": "1"}
        with patch.dict("os.environ", env, clear=True):
            from adapters.telegram.adapter import TelegramAdapter

            with patch.object(TelegramAdapter, "_check_proxy_reachable", return_value=True):
                assert TelegramAdapter._resolve_proxy_url() == "socks5://telegram-proxy:1080"

    def test_builtin_proxy_with_yes(self):
        env = {"TELEGRAM_USE_PROXY": "YES"}
        with patch.dict("os.environ", env, clear=True):
            from adapters.telegram.adapter import TelegramAdapter

            with patch.object(TelegramAdapter, "_check_proxy_reachable", return_value=True):
                assert TelegramAdapter._resolve_proxy_url() == "socks5://telegram-proxy:1080"

    def test_builtin_proxy_unreachable_falls_back(self):
        """When TELEGRAM_USE_PROXY=true but proxy is unreachable, falls back to direct"""
        env = {"TELEGRAM_USE_PROXY": "true"}
        with patch.dict("os.environ", env, clear=True):
            from adapters.telegram.adapter import TelegramAdapter

            with patch.object(TelegramAdapter, "_check_proxy_reachable", return_value=False):
                assert TelegramAdapter._resolve_proxy_url() == ""

    def test_explicit_takes_priority_over_builtin(self):
        env = {"TELEGRAM_PROXY_URL": "http://ext:8080", "TELEGRAM_USE_PROXY": "true"}
        with patch.dict("os.environ", env, clear=True):
            from adapters.telegram.adapter import TelegramAdapter

            assert TelegramAdapter._resolve_proxy_url() == "http://ext:8080"

    def test_false_means_no_proxy(self):
        env = {"TELEGRAM_USE_PROXY": "false"}
        with patch.dict("os.environ", env, clear=True):
            from adapters.telegram.adapter import TelegramAdapter

            assert TelegramAdapter._resolve_proxy_url() == ""

    def test_whitespace_proxy_url_ignored(self):
        env = {"TELEGRAM_PROXY_URL": "  "}
        with patch.dict("os.environ", env, clear=True):
            from adapters.telegram.adapter import TelegramAdapter

            assert TelegramAdapter._resolve_proxy_url() == ""


# ---------------------------------------------------------------------------
# Message standardisation
# ---------------------------------------------------------------------------

class TestMessageStandardisation:
    """Tests for _standardize_message and _standardize_callback"""

    def _make_adapter(self):
        with patch.dict("os.environ", {"TELEGRAM_TOKEN": "tok"}):
            with patch("adapters.telegram.adapter.AiohttpSession"):
                with patch("adapters.telegram.adapter.Bot"):
                    from adapters.telegram.adapter import TelegramAdapter

                    return TelegramAdapter()

    def test_standardize_message(self):
        adapter = self._make_adapter()

        user = MagicMock()
        user.id = 111
        user.first_name = "Alice"
        user.last_name = "B"
        user.username = "alice"
        user.language_code = "en"

        msg = MagicMock()
        msg.from_user = user
        msg.chat.id = 111
        msg.text = "hello"
        msg.message_id = 1
        msg.date.isoformat.return_value = "2026-01-01T00:00:00"

        result = adapter._standardize_message(msg)

        assert result["platform"] == "telegram"
        assert result["user_id"] == "111"
        assert result["text"] == "hello"
        assert result["type"] == "message"
        assert result["user_info"]["first_name"] == "Alice"

    def test_standardize_callback(self):
        adapter = self._make_adapter()

        user = MagicMock()
        user.id = 222
        user.first_name = "Bob"
        user.last_name = ""
        user.username = "bob"
        user.language_code = "ru"

        cq = MagicMock()
        cq.from_user = user
        cq.data = "btn_profile"
        cq.message.message_id = 5

        result = adapter._standardize_callback(cq)

        assert result["platform"] == "telegram"
        assert result["user_id"] == "222"
        assert result["callback_data"] == "btn_profile"
        assert result["type"] == "callback"


# ---------------------------------------------------------------------------
# Persistent HTTP session
# ---------------------------------------------------------------------------

class TestPersistentHttpSession:
    """Tests for _get_http_session and _route_message"""

    @pytest.mark.asyncio
    async def test_get_http_session_creates_once(self):
        """_get_http_session creates a session lazily and reuses it"""
        with patch.dict("os.environ", {"TELEGRAM_TOKEN": "tok"}):
            with patch("adapters.telegram.adapter.AiohttpSession"):
                with patch("adapters.telegram.adapter.Bot"):
                    import aiohttp
                    from adapters.telegram.adapter import TelegramAdapter

                    adapter = TelegramAdapter()
                    assert adapter._http_session is None

                    with patch("aiohttp.ClientSession") as mock_cls:
                        mock_session = MagicMock()
                        mock_session.closed = False
                        mock_cls.return_value = mock_session

                        s1 = await adapter._get_http_session()
                        s2 = await adapter._get_http_session()

                        # Session created only once
                        mock_cls.assert_called_once()
                        assert s1 is s2

    @pytest.mark.asyncio
    async def test_route_message_uses_persistent_session(self):
        """_route_message uses the persistent session, not a fresh one each time"""
        with patch.dict("os.environ", {"TELEGRAM_TOKEN": "tok"}):
            with patch("adapters.telegram.adapter.AiohttpSession"):
                with patch("adapters.telegram.adapter.Bot"):
                    from adapters.telegram.adapter import TelegramAdapter

                    adapter = TelegramAdapter()

                    mock_response = AsyncMock()
                    mock_response.status = 200
                    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
                    mock_response.__aexit__ = AsyncMock(return_value=None)

                    mock_session = MagicMock()
                    mock_session.closed = False
                    mock_session.post = MagicMock(return_value=mock_response)
                    adapter._http_session = mock_session

                    await adapter._route_message(
                        {"platform": "telegram", "user_id": "1", "text": "hi"}
                    )

                    mock_session.post.assert_called_once_with(
                        "http://bot:8001/message",
                        json={"platform": "telegram", "user_id": "1", "text": "hi"},
                    )


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------

class TestRetryLogic:
    """Tests for start() retry behaviour on network errors"""

    @pytest.mark.asyncio
    async def test_start_succeeds_immediately(self):
        """start() completes normally when polling raises no exception"""
        with patch.dict("os.environ", {"TELEGRAM_TOKEN": "tok"}):
            with patch("adapters.telegram.adapter.AiohttpSession"):
                with patch("adapters.telegram.adapter.Bot"):
                    from adapters.telegram.adapter import TelegramAdapter

                    adapter = TelegramAdapter()
                    adapter.dp = MagicMock()
                    adapter.dp.start_polling = AsyncMock()

                    # No error — should return normally
                    adapter.is_running = False  # prevent process_queue loop
                    with patch.object(adapter, "process_queue", new_callable=AsyncMock):
                        with patch("asyncio.create_task"):
                            await adapter.start()

                    adapter.dp.start_polling.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_retries_on_network_error(self):
        """start() retries when polling raises a network error, then succeeds"""
        with patch.dict("os.environ", {"TELEGRAM_TOKEN": "tok"}):
            with patch("adapters.telegram.adapter.AiohttpSession"):
                with patch("adapters.telegram.adapter.Bot"):
                    from adapters.telegram.adapter import TelegramAdapter

                    adapter = TelegramAdapter()
                    adapter.dp = MagicMock()

                    call_count = 0

                    async def flaky_poll(_bot):
                        nonlocal call_count
                        call_count += 1
                        if call_count < 3:
                            raise Exception("TelegramNetworkError: timeout")

                    adapter.dp.start_polling = flaky_poll

                    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                        with patch("asyncio.create_task"):
                            await adapter.start()

                    # Should have retried twice (call_count == 3) with sleep in between
                    assert call_count == 3
                    assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_start_raises_after_max_retries(self):
        """start() raises after exhausting all retry attempts"""
        with patch.dict("os.environ", {"TELEGRAM_TOKEN": "tok"}):
            with patch("adapters.telegram.adapter.AiohttpSession"):
                with patch("adapters.telegram.adapter.Bot"):
                    from adapters.telegram.adapter import (
                        TelegramAdapter,
                        _MAX_RETRY_ATTEMPTS,
                    )

                    adapter = TelegramAdapter()
                    adapter.dp = MagicMock()
                    adapter.dp.start_polling = AsyncMock(
                        side_effect=Exception("network error")
                    )

                    with patch("asyncio.sleep", new_callable=AsyncMock):
                        with patch("asyncio.create_task"):
                            with pytest.raises(Exception, match="network error"):
                                await adapter.start()

                    assert adapter.dp.start_polling.call_count == _MAX_RETRY_ATTEMPTS


# ---------------------------------------------------------------------------
# Keyboard conversion
# ---------------------------------------------------------------------------

class TestKeyboardConversion:
    """Tests for _convert_keyboard"""

    def _make_adapter(self):
        with patch.dict("os.environ", {"TELEGRAM_TOKEN": "tok"}):
            with patch("adapters.telegram.adapter.AiohttpSession"):
                with patch("adapters.telegram.adapter.Bot"):
                    from adapters.telegram.adapter import TelegramAdapter

                    return TelegramAdapter()

    def test_convert_keyboard_structure(self):
        """Keyboard conversion produces InlineKeyboardMarkup with correct rows"""
        adapter = self._make_adapter()

        keyboard_data = {
            "buttons": [
                [
                    {"text": "Profile", "callback_data": "profile"},
                    {"text": "Balance", "callback_data": "balance"},
                ],
                [{"text": "Help", "callback_data": "help"}],
            ]
        }

        markup = adapter._convert_keyboard(keyboard_data)

        assert markup is not None
        assert len(markup.inline_keyboard) == 2
        assert len(markup.inline_keyboard[0]) == 2
        assert len(markup.inline_keyboard[1]) == 1
        assert markup.inline_keyboard[0][0].text == "Profile"
        assert markup.inline_keyboard[0][0].callback_data == "profile"

    def test_convert_keyboard_with_url(self):
        """URL buttons are included correctly"""
        adapter = self._make_adapter()

        keyboard_data = {
            "buttons": [
                [{"text": "Visit", "url": "https://example.com"}],
            ]
        }

        markup = adapter._convert_keyboard(keyboard_data)
        assert markup.inline_keyboard[0][0].url == "https://example.com"
