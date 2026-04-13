"""
Tests for broadcast/outreach command handlers
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestBroadcastKeyboards:
    """Tests for broadcast keyboard utilities"""

    def test_get_broadcast_keyboard(self):
        """Test main broadcast management keyboard"""
        from bot.handlers.broadcast_commands import get_broadcast_keyboard

        keyboard = get_broadcast_keyboard()
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) > 0

        all_callbacks = [
            btn.callback_data for row in keyboard.inline_keyboard for btn in row
        ]
        assert "broadcast_add_channel" in all_callbacks
        assert "broadcast_list_targets" in all_callbacks
        assert "broadcast_compose" in all_callbacks
        assert "broadcast_history" in all_callbacks

    def test_get_broadcast_confirm_keyboard(self):
        """Test confirmation keyboard for broadcast"""
        from bot.handlers.broadcast_commands import get_broadcast_confirm_keyboard

        keyboard = get_broadcast_confirm_keyboard("test preview")
        assert keyboard is not None

        all_callbacks = [
            btn.callback_data for row in keyboard.inline_keyboard for btn in row
        ]
        assert "broadcast_send_all" in all_callbacks
        assert "broadcast_cancel" in all_callbacks


class TestBroadcastTargetManagement:
    """Tests for managing broadcast target list"""

    def setup_method(self):
        """Clear broadcast state before each test"""
        from bot.handlers.broadcast_commands import clear_targets, clear_history

        clear_targets()
        clear_history()

    def test_get_targets_empty(self):
        """Test that targets list starts empty"""
        from bot.handlers.broadcast_commands import get_targets

        targets = get_targets()
        assert targets == []

    def test_get_history_empty(self):
        """Test that history starts empty"""
        from bot.handlers.broadcast_commands import get_history

        history = get_history()
        assert history == []

    def test_clear_targets(self):
        """Test clearing the target list"""
        import bot.handlers.broadcast_commands as bc

        bc._broadcast_targets.append(
            {"id": -1001111111111, "title": "Test", "username": None, "type": "channel"}
        )
        assert len(bc._broadcast_targets) == 1

        bc.clear_targets()
        assert len(bc._broadcast_targets) == 0

    def test_clear_history(self):
        """Test clearing broadcast history"""
        import bot.handlers.broadcast_commands as bc

        bc._broadcast_history.append(
            {
                "text": "test",
                "sent_count": 1,
                "failed_count": 0,
                "timestamp": "2025-01-01",
            }
        )
        assert len(bc._broadcast_history) == 1

        bc.clear_history()
        assert len(bc._broadcast_history) == 0


class TestBroadcastCommand:
    """Tests for /broadcast command handler"""

    def setup_method(self):
        """Reset broadcast state before each test"""
        from bot.handlers.broadcast_commands import clear_targets, clear_history

        clear_targets()
        clear_history()

    @pytest.mark.asyncio
    async def test_cmd_broadcast_no_targets(self):
        """Test /broadcast command when no targets registered"""
        from bot.handlers.broadcast_commands import cmd_broadcast

        message = MagicMock()
        message.answer = AsyncMock()

        await cmd_broadcast(message)

        message.answer.assert_called_once()
        call_args = message.answer.call_args
        text = call_args[0][0]

        assert "Registered targets:* 0" in text or "Registered targets: 0" in text
        assert "Broadcast" in text

    @pytest.mark.asyncio
    async def test_cmd_broadcast_with_targets(self):
        """Test /broadcast command when targets are registered"""
        import bot.handlers.broadcast_commands as bc
        from bot.handlers.broadcast_commands import cmd_broadcast

        bc._broadcast_targets.append(
            {
                "id": -1001111111111,
                "title": "Test Channel",
                "username": "testchannel",
                "type": "channel",
            }
        )

        message = MagicMock()
        message.answer = AsyncMock()

        await cmd_broadcast(message)

        message.answer.assert_called_once()
        call_args = message.answer.call_args
        text = call_args[0][0]

        assert "Registered targets:* 1" in text or "Registered targets: 1" in text


class TestChannelVerification:
    """Tests for channel verification during add"""

    def setup_method(self):
        """Reset broadcast state before each test"""
        from bot.handlers.broadcast_commands import clear_targets

        clear_targets()

    @pytest.mark.asyncio
    async def test_process_channel_input_valid_username(self):
        """Test adding a valid channel by username"""
        from bot.handlers.broadcast_commands import process_channel_input, get_targets

        message = MagicMock()
        message.text = "@valid_channel"
        message.answer = AsyncMock()

        state = AsyncMock()
        state.clear = AsyncMock()

        bot = AsyncMock()
        # Mock chat info
        chat = MagicMock()
        chat.id = -1001111111111
        chat.title = "Valid Channel"
        chat.username = "valid_channel"
        chat.type = "channel"
        bot.get_chat = AsyncMock(return_value=chat)

        # Mock bot admin status
        chat_member = MagicMock()
        chat_member.status = "administrator"
        bot.get_chat_member = AsyncMock(return_value=chat_member)
        bot.id = 123456789

        await process_channel_input(message, state, bot)

        targets = get_targets()
        assert len(targets) == 1
        assert targets[0]["title"] == "Valid Channel"
        assert targets[0]["id"] == -1001111111111

    @pytest.mark.asyncio
    async def test_process_channel_input_bot_not_admin(self):
        """Test adding a channel where bot is not admin"""
        from bot.handlers.broadcast_commands import process_channel_input, get_targets

        message = MagicMock()
        message.text = "@some_channel"
        message.answer = AsyncMock()

        state = AsyncMock()
        state.clear = AsyncMock()

        bot = AsyncMock()
        chat = MagicMock()
        chat.id = -1001111111111
        chat.title = "Some Channel"
        chat.username = "some_channel"
        chat.type = "channel"
        bot.get_chat = AsyncMock(return_value=chat)

        # Bot is NOT an admin
        chat_member = MagicMock()
        chat_member.status = "member"
        bot.get_chat_member = AsyncMock(return_value=chat_member)
        bot.id = 123456789

        await process_channel_input(message, state, bot)

        # Should NOT be added to targets
        targets = get_targets()
        assert len(targets) == 0

        # Should show error message
        message.answer.assert_called_once()
        error_text = message.answer.call_args[0][0]
        assert "not an admin" in error_text.lower()

    @pytest.mark.asyncio
    async def test_process_channel_input_duplicate(self):
        """Test adding a channel that already exists in target list"""
        import bot.handlers.broadcast_commands as bc
        from bot.handlers.broadcast_commands import process_channel_input, get_targets

        existing_id = -1001111111111
        bc._broadcast_targets.append(
            {
                "id": existing_id,
                "title": "Existing Channel",
                "username": "existing",
                "type": "channel",
            }
        )

        message = MagicMock()
        message.text = "@existing"
        message.answer = AsyncMock()

        state = AsyncMock()
        state.clear = AsyncMock()

        bot = AsyncMock()
        chat = MagicMock()
        chat.id = existing_id
        chat.title = "Existing Channel"
        chat.username = "existing"
        chat.type = "channel"
        bot.get_chat = AsyncMock(return_value=chat)

        chat_member = MagicMock()
        chat_member.status = "administrator"
        bot.get_chat_member = AsyncMock(return_value=chat_member)
        bot.id = 123456789

        await process_channel_input(message, state, bot)

        # Should still be only 1 target (no duplicate)
        targets = get_targets()
        assert len(targets) == 1

    @pytest.mark.asyncio
    async def test_process_channel_input_invalid_format(self):
        """Test adding channel with invalid format (no @ or numeric ID)"""
        from bot.handlers.broadcast_commands import process_channel_input, get_targets

        message = MagicMock()
        message.text = "invalid_channel_name"
        message.answer = AsyncMock()

        state = AsyncMock()
        bot = AsyncMock()

        await process_channel_input(message, state, bot)

        # Should show error and not add anything
        targets = get_targets()
        assert len(targets) == 0
        message.answer.assert_called_once()


class TestBroadcastSend:
    """Tests for sending broadcast messages"""

    def setup_method(self):
        """Reset broadcast state before each test"""
        from bot.handlers.broadcast_commands import clear_targets, clear_history

        clear_targets()
        clear_history()

    @pytest.mark.asyncio
    async def test_broadcast_send_all_success(self):
        """Test successful broadcast to all channels"""
        import bot.handlers.broadcast_commands as bc
        from bot.handlers.broadcast_commands import broadcast_send_all, get_history

        bc._broadcast_targets = [
            {
                "id": -1001111111111,
                "title": "Channel 1",
                "username": "ch1",
                "type": "channel",
            },
            {
                "id": -1002222222222,
                "title": "Channel 2",
                "username": "ch2",
                "type": "channel",
            },
        ]

        callback = MagicMock()
        callback.message = MagicMock()
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        state = AsyncMock()
        state.get_data = AsyncMock(
            return_value={"broadcast_text": "Test broadcast message"}
        )
        state.clear = AsyncMock()

        bot = AsyncMock()
        bot.send_message = AsyncMock()

        await broadcast_send_all(callback, state, bot)

        # Should have tried to send to both channels
        assert bot.send_message.call_count == 2

        # Should have recorded in history
        history = get_history()
        assert len(history) == 1
        assert history[0]["sent_count"] == 2
        assert history[0]["failed_count"] == 0

    @pytest.mark.asyncio
    async def test_broadcast_send_all_partial_failure(self):
        """Test broadcast with some channels failing"""
        import bot.handlers.broadcast_commands as bc
        from bot.handlers.broadcast_commands import broadcast_send_all, get_history
        from aiogram.exceptions import TelegramForbiddenError

        bc._broadcast_targets = [
            {
                "id": -1001111111111,
                "title": "Channel 1",
                "username": "ch1",
                "type": "channel",
            },
            {
                "id": -1002222222222,
                "title": "Channel 2",
                "username": "ch2",
                "type": "channel",
            },
        ]

        callback = MagicMock()
        callback.message = MagicMock()
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        state = AsyncMock()
        state.get_data = AsyncMock(return_value={"broadcast_text": "Test broadcast"})
        state.clear = AsyncMock()

        bot = AsyncMock()
        # First call succeeds, second raises Forbidden
        forbidden_error = TelegramForbiddenError(
            method=MagicMock(), message="Forbidden: bot was kicked"
        )
        bot.send_message = AsyncMock(side_effect=[None, forbidden_error])

        await broadcast_send_all(callback, state, bot)

        history = get_history()
        assert len(history) == 1
        assert history[0]["sent_count"] == 1
        assert history[0]["failed_count"] == 1

    @pytest.mark.asyncio
    async def test_process_broadcast_message_too_short(self):
        """Test that very short broadcast messages are rejected"""
        from bot.handlers.broadcast_commands import process_broadcast_message

        message = MagicMock()
        message.text = "Hi"
        message.caption = None
        message.answer = AsyncMock()

        state = AsyncMock()
        state.update_data = AsyncMock()
        state.set_state = AsyncMock()

        await process_broadcast_message(message, state)

        # Should ask for longer message
        message.answer.assert_called_once()
        assert state.update_data.call_count == 0

    @pytest.mark.asyncio
    async def test_process_broadcast_message_valid(self):
        """Test that valid broadcast messages are accepted"""
        from bot.handlers.broadcast_commands import process_broadcast_message

        message = MagicMock()
        message.text = "This is a valid promotional message for our group buy!"
        message.caption = None
        message.answer = AsyncMock()

        state = AsyncMock()
        state.update_data = AsyncMock()
        state.set_state = AsyncMock()

        await process_broadcast_message(message, state)

        # Should show confirmation
        message.answer.assert_called_once()
        state.update_data.assert_called_once_with(broadcast_text=message.text)


class TestBroadcastHistory:
    """Tests for broadcast history"""

    def setup_method(self):
        """Reset state before each test"""
        from bot.handlers.broadcast_commands import clear_targets, clear_history

        clear_targets()
        clear_history()

    @pytest.mark.asyncio
    async def test_broadcast_history_empty(self):
        """Test history view when no broadcasts sent"""
        from bot.handlers.broadcast_commands import broadcast_history_view

        callback = MagicMock()
        callback.message = MagicMock()
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        await broadcast_history_view(callback)

        callback.message.edit_text.assert_called_once()
        text = callback.message.edit_text.call_args[0][0]
        assert "No broadcast history" in text

    @pytest.mark.asyncio
    async def test_broadcast_history_with_entries(self):
        """Test history view with existing entries"""
        import bot.handlers.broadcast_commands as bc
        from bot.handlers.broadcast_commands import broadcast_history_view

        bc._broadcast_history = [
            {
                "text": "Test message 1",
                "sent_count": 5,
                "failed_count": 1,
                "timestamp": "2025-01-15T10:00:00",
            }
        ]

        callback = MagicMock()
        callback.message = MagicMock()
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        await broadcast_history_view(callback)

        callback.message.edit_text.assert_called_once()
        text = callback.message.edit_text.call_args[0][0]
        assert "Broadcast History" in text
        assert "2025-01-15" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
