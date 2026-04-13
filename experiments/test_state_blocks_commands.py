"""
Test whether catch_all state handler blocks commands when SAME router registers it
Test the ACTUAL scenario from the bot code where registration.router is registered LAST
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

# Mimic EXACT structure from the bot:
# cmd_router registered FIRST, state_router registered LAST
cmd_router = Router()
state_router = Router()

@cmd_router.message(Command("start"))
async def cmd_start(message: Message):
    results.append("command_handler_start")

@cmd_router.message(Command("help"))
async def cmd_help(message: Message):
    results.append("command_handler_help")

# This is exactly how registration.py is structured:
# Skip handler is BEFORE catch_all (same router, registered first)
@state_router.message(TestStates.waiting_for_input, Command("skip_photo"))
async def skip_photo(message: Message, state: FSMContext):
    results.append("skip_photo_handler")

# This is the problematic handler - catch-all in state
@state_router.message(TestStates.waiting_for_input)
async def catch_all(message: Message):
    results.append("catch_all_in_state")


async def test(dp, storage, bot, bot_id, test_name, user_id, text, state=None):
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
    results.clear()
    await dp._process_update(bot=bot, update=update)
    
    print(f"{test_name}: {results}")
    return list(results)


async def main():
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(cmd_router)   # Command handlers FIRST
    dp.include_router(state_router)  # State handlers LAST (like registration.router in bot)
    
    bot_id = 12345
    bot = AsyncMock()
    bot.id = bot_id
    
    # Test 1: No state - command should be handled
    r = await test(dp, storage, bot, bot_id, "Test 1 (/start, no state)", 101, "/start", None)
    assert "command_handler_start" in r, f"FAIL: {r}"
    
    # Test 2: In state - /start should STILL be handled by command handler
    r = await test(dp, storage, bot, bot_id, "Test 2 (/start, in state)", 102, "/start", TestStates.waiting_for_input)
    if "command_handler_start" in r:
        print("  -> Command ESCAPES state catch-all (commands registered FIRST win)")
    elif "catch_all_in_state" in r:
        print("  -> BUG: State catch-all blocks commands!")
    
    # Test 3: In state - /help should be handled
    r = await test(dp, storage, bot, bot_id, "Test 3 (/help, in state)", 103, "/help", TestStates.waiting_for_input)
    if "command_handler_help" in r:
        print("  -> /help ESCAPES state catch-all")
    elif "catch_all_in_state" in r:
        print("  -> BUG: State catch-all blocks /help!")
    
    # Test 4: In state - /skip_photo (registered in state router) should be handled
    r = await test(dp, storage, bot, bot_id, "Test 4 (/skip_photo, in state)", 104, "/skip_photo", TestStates.waiting_for_input)
    if "skip_photo_handler" in r:
        print("  -> /skip_photo handled by specific state handler")
    elif "catch_all_in_state" in r:
        print("  -> FAIL: catch-all grabbed /skip_photo!")
    
    # Test 5: In state - regular text
    r = await test(dp, storage, bot, bot_id, "Test 5 (text, in state)", 105, "hello", TestStates.waiting_for_input)
    if "catch_all_in_state" in r:
        print("  -> Regular text correctly caught by catch-all")

asyncio.run(main())
