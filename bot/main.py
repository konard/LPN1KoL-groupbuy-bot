"""
Main entry point for the GroupBuy Bot
"""

import asyncio
import logging
import sys
from typing import Dict, Any

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from handlers import (
    user_commands,
    procurement_commands,
    chat_commands,
    broadcast_commands,
)
from dialogs import registration


# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Bot and dispatcher are module-level so the message server can access them
_bot: Bot = None
_dp: Dispatcher = None


async def _send_adapter_reply(reply_url: str, user_id: str, text: str) -> None:
    """POST a reply back to the platform adapter that sent the original message."""
    import aiohttp

    payload = {"user_id": user_id, "text": text}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(reply_url, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning(
                        "Adapter reply_url returned %d: %s", resp.status, body
                    )
    except Exception as exc:
        logger.error("Failed to POST reply to adapter reply_url %s: %s", reply_url, exc)


def _build_command_reply(text: str, user_info: Dict[str, Any]) -> str:
    """
    Return a plain-text reply for the given command text.

    Handles the slash commands that the bot exposes, producing the same
    informational responses that Telegram users receive.  This is intentionally
    simple — it mirrors the text from the aiogram handlers in handlers/ without
    requiring a full aiogram dispatcher round-trip for non-Telegram platforms.
    """
    cmd = text.strip().split()[0].lower() if text.strip() else ""
    # Normalise both "/start" and "start" forms
    if cmd.startswith("/"):
        cmd = cmd[1:]

    first_name = user_info.get("first_name", "") or user_info.get("username", "User")

    if cmd == "start":
        return (
            f"Welcome to GroupBuy Bot, {first_name}!\n\n"
            "You can browse active procurements without registering.\n"
            "Registration is only needed when you want to join a procurement or write in a chat.\n\n"
            "Available commands:\n"
            "/help - List all commands\n"
            "/procurements - Browse active procurements\n"
            "/profile - View your profile\n"
            "/balance - Check your balance"
        )

    if cmd == "help":
        return (
            "Available Commands:\n\n"
            "Profile:\n"
            "/start - Start or re-register\n"
            "/profile - View and edit your profile\n"
            "/balance - Check your balance\n\n"
            "Procurements:\n"
            "/procurements - Browse active procurements\n"
            "/my_procurements - Your procurements\n"
            "/search - Search procurements by keyword\n"
            "/create_procurement - Create new (organizers only)\n\n"
            "Chat:\n"
            "/chat - Enter procurement chat\n\n"
            "Payments:\n"
            "/deposit - Top up your balance\n"
            "/transactions - Payment history\n\n"
            "Notifications:\n"
            "/notifications - View unread notifications\n\n"
            "Help:\n"
            "/help - This help message\n"
            "/status - Bot health status"
        )

    if cmd == "status":
        return "Bot is running."

    if cmd in (
        "procurements",
        "my_procurements",
        "profile",
        "balance",
        "deposit",
        "transactions",
        "notifications",
        "chat",
        "search",
        "create_procurement",
        "broadcast",
    ):
        return (
            f"Command /{cmd} received. "
            "Please use the web interface or Telegram to access the full functionality."
        )

    if text.strip():
        return "I received your message. Use /help to see available commands."

    return ""


async def handle_adapter_message(request: web.Request) -> web.Response:
    """
    HTTP endpoint that receives messages from platform adapters (VK, Mattermost).

    Adapter services POST a standardised message dict here.  When the payload
    includes a ``reply_url`` field the bot processes the command and POSTs the
    reply back to that URL so the adapter can forward it to the user.
    """
    try:
        data: Dict[str, Any] = await request.json()
    except Exception as e:
        logger.warning("Invalid JSON in adapter message: %s", e)
        return web.json_response({"error": "Invalid JSON"}, status=400)

    platform = data.get("platform", "unknown")
    user_id = data.get("user_id", "")
    text = data.get("text", "")
    msg_type = data.get("type", "message")
    reply_url = data.get("reply_url", "")
    user_info: Dict[str, Any] = data.get("user_info", {})

    logger.info(
        "Received %s message from platform=%s user=%s", msg_type, platform, user_id
    )

    if msg_type in ("message", "slash_command") and text and reply_url:
        logger.debug("Adapter message text: %s", text[:100])
        reply_text = _build_command_reply(text, user_info)
        if reply_text:
            await _send_adapter_reply(reply_url, user_id, reply_text)

    return web.json_response({"status": "ok"})


async def handle_health(request: web.Request) -> web.Response:
    """Health check endpoint"""
    return web.json_response({"status": "ok", "service": "bot"})


async def start_adapter_server() -> web.AppRunner:
    """Start the HTTP server for adapter message routing on port 8001."""
    app = web.Application()
    app.router.add_post("/message", handle_adapter_message)
    app.router.add_get("/health", handle_health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8001)
    await site.start()
    logger.info("Adapter message server listening on port 8001")
    return runner


async def main():
    """Main function to start the bot"""
    global _bot, _dp

    # Check for token
    if not config.telegram_token:
        logger.error("TELEGRAM_TOKEN is not set!")
        sys.exit(1)

    # Initialize bot and dispatcher
    _bot = Bot(
        token=config.telegram_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    storage = MemoryStorage()
    _dp = Dispatcher(storage=storage)

    # Register routers
    _dp.include_router(user_commands.router)
    _dp.include_router(procurement_commands.router)
    _dp.include_router(chat_commands.router)
    _dp.include_router(broadcast_commands.router)
    _dp.include_router(registration.router)

    logger.info("Starting GroupBuy Bot in %s mode...", config.bot_mode)

    # Always start the adapter message server so VK/Mattermost adapters can
    # forward messages even when the bot is running in polling mode.
    adapter_runner = await start_adapter_server()

    try:
        if config.bot_mode == "webhook" and config.webhook_host:
            from aiogram.webhook.aiohttp_server import (
                SimpleRequestHandler,
                setup_application,
            )

            webhook_url = f"{config.webhook_host}{config.webhook_path}"
            await _bot.set_webhook(webhook_url, drop_pending_updates=True)
            logger.info("Webhook set to: %s", webhook_url)

            app = web.Application()
            handler = SimpleRequestHandler(dispatcher=_dp, bot=_bot)
            handler.register(app, path=config.webhook_path)
            setup_application(app, _dp, bot=_bot)

            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", 8080)
            await site.start()
            logger.info("Webhook server started on port 8080")

            # Keep running
            await asyncio.Event().wait()
        else:
            # Default: long polling
            await _bot.delete_webhook(drop_pending_updates=True)
            await _dp.start_polling(_bot)
    finally:
        await adapter_runner.cleanup()
        await _bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
