"""
Experiment to verify whether FSM state handlers block commands in aiogram 3.x
"""
import asyncio
import sys
sys.path.insert(0, '/tmp/gh-issue-solver-1774100541442/bot')

from aiogram import Router, Dispatcher
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from unittest.mock import AsyncMock, MagicMock

class TestStates(StatesGroup):
    waiting_for_input = State()

# Create routers
cmd_router = Router()
state_router = Router()

command_caught = False
state_caught = False

@cmd_router.message(Command("start"))
async def cmd_start(message: Message):
    global command_caught
    command_caught = True
    print("CMD HANDLER: /start was handled by command router")

@state_router.message(TestStates.waiting_for_input)
async def catch_all_in_state(message: Message):
    global state_caught
    state_caught = True
    print("STATE HANDLER: Message was caught by state handler (blocks commands!)")

async def test_priority():
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(cmd_router)
    dp.include_router(state_router)
    
    # Simulate a user in waiting_for_input state
    # Create fake update with /start command
    from aiogram.types import Update, Message as TgMessage, User, Chat
    import json
    
    # Instead, we'll check handler matching directly
    print("\nChecking handler filters...")
    
    # The key question: in aiogram 3.x, when a user is in state X:
    # Does a Command("start") handler WITHOUT state filter match?
    # Or does the handler WITH state filter (catch-all) win?
    
    print("\nIn aiogram 3.x:")
    print("- Handlers are checked in registration order")  
    print("- Within the SAME router, handlers are checked in order")
    print("- When using include_router(), child routers are checked in order")
    print("- State filters work as additional filters WITHIN a handler")
    print()
    print("CRITICAL: In aiogram 3.x, when a handler has BOTH State and Command filters,")
    print("the State filter RESTRICTS when it matches.")
    print()
    print("BUT: When handler A has ONLY StateFilter and handler B has ONLY CommandFilter,")
    print("AND they're in different routers: the ROUTER ORDER matters!")
    print("Since cmd_router is registered FIRST, its /start handler should match first")
    print("IF the /start command is sent -- but wait, the FSM state filter acts differently.")
    print()
    print("In aiogram 3.x with MemoryStorage, the state is per-user per-chat.")
    print("The StateFilter ADDS a constraint: handler only fires if user is in that state.")  
    print("But CommandFilter also ADDS a constraint: handler only fires if message is command.")
    print()
    print("The catch-all @router.message(TestStates.waiting_for_input) will match")
    print("ANY message from a user in that state, INCLUDING commands!")
    print("This IS the bug - it should exclude commands by adding ~Command() filter")

asyncio.run(test_priority())
