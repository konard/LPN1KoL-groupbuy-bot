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
from aiogram.types import Message, Update, Chat, User
from unittest.mock import AsyncMock, patch, MagicMock
import json

class TestStates(StatesGroup):
    waiting_for_input = State()

results = []

# Router 1 - command handlers (registered FIRST)
cmd_router = Router()

@cmd_router.message(Command("start"))
async def cmd_start(message: Message):
    results.append("command_handler_start")

@cmd_router.message(Command("help"))
async def cmd_help(message: Message):
    results.append("command_handler_help")

# Router 2 - state handlers (registered SECOND)
state_router = Router()

@state_router.message(TestStates.waiting_for_input, F.photo)
async def handle_photo(message: Message, state: FSMContext):
    results.append("photo_handler")

@state_router.message(TestStates.waiting_for_input, Command("skip_photo"))
async def skip_photo(message: Message, state: FSMContext):
    results.append("skip_photo_handler")

@state_router.message(TestStates.waiting_for_input)
async def catch_all(message: Message):
    results.append("catch_all_in_state")


async def simulate_message(dp, text, state=None, user_id=100):
    """Simulate a Telegram message update"""
    # Build a minimal Update object
    update_data = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 1700000000,
            "chat": {"id": user_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "Test"},
            "text": text,
        }
    }
    
    if text.startswith("/"):
        cmd = text.lstrip("/").split()[0]
        update_data["message"]["entities"] = [{
            "type": "bot_command",
            "offset": 0,
            "length": len(text.split()[0])
        }]
    
    from aiogram.types import Update
    update = Update(**update_data)
    
    # Set the state for this user if requested
    if state:
        storage_key = dp.fsm.resolve_event_context(update)
        if storage_key:
            await dp.storage.set_state(storage_key, state=state)
    
    await dp.process_update(update)


async def main():
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(cmd_router)
    dp.include_router(state_router)
    
    # Test 1: /start without any state - should be caught by command handler
    print("Test 1: /start with no state")
    results.clear()
    await simulate_message(dp, "/start", state=None, user_id=1)
    print(f"  Result: {results}")
    assert "command_handler_start" in results, "FAIL: command not caught!"
    print("  PASS")
    
    # Test 2: /start with user in waiting_for_input state
    print("\nTest 2: /start with user in waiting_for_input state")
    results.clear()
    await simulate_message(dp, "/start", state=TestStates.waiting_for_input, user_id=2)
    print(f"  Result: {results}")
    if "command_handler_start" in results:
        print("  INFO: Command handler caught /start (commands escape state trap)")
    elif "catch_all_in_state" in results:
        print("  BUG CONFIRMED: State handler blocked /start command!")
    
    # Test 3: /skip_photo with user in waiting_for_input state
    print("\nTest 3: /skip_photo with user in waiting_for_input state")
    results.clear()
    await simulate_message(dp, "/skip_photo", state=TestStates.waiting_for_input, user_id=3)
    print(f"  Result: {results}")
    
    # Test 4: Regular text with user in state
    print("\nTest 4: 'hello' text with user in waiting_for_input state")
    results.clear()
    await simulate_message(dp, "hello", state=TestStates.waiting_for_input, user_id=4)
    print(f"  Result: {results}")
    
asyncio.run(main())
