"""
Unit tests for VK adapter
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.mark.asyncio
async def test_vk_adapter_initialization():
    """Test VK adapter initialization"""
    with patch.dict('os.environ', {'VK_TOKEN': 'test_token'}):
        from adapters.vk.adapter import VKAdapter

        adapter = VKAdapter()
        assert adapter.token == 'test_token'
        assert adapter.bot_service_url == 'http://bot:8001'
        assert isinstance(adapter.message_queue, asyncio.Queue)
        assert adapter.is_running is False


@pytest.mark.asyncio
async def test_vk_adapter_no_token():
    """Test VK adapter raises error without token"""
    with patch.dict('os.environ', {}, clear=True):
        from adapters.vk.adapter import VKAdapter

        with pytest.raises(ValueError, match="VK_TOKEN is not set"):
            VKAdapter()


@pytest.mark.asyncio
async def test_standardize_message():
    """Test message standardization"""
    with patch.dict('os.environ', {'VK_TOKEN': 'test_token'}):
        from adapters.vk.adapter import VKAdapter
        from vkbottle.bot import Message

        adapter = VKAdapter()

        # Mock VK API response
        mock_user = MagicMock()
        mock_user.id = 123
        mock_user.first_name = "Иван"
        mock_user.last_name = "Петров"

        mock_users_api = MagicMock()
        mock_users_api.get = AsyncMock(return_value=[mock_user])
        adapter.api = MagicMock()
        adapter.api.users = mock_users_api

        # Create mock message
        mock_message = MagicMock(spec=Message)
        mock_message.from_id = 123
        mock_message.peer_id = 123
        mock_message.text = "Привет"
        mock_message.conversation_message_id = 1
        mock_message.date = 1640000000

        result = await adapter._standardize_message(mock_message)

        assert result['platform'] == 'vk'
        assert result['user_id'] == '123'
        assert result['chat_id'] == '123'
        assert result['text'] == 'Привет'
        assert result['type'] == 'message'
        assert result['user_info']['first_name'] == 'Иван'
        assert result['user_info']['last_name'] == 'Петров'


@pytest.mark.asyncio
async def test_standardize_callback():
    """Test callback standardization"""
    with patch.dict('os.environ', {'VK_TOKEN': 'test_token'}):
        from adapters.vk.adapter import VKAdapter

        adapter = VKAdapter()

        # Mock VK API response
        mock_user = MagicMock()
        mock_user.id = 456
        mock_user.first_name = "Мария"
        mock_user.last_name = "Иванова"

        mock_users_api = MagicMock()
        mock_users_api.get = AsyncMock(return_value=[mock_user])
        adapter.api = MagicMock()
        adapter.api.users = mock_users_api

        # Create mock event
        mock_event = {
            "object": {
                "user_id": 456,
                "payload": {"action": "callback", "data": "test_data"},
                "conversation_message_id": 2,
                "event_id": "event_123",
                "peer_id": 456
            }
        }

        result = await adapter._standardize_callback(mock_event)

        assert result['platform'] == 'vk'
        assert result['user_id'] == '456'
        assert result['type'] == 'callback'
        assert result['callback_data'] == {"action": "callback", "data": "test_data"}
        assert result['user_info']['first_name'] == 'Мария'
        assert result['user_info']['last_name'] == 'Иванова'


@pytest.mark.asyncio
async def test_send_message():
    """Test sending a message"""
    with patch.dict('os.environ', {'VK_TOKEN': 'test_token'}):
        from adapters.vk.adapter import VKAdapter

        adapter = VKAdapter()

        # Mock VK API send method
        mock_messages_api = MagicMock()
        mock_messages_api.send = AsyncMock(return_value={'message_id': 123})
        adapter.api = MagicMock()
        adapter.api.messages = mock_messages_api

        result = await adapter.send_message(
            peer_id="123",
            text="Test message"
        )

        assert result is True
        adapter.api.messages.send.assert_called_once_with(
            peer_id=123,
            message="Test message",
            random_id=0,
        )


@pytest.mark.asyncio
async def test_send_message_with_keyboard():
    """Test sending a message with keyboard"""
    with patch.dict('os.environ', {'VK_TOKEN': 'test_token'}):
        from adapters.vk.adapter import VKAdapter

        adapter = VKAdapter()

        # Mock VK API send method
        mock_messages_api = MagicMock()
        mock_messages_api.send = AsyncMock(return_value={'message_id': 123})
        adapter.api = MagicMock()
        adapter.api.messages = mock_messages_api

        keyboard_data = {
            "buttons": [
                [
                    {"text": "Button 1", "callback_data": "btn1"},
                    {"text": "Button 2", "callback_data": "btn2"}
                ]
            ]
        }

        result = await adapter.send_message_with_keyboard(
            peer_id="123",
            text="Choose option",
            keyboard=keyboard_data
        )

        assert result is True
        adapter.api.messages.send.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_info():
    """Test getting user info"""
    with patch.dict('os.environ', {'VK_TOKEN': 'test_token'}):
        from adapters.vk.adapter import VKAdapter

        adapter = VKAdapter()

        # Mock VK API response
        mock_user = MagicMock()
        mock_user.id = 789
        mock_user.first_name = "Петр"
        mock_user.last_name = "Сидоров"

        mock_users_api = MagicMock()
        mock_users_api.get = AsyncMock(return_value=[mock_user])
        adapter.api = MagicMock()
        adapter.api.users = mock_users_api

        result = await adapter.get_user_info("789")

        assert result is not None
        assert result['id'] == '789'
        assert result['first_name'] == 'Петр'
        assert result['last_name'] == 'Сидоров'
        assert result['username'] == 'id789'


@pytest.mark.asyncio
async def test_convert_keyboard():
    """Test keyboard conversion from standard format to VK format"""
    with patch.dict('os.environ', {'VK_TOKEN': 'test_token'}):
        from adapters.vk.adapter import VKAdapter

        adapter = VKAdapter()

        keyboard_data = {
            "buttons": [
                [
                    {"text": "Профиль", "callback_data": "profile"},
                    {"text": "Баланс", "callback_data": "balance"}
                ],
                [
                    {"text": "Закупки", "callback_data": "procurements"}
                ]
            ]
        }

        vk_keyboard = adapter._convert_keyboard(keyboard_data)

        assert vk_keyboard is not None
        # Verify that the keyboard was created
        keyboard_json = json.loads(vk_keyboard.get_json())
        assert 'buttons' in keyboard_json
        assert len(keyboard_json['buttons']) == 2


@pytest.mark.asyncio
async def test_route_message():
    """Test message routing to bot service"""
    with patch.dict('os.environ', {'VK_TOKEN': 'test_token'}):
        from adapters.vk.adapter import VKAdapter

        adapter = VKAdapter()

        # Mock aiohttp session
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.__aenter__.return_value = mock_response
            mock_response.__aexit__.return_value = None

            mock_post = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.post = mock_post
            mock_session.return_value.__aexit__.return_value = None

            test_message = {
                'platform': 'vk',
                'user_id': '123',
                'text': 'test'
            }

            await adapter._route_message(test_message)

            # Verify that post was called with correct URL
            mock_post.assert_called_once()


# ---------------------------------------------------------------------------
# Group-chat feature tests
# ---------------------------------------------------------------------------

def test_is_group_chat():
    """Test detection of VK group conversation peer_id."""
    from adapters.vk.adapter import VKAdapter

    # Private message — peer_id == from_id (small number)
    assert VKAdapter.is_group_chat(123456) is False
    # Group conversation — peer_id > 2_000_000_000
    assert VKAdapter.is_group_chat(2_000_000_001) is True
    assert VKAdapter.is_group_chat(2_000_001_234) is True
    # Exact boundary
    assert VKAdapter.is_group_chat(2_000_000_000) is False


@pytest.mark.asyncio
async def test_standardize_message_includes_is_group_chat_flag():
    """Standardised message must carry is_group_chat flag."""
    with patch.dict('os.environ', {'VK_TOKEN': 'test_token'}):
        from adapters.vk.adapter import VKAdapter
        from vkbottle.bot import Message

        adapter = VKAdapter()

        mock_user = MagicMock()
        mock_user.id = 100
        mock_user.first_name = "Иван"
        mock_user.last_name = "Иванов"

        adapter.api = MagicMock()
        adapter.api.users = MagicMock()
        adapter.api.users.get = AsyncMock(return_value=[mock_user])

        # Private message
        private_msg = MagicMock(spec=Message)
        private_msg.from_id = 100
        private_msg.peer_id = 100
        private_msg.text = "привет"
        private_msg.conversation_message_id = 1
        private_msg.date = 1640000000

        result = await adapter._standardize_message(private_msg)
        assert result['is_group_chat'] is False

        # Group conversation message
        group_msg = MagicMock(spec=Message)
        group_msg.from_id = 100
        group_msg.peer_id = 2_000_000_001
        group_msg.text = "привет"
        group_msg.conversation_message_id = 2
        group_msg.date = 1640000000

        result = await adapter._standardize_message(group_msg)
        assert result['is_group_chat'] is True


@pytest.mark.asyncio
async def test_get_invite_link():
    """get_invite_link returns correct VK deeplink."""
    with patch.dict('os.environ', {'VK_TOKEN': 'test_token', 'VK_GROUP_ID': '12345678'}):
        from adapters.vk.adapter import VKAdapter

        adapter = VKAdapter()
        link = adapter.get_invite_link()

        assert 'https://vk.me/join/12345678' in link
        assert 'chat_invite' in link


@pytest.mark.asyncio
async def test_send_invite_link():
    """send_invite_link sends a message containing the invite URL."""
    with patch.dict('os.environ', {'VK_TOKEN': 'test_token', 'VK_GROUP_ID': '99999'}):
        from adapters.vk.adapter import VKAdapter

        adapter = VKAdapter()

        mock_messages = MagicMock()
        mock_messages.send = AsyncMock(return_value=None)
        adapter.api = MagicMock()
        adapter.api.messages = mock_messages

        ok = await adapter.send_invite_link(peer_id="555", procurement_title="Тест")

        assert ok is True
        call_kwargs = mock_messages.send.call_args
        assert call_kwargs is not None
        # The message text should contain the invite link
        sent_text = call_kwargs.kwargs.get('message', call_kwargs.args[0] if call_kwargs.args else '')
        assert 'vk.me/join/99999' in sent_text


@pytest.mark.asyncio
async def test_send_stop_amount_notification_reached():
    """Notification when stop amount is fully reached."""
    with patch.dict('os.environ', {'VK_TOKEN': 'test_token'}):
        from adapters.vk.adapter import VKAdapter

        adapter = VKAdapter()

        mock_messages = MagicMock()
        mock_messages.send = AsyncMock(return_value=None)
        adapter.api = MagicMock()
        adapter.api.messages = mock_messages

        ok = await adapter.send_stop_amount_notification(
            peer_id="2000000001",
            procurement_title="Закупка ноутбуков",
            stop_amount=50000,
            current_amount=50000,
        )

        assert ok is True
        call_kwargs = mock_messages.send.call_args
        sent_text = call_kwargs.kwargs.get('message', '')
        assert 'ДОСТИГНУТА' in sent_text
        assert 'Закупка ноутбуков' in sent_text


@pytest.mark.asyncio
async def test_send_stop_amount_notification_approaching():
    """Notification when stop amount is approaching but not yet reached."""
    with patch.dict('os.environ', {'VK_TOKEN': 'test_token'}):
        from adapters.vk.adapter import VKAdapter

        adapter = VKAdapter()

        mock_messages = MagicMock()
        mock_messages.send = AsyncMock(return_value=None)
        adapter.api = MagicMock()
        adapter.api.messages = mock_messages

        ok = await adapter.send_stop_amount_notification(
            peer_id="2000000001",
            procurement_title="Закупка",
            stop_amount=100000,
            current_amount=75000,
        )

        assert ok is True
        call_kwargs = mock_messages.send.call_args
        sent_text = call_kwargs.kwargs.get('message', '')
        assert '75%' in sent_text
        assert 'приближается' in sent_text


@pytest.mark.asyncio
async def test_send_payment_link_to_chat():
    """Payment link message is sent to the group chat."""
    with patch.dict('os.environ', {'VK_TOKEN': 'test_token'}):
        from adapters.vk.adapter import VKAdapter

        adapter = VKAdapter()

        mock_messages = MagicMock()
        mock_messages.send = AsyncMock(return_value=None)
        adapter.api = MagicMock()
        adapter.api.messages = mock_messages

        ok = await adapter.send_payment_link_to_chat(
            peer_id="2000000001",
            payment_url="https://pay.example.com/abc123",
            amount=3500,
            procurement_title="Закупка телефонов",
        )

        assert ok is True
        call_kwargs = mock_messages.send.call_args
        sent_text = call_kwargs.kwargs.get('message', '')
        assert 'Закупка телефонов' in sent_text
        assert '3' in sent_text  # amount present


@pytest.mark.asyncio
async def test_create_poll_in_chat_requires_group_peer():
    """create_poll_in_chat should fail gracefully for non-group peer_ids."""
    with patch.dict('os.environ', {'VK_TOKEN': 'test_token', 'VK_GROUP_ID': '1234'}):
        from adapters.vk.adapter import VKAdapter

        adapter = VKAdapter()
        adapter.api = MagicMock()
        adapter.api.polls = MagicMock()
        adapter.api.polls.create = AsyncMock(return_value=None)

        # Private chat – should return False without calling the API
        ok = await adapter.create_poll_in_chat(
            peer_id="100",
            question="За или против?",
            answers=["За", "Против"],
        )

        assert ok is False
        adapter.api.polls.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_poll_in_chat_requires_two_answers():
    """create_poll_in_chat should reject fewer than 2 answer options."""
    with patch.dict('os.environ', {'VK_TOKEN': 'test_token', 'VK_GROUP_ID': '1234'}):
        from adapters.vk.adapter import VKAdapter

        adapter = VKAdapter()
        adapter.api = MagicMock()
        adapter.api.polls = MagicMock()
        adapter.api.polls.create = AsyncMock(return_value=None)

        ok = await adapter.create_poll_in_chat(
            peer_id="2000000001",
            question="За?",
            answers=["За"],  # Only one answer
        )

        assert ok is False
        adapter.api.polls.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_poll_in_chat_success():
    """create_poll_in_chat should create a poll and send it to the chat."""
    with patch.dict('os.environ', {'VK_TOKEN': 'test_token', 'VK_GROUP_ID': '1234'}):
        from adapters.vk.adapter import VKAdapter

        adapter = VKAdapter()

        # Mock poll creation
        mock_poll = MagicMock()
        mock_poll.id = 42
        mock_poll.owner_id = -1234

        mock_polls = MagicMock()
        mock_polls.create = AsyncMock(return_value=mock_poll)

        mock_messages = MagicMock()
        mock_messages.send = AsyncMock(return_value=None)

        adapter.api = MagicMock()
        adapter.api.polls = mock_polls
        adapter.api.messages = mock_messages

        ok = await adapter.create_poll_in_chat(
            peer_id="2000000001",
            question="Голосуем за поставщика?",
            answers=["Да, берём", "Нет, отказываемся", "Нужно обсудить"],
        )

        assert ok is True
        mock_polls.create.assert_called_once()
        # Verify a message with attachment was sent to the chat
        mock_messages.send.assert_called_once()
        send_kwargs = mock_messages.send.call_args.kwargs
        assert send_kwargs.get('peer_id') == 2000000001
        assert 'attachment' in send_kwargs
        assert 'poll' in send_kwargs['attachment']
