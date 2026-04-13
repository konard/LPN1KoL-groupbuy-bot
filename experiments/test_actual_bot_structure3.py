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
import api_client as api_client_module

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
    
    # Track answers
    message_answers = []
    
    def build_update(user_id, text):
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
        if text.startswith("/"):
            data["message"]["entities"] = [{
                "type": "bot_command", "offset": 0, "length": len(text.split()[0])
            }]
        return Update(**data)
    
    async def run_test(test_name, user_id, text, state=None):
        storage_key = StorageKey(bot_id=bot_id, chat_id=user_id, user_id=user_id)
        await storage.set_state(storage_key, state)
        message_answers.clear()
        
        # Mock the api_client singleton directly
        original_check = api_client_module.api_client.check_user_exists
        original_get = api_client_module.api_client.get_user_by_platform
        api_client_module.api_client.check_user_exists = AsyncMock(return_value=False)
        api_client_module.api_client.get_user_by_platform = AsyncMock(return_value=None)
        
        update = build_update(user_id, text)
        
        # Patch Message.answer and Message.edit_text on the built update
        # We can't easily do this - let's use a different approach
        
        try:
            await dp._process_update(bot=bot, update=update)
        except Exception as e:
            pass
        finally:
            api_client_module.api_client.check_user_exists = original_check
            api_client_module.api_client.get_user_by_platform = original_get
        
        state_now = await storage.get_state(storage_key)
        print(f"{test_name}: state {state} -> {state_now}")
    
    print("=== Testing Command Handling with FSM States ===\n")
    print("Checking if state transitions show which handler ran:\n")
    
    # Test /start with no state - should stay in no state (cmd_start just answers)
    await run_test("Test 1: /start (no state)", 301, "/start", None)
    
    # Test /start with waiting_for_selfie - if command handler ran, state stays
    # If selfie_invalid ran, state stays too (it just answers)
    # Difference: command handler triggers api_client.check_user_exists
    print("\nNeed a different approach - tracking state transitions...")
    
    # Let's check: when user is in waiting_for_selfie and sends /start:
    # Does waiting_for_selfie REMAIN? or does state change?
    user_id = 302
    storage_key = StorageKey(bot_id=bot_id, chat_id=user_id, user_id=user_id)
    await storage.set_state(storage_key, registration.RegistrationStates.waiting_for_selfie)
    
    # Mock api to track calls  
    calls = []
    
    async def track_check(*args, **kwargs):
        calls.append(("check_user_exists", args, kwargs))
        return False
    
    async def track_get(*args, **kwargs):
        calls.append(("get_user_by_platform", args, kwargs))
        return None
    
    api_client_module.api_client.check_user_exists = AsyncMock(side_effect=track_check)
    api_client_module.api_client.get_user_by_platform = AsyncMock(side_effect=track_get)
    
    update = build_update(user_id, "/start")
    try:
        await dp._process_update(bot=bot, update=update)
    except Exception as e:
        print(f"Error: {e}")
    
    state_after = await storage.get_state(storage_key)
    print(f"\nTest: /start when in waiting_for_selfie state:")
    print(f"  API calls made: {calls}")
    print(f"  State after: {state_after}")
    
    if calls and "check_user_exists" in str(calls):
        print("  -> cmd_start RAN (command_handler fired, called check_user_exists)")
    elif not calls:
        print("  -> selfie_invalid RAN (no API calls, just showed 'please send photo' message)")
        print("  -> BUG: Commands are BLOCKED by the selfie state handler!")

asyncio.run(main())
