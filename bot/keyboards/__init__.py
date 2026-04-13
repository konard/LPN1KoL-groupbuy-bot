"""
Keyboard utilities for the bot
"""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)


def get_guest_keyboard() -> ReplyKeyboardMarkup:
    """Get reply keyboard for unauthenticated (guest) users"""
    buttons = [
        [KeyboardButton(text="Procurements")],
        [KeyboardButton(text="Help")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_main_keyboard(role: str = "buyer") -> ReplyKeyboardMarkup:
    """Get main reply keyboard based on user role"""
    buttons = [
        [KeyboardButton(text="Procurements"), KeyboardButton(text="My Orders")],
        [KeyboardButton(text="Profile"), KeyboardButton(text="Balance")],
    ]

    if role == "organizer":
        buttons.insert(1, [KeyboardButton(text="Create Procurement")])

    if role == "supplier":
        buttons.insert(1, [KeyboardButton(text="My Supplies")])

    buttons.append([KeyboardButton(text="Help")])

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_role_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for role selection"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Buyer", callback_data="role_buyer"),
                InlineKeyboardButton(text="Organizer", callback_data="role_organizer"),
            ],
            [InlineKeyboardButton(text="Supplier", callback_data="role_supplier")],
        ]
    )


def get_procurements_keyboard(procurements: list) -> InlineKeyboardMarkup:
    """Get keyboard for procurement list"""
    buttons = []

    for proc in procurements[:10]:
        progress = proc.get("progress", 0)
        title = proc.get("title", "Unknown")
        btn_text = f"{title} ({progress}%)"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=btn_text, callback_data=f"view_proc_{proc['id']}"
                )
            ]
        )

    # Navigation buttons
    buttons.append(
        [
            InlineKeyboardButton(text="By City", callback_data="filter_city"),
            InlineKeyboardButton(text="By Category", callback_data="filter_category"),
        ]
    )
    buttons.append(
        [InlineKeyboardButton(text="Search", callback_data="search_procurement")]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_procurement_detail_keyboard(
    procurement_id: int, can_join: bool = True, is_participant: bool = False
) -> InlineKeyboardMarkup:
    """Get keyboard for procurement details"""
    buttons = []

    if can_join:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="Join", callback_data=f"join_proc_{procurement_id}"
                )
            ]
        )

    if is_participant:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="Leave procurement",
                    callback_data=f"leave_proc_{procurement_id}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(text="Chat", callback_data=f"chat_{procurement_id}"),
            InlineKeyboardButton(
                text="Participants", callback_data=f"participants_{procurement_id}"
            ),
        ]
    )
    buttons.append(
        [
            InlineKeyboardButton(
                text="Refresh", callback_data=f"refresh_proc_{procurement_id}"
            )
        ]
    )
    buttons.append(
        [
            InlineKeyboardButton(
                text="Back to list", callback_data="back_to_procurements"
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_deposit_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for deposit amount selection"""
    amounts = [100, 500, 1000, 2000, 5000, 10000]
    buttons = []

    row = []
    for amount in amounts:
        row.append(
            InlineKeyboardButton(
                text=f"{amount} RUB", callback_data=f"deposit_{amount}"
            )
        )
        if len(row) == 3:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append(
        [InlineKeyboardButton(text="Custom amount", callback_data="deposit_custom")]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_balance_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for balance management"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Deposit", callback_data="deposit_options"),
                InlineKeyboardButton(text="History", callback_data="payment_history"),
            ],
            [InlineKeyboardButton(text="Refresh", callback_data="refresh_balance")],
        ]
    )


def get_profile_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for profile management"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Edit phone", callback_data="edit_phone"),
                InlineKeyboardButton(text="Edit email", callback_data="edit_email"),
            ],
            [InlineKeyboardButton(text="Change role", callback_data="change_role")],
        ]
    )


def get_categories_keyboard(categories: list) -> InlineKeyboardMarkup:
    """Get keyboard for category selection (browse/filter, uses 'category_' prefix)"""
    buttons = []
    row = []

    for cat in categories:
        row.append(
            InlineKeyboardButton(
                text=cat.get("name", "Unknown"), callback_data=f"category_{cat['id']}"
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_procurement_category_keyboard(categories: list) -> InlineKeyboardMarkup:
    """Get keyboard for category selection during procurement creation.

    Uses the 'proc_category_' prefix so these callbacks are handled by the
    procurement-creation FSM handler and don't collide with the browse filter.
    """
    buttons = []
    row = []

    for cat in categories:
        row.append(
            InlineKeyboardButton(
                text=cat.get("name", "Unknown"),
                callback_data=f"proc_category_{cat['id']}",
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirmation_keyboard(action: str, item_id: int) -> InlineKeyboardMarkup:
    """Get confirmation keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Confirm", callback_data=f"confirm_{action}_{item_id}"
                ),
                InlineKeyboardButton(
                    text="Cancel", callback_data=f"cancel_{action}_{item_id}"
                ),
            ]
        ]
    )
