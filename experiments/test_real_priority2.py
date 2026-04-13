"""
Real test of aiogram 3.x handler priority with FSM state vs command
"""
import asyncio
import sys
sys.path.insert(0, '/tmp/gh-issue-solver-1774100541442/bot')

from aiogram import Router, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import Message, Update
from unittest.mock import AsyncMock

class TestStates(StatesGroup):
    waiting_for_input = State()

results = []

# Router 1 - command handlers (registered FIRST)
cmd_router = Router()

@cmd_router.message(Command("start"))
async def cmd_start(message: Message):
    results.append("command_handler_start")

# Router 2 - state handlers (registered SECOND)
state_router = Router()

@state_router.message(TestStates.waiting_for_input, Command("skip_photo"))
async def skip_photo(message: Message, state: FSMContext):
    results.append("skip_photo_handler")

@state_router.message(TestStates.waiting_for_input)
async def catch_all(message: Message):
    results.append("catch_all_in_state")


async def main():
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(cmd_router)
    dp.include_router(state_router)
    
    bot_id = 12345
    user_id = 1001
    chat_id = 1001
    
    # Set up the storage key for user 2 to be in waiting_for_input
    storage_key = StorageKey(bot_id=bot_id, chat_id=chat_id, user_id=user_id)
    await storage.set_state(storage_key, TestStates.waiting_for_input)
    
    # Verify state was set
    current_state = await storage.get_state(storage_key)
    print(f"State set to: {current_state}")
    
    # Now simulate /start command for user in that state
    update_json = {
        "update_id": 101,
        "message": {
            "message_id": 1,
            "date": 1700000000,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "Test"},
            "text": "/start",
            "entities": [{"type": "bot_command", "offset": 0, "length": 6}]
        }
    }
    
    update = Update(**update_json)
    
    # Create a mock bot
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    
    bot = AsyncMock(spec=Bot)
    bot.id = bot_id
    bot.token = "test_token"
    
    print("\nTest: /start with user in waiting_for_input state")
    results.clear()
    await dp._process_update(bot=bot, update=update)
    print(f"Result: {results}")
    
    if "command_handler_start" in results:
        print("INFO: Command handler caught /start (commands CAN escape state trap)")
        print("This means the bug is NOT that state blocks commands, it's something else")
    elif "catch_all_in_state" in results:
        print("BUG CONFIRMED: State catch-all handler blocked /start command!")
    else:
        print("Neither handler caught it - something else happened")
    
asyncio.run(main())
