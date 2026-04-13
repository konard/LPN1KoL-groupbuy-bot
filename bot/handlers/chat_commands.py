"""
Chat command handlers
"""

import jwt
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from api_client import api_client
from config import config
from dialogs.registration import start_registration

router = Router()


def generate_chat_token(user_id: int) -> str:
    """Generate JWT token for WebSocket chat authentication"""
    secret = getattr(config, "jwt_secret", "dev-jwt-secret")
    payload = {"user_id": user_id, "exp": datetime.utcnow() + timedelta(hours=24)}
    return jwt.encode(payload, secret, algorithm="HS256")


@router.message(Command("chat"))
async def cmd_chat(message: Message, state: FSMContext):
    """Handle /chat command - show available chats"""
    user = await api_client.get_user_by_platform(
        platform="telegram", platform_user_id=str(message.from_user.id)
    )

    if not user:
        await start_registration(message, state, reason="chat")
        return

    # Get user's procurements (they can chat in procurements they participate in)
    result = await api_client.get_user_procurements(user["id"])

    if not result:
        await message.answer(
            "You don't have access to any chats.\n"
            "Join a procurement first using /procurements"
        )
        return

    organized = result.get("organized", [])
    participating = result.get("participating", [])
    all_procurements = organized + participating

    if not all_procurements:
        await message.answer(
            "You don't have access to any chats.\n"
            "Join a procurement first using /procurements"
        )
        return

    # Build keyboard with available chats
    buttons = []
    for proc in all_procurements[:10]:
        # Get unread count for this chat
        unread_count = await api_client.get_unread_count(user["id"], proc["id"])

        btn_text = f"💬 {proc.get('title', 'Unknown')}"
        if unread_count > 0:
            btn_text += f" ({unread_count} new)"

        buttons.append(
            [
                InlineKeyboardButton(
                    text=btn_text, callback_data=f"enter_chat_{proc['id']}"
                )
            ]
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(
        "*Select a chat to enter:*\n\n"
        "You can chat with other participants in procurements you've joined.",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


@router.message(F.text == "Chat")
async def text_chat(message: Message, state: FSMContext):
    """Handle 'Chat' text button"""
    await cmd_chat(message, state)


@router.callback_query(F.data.startswith("enter_chat_"))
async def enter_chat(callback: CallbackQuery):
    """Enter a procurement chat"""
    procurement_id = int(callback.data.split("_")[2])

    user = await api_client.get_user_by_platform(
        platform="telegram", platform_user_id=str(callback.from_user.id)
    )

    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    # Check access to this procurement chat
    has_access = await api_client.check_procurement_access(procurement_id, user["id"])
    if not has_access:
        await callback.answer(
            "You don't have access to this chat. Join the procurement first.",
            show_alert=True,
        )
        return

    # Get procurement details
    procurement = await api_client.get_procurement_details(procurement_id, user["id"])
    if not procurement:
        await callback.answer("Procurement not found", show_alert=True)
        return

    # Generate WebSocket token (for future WebSocket client use)
    _ = generate_chat_token(user["id"])

    # Get web chat URL (frontend)
    web_url = getattr(config, "web_app_url", "")
    if web_url:
        web_chat_url = f"{web_url}/chat/{procurement_id}"
    else:
        web_chat_url = None

    # Build message with chat options
    chat_info = (
        f"💬 *Chat: {procurement.get('title', 'Unknown')}*\n\n"
        f"📊 Status: {procurement.get('status', 'Unknown')}\n"
        f"👥 Participants: {procurement.get('participant_count', 0)}\n\n"
        "*How to join the chat:*\n\n"
    )

    buttons = []

    # Add web app button if URL is available
    if web_chat_url:
        chat_info += "1. Click the button below to open in browser\n"
        buttons.append(
            [InlineKeyboardButton(text="🌐 Open Chat in Browser", url=web_chat_url)]
        )

    chat_info += (
        "2. Or use the Telegram Web App integration\n\n"
        "*Note:* Messages are delivered in real-time to all participants."
    )

    # Add refresh button
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔄 Refresh", callback_data=f"refresh_chat_{procurement_id}"
            ),
            InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_chat_list"),
        ]
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        chat_info, parse_mode="Markdown", reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("refresh_chat_"))
async def refresh_chat(callback: CallbackQuery):
    """Refresh chat view"""
    procurement_id = callback.data.split("_")[2]
    callback.data = f"enter_chat_{procurement_id}"
    await enter_chat(callback)


@router.callback_query(F.data == "back_to_chat_list")
async def back_to_chat_list(callback: CallbackQuery):
    """Go back to chat list"""
    # Reuse cmd_chat logic
    user = await api_client.get_user_by_platform(
        platform="telegram", platform_user_id=str(callback.from_user.id)
    )

    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    result = await api_client.get_user_procurements(user["id"])

    if not result:
        await callback.message.edit_text(
            "You don't have access to any chats.\n"
            "Join a procurement first using /procurements"
        )
        return

    organized = result.get("organized", [])
    participating = result.get("participating", [])
    all_procurements = organized + participating

    if not all_procurements:
        await callback.message.edit_text(
            "You don't have access to any chats.\n"
            "Join a procurement first using /procurements"
        )
        return

    buttons = []
    for proc in all_procurements[:10]:
        unread_count = await api_client.get_unread_count(user["id"], proc["id"])

        btn_text = f"💬 {proc.get('title', 'Unknown')}"
        if unread_count > 0:
            btn_text += f" ({unread_count} new)"

        buttons.append(
            [
                InlineKeyboardButton(
                    text=btn_text, callback_data=f"enter_chat_{proc['id']}"
                )
            ]
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "*Select a chat to enter:*\n\n"
        "You can chat with other participants in procurements you've joined.",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("chat_"))
async def chat_callback(callback: CallbackQuery):
    """Handle chat_{procurement_id} callback from procurement details"""
    procurement_id = int(callback.data.split("_")[1])
    callback.data = f"enter_chat_{procurement_id}"
    await enter_chat(callback)
