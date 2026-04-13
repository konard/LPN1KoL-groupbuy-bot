"""
Telegram Adapter for GroupBuy Bot
Handles Telegram-specific message routing and formatting
"""

import asyncio
import logging
import os
import socket
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Retry configuration for Telegram API network errors
_MAX_RETRY_ATTEMPTS = 5
_RETRY_BASE_DELAY = 5  # seconds


class TelegramAdapter:
    """Adapter for Telegram messenger"""

    def __init__(self):
        self.token = os.getenv("TELEGRAM_TOKEN", "")
        self.bot_service_url = os.getenv("BOT_SERVICE_URL", "http://bot:8001")
        self.proxy_url = self._resolve_proxy_url()

        if not self.token:
            raise ValueError("TELEGRAM_TOKEN is not set")

        # Build bot session with optional proxy
        if self.proxy_url:
            logger.info("Using proxy for Telegram: %s", self.proxy_url)
            session = AiohttpSession(proxy=self.proxy_url)
        else:
            session = AiohttpSession()

        self.bot = Bot(token=self.token, session=session)
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)

        # Persistent aiohttp session for routing messages to the bot service
        self._http_session: Optional[aiohttp.ClientSession] = None

        # Message queue for async processing
        self.message_queue = asyncio.Queue()
        self.is_running = False

        self._register_handlers()

    @staticmethod
    def _check_proxy_reachable(proxy_url: str) -> bool:
        """Check if the proxy host is reachable via DNS lookup."""
        try:
            parsed = urlparse(proxy_url)
            host = parsed.hostname or ""
            port = parsed.port or 1080
            socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
            return True
        except (socket.gaierror, OSError) as exc:
            logger.warning("Proxy %s is not reachable: %s", proxy_url, exc)
            return False

    @staticmethod
    def _resolve_proxy_url() -> str:
        """Determine proxy URL from environment variables.

        Priority:
        1. TELEGRAM_PROXY_URL — explicit external proxy (HTTP or SOCKS5)
        2. TELEGRAM_USE_PROXY=true — use the built-in Docker SOCKS5 proxy
           at socks5://telegram-proxy:1080
        3. Empty string — direct connection

        If the resolved proxy is not reachable (DNS lookup fails), falls back
        to a direct connection so the adapter can still start.
        """
        explicit = os.getenv("TELEGRAM_PROXY_URL", "").strip()
        if explicit:
            return explicit

        use_builtin = os.getenv("TELEGRAM_USE_PROXY", "").strip().lower()
        if use_builtin in ("true", "1", "yes"):
            proxy = "socks5://telegram-proxy:1080"
            if TelegramAdapter._check_proxy_reachable(proxy):
                logger.info(
                    "TELEGRAM_USE_PROXY=true: using built-in SOCKS5 proxy at %s",
                    proxy,
                )
                return proxy
            logger.warning(
                "TELEGRAM_USE_PROXY=true but the proxy at %s is not reachable. "
                "Make sure the 'proxy' Docker Compose profile is active "
                "(--profile proxy). Falling back to direct connection.",
                proxy,
            )
            return ""

        return ""

    def _register_handlers(self):
        """Register message handlers"""

        @self.dp.message()
        async def handle_all_messages(message: types.Message):
            """Handle all incoming messages"""
            standardized_msg = self._standardize_message(message)
            await self.message_queue.put(standardized_msg)
            logger.info(f"Message queued from user {message.from_user.id}")

        @self.dp.callback_query()
        async def handle_callback(callback_query: types.CallbackQuery):
            """Handle callback queries"""
            standardized_msg = self._standardize_callback(callback_query)
            await self.message_queue.put(standardized_msg)
            await self.bot.answer_callback_query(callback_query.id)

    def _standardize_message(self, message: types.Message) -> Dict[str, Any]:
        """Convert Telegram message to standardized format"""
        return {
            "platform": "telegram",
            "user_id": str(message.from_user.id),
            "chat_id": str(message.chat.id),
            "text": message.text or "",
            "message_id": str(message.message_id),
            "user_info": {
                "first_name": message.from_user.first_name,
                "last_name": message.from_user.last_name or "",
                "username": message.from_user.username or "",
                "language_code": message.from_user.language_code or "en",
            },
            "timestamp": message.date.isoformat()
            if message.date
            else datetime.now().isoformat(),
            "type": "message",
        }

    def _standardize_callback(
        self, callback_query: types.CallbackQuery
    ) -> Dict[str, Any]:
        """Convert callback query to standardized format"""
        return {
            "platform": "telegram",
            "user_id": str(callback_query.from_user.id),
            "callback_data": callback_query.data,
            "message_id": str(callback_query.message.message_id)
            if callback_query.message
            else "",
            "user_info": {
                "first_name": callback_query.from_user.first_name,
                "last_name": callback_query.from_user.last_name or "",
                "username": callback_query.from_user.username or "",
                "language_code": callback_query.from_user.language_code or "en",
            },
            "timestamp": datetime.now().isoformat(),
            "type": "callback",
        }

    async def send_message(
        self,
        user_id: str,
        text: str,
        parse_mode: str = None,
        disable_web_page_preview: bool = False,
    ) -> bool:
        """Send message to Telegram user"""
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
            return True
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

    async def send_message_with_keyboard(
        self,
        user_id: str,
        text: str,
        keyboard: Dict[str, Any],
        parse_mode: str = "Markdown",
    ) -> bool:
        """Send message with keyboard"""
        try:
            # Convert standardized keyboard to Telegram format
            markup = self._convert_keyboard(keyboard)

            await self.bot.send_message(
                chat_id=user_id, text=text, reply_markup=markup, parse_mode=parse_mode
            )
            return True
        except Exception as e:
            logger.error(f"Error sending Telegram message with keyboard: {e}")
            return False

    def _convert_keyboard(self, keyboard: Dict[str, Any]) -> types.InlineKeyboardMarkup:
        """Convert standardized keyboard to Telegram InlineKeyboardMarkup"""
        buttons = keyboard.get("buttons", [])
        inline_keyboard = []

        for row in buttons:
            inline_row = []
            for button in row:
                inline_row.append(
                    types.InlineKeyboardButton(
                        text=button.get("text", ""),
                        callback_data=button.get("callback_data", ""),
                        url=button.get("url"),
                    )
                )
            inline_keyboard.append(inline_row)

        return types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a Telegram user"""
        try:
            user = await self.bot.get_chat(user_id)
            return {
                "id": str(user.id),
                "first_name": user.first_name,
                "last_name": user.last_name or "",
                "username": user.username or "",
            }
        except Exception as e:
            logger.error(f"Error getting Telegram user info: {e}")
            return None

    async def _get_http_session(self) -> aiohttp.ClientSession:
        """Return a persistent aiohttp session, creating it if needed."""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._http_session

    async def process_queue(self):
        """Process messages from queue and send to bot service"""
        while self.is_running:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await self._route_message(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing queue: {e}")

    async def _route_message(self, message: Dict[str, Any]):
        """Route message to bot service"""
        try:
            session = await self._get_http_session()
            async with session.post(
                f"{self.bot_service_url}/message", json=message
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    logger.warning(f"Bot service error: {text}")
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error routing message to bot service: {e}")
        except Exception as e:
            logger.error(f"Error routing message: {e}")

    async def start(self):
        """Start the adapter with retry on network errors."""
        self.is_running = True

        # Start queue processor
        asyncio.create_task(self.process_queue())

        attempt = 0
        while True:
            try:
                logger.info("Starting Telegram adapter (attempt %d)...", attempt + 1)
                await self.dp.start_polling(self.bot)
                # start_polling returned normally — exit the retry loop
                break
            except Exception as e:
                attempt += 1
                if attempt >= _MAX_RETRY_ATTEMPTS:
                    logger.error(
                        "Telegram adapter failed after %d attempts: %s",
                        _MAX_RETRY_ATTEMPTS,
                        e,
                    )
                    raise

                delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Telegram network error (attempt %d/%d): %s. "
                    "Retrying in %d seconds...",
                    attempt,
                    _MAX_RETRY_ATTEMPTS,
                    e,
                    delay,
                )
                await asyncio.sleep(delay)

    async def stop(self):
        """Stop the adapter"""
        self.is_running = False
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
        await self.bot.session.close()


async def main():
    """Main entry point"""
    adapter = TelegramAdapter()

    try:
        await adapter.start()
    except KeyboardInterrupt:
        await adapter.stop()


if __name__ == "__main__":
    asyncio.run(main())
