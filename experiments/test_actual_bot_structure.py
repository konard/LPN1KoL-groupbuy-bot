"""
Test the EXACT registration order from main.py to find the real bug
"""
import asyncio
import sys
sys.path.insert(0, '/tmp/gh-issue-solver-1774100541442/bot')

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import Update
from unittest.mock import AsyncMock

from handlers import user_commands, procurement_commands, chat_commands, broadcast_commands
from dialogs import registration

results_log = []

async def test_command(dp, storage, bot_id, bot, test_name, user_id, text, state=None):
    """Helper to simulate a command and see what happens"""
    chat_id = user_id
    storage_key = StorageKey(bot_id=bot_id, chat_id=chat_id, user_id=user_id)
    
    if state:
        await storage.set_state(storage_key, state)
    else:
        await storage.set_state(storage_key, None)
    
    entities = []
    if text.startswith("/"):
        entities = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
    
    update_json = {
        "update_id": user_id,
        "message": {
            "message_id": 1,
            "date": 1700000000,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "Test"},
            "text": text,
        }
    }
    if entities:
        update_json["message"]["entities"] = entities
    
    update = Update(**update_json)
    
    # Patch the answer method to capture what's sent
    sent_messages = []
    
    async def mock_send_message(chat_id, text=None, **kwargs):
        sent_messages.append(text or "")
        return AsyncMock()
    
    bot.send_message = AsyncMock(side_effect=mock_send_message)
    
    await dp._process_update(bot=bot, update=update)
    
    print(f"\n{test_name}:")
    if sent_messages:
        print(f"  Bot replied: {sent_messages[0][:100]}")
    else:
        print(f"  No reply sent (handler might have called message.answer directly)")


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
    bot = AsyncMock()
    bot.id = bot_id
    
    print("=== Testing Actual Bot Structure ===")
    
    # Test 1: Fresh user uses /start - should get guest welcome
    await test_command(dp, storage, bot, bot_id, "Test 1: /start (no state)", 201, "/start", None)
    
    # Test 2: User in waiting_for_selfie state sends /start
    await test_command(dp, storage, bot, bot_id, 
                      "Test 2: /start (in waiting_for_selfie)", 
                      202, "/start", 
                      registration.RegistrationStates.waiting_for_selfie)
    
    # Test 3: User in waiting_for_selfie state sends /help
    await test_command(dp, storage, bot, bot_id, 
                      "Test 3: /help (in waiting_for_selfie)", 
                      203, "/help", 
                      registration.RegistrationStates.waiting_for_selfie)
    
    # Test 4: User in waiting_for_phone state sends /start  
    await test_command(dp, storage, bot, bot_id, 
                      "Test 4: /start (in waiting_for_phone)", 
                      204, "/start", 
                      registration.RegistrationStates.waiting_for_phone)
    
    # Test 5: User in waiting_for_selfie sends regular text (should be caught)
    await test_command(dp, storage, bot, bot_id, 
                      "Test 5: 'hello' (in waiting_for_selfie)", 
                      205, "hello", 
                      registration.RegistrationStates.waiting_for_selfie)
    
    print("\nDone!")

asyncio.run(main())
