"""
User command handlers
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

import time

from api_client import api_client
from keyboards import (
    get_main_keyboard,
    get_guest_keyboard,
    get_profile_keyboard,
    get_balance_keyboard,
    get_deposit_keyboard,
)
from dialogs.registration import start_registration

router = Router()

_bot_start_time = time.time()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command.

    Registered users get their full menu; guests can browse freely.
    Registration is only triggered when the user wants to participate
    (join a procurement, enter a chat, etc.).
    """
    user_exists = await api_client.check_user_exists(
        platform="telegram", platform_user_id=str(message.from_user.id)
    )

    if user_exists:
        user = await api_client.get_user_by_platform(
            platform="telegram", platform_user_id=str(message.from_user.id)
        )
        role = user.get("role", "buyer") if user else "buyer"
        await message.answer(
            f"Welcome back, {user.get('first_name', 'User')}!",
            reply_markup=get_main_keyboard(role),
        )
    else:
        # Allow free browsing — do not force registration on entry
        first_name = message.from_user.first_name or "Guest"
        await message.answer(
            f"Welcome to GroupBuy Bot, {first_name}!\n\n"
            "You can browse active procurements without registering.\n"
            "Registration is only needed when you want to join a procurement or write in a chat.\n\n"
            "Use the menu below to get started:",
            reply_markup=get_guest_keyboard(),
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command"""
    help_text = (
        "*Available Commands:*\n\n"
        "*Profile:*\n"
        "/start - Start or re-register\n"
        "/profile - View and edit your profile\n"
        "/balance - Check your balance\n\n"
        "*Procurements:*\n"
        "/procurements - Browse active procurements\n"
        "/my\\_procurements - Your procurements\n"
        "/search - Search procurements by keyword\n"
        "/create\\_procurement - Create new (organizers only)\n\n"
        "*Chat:*\n"
        "/chat - Enter procurement chat\n\n"
        "*Payments:*\n"
        "/deposit - Top up your balance\n"
        "/transactions - Payment history\n\n"
        "*Notifications:*\n"
        "/notifications - View unread notifications\n\n"
        "*Broadcast:*\n"
        "/broadcast - Send messages to channels and groups\n\n"
        "*Help:*\n"
        "/help - This help message\n"
        "/status - Bot health status"
    )
    await message.answer(help_text, parse_mode="Markdown")


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Handle /status command — show bot health"""
    from config import config as bot_config

    uptime_seconds = int(time.time() - _bot_start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Check API connectivity
    api_ok = False
    try:
        result = await api_client.get_procurements(limit=1)
        api_ok = result is not None
    except Exception:
        api_ok = False

    api_status = "OK" if api_ok else "Unavailable"
    mode = bot_config.bot_mode.upper()

    status_text = (
        f"*Bot Status*\n\n"
        f"*Mode:* {mode}\n"
        f"*Uptime:* {hours}h {minutes}m {seconds}s\n"
        f"*API:* {api_status}\n"
        f"*API URL:* `{bot_config.core_api_url}`"
    )
    await message.answer(status_text, parse_mode="Markdown")


@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext):
    """Handle /profile command"""
    user = await api_client.get_user_by_platform(
        platform="telegram", platform_user_id=str(message.from_user.id)
    )

    if not user:
        await start_registration(message, state, reason="profile")
        return

    role_display = {
        "buyer": "Buyer",
        "organizer": "Organizer",
        "supplier": "Supplier",
    }.get(user.get("role"), user.get("role", "Unknown"))

    profile_text = (
        f"*Your Profile*\n\n"
        f"*Name:* {user.get('first_name', '')} {user.get('last_name', '')}\n"
        f"*Phone:* {user.get('phone', 'Not set')}\n"
        f"*Email:* {user.get('email', 'Not set')}\n"
        f"*Role:* {role_display}\n"
        f"*Balance:* {user.get('balance', 0)} RUB\n"
        f"*Registered:* {user.get('created_at', '')[:10]}"
    )

    await message.answer(
        profile_text, parse_mode="Markdown", reply_markup=get_profile_keyboard()
    )


@router.message(Command("balance"))
async def cmd_balance(message: Message, state: FSMContext):
    """Handle /balance command"""
    user = await api_client.get_user_by_platform(
        platform="telegram", platform_user_id=str(message.from_user.id)
    )

    if not user:
        await start_registration(message, state, reason="balance")
        return

    balance_data = await api_client.get_user_balance(user["id"])

    if balance_data:
        balance_text = (
            f"*Your Balance:* {balance_data.get('balance', 0)} RUB\n\n"
            f"*Statistics:*\n"
            f"- Deposited: {balance_data.get('total_deposited', 0)} RUB\n"
            f"- Spent: {balance_data.get('total_spent', 0)} RUB\n"
            f"- Available: {balance_data.get('available', 0)} RUB"
        )
    else:
        balance_text = f"*Your Balance:* {user.get('balance', 0)} RUB"

    await message.answer(
        balance_text, parse_mode="Markdown", reply_markup=get_balance_keyboard()
    )


@router.message(Command("deposit"))
async def cmd_deposit(message: Message, state: FSMContext):
    """Handle /deposit command — show deposit options"""
    user = await api_client.get_user_by_platform(
        platform="telegram", platform_user_id=str(message.from_user.id)
    )

    if not user:
        await start_registration(message, state, reason="balance")
        return

    await message.answer(
        "*Deposit to Balance*\n\nSelect amount to deposit:",
        parse_mode="Markdown",
        reply_markup=get_deposit_keyboard(),
    )


@router.message(F.text == "Profile")
async def text_profile(message: Message, state: FSMContext):
    """Handle 'Profile' text button"""
    await cmd_profile(message, state)


@router.message(F.text == "Balance")
async def text_balance(message: Message, state: FSMContext):
    """Handle 'Balance' text button"""
    await cmd_balance(message, state)


@router.message(F.text == "Help")
async def text_help(message: Message):
    """Handle 'Help' text button"""
    await cmd_help(message)


@router.callback_query(F.data == "deposit_options")
async def deposit_options(callback: CallbackQuery):
    """Show deposit options"""
    await callback.message.edit_text(
        "*Deposit to Balance*\n\nSelect amount to deposit:",
        parse_mode="Markdown",
        reply_markup=get_deposit_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("deposit_"))
async def process_deposit(callback: CallbackQuery):
    """Process deposit selection"""
    amount_str = callback.data.replace("deposit_", "")

    if amount_str == "custom":
        await callback.message.edit_text(
            "Please enter the amount you want to deposit (minimum 100 RUB):",
            reply_markup=None,
        )
        # Set state for custom amount input
        # This would require FSMContext
        await callback.answer()
        return

    try:
        amount = int(amount_str)
    except ValueError:
        await callback.answer("Invalid amount", show_alert=True)
        return

    user = await api_client.get_user_by_platform(
        platform="telegram", platform_user_id=str(callback.from_user.id)
    )

    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    payment = await api_client.create_payment(
        user_id=user["id"], amount=amount, description=f"Deposit {amount} RUB"
    )

    if payment and payment.get("confirmation_url"):
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Pay", url=payment["confirmation_url"])],
                [
                    InlineKeyboardButton(
                        text="Check status",
                        callback_data=f"check_payment_{payment['id']}",
                    )
                ],
            ]
        )

        await callback.message.edit_text(
            f"*Payment: {amount} RUB*\n\n"
            f"Click the button below to pay.\n\n"
            f"*Important:*\n"
            f"- Link is valid for 24 hours\n"
            f"- Balance will update automatically after payment",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    else:
        await callback.message.edit_text(
            "Failed to create payment. Please try again later.",
            reply_markup=get_balance_keyboard(),
        )

    await callback.answer()


@router.callback_query(F.data.startswith("check_payment_"))
async def check_payment_status(callback: CallbackQuery):
    """Check payment status"""
    payment_id = callback.data.split("_")[2]

    payment_status = await api_client.get_payment_status(int(payment_id))

    if not payment_status:
        await callback.answer("Could not check status", show_alert=True)
        return

    status = payment_status.get("status", "unknown")

    if status == "succeeded":
        await callback.message.edit_text(
            f"*Payment Confirmed!*\n\n"
            f"Amount: {payment_status.get('amount', 0)} RUB\n"
            f"Time: {payment_status.get('paid_at', '')[:19]}\n\n"
            f"Your balance has been updated.",
            parse_mode="Markdown",
            reply_markup=get_balance_keyboard(),
        )
    elif status == "pending":
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Check again", callback_data=f"check_payment_{payment_id}"
                    )
                ]
            ]
        )

        await callback.message.edit_text(
            f"*Payment Processing*\n\n"
            f"Amount: {payment_status.get('amount', 0)} RUB\n"
            f"Waiting for bank confirmation...",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    else:
        await callback.message.edit_text(
            f"*Payment Failed*\n\nStatus: {status}\n\nPlease try again.",
            parse_mode="Markdown",
            reply_markup=get_deposit_keyboard(),
        )

    await callback.answer()


@router.callback_query(F.data == "refresh_balance")
async def refresh_balance(callback: CallbackQuery):
    """Refresh balance"""
    user = await api_client.get_user_by_platform(
        platform="telegram", platform_user_id=str(callback.from_user.id)
    )

    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    balance_data = await api_client.get_user_balance(user["id"])

    if balance_data:
        balance_text = (
            f"*Your Balance:* {balance_data.get('balance', 0)} RUB\n\n"
            f"*Statistics:*\n"
            f"- Deposited: {balance_data.get('total_deposited', 0)} RUB\n"
            f"- Spent: {balance_data.get('total_spent', 0)} RUB\n"
            f"- Available: {balance_data.get('available', 0)} RUB"
        )
    else:
        balance_text = f"*Your Balance:* {user.get('balance', 0)} RUB"

    await callback.message.edit_text(
        balance_text, parse_mode="Markdown", reply_markup=get_balance_keyboard()
    )
    await callback.answer("Balance updated")


@router.callback_query(F.data == "payment_history")
async def payment_history(callback: CallbackQuery):
    """Show payment history"""
    user = await api_client.get_user_by_platform(
        platform="telegram", platform_user_id=str(callback.from_user.id)
    )

    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    history = await api_client.get_payment_history(user["id"])

    if not history:
        await callback.answer("No payment history", show_alert=True)
        return

    history_text = "*Payment History*\n\n"

    for i, payment in enumerate(history, 1):
        status_emoji = {"succeeded": "", "pending": "", "cancelled": ""}.get(
            payment.get("status", ""), ""
        )

        history_text += (
            f"{i}. {status_emoji} *{payment.get('amount', 0)} RUB*\n"
            f"   Status: {payment.get('status_display', payment.get('status', ''))}\n"
            f"   Date: {payment.get('created_at', '')[:10]}\n\n"
        )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Back", callback_data="refresh_balance")]
        ]
    )

    await callback.message.edit_text(
        history_text, parse_mode="Markdown", reply_markup=keyboard
    )
    await callback.answer()


@router.message(Command("transactions"))
async def cmd_transactions(message: Message):
    """Handle /transactions command — show payment history"""
    user = await api_client.get_user_by_platform(
        platform="telegram", platform_user_id=str(message.from_user.id)
    )

    if not user:
        await message.answer("You are not registered. Use /start to register.")
        return

    history = await api_client.get_payment_history(user["id"])

    if not history:
        await message.answer("No payment history yet.")
        return

    history_text = "*Payment History*\n\n"
    for i, payment in enumerate(history, 1):
        status_emoji = {"succeeded": "", "pending": "", "cancelled": ""}.get(
            payment.get("status", ""), ""
        )
        history_text += (
            f"{i}. {status_emoji} *{payment.get('amount', 0)} RUB*\n"
            f"   Status: {payment.get('status_display', payment.get('status', ''))}\n"
            f"   Date: {payment.get('created_at', '')[:10]}\n\n"
        )

    await message.answer(
        history_text, parse_mode="Markdown", reply_markup=get_balance_keyboard()
    )


@router.message(Command("notifications"))
async def cmd_notifications(message: Message):
    """Handle /notifications command"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    user = await api_client.get_user_by_platform(
        platform="telegram", platform_user_id=str(message.from_user.id)
    )

    if not user:
        await message.answer("You are not registered. Use /start to register.")
        return

    notifications = await api_client.get_notifications(user["id"], unread_only=True)

    if not notifications:
        await message.answer(
            "No new notifications.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Show all", callback_data="notifications_all"
                        )
                    ]
                ]
            ),
        )
        return

    text = f"*Notifications ({len(notifications)} unread)*\n\n"
    for notif in notifications[:10]:
        text += f"• {notif.get('text', notif.get('message', ''))}\n"
        if notif.get("created_at"):
            text += f"  _{notif['created_at'][:10]}_\n"
        text += "\n"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Mark all as read", callback_data="notifications_mark_read"
                )
            ],
            [InlineKeyboardButton(text="Show all", callback_data="notifications_all")],
        ]
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)


@router.callback_query(F.data == "notifications_all")
async def notifications_all(callback: CallbackQuery):
    """Show all notifications"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    user = await api_client.get_user_by_platform(
        platform="telegram", platform_user_id=str(callback.from_user.id)
    )

    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    notifications = await api_client.get_notifications(user["id"], unread_only=False)

    if not notifications:
        await callback.answer("No notifications", show_alert=True)
        return

    text = f"*All Notifications ({len(notifications)})*\n\n"
    for notif in notifications[:15]:
        read_mark = "" if notif.get("is_read") else ""
        text += f"{read_mark} {notif.get('text', notif.get('message', ''))}\n"
        if notif.get("created_at"):
            text += f"  _{notif['created_at'][:10]}_\n"
        text += "\n"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Back", callback_data="refresh_balance")]
        ]
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "notifications_mark_read")
async def notifications_mark_read(callback: CallbackQuery):
    """Mark all notifications as read (placeholder)"""
    await callback.answer("All notifications marked as read.", show_alert=True)
