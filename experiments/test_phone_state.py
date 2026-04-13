"""
Test: does /start work when user is in waiting_for_phone state?
"""
import asyncio
import sys
sys.path.insert(0, '/tmp/gh-issue-solver-1774100541442/bot')

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import Update
from unittest.mock import AsyncMock, MagicMock
from aiogram import Bot

from handlers import user_commands, procurement_commands, chat_commands, broadcast_commands
from dialogs import registration
import api_client as api_client_module

async def main():
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(user_commands.router)
    dp.include_router(procurement_commands.router)
    dp.include_router(chat_commands.router)
    dp.include_router(broadcast_commands.router)
    dp.include_router(registration.router)
    
    bot_id = 99999
    bot = MagicMock(spec=Bot)
    bot.id = bot_id
    
    api_client_module.api_client.check_user_exists = AsyncMock(return_value=False)
    api_client_module.api_client.get_user_by_platform = AsyncMock(return_value=None)
    
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
    
    tests = [
        ("in waiting_for_phone", 401, "/start", registration.RegistrationStates.waiting_for_phone),
        ("in waiting_for_role", 402, "/start", registration.RegistrationStates.waiting_for_role),
        ("in waiting_for_selfie", 403, "/start", registration.RegistrationStates.waiting_for_selfie),
        ("no state", 404, "/start", None),
    ]
    
    for test_name, user_id, text, state in tests:
        storage_key = StorageKey(bot_id=bot_id, chat_id=user_id, user_id=user_id)
        await storage.set_state(storage_key, state)
        
        calls = []
        api_client_module.api_client.check_user_exists = AsyncMock(
            side_effect=lambda *a, **kw: calls.append("check_user_exists") or False
        )
        
        update = build_update(user_id, text)
        try:
            await dp._process_update(bot=bot, update=update)
        except Exception:
            pass
        
        state_after = await storage.get_state(storage_key)
        cmd_ran = "check_user_exists" in calls
        print(f"Test ({test_name}): cmd_start ran={cmd_ran}, state={state} -> {state_after}")

asyncio.run(main())
