"""
Test the EXACT registration order from main.py
"""
import asyncio
import sys
sys.path.insert(0, '/tmp/gh-issue-solver-1774100541442/bot')

from aiogram import Dispatcher, Bot
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import Update
from unittest.mock import AsyncMock, MagicMock, patch

from handlers import user_commands, procurement_commands, chat_commands, broadcast_commands
from dialogs import registration

# Track which handler fired by monkey-patching responses
handler_calls = []

async def main():
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # EXACT registration order from main.py
    dp.include_router(user_commands.router)
    dp.include_router(procurement_commands.router)
    dp.include_router(chat_commands.router)
    dp.include_router(broadcast_commands.router)
    dp.include_router(registration.router)
    
    bot_id = 99999
    bot = MagicMock(spec=Bot)
    bot.id = bot_id
    
    # Mock answer to capture what handlers send
    message_answers = []
    
    def make_message_mock(user_id, chat_id, text_input):
        msg = AsyncMock()
        msg.text = text_input
        msg.from_user = MagicMock()
        msg.from_user.id = user_id
        msg.from_user.first_name = "Test"
        msg.from_user.username = "testuser"
        msg.chat = MagicMock()
        msg.chat.id = chat_id
        
        async def answer_fn(text, **kwargs):
            message_answers.append(f"ANSWER: {text[:80]}")
            return AsyncMock()
        
        async def edit_text_fn(text, **kwargs):
            message_answers.append(f"EDIT: {text[:80]}")
            return AsyncMock()
        
        msg.answer = answer_fn
        msg.edit_text = edit_text_fn
        return msg
    
    def build_update(user_id, text, entities=None):
        data = {
            "update_id": user_id,
            "message": {
                "message_id": 1,
                "date": 1700000000,
                "chat": {"id": user_id, "type": "private"},
                "from": {"id": user_id, "is_bot": False, "first_name": "Test"},
                "text": text,
            }
        }
        if entities:
            data["message"]["entities"] = entities
        return Update(**data)
    
    async def run_test(test_name, user_id, text, state=None):
        storage_key = StorageKey(bot_id=bot_id, chat_id=user_id, user_id=user_id)
        await storage.set_state(storage_key, state)
        
        entities = []
        if text.startswith("/"):
            entities = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
        
        update = build_update(user_id, text, entities if entities else None)
        message_answers.clear()
        
        with patch('bot.handlers.user_commands.api_client') as mock_api, \
             patch('bot.handlers.procurement_commands.api_client') as mock_api2, \
             patch('bot.handlers.chat_commands.api_client') as mock_api3, \
             patch('bot.dialogs.registration.api_client') as mock_api4:
            
            mock_api.check_user_exists = AsyncMock(return_value=False)
            mock_api.get_user_by_platform = AsyncMock(return_value=None)
            
            await dp._process_update(bot=bot, update=update)
        
        state_now = await storage.get_state(storage_key)
        print(f"\n{test_name}")
        print(f"  State: {state} -> {state_now}")
        if message_answers:
            for a in message_answers:
                print(f"  {a}")
        else:
            print(f"  (no response captured)")
    
    print("=== Testing Command Handling with FSM States ===\n")
    
    # Test with no state
    await run_test("Test 1: /start (no state)", 301, "/start", None)
    
    # Test with waiting_for_selfie state
    await run_test("Test 2: /start (in waiting_for_selfie)", 302, "/start",
                  registration.RegistrationStates.waiting_for_selfie)
    
    # Test with waiting_for_selfie state  
    await run_test("Test 3: /help (in waiting_for_selfie)", 303, "/help",
                  registration.RegistrationStates.waiting_for_selfie)
    
    # Test with waiting_for_selfie state - text message
    await run_test("Test 4: 'hello' (in waiting_for_selfie)", 304, "hello",
                  registration.RegistrationStates.waiting_for_selfie)
    
    # Test /skip_photo in waiting_for_selfie state
    await run_test("Test 5: /skip_photo (in waiting_for_selfie)", 305, "/skip_photo",
                  registration.RegistrationStates.waiting_for_selfie)

asyncio.run(main())
