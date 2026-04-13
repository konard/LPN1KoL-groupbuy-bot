"""
Tests for issue #118 fixes:
1. Mattermost adapter correctly uses MATTERMOST_ADAPTER_URL when Mattermost is on a
   separate (third) server — the adapter URL is embedded in interactive-button payloads
   so Mattermost can reach the adapter even across different hosts.
2. Cabinet navigation: 'Делегаты', 'Общение', and 'Публичные чаты' slider items should
   route to the chat list, not the under-development placeholder page.
"""

import os
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Env fixtures
# ---------------------------------------------------------------------------

BASE_ENV = {
    "MATTERMOST_TOKEN": "tok123",
    "MATTERMOST_WEBHOOK_URL": "http://mattermost.example.com/hooks/abc",
}

EXTERNAL_MM_ENV = {
    **BASE_ENV,
    "MATTERMOST_URL": "https://mattermost.example.com",
    "MATTERMOST_BOT_TOKEN": "bot-pat-token",
    # Mattermost is on a different server; adapter is reachable at a public IP
    "MATTERMOST_ADAPTER_URL": "http://192.0.2.50:8002",
    "BOT_SERVICE_URL": "http://bot:8001",
}


# ---------------------------------------------------------------------------
# Mattermost adapter — separate-server configuration
# ---------------------------------------------------------------------------


class TestMattermostSeparateServer:
    """When Mattermost is deployed on a different server from the bot."""

    def test_adapter_url_used_in_button_actions(self):
        """
        Interactive button integration URLs must use MATTERMOST_ADAPTER_URL, not
        the internal bot service URL.  When Mattermost is on a separate server it
        cannot reach http://bot:8001; it must call the publicly reachable adapter.
        """
        with patch.dict("os.environ", EXTERNAL_MM_ENV, clear=True):
            from adapters.mattermost.adapter import MattermostAdapter

            adapter = MattermostAdapter()
            assert adapter.adapter_url == "http://192.0.2.50:8002"
            assert adapter.mattermost_url == "https://mattermost.example.com"

            keyboard = {
                "buttons": [
                    [{"text": "Посмотреть", "callback_data": "view_item_1"}],
                    [{"text": "Присоединиться", "callback_data": "join_item_1"}],
                ]
            }
            attachments = adapter._convert_keyboard_to_attachments(keyboard, "Выберите действие")

            assert len(attachments) == 1
            actions = attachments[0]["actions"]
            assert len(actions) == 2

            for action in actions:
                url = action["integration"]["url"]
                # Must point to the public adapter URL, not the internal bot service
                assert url.startswith("http://192.0.2.50:8002"), (
                    f"Button URL {url!r} should use MATTERMOST_ADAPTER_URL "
                    f"(http://192.0.2.50:8002), not the internal bot service URL"
                )
                assert "bot:8001" not in url, (
                    "Button URL must not reference the internal bot service URL "
                    "when Mattermost runs on a separate host"
                )

    def test_adapter_url_in_reply_url(self):
        """
        The reply_url embedded in standardised messages must also use
        MATTERMOST_ADAPTER_URL so bot replies are POST-ed to the public adapter.
        """
        with patch.dict("os.environ", EXTERNAL_MM_ENV, clear=True):
            from adapters.mattermost.adapter import MattermostAdapter

            adapter = MattermostAdapter()
            data = {
                "token": "tok123",
                "user_id": "u1",
                "user_name": "alice",
                "text": "/start",
                "channel_id": "c1",
                "channel_name": "town-square",
                "post_id": "p1",
                "team_id": "t1",
                "team_domain": "acme",
                "trigger_word": "",
            }
            msg = adapter._standardize_message(data)
            assert msg["reply_url"] == "http://192.0.2.50:8002/send"

    def test_slash_command_reply_url(self):
        """Slash-command standardised message also carries the public adapter reply_url."""
        with patch.dict("os.environ", EXTERNAL_MM_ENV, clear=True):
            from adapters.mattermost.adapter import MattermostAdapter

            adapter = MattermostAdapter()
            data = {
                "token": "tok123",
                "user_id": "u2",
                "user_name": "bob",
                "command": "/help",
                "text": "",
                "channel_id": "c2",
                "channel_name": "general",
                "team_id": "t2",
                "team_domain": "corp",
            }
            msg = adapter._standardize_slash(data)
            assert msg["reply_url"] == "http://192.0.2.50:8002/send"

    def test_default_adapter_url_same_host(self):
        """When no MATTERMOST_ADAPTER_URL is set, the default internal URL is used."""
        with patch.dict("os.environ", BASE_ENV, clear=True):
            from adapters.mattermost.adapter import MattermostAdapter

            adapter = MattermostAdapter()
            assert adapter.adapter_url == "http://mattermost-adapter:8002"

    def test_external_mattermost_url_stored(self):
        """MATTERMOST_URL is accessible via adapter.mattermost_url for REST calls."""
        env = {
            **BASE_ENV,
            "MATTERMOST_URL": "https://mattermost.example.com/",  # trailing slash
        }
        with patch.dict("os.environ", env, clear=True):
            from adapters.mattermost.adapter import MattermostAdapter

            adapter = MattermostAdapter()
            # Trailing slash should be stripped
            assert adapter.mattermost_url == "https://mattermost.example.com"


# ---------------------------------------------------------------------------
# Cabinet navigation — chat-related slider items
# ---------------------------------------------------------------------------


class TestCabinetChatSliderItems:
    """
    Verify that the CHAT_SLIDER_ITEMS constant covers the items that must navigate
    to the chat list rather than the under-development placeholder.
    """

    def _get_chat_slider_items(self):
        """Import CHAT_SLIDER_ITEMS from the Cabinet module source via regex parsing."""
        import re

        cabinet_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "frontend-react",
            "src",
            "components",
            "Cabinet.jsx",
        )
        with open(cabinet_path, encoding="utf-8") as f:
            source = f.read()

        # Extract the set literal: new Set(['item1', 'item2', ...])
        match = re.search(r"CHAT_SLIDER_ITEMS\s*=\s*new Set\(\[([^\]]+)\]\)", source)
        assert match, "CHAT_SLIDER_ITEMS constant not found in Cabinet.jsx"
        items_str = match.group(1)
        # Parse quoted strings
        items = re.findall(r"['\"]([^'\"]+)['\"]", items_str)
        return set(items)

    def _get_organizer_slider_items(self):
        import re

        cabinet_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "frontend-react",
            "src",
            "components",
            "Cabinet.jsx",
        )
        with open(cabinet_path, encoding="utf-8") as f:
            source = f.read()

        match = re.search(r"ORGANIZER_SLIDER_ITEMS\s*=\s*\[([^\]]+)\]", source)
        assert match, "ORGANIZER_SLIDER_ITEMS constant not found in Cabinet.jsx"
        items_str = match.group(1)
        items = re.findall(r"['\"]([^'\"]+)['\"]", items_str)
        return items

    def test_delegaty_in_chat_slider_items(self):
        """'Делегаты' must be in CHAT_SLIDER_ITEMS so it navigates to chat."""
        chat_items = self._get_chat_slider_items()
        assert "Делегаты" in chat_items, (
            "'Делегаты' must be in CHAT_SLIDER_ITEMS so clicking it navigates to "
            "the chat list instead of the under-development page"
        )

    def test_obshchenie_in_chat_slider_items(self):
        """'Общение' must be in CHAT_SLIDER_ITEMS."""
        chat_items = self._get_chat_slider_items()
        assert "Общение" in chat_items, (
            "'Общение' (Communication) must navigate to chat, not under-development"
        )

    def test_publichnye_chaty_in_chat_slider_items(self):
        """'Публичные чаты' must be in CHAT_SLIDER_ITEMS."""
        chat_items = self._get_chat_slider_items()
        assert "Публичные чаты" in chat_items, (
            "'Публичные чаты' (Public chats) must navigate to chat, not under-development"
        )

    def test_delegaty_in_organizer_slider(self):
        """'Делегаты' must appear in the organizer slider items."""
        items = self._get_organizer_slider_items()
        assert "Делегаты" in items, (
            "'Делегаты' must be listed in ORGANIZER_SLIDER_ITEMS so organizers "
            "can access the delegates/chat section from the slider"
        )

    def test_cabinet_jsx_has_delegaty_menu_item(self):
        """Organizer cabinet must have a 'Делегаты' menu item navigating to chat."""
        cabinet_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "frontend-react",
            "src",
            "components",
            "Cabinet.jsx",
        )
        with open(cabinet_path, encoding="utf-8") as f:
            source = f.read()

        assert "Делегаты" in source, (
            "Cabinet.jsx must contain a 'Делегаты' menu item"
        )
