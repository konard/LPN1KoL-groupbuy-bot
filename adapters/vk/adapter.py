"""
VK Adapter for GroupBuy Bot
Handles VK-specific message routing and formatting.

Supports both private messages (peer_id == from_id) and group conversations
(peer_id > 2_000_000_000 in VK's numbering scheme).

Group-chat features
-------------------
- Invite: share a deeplink so chat owners can add the bot to their conversation.
- Polls: create native VK polls for procurement voting.
- Stop amount: broadcast a stop-amount notification to the conversation.
- Payment: send a payment link into the group chat so members can pay directly.

Environment variables
---------------------
VK_TOKEN        – Community token (required)
VK_GROUP_ID     – VK community/group numeric ID (required for invite links)
BOT_SERVICE_URL – Internal bot service base URL (default: http://bot:8001)
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

import aiohttp
from vkbottle import API, Bot, Keyboard, KeyboardButtonColor, Text, Callback
from vkbottle.bot import Message

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# VK group-conversation peer_id lower bound
VK_CHAT_PEER_OFFSET = 2_000_000_000


class VKAdapter:
    """Adapter for VK messenger — supports private and group chats."""

    def __init__(self):
        self.token = os.getenv("VK_TOKEN", "")
        self.group_id = os.getenv("VK_GROUP_ID", "")
        self.bot_service_url = os.getenv("BOT_SERVICE_URL", "http://bot:8001")

        if not self.token:
            raise ValueError("VK_TOKEN is not set")

        self.api = API(self.token)
        self.bot = Bot(token=self.token)

        # Message queue for async processing
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.is_running = False

        self._register_handlers()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def is_group_chat(peer_id: int) -> bool:
        """Return True when *peer_id* refers to a VK multi-user conversation."""
        return peer_id > VK_CHAT_PEER_OFFSET

    # ------------------------------------------------------------------
    # Handler registration
    # ------------------------------------------------------------------

    def _register_handlers(self):
        """Register message handlers."""

        @self.bot.on.message()
        async def handle_all_messages(message: Message):
            """Handle all incoming messages."""
            standardized_msg = await self._standardize_message(message)
            await self.message_queue.put(standardized_msg)
            logger.info(
                "Message queued from user %s (peer_id=%s)",
                message.from_id,
                message.peer_id,
            )

        @self.bot.on.raw_event("message_event", dataclass=dict)
        async def handle_callback(event: dict):
            """Handle callback queries (button clicks)."""
            standardized_msg = await self._standardize_callback(event)
            await self.message_queue.put(standardized_msg)
            # Acknowledge the callback so the spinner disappears for the user
            try:
                await self.api.messages.send_message_event_answer(
                    event_id=event["object"]["event_id"],
                    user_id=event["object"]["user_id"],
                    peer_id=event["object"]["peer_id"],
                )
            except Exception as e:
                logger.error("Error answering callback: %s", e)

    # ------------------------------------------------------------------
    # Message standardisation
    # ------------------------------------------------------------------

    async def _standardize_message(self, message: Message) -> Dict[str, Any]:
        """Convert a VK message to the platform-neutral format."""
        user_info = {
            "first_name": "",
            "last_name": "",
            "username": f"id{message.from_id}",
            "language_code": "ru",
        }

        try:
            users = await self.api.users.get(user_ids=[message.from_id])
            if users:
                user = users[0]
                user_info["first_name"] = user.first_name
                user_info["last_name"] = user.last_name or ""
                user_info["username"] = f"id{user.id}"
        except Exception as e:
            logger.error("Error fetching user info: %s", e)

        return {
            "platform": "vk",
            "user_id": str(message.from_id),
            "chat_id": str(message.peer_id),
            "text": message.text or "",
            "message_id": str(message.conversation_message_id),
            "user_info": user_info,
            "timestamp": datetime.fromtimestamp(message.date).isoformat(),
            "type": "message",
            "is_group_chat": self.is_group_chat(message.peer_id),
        }

    async def _standardize_callback(self, event: dict) -> Dict[str, Any]:
        """Convert a VK callback event to the platform-neutral format."""
        event_obj = event.get("object", {})
        user_id = event_obj.get("user_id")
        peer_id = event_obj.get("peer_id", user_id)

        user_info = {
            "first_name": "",
            "last_name": "",
            "username": f"id{user_id}",
            "language_code": "ru",
        }

        try:
            users = await self.api.users.get(user_ids=[user_id])
            if users:
                user = users[0]
                user_info["first_name"] = user.first_name
                user_info["last_name"] = user.last_name or ""
        except Exception as e:
            logger.error("Error fetching user info: %s", e)

        return {
            "platform": "vk",
            "user_id": str(user_id),
            "chat_id": str(peer_id),
            "callback_data": event_obj.get("payload"),
            "message_id": str(event_obj.get("conversation_message_id", "")),
            "user_info": user_info,
            "timestamp": datetime.now().isoformat(),
            "type": "callback",
            "is_group_chat": self.is_group_chat(int(peer_id)) if peer_id else False,
        }

    # ------------------------------------------------------------------
    # Sending messages
    # ------------------------------------------------------------------

    async def send_message(
        self,
        peer_id: str,
        text: str,
        parse_mode: str = None,
        disable_web_page_preview: bool = False,
    ) -> bool:
        """Send a plain-text message to a user or group conversation."""
        try:
            await self.api.messages.send(
                peer_id=int(peer_id),
                message=text,
                random_id=0,
            )
            return True
        except Exception as e:
            logger.error("Error sending VK message: %s", e)
            return False

    async def send_message_with_keyboard(
        self,
        peer_id: str,
        text: str,
        keyboard: Dict[str, Any],
        parse_mode: str = None,
    ) -> bool:
        """Send a message with an inline keyboard to a user or group conversation."""
        try:
            vk_keyboard = self._convert_keyboard(keyboard)
            await self.api.messages.send(
                peer_id=int(peer_id),
                message=text,
                keyboard=vk_keyboard.get_json() if vk_keyboard else None,
                random_id=0,
            )
            return True
        except Exception as e:
            logger.error("Error sending VK message with keyboard: %s", e)
            return False

    def _convert_keyboard(self, keyboard: Dict[str, Any]) -> Optional[Keyboard]:
        """Convert the platform-neutral keyboard dict to a VK Keyboard object."""
        buttons = keyboard.get("buttons", [])
        if not buttons:
            return None

        vk_keyboard = Keyboard(inline=True)

        for row_idx, row in enumerate(buttons):
            if row_idx > 0:
                vk_keyboard.row()

            for button in row:
                button_text = button.get("text", "")
                callback_data = button.get("callback_data", "")
                url = button.get("url")

                if url:
                    # VK does not support inline URL buttons like Telegram;
                    # encode the URL in the callback payload instead.
                    vk_keyboard.add(
                        Callback(button_text, payload={"action": "url", "url": url}),
                        color=KeyboardButtonColor.PRIMARY,
                    )
                elif callback_data:
                    vk_keyboard.add(
                        Callback(
                            button_text,
                            payload={"action": "callback", "data": callback_data},
                        ),
                        color=KeyboardButtonColor.PRIMARY,
                    )
                else:
                    vk_keyboard.add(
                        Text(button_text), color=KeyboardButtonColor.SECONDARY
                    )

        return vk_keyboard

    # ------------------------------------------------------------------
    # Group-chat features
    # ------------------------------------------------------------------

    def get_invite_link(self) -> str:
        """
        Return a VK deeplink that chat owners can use to add this bot
        (community) to their multi-user conversation.

        The resulting link has the form:
            https://vk.me/join/<group_id>?from=chat_invite
        Chat admins tap the link and choose 'Add to chat'.
        """
        if not self.group_id:
            logger.warning("VK_GROUP_ID is not set – invite link will be incomplete")
        return f"https://vk.me/join/{self.group_id}?from=chat_invite"

    async def send_invite_link(self, peer_id: str, procurement_title: str = "") -> bool:
        """
        Send the invite link to a user (or group chat) so they can add the bot
        to their own conversation.

        Parameters
        ----------
        peer_id:
            Destination (user or chat peer_id as string).
        procurement_title:
            Optional procurement name included in the invite message.
        """
        invite_url = self.get_invite_link()
        subject = f" для закупки «{procurement_title}»" if procurement_title else ""
        text = (
            f"Чтобы использовать функции совместной закупки{subject} в вашем чате ВКонтакте, "
            f"добавьте нашего бота в беседу по ссылке:\n\n"
            f"{invite_url}\n\n"
            "После добавления бота участники смогут голосовать, отслеживать стоп-сумму "
            "и оплачивать заказы прямо в чате."
        )
        return await self.send_message(peer_id, text)

    async def create_poll_in_chat(
        self,
        peer_id: str,
        question: str,
        answers: List[str],
        is_anonymous: bool = False,
        is_multiple: bool = False,
    ) -> bool:
        """
        Create a native VK poll (опрос) inside a group conversation.

        VK polls are created as wall posts attached to a message; the bot must
        have the 'messages' and 'polls' permissions in the community token.

        Parameters
        ----------
        peer_id:
            The conversation peer_id (must be a group chat, i.e. > 2_000_000_000).
        question:
            Poll question text.
        answers:
            List of answer option strings (2–10 items).
        is_anonymous:
            Whether votes are anonymous.
        is_multiple:
            Whether multiple choices are allowed.
        """
        if not self.is_group_chat(int(peer_id)):
            logger.warning(
                "create_poll_in_chat called with non-group peer_id=%s", peer_id
            )
            return False

        if len(answers) < 2:
            logger.error("Poll requires at least 2 answer options")
            return False

        try:
            poll = await self.api.polls.create(
                question=question,
                add_answers=str(answers),  # JSON-encoded list expected by vkbottle
                is_anonymous=is_anonymous,
                is_multiple=is_multiple,
                owner_id=f"-{self.group_id}" if self.group_id else None,
            )

            if not poll or not hasattr(poll, "id"):
                logger.error("Failed to create poll object")
                return False

            owner_id = f"-{self.group_id}" if self.group_id else poll.owner_id
            attachment = f"poll{owner_id}_{poll.id}"

            await self.api.messages.send(
                peer_id=int(peer_id),
                attachment=attachment,
                random_id=0,
                message="",
            )
            logger.info(
                "Poll '%s' sent to peer_id=%s (attachment=%s)",
                question,
                peer_id,
                attachment,
            )
            return True
        except Exception as e:
            logger.error("Error creating poll in VK chat: %s", e)
            return False

    async def send_stop_amount_notification(
        self,
        peer_id: str,
        procurement_title: str,
        stop_amount: float,
        current_amount: float,
    ) -> bool:
        """
        Broadcast a stop-amount reached / approaching notification to a group chat.

        Parameters
        ----------
        peer_id:
            The conversation peer_id.
        procurement_title:
            Human-readable procurement name.
        stop_amount:
            The configured stop amount for the procurement.
        current_amount:
            The amount collected so far.
        """
        if current_amount >= stop_amount:
            status = "ДОСТИГНУТА"
            emoji = "🛑"
        else:
            remaining = stop_amount - current_amount
            pct = int(current_amount / stop_amount * 100)
            status = f"приближается ({pct}%, осталось {remaining:,.0f} ₽)"
            emoji = "⚠️"

        text = (
            f"{emoji} *Стоп-сумма по закупке «{procurement_title}»* {status}\n\n"
            f"Собрано: {current_amount:,.0f} ₽ из {stop_amount:,.0f} ₽\n\n"
            "Нажмите кнопку ниже, чтобы перейти к оплате или посмотреть детали закупки."
        )

        keyboard_data = {
            "buttons": [
                [
                    {
                        "text": "Оплатить",
                        "callback_data": f"payment_link_{peer_id}",
                    },
                    {
                        "text": "Детали закупки",
                        "callback_data": f"procurement_details_{peer_id}",
                    },
                ]
            ]
        }

        return await self.send_message_with_keyboard(peer_id, text, keyboard_data)

    async def send_payment_link_to_chat(
        self,
        peer_id: str,
        payment_url: str,
        amount: float,
        procurement_title: str,
    ) -> bool:
        """
        Send a payment link into a group chat so that members can pay directly.

        Parameters
        ----------
        peer_id:
            The conversation peer_id.
        payment_url:
            The confirmation/payment URL from the payment system.
        amount:
            Amount in RUB that the user needs to pay.
        procurement_title:
            Human-readable procurement name.
        """
        text = (
            f"💳 Оплата закупки «{procurement_title}»\n\n"
            f"Сумма: {amount:,.0f} ₽\n\n"
            "Перейдите по ссылке для оплаты:"
        )

        keyboard_data = {
            "buttons": [
                [
                    {
                        "text": "Оплатить",
                        "url": payment_url,
                    }
                ]
            ]
        }

        return await self.send_message_with_keyboard(peer_id, text, keyboard_data)

    # ------------------------------------------------------------------
    # User info
    # ------------------------------------------------------------------

    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a VK user."""
        try:
            users = await self.api.users.get(user_ids=[int(user_id)])
            if users:
                user = users[0]
                return {
                    "id": str(user.id),
                    "first_name": user.first_name,
                    "last_name": user.last_name or "",
                    "username": f"id{user.id}",
                }
            return None
        except Exception as e:
            logger.error("Error getting VK user info: %s", e)
            return None

    # ------------------------------------------------------------------
    # Queue processor
    # ------------------------------------------------------------------

    async def process_queue(self):
        """Process messages from queue and forward to bot service."""
        while self.is_running:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await self._route_message(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("Error processing queue: %s", e)

    async def _route_message(self, message: Dict[str, Any]):
        """Route a standardised message to the bot service."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.bot_service_url}/message", json=message
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        logger.warning("Bot service error: %s", text)
        except Exception as e:
            logger.error("Error routing message: %s", e)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        """Start the adapter."""
        self.is_running = True
        asyncio.create_task(self.process_queue())
        logger.info("Starting VK adapter…")
        await self.bot.run_polling()

    async def stop(self):
        """Stop the adapter."""
        self.is_running = False
        await self.api.http_client.close()


async def main():
    """Main entry point."""
    adapter = VKAdapter()
    try:
        await adapter.start()
    except KeyboardInterrupt:
        await adapter.stop()


if __name__ == "__main__":
    asyncio.run(main())
