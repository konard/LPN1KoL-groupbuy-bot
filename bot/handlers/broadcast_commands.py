"""
Broadcast/outreach command handlers for Telegram channels and chats.

This module provides functionality for:
- Searching and adding public Telegram channels/chats to an outreach list
- Sending promotional messages to channels where the bot is an admin
- Managing the broadcast history and target lists
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

logger = logging.getLogger(__name__)

router = Router()

# In-memory storage for broadcast targets (channel usernames/IDs)
# In production, this would be stored in a database
_broadcast_targets: list[dict] = []
_broadcast_history: list[dict] = []


class BroadcastStates(StatesGroup):
    """States for broadcast workflow"""

    waiting_for_channel = State()
    waiting_for_message = State()
    confirm_broadcast = State()


def get_broadcast_keyboard() -> InlineKeyboardMarkup:
    """Get main broadcast management keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Add channel/chat", callback_data="broadcast_add_channel"
                )
            ],
            [
                InlineKeyboardButton(
                    text="View target list", callback_data="broadcast_list_targets"
                ),
                InlineKeyboardButton(
                    text="Send broadcast", callback_data="broadcast_compose"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Broadcast history", callback_data="broadcast_history"
                )
            ],
        ]
    )


def get_broadcast_confirm_keyboard(message_preview: str) -> InlineKeyboardMarkup:
    """Get confirmation keyboard for broadcast"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Send to all channels", callback_data="broadcast_send_all"
                )
            ],
            [InlineKeyboardButton(text="Cancel", callback_data="broadcast_cancel")],
        ]
    )


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    """Handle /broadcast command — show broadcast management menu"""
    target_count = len(_broadcast_targets)
    text = (
        "*Broadcast / Outreach*\n\n"
        "Send promotional messages to Telegram channels and group chats.\n\n"
        f"*Registered targets:* {target_count}\n\n"
        "*How it works:*\n"
        "1. Add channels or group chats where this bot is an admin\n"
        "2. Compose your promotional message\n"
        "3. Send to all registered targets at once\n\n"
        "_Note: The bot must be an admin in each channel/chat to send messages._"
    )
    await message.answer(
        text, parse_mode="Markdown", reply_markup=get_broadcast_keyboard()
    )


@router.callback_query(F.data == "broadcast_add_channel")
async def broadcast_add_channel(callback: CallbackQuery, state: FSMContext):
    """Prompt user to enter channel username or ID"""
    await state.set_state(BroadcastStates.waiting_for_channel)
    await callback.message.edit_text(
        "*Add Channel or Group Chat*\n\n"
        "Enter the public username or chat ID of the channel/group:\n\n"
        "Examples:\n"
        "• `@my_channel`\n"
        "• `-1001234567890` (for groups/supergroups)\n\n"
        "_The bot must already be an admin in the target channel/group._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Cancel", callback_data="broadcast_cancel")]
            ]
        ),
    )
    await callback.answer()


@router.message(BroadcastStates.waiting_for_channel)
async def process_channel_input(message: Message, state: FSMContext, bot: Bot):
    """Process channel username/ID input and verify bot admin status"""
    channel_input = message.text.strip()

    # Parse channel identifier
    if channel_input.startswith("@"):
        channel_id = channel_input
    elif channel_input.lstrip("-").isdigit():
        channel_id = int(channel_input)
    else:
        await message.answer(
            "Invalid format. Please enter `@username` or a numeric chat ID.",
            parse_mode="Markdown",
        )
        return

    # Verify bot is admin in this channel/group
    try:
        chat = await bot.get_chat(channel_id)
        chat_member = await bot.get_chat_member(chat.id, bot.id)

        is_admin = chat_member.status in ("administrator", "creator")
        if not is_admin:
            await message.answer(
                f"*Bot is not an admin in {chat.title or channel_id}*\n\n"
                "Please add the bot as an admin first, then try again.",
                parse_mode="Markdown",
            )
            await state.clear()
            return

        # Check for duplicates
        existing_ids = [t["id"] for t in _broadcast_targets]
        if chat.id in existing_ids:
            await message.answer(
                f"*{chat.title}* is already in your target list.",
                parse_mode="Markdown",
                reply_markup=get_broadcast_keyboard(),
            )
            await state.clear()
            return

        # Add to target list
        target_info = {
            "id": chat.id,
            "title": chat.title or str(chat.id),
            "username": chat.username,
            "type": chat.type,
        }
        _broadcast_targets.append(target_info)

        await message.answer(
            f"*Added successfully!*\n\n"
            f"Channel/chat: *{chat.title}*\n"
            f"Type: {chat.type}\n"
            f"Total targets: {len(_broadcast_targets)}",
            parse_mode="Markdown",
            reply_markup=get_broadcast_keyboard(),
        )
        await state.clear()

    except TelegramBadRequest as e:
        logger.warning("Failed to get chat info: %s", e)
        await message.answer(
            "Could not find the channel/group. Make sure:\n"
            "• The username/ID is correct\n"
            "• The channel is public or the bot has been added\n\n"
            "Try again or /broadcast to return to menu.",
        )
        await state.clear()
    except TelegramForbiddenError:
        await message.answer(
            "Access denied. Make sure the bot is a member of this channel/group.",
        )
        await state.clear()
    except Exception as e:
        logger.error("Unexpected error adding channel: %s", e)
        await message.answer("An error occurred. Please try again.")
        await state.clear()


@router.callback_query(F.data == "broadcast_list_targets")
async def broadcast_list_targets(callback: CallbackQuery):
    """Show list of registered broadcast targets"""
    if not _broadcast_targets:
        await callback.message.edit_text(
            "*No channels/chats registered yet.*\n\n"
            "Add channels where this bot is an admin to get started.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Add channel", callback_data="broadcast_add_channel"
                        )
                    ],
                    [InlineKeyboardButton(text="Back", callback_data="broadcast_back")],
                ]
            ),
        )
        await callback.answer()
        return

    text = f"*Broadcast Targets ({len(_broadcast_targets)})*\n\n"
    buttons = []
    for i, target in enumerate(_broadcast_targets, 1):
        username_part = f" (@{target['username']})" if target.get("username") else ""
        text += f"{i}. *{target['title']}*{username_part}\n"
        text += f"   Type: {target['type']}\n\n"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"Remove: {target['title']}",
                    callback_data=f"broadcast_remove_{target['id']}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="Add more", callback_data="broadcast_add_channel"
            ),
            InlineKeyboardButton(text="Back", callback_data="broadcast_back"),
        ]
    )

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("broadcast_remove_"))
async def broadcast_remove_target(callback: CallbackQuery):
    """Remove a target from the broadcast list"""
    global _broadcast_targets
    target_id = int(callback.data.replace("broadcast_remove_", ""))

    target = next((t for t in _broadcast_targets if t["id"] == target_id), None)
    if not target:
        await callback.answer("Target not found", show_alert=True)
        return

    _broadcast_targets = [t for t in _broadcast_targets if t["id"] != target_id]

    await callback.answer(f"Removed: {target['title']}", show_alert=True)

    # Refresh list view
    await broadcast_list_targets(callback)


@router.callback_query(F.data == "broadcast_compose")
async def broadcast_compose(callback: CallbackQuery, state: FSMContext):
    """Start composing a broadcast message"""
    if not _broadcast_targets:
        await callback.answer(
            "No channels registered. Add channels first.", show_alert=True
        )
        return

    await state.set_state(BroadcastStates.waiting_for_message)
    await callback.message.edit_text(
        f"*Compose Broadcast Message*\n\n"
        f"Your message will be sent to *{len(_broadcast_targets)} channel(s)*.\n\n"
        "Type your promotional message below.\n\n"
        "_Tip: You can use Markdown formatting (bold, italic, links)._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Cancel", callback_data="broadcast_cancel")]
            ]
        ),
    )
    await callback.answer()


@router.message(BroadcastStates.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    """Process composed broadcast message and ask for confirmation"""
    broadcast_text = message.text or message.caption or ""

    if len(broadcast_text.strip()) < 5:
        await message.answer(
            "Message is too short. Please write at least 5 characters."
        )
        return

    await state.update_data(broadcast_text=broadcast_text)
    await state.set_state(BroadcastStates.confirm_broadcast)

    target_count = len(_broadcast_targets)
    preview = broadcast_text[:200] + ("..." if len(broadcast_text) > 200 else "")

    await message.answer(
        f"*Confirm Broadcast*\n\n"
        f"*Recipients:* {target_count} channel(s)\n\n"
        f"*Message preview:*\n"
        f"───────────────\n"
        f"{preview}\n"
        f"───────────────\n\n"
        f"Send this message to all registered channels?",
        parse_mode="Markdown",
        reply_markup=get_broadcast_confirm_keyboard(preview),
    )


@router.callback_query(
    F.data == "broadcast_send_all", BroadcastStates.confirm_broadcast
)
async def broadcast_send_all(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Execute the broadcast — send message to all targets"""
    data = await state.get_data()
    broadcast_text = data.get("broadcast_text", "")
    await state.clear()

    if not broadcast_text:
        await callback.answer("No message to send", show_alert=True)
        return

    await callback.message.edit_text(
        f"*Sending broadcast to {len(_broadcast_targets)} channel(s)...*",
        parse_mode="Markdown",
    )

    sent_count = 0
    failed_targets = []

    for target in _broadcast_targets:
        try:
            await bot.send_message(
                chat_id=target["id"],
                text=broadcast_text,
                parse_mode="Markdown",
            )
            sent_count += 1
            logger.info("Broadcast sent to %s (%s)", target["title"], target["id"])
        except TelegramForbiddenError:
            logger.warning("Bot was removed from channel %s", target["title"])
            failed_targets.append(f"{target['title']} (bot removed)")
        except TelegramBadRequest as e:
            logger.warning("Failed to send to %s: %s", target["title"], e)
            failed_targets.append(f"{target['title']} (error: {e})")
        except Exception as e:
            logger.error("Unexpected error sending to %s: %s", target["title"], e)
            failed_targets.append(target["title"])

    # Record broadcast in history
    from datetime import datetime, timezone

    _broadcast_history.append(
        {
            "text": broadcast_text,
            "sent_count": sent_count,
            "failed_count": len(failed_targets),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    result_text = (
        f"*Broadcast Complete*\n\n"
        f"Sent: *{sent_count}/{len(_broadcast_targets)}* channels\n"
    )

    if failed_targets:
        result_text += f"\n*Failed ({len(failed_targets)}):*\n"
        for f in failed_targets[:5]:
            result_text += f"• {f}\n"

    await callback.message.edit_text(
        result_text,
        parse_mode="Markdown",
        reply_markup=get_broadcast_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast_history")
async def broadcast_history_view(callback: CallbackQuery):
    """Show broadcast history"""
    if not _broadcast_history:
        await callback.message.edit_text(
            "*No broadcast history yet.*\n\n"
            "Send your first broadcast to see history here.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Back", callback_data="broadcast_back")]
                ]
            ),
        )
        await callback.answer()
        return

    text = f"*Broadcast History ({len(_broadcast_history)} total)*\n\n"
    for i, entry in enumerate(reversed(_broadcast_history[-10:]), 1):
        preview = entry["text"][:60] + ("..." if len(entry["text"]) > 60 else "")
        text += (
            f"{i}. {entry['timestamp'][:10]}\n"
            f"   Sent: {entry['sent_count']} | Failed: {entry['failed_count']}\n"
            f"   _{preview}_\n\n"
        )

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Back", callback_data="broadcast_back")]
            ]
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast_cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel current broadcast operation"""
    await state.clear()
    await callback.message.edit_text(
        "*Broadcast cancelled.*",
        parse_mode="Markdown",
        reply_markup=get_broadcast_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast_back")
async def broadcast_back(callback: CallbackQuery):
    """Return to broadcast menu"""
    target_count = len(_broadcast_targets)
    text = (
        "*Broadcast / Outreach*\n\n"
        "Send promotional messages to Telegram channels and group chats.\n\n"
        f"*Registered targets:* {target_count}\n\n"
        "*How it works:*\n"
        "1. Add channels or group chats where this bot is an admin\n"
        "2. Compose your promotional message\n"
        "3. Send to all registered targets at once\n\n"
        "_Note: The bot must be an admin in each channel/chat to send messages._"
    )
    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=get_broadcast_keyboard()
    )
    await callback.answer()


def get_targets() -> list[dict]:
    """Return current broadcast target list (for testing)"""
    return _broadcast_targets


def get_history() -> list[dict]:
    """Return broadcast history (for testing)"""
    return _broadcast_history


def clear_targets() -> None:
    """Clear broadcast targets (for testing)"""
    global _broadcast_targets
    _broadcast_targets = []


def clear_history() -> None:
    """Clear broadcast history (for testing)"""
    global _broadcast_history
    _broadcast_history = []
