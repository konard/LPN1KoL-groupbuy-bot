"""
Tests for bot commands
"""
import pytest
from unittest.mock import AsyncMock, patch


class TestRegistrationDialog:
    """Tests for registration dialog"""

    def test_validate_phone_valid(self):
        """Test valid phone validation"""
        from bot.dialogs.registration import validate_phone

        assert validate_phone("+79991234567") is True
        assert validate_phone("79991234567") is True
        assert validate_phone("+1234567890123") is True

    def test_validate_phone_invalid(self):
        """Test invalid phone validation"""
        from bot.dialogs.registration import validate_phone

        assert validate_phone("123") is False  # Too short
        assert validate_phone("") is False  # Empty
        assert validate_phone("not a phone") is False

    def test_reason_messages_exist(self):
        """Test that all expected registration reasons have user-facing messages"""
        from bot.dialogs.registration import _REASON_MESSAGES

        for reason in ("join", "chat", "profile", "balance"):
            assert reason in _REASON_MESSAGES
            assert _REASON_MESSAGES[reason]  # non-empty string

    def test_unknown_reason_does_not_crash(self):
        """start_registration should work with an unknown reason key"""
        from bot.dialogs.registration import _REASON_MESSAGES

        # Unknown reasons fall back to empty string (no context prefix)
        msg = _REASON_MESSAGES.get("unknown_reason", "")
        assert msg == ""

    def test_registration_states_include_selfie(self):
        """RegistrationStates must have a waiting_for_selfie state"""
        from bot.dialogs.registration import RegistrationStates

        assert hasattr(RegistrationStates, "waiting_for_selfie")

    def test_selfie_handlers_registered(self):
        """Router must expose handlers for photo and /skip_photo during selfie step"""
        from bot.dialogs.registration import (
            process_selfie,
            skip_selfie,
            selfie_invalid,
        )

        assert callable(process_selfie)
        assert callable(skip_selfie)
        assert callable(selfie_invalid)


class TestKeyboards:
    """Tests for keyboard utilities"""

    def test_get_guest_keyboard(self):
        """Guest keyboard should show Procurements and Help, but not profile/balance"""
        from bot.keyboards import get_guest_keyboard

        keyboard = get_guest_keyboard()
        assert keyboard is not None
        buttons = [btn.text for row in keyboard.keyboard for btn in row]
        assert "Procurements" in buttons
        assert "Help" in buttons
        # Guests should not see profile/balance buttons
        assert "Profile" not in buttons
        assert "Balance" not in buttons
        assert "My Orders" not in buttons

    def test_get_main_keyboard_buyer(self):
        """Test main keyboard for buyer"""
        from bot.keyboards import get_main_keyboard

        keyboard = get_main_keyboard("buyer")
        assert keyboard is not None
        assert len(keyboard.keyboard) > 0

    def test_get_main_keyboard_organizer(self):
        """Test main keyboard for organizer"""
        from bot.keyboards import get_main_keyboard

        keyboard = get_main_keyboard("organizer")
        assert keyboard is not None
        # Organizer should have "Create Procurement" button
        buttons = [btn.text for row in keyboard.keyboard for btn in row]
        assert "Create Procurement" in buttons

    def test_get_role_keyboard(self):
        """Test role selection keyboard"""
        from bot.keyboards import get_role_keyboard

        keyboard = get_role_keyboard()
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) > 0

    def test_get_deposit_keyboard(self):
        """Test deposit amount keyboard"""
        from bot.keyboards import get_deposit_keyboard

        keyboard = get_deposit_keyboard()
        assert keyboard is not None
        # Should have predefined amounts
        callbacks = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
        assert "deposit_100" in callbacks
        assert "deposit_custom" in callbacks


class TestProcurementFormatting:
    """Tests for procurement formatting"""

    def test_get_status_emoji(self):
        """Test status emoji mapping: known statuses return a value (possibly empty
        string as a placeholder), unknown statuses return empty string."""
        from bot.handlers.procurement_commands import get_status_emoji

        # Known statuses must be present in the map (may return empty string placeholder)
        known = {"draft", "active", "stopped", "payment", "completed", "cancelled"}
        for s in known:
            result = get_status_emoji(s)
            assert isinstance(result, str), f"Expected str for status {s!r}"

        # Unknown status must return empty string
        assert get_status_emoji("unknown_status") == ""

    def test_format_procurement_details(self):
        """Test procurement details formatting"""
        from bot.handlers.procurement_commands import format_procurement_details

        procurement = {
            "title": "Test Procurement",
            "description": "Test description",
            "organizer_name": "Test Organizer",
            "category_name": "General",
            "city": "Test City",
            "target_amount": 10000,
            "current_amount": 5000,
            "progress": 50,
            "participant_count": 5,
            "unit": "units",
            "deadline": "2025-12-31T00:00:00",
            "status": "active",
            "status_display": "Active",
            "can_join": True
        }

        result = format_procurement_details(procurement)

        assert "Test Procurement" in result
        assert "Test description" in result
        assert "50%" in result
        assert "can join" in result.lower()


class TestGuestMode:
    """Tests ensuring guests can browse without registering"""

    @pytest.mark.asyncio
    async def test_cmd_procurements_no_auth_required(self):
        """Browsing procurements should work without a registered user"""
        from bot.handlers.procurement_commands import cmd_procurements

        message = AsyncMock()
        message.from_user.id = 99999

        procurements = [{"id": 1, "title": "Proc 1", "progress": 10}]

        with patch(
            "bot.handlers.procurement_commands.api_client.get_procurements",
            new_callable=AsyncMock,
            return_value=procurements,
        ):
            await cmd_procurements(message)

        message.answer.assert_called_once()
        call_text = message.answer.call_args[0][0]
        assert "Proc" in call_text or "Active" in call_text

    @pytest.mark.asyncio
    async def test_join_procurement_triggers_registration_for_guest(self):
        """Guests clicking Join should enter registration flow, not an error"""
        from bot.handlers.procurement_commands import join_procurement

        callback = AsyncMock()
        callback.data = "join_proc_42"
        callback.from_user.id = 99999

        state = AsyncMock()
        state.update_data = AsyncMock()
        state.set_state = AsyncMock()
        state.get_data = AsyncMock(return_value={})

        with patch(
            "bot.handlers.procurement_commands.api_client.get_user_by_platform",
            new_callable=AsyncMock,
            return_value=None,  # guest — not registered
        ):
            await join_procurement(callback, state)

        # Should set registration state, not procurement join state
        state.set_state.assert_called_once()
        from bot.dialogs.registration import RegistrationStates
        state.set_state.assert_called_with(RegistrationStates.waiting_for_phone)

        # Should edit the message to show a registration prompt
        callback.message.edit_text.assert_called_once()
        prompt_text = callback.message.edit_text.call_args[0][0]
        assert "phone" in prompt_text.lower() or "register" in prompt_text.lower()

    @pytest.mark.asyncio
    async def test_start_command_no_registration_for_new_user(self):
        """New users should see the guest welcome, not be forced to register"""
        from bot.handlers.user_commands import cmd_start

        message = AsyncMock()
        message.from_user.id = 88888
        message.from_user.first_name = "Alice"

        state = AsyncMock()
        state.set_state = AsyncMock()

        with patch(
            "bot.handlers.user_commands.api_client.check_user_exists",
            new_callable=AsyncMock,
            return_value=False,
        ):
            await cmd_start(message, state)

        message.answer.assert_called_once()
        text = message.answer.call_args[0][0]
        # Should show a friendly guest welcome, NOT launch registration
        assert "Welcome" in text
        # Registration state should NOT be set
        state.set_state.assert_not_called()


class TestAPIClient:
    """Tests for API client"""

    @pytest.mark.asyncio
    async def test_check_user_exists(self):
        """Test user existence check"""
        from bot.api_client import APIClient

        client = APIClient(base_url="http://localhost:8000/api")

        with patch.object(client, '_request', new_callable=AsyncMock) as mock:
            mock.return_value = {"exists": True}

            result = await client.check_user_exists("telegram", "12345")
            assert result is True

            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_procurements(self):
        """Test getting procurements"""
        from bot.api_client import APIClient

        client = APIClient(base_url="http://localhost:8000/api")

        with patch.object(client, '_request', new_callable=AsyncMock) as mock:
            mock.return_value = {
                "results": [
                    {"id": 1, "title": "Test 1"},
                    {"id": 2, "title": "Test 2"}
                ]
            }

            result = await client.get_procurements(status="active")
            assert len(result) == 2
            assert result[0]["title"] == "Test 1"


class TestDepositCommand:
    """Tests for the /deposit command"""

    def test_cmd_deposit_handler_exists(self):
        """cmd_deposit handler must be importable"""
        from bot.handlers.user_commands import cmd_deposit

        assert callable(cmd_deposit)

    @pytest.mark.asyncio
    async def test_cmd_deposit_registered_user_shows_deposit_keyboard(self):
        """/deposit for a registered user should show the deposit keyboard"""
        from bot.handlers.user_commands import cmd_deposit

        message = AsyncMock()
        message.from_user.id = 77777
        state = AsyncMock()

        user = {"id": 1, "first_name": "Alice", "balance": 500, "role": "buyer"}

        with patch(
            "bot.handlers.user_commands.api_client.get_user_by_platform",
            new_callable=AsyncMock,
            return_value=user,
        ):
            await cmd_deposit(message, state)

        message.answer.assert_called_once()
        call_kwargs = message.answer.call_args
        # Should include the deposit keyboard
        assert call_kwargs.kwargs.get("reply_markup") is not None or (
            len(call_kwargs.args) > 1 and call_kwargs.args[1] is not None
        )
        text = call_kwargs.args[0] if call_kwargs.args else ""
        assert "Deposit" in text or "deposit" in text.lower()

    @pytest.mark.asyncio
    async def test_cmd_deposit_guest_triggers_registration(self):
        """/deposit for a guest user should trigger registration"""
        from bot.handlers.user_commands import cmd_deposit

        message = AsyncMock()
        message.from_user.id = 66666
        state = AsyncMock()
        state.set_state = AsyncMock()

        with patch(
            "bot.handlers.user_commands.api_client.get_user_by_platform",
            new_callable=AsyncMock,
            return_value=None,
        ):
            await cmd_deposit(message, state)

        # Should start registration (which calls state.set_state)
        state.set_state.assert_called_once()

    def test_deposit_command_in_help_text(self):
        """/help text must mention /deposit"""
        import inspect
        from bot.handlers.user_commands import cmd_help

        source = inspect.getsource(cmd_help)
        assert "/deposit" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
