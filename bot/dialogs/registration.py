"""
Registration dialog for new users.

Registration is lazy — it is only triggered when the user actually wants to
participate (join a procurement, enter a chat, use their profile/balance, etc.).
Guests can browse all public content without registering.

Only a phone number is required.  The user's name is taken from their Telegram
profile automatically; email is intentionally not collected during sign-up
because users share personal data voluntarily and at their own discretion.

After selecting a role the user is asked to send a selfie photo for identity
verification.  The photo is stored server-side and is visible only to admins.
If the user has no camera (or chooses to skip), they can send the /skip_photo
command and registration will still complete without a selfie.
"""

import re

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from api_client import api_client
from keyboards import get_role_keyboard, get_main_keyboard


class RegistrationStates(StatesGroup):
    """Registration dialog states"""

    waiting_for_phone = State()
    waiting_for_role = State()
    waiting_for_selfie = State()


router = Router()


def validate_phone(phone: str) -> bool:
    """Validate phone format"""
    return bool(re.match(r"^\+?[1-9]\d{10,14}$", phone))


# Map of reasons to user-facing messages shown before registration starts
_REASON_MESSAGES = {
    "join": "To join a procurement you need to register first.",
    "chat": "To write in a chat you need to register first.",
    "profile": "To view your profile you need to register first.",
    "balance": "To check your balance you need to register first.",
}


async def _finish_registration(
    message: Message,
    state: FSMContext,
    role: str,
    selfie_file_id: str = "",
) -> None:
    """Complete registration after the selfie step (with or without a photo)."""
    data = await state.get_data()

    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")

    user_data = {
        "platform": "telegram",
        "platform_user_id": data.get("platform_user_id", ""),
        "username": data.get("username", ""),
        "first_name": first_name,
        "last_name": last_name,
        "phone": data.get("phone", ""),
        # email is intentionally omitted — users share it voluntarily later
        "email": "",
        "role": role,
        "language_code": data.get("language_code", "en"),
        "selfie_file_id": selfie_file_id,
    }

    result = await api_client.register_user(user_data)

    await state.clear()

    if result:
        role_display = {
            "buyer": "Buyer",
            "organizer": "Organizer",
            "supplier": "Supplier",
        }.get(role, role)

        await message.answer(
            f"Registration complete!\n\n"
            f"You are registered as: {role_display}\n\n"
            f"Use the menu below to navigate.",
        )
        await message.answer(
            "Welcome to GroupBuy Bot!", reply_markup=get_main_keyboard(role)
        )
    else:
        await message.answer(
            "Registration failed. Please try again later.\nUse /start to restart.",
        )


@router.message(RegistrationStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    """Process phone input"""
    phone = message.text.strip()

    if not validate_phone(phone):
        await message.answer("Please enter a valid phone number (e.g., +79991234567).")
        return

    if not phone.startswith("+"):
        phone = "+" + phone

    await state.update_data(phone=phone)
    await state.set_state(RegistrationStates.waiting_for_role)
    await message.answer(
        "Almost done! Please select your role:", reply_markup=get_role_keyboard()
    )


@router.callback_query(F.data.startswith("role_"), RegistrationStates.waiting_for_role)
async def process_role(callback: CallbackQuery, state: FSMContext):
    """Process role selection and prompt for selfie photo."""
    role = callback.data.split("_")[1]

    # Store all user data and role so the selfie handler can use them
    await state.update_data(
        role=role,
        platform_user_id=str(callback.from_user.id),
        username=callback.from_user.username or "",
        first_name=callback.from_user.first_name or "",
        last_name=callback.from_user.last_name or "",
        language_code=callback.from_user.language_code or "en",
    )
    await state.set_state(RegistrationStates.waiting_for_selfie)

    await callback.message.edit_text(
        "Almost there!\n\n"
        "For identity verification please send a selfie photo (a photo of your face).\n\n"
        "If your device does not have a camera or you prefer to skip, "
        "send /skip_photo and registration will complete without a photo.",
        reply_markup=None,
    )
    await callback.answer()


@router.message(RegistrationStates.waiting_for_selfie, F.photo)
async def process_selfie(message: Message, state: FSMContext):
    """Accept a selfie photo and complete registration."""
    # Use the highest-resolution version of the photo
    photo = message.photo[-1]
    selfie_file_id = photo.file_id

    data = await state.get_data()
    role = data.get("role", "buyer")

    await _finish_registration(message, state, role, selfie_file_id=selfie_file_id)


@router.message(RegistrationStates.waiting_for_selfie, Command("skip_photo"))
async def skip_selfie(message: Message, state: FSMContext):
    """Allow users without a camera (or who prefer not to send a photo) to skip."""
    data = await state.get_data()
    role = data.get("role", "buyer")

    await _finish_registration(message, state, role, selfie_file_id="")


@router.message(RegistrationStates.waiting_for_selfie)
async def selfie_invalid(message: Message, state: FSMContext):
    """Remind the user to send a photo or skip."""
    await message.answer(
        "Please send a photo (selfie) or use /skip_photo to skip this step."
    )


async def start_registration(
    message: Message, state: FSMContext, reason: str = ""
) -> None:
    """Start the registration process.

    ``reason`` is a short key that explains *why* registration is needed
    (e.g. "join", "chat", "profile", "balance").  An appropriate context
    message is shown to the user before the phone-number prompt.
    """
    context_msg = _REASON_MESSAGES.get(reason, "")
    intro = (f"{context_msg}\n\n" if context_msg else "") + (
        "Registration is quick — we only need your phone number.\n"
        "Your name is taken from your Telegram profile automatically.\n\n"
        "Please enter your phone number (e.g., +79991234567):"
    )

    await state.set_state(RegistrationStates.waiting_for_phone)
    await message.answer(intro)
