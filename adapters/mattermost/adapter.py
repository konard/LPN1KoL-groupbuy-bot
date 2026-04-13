"""
Mattermost Adapter for GroupBuy Bot
Handles Mattermost-specific message routing and formatting.

Integration approach:
  - Outgoing Webhooks: Mattermost POSTs to this adapter when users send messages.
  - Incoming Webhooks: This adapter POSTs to Mattermost to send messages back.
  - Slash Commands: Mattermost POSTs slash-command payloads to this adapter.
  - Interactive Buttons: Mattermost POSTs button-click payloads; adapter forwards
    action to the bot service and may reply inline.
  - REST API: When MATTERMOST_BOT_TOKEN is set, the adapter uses the Mattermost
    REST API to look up user info and send direct messages more reliably.

Environment variables required:
  MATTERMOST_URL        – Base URL of the Mattermost server (e.g. https://mm.example.com)
  MATTERMOST_TOKEN      – Outgoing-webhook / slash-command token for request verification
  MATTERMOST_WEBHOOK_URL – Incoming webhook URL used to post messages back to Mattermost
  MATTERMOST_BOT_TOKEN  – (optional) Bot-user personal-access token for REST API calls
  BOT_SERVICE_URL       – URL of the internal bot service (default: http://bot:8001)
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Optional

import aiohttp
from aiohttp import web

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MattermostAdapter
# ---------------------------------------------------------------------------
class MattermostAdapter:
    """Adapter that bridges Mattermost and the internal GroupBuy bot service."""

    def __init__(self) -> None:
        self.mattermost_url: str = os.getenv("MATTERMOST_URL", "").rstrip("/")
        self.token: str = os.getenv("MATTERMOST_TOKEN", "")
        self.webhook_url: str = os.getenv("MATTERMOST_WEBHOOK_URL", "")
        self.bot_token: str = os.getenv("MATTERMOST_BOT_TOKEN", "")
        self.bot_service_url: str = os.getenv(
            "BOT_SERVICE_URL", "http://bot:8001"
        ).rstrip("/")
        # Public base URL of this adapter service, used as the reply_url sent to
        # the bot service so it can POST replies back here.
        self.adapter_url: str = os.getenv(
            "MATTERMOST_ADAPTER_URL", "http://mattermost-adapter:8002"
        ).rstrip("/")

        if not self.token:
            raise ValueError("MATTERMOST_TOKEN is not set")
        if not self.webhook_url:
            raise ValueError("MATTERMOST_WEBHOOK_URL is not set")

        # Queue for decoupled async message processing
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.is_running: bool = False

        # aiohttp web app that receives Mattermost hooks
        self.app = web.Application()
        self._register_routes()

    # ------------------------------------------------------------------
    # HTTP routes
    # ------------------------------------------------------------------
    def _register_routes(self) -> None:
        """Register HTTP routes for incoming Mattermost events."""
        self.app.router.add_post("/webhook", self._handle_webhook)
        self.app.router.add_post("/slash", self._handle_slash)
        self.app.router.add_post("/mattermost_action", self._handle_action)
        self.app.router.add_post("/send", self._handle_send)
        self.app.router.add_get("/health", self._handle_health)

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Health-check endpoint."""
        return web.json_response({"status": "ok"})

    async def _handle_send(self, request: web.Request) -> web.Response:
        """
        Receive a reply from the bot service and forward it to Mattermost.

        The bot service POSTs ``{"user_id": <str>, "text": <str>}`` here after
        processing a command that arrived via ``/webhook`` or ``/slash``.
        This is the reply path that makes the Mattermost bot actually respond
        to user commands.
        """
        try:
            data = await request.json()
        except Exception as exc:
            logger.error("Failed to parse /send request: %s", exc)
            return web.Response(status=400, text="Bad Request")

        user_id = data.get("user_id", "")
        text = data.get("text", "")

        if not user_id or not text:
            return web.Response(status=400, text="Missing user_id or text")

        success = await self.send_message(user_id, text)
        if success:
            return web.json_response({"status": "ok"})
        return web.Response(status=502, text="Failed to deliver message to Mattermost")

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        """
        Handle incoming Mattermost outgoing-webhook requests.

        Mattermost can send payloads as:
          - application/x-www-form-urlencoded  (outgoing webhooks)
          - application/json                   (custom integrations)
        """
        content_type = request.content_type or ""

        try:
            if "json" in content_type:
                data: dict[str, Any] = await request.json()
            else:
                form = await request.post()
                data = dict(form)
        except Exception as exc:
            logger.error("Failed to parse Mattermost webhook request: %s", exc)
            return web.Response(status=400, text="Bad Request")

        # Verify the shared token so we only process genuine Mattermost events
        incoming_token = data.get("token", "")
        if incoming_token != self.token:
            logger.warning(
                "Webhook token mismatch – ignoring request (got %r)", incoming_token
            )
            return web.Response(status=403, text="Forbidden")

        # Normalise and enqueue
        standardized = self._standardize_message(data)
        await self.message_queue.put(standardized)

        # Return an empty 200 so Mattermost doesn't display an error to the user.
        # Actual bot replies are sent asynchronously via the incoming webhook.
        return web.Response(status=200)

    async def _handle_slash(self, request: web.Request) -> web.Response:
        """
        Handle Mattermost slash-command requests.

        Slash-command payloads are always application/x-www-form-urlencoded and
        include a ``command`` field (e.g. ``/groupbuy``) and a ``text`` field with
        the arguments supplied by the user.  The adapter converts the payload to
        the standardised format and returns an immediate acknowledgement so
        Mattermost doesn't time out while the bot processes the command.
        """
        try:
            form = await request.post()
            data = dict(form)
        except Exception as exc:
            logger.error("Failed to parse Mattermost slash request: %s", exc)
            return web.Response(status=400, text="Bad Request")

        incoming_token = data.get("token", "")
        if incoming_token != self.token:
            logger.warning(
                "Slash token mismatch – ignoring request (got %r)", incoming_token
            )
            return web.Response(status=403, text="Forbidden")

        standardized = self._standardize_slash(data)
        await self.message_queue.put(standardized)

        # Immediate ephemeral acknowledgement visible only to the caller
        return web.json_response(
            {"response_type": "ephemeral", "text": "Processing your request…"}
        )

    async def _handle_action(self, request: web.Request) -> web.Response:
        """
        Handle Mattermost interactive-button (integration action) requests.

        When a user clicks a button rendered as a Mattermost attachment action,
        Mattermost POSTs a JSON payload to the URL configured in the action's
        ``integration.url`` field.  This handler decodes that payload, converts
        it to the standardised callback format, and enqueues it for processing.
        """
        try:
            data = await request.json()
        except Exception as exc:
            logger.error("Failed to parse Mattermost action request: %s", exc)
            return web.Response(status=400, text="Bad Request")

        standardized = self._standardize_action(data)
        await self.message_queue.put(standardized)

        # Respond with an updated message to acknowledge the button click
        return web.json_response({"update": {"props": {}}})

    # ------------------------------------------------------------------
    # Message standardisation
    # ------------------------------------------------------------------
    def _standardize_message(self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert a Mattermost outgoing-webhook payload to the standardised format."""
        user_id = data.get("user_id", "")
        user_name = data.get("user_name", "")
        text = data.get("text", "")

        # Remove the trigger_word prefix so bot sees clean command text
        trigger_word = data.get("trigger_word", "")
        if trigger_word and text.startswith(trigger_word):
            text = text[len(trigger_word) :].strip()

        # Channel information (used as the "chat_id" equivalent)
        channel_id = data.get("channel_id", "")

        return {
            "platform": "mattermost",
            "user_id": user_id,
            "chat_id": channel_id,
            "text": text,
            "message_id": data.get("post_id", ""),
            "user_info": {
                "first_name": user_name,
                "last_name": "",
                "username": user_name,
                "language_code": "en",
                "channel_name": data.get("channel_name", ""),
                "team_id": data.get("team_id", ""),
                "team_domain": data.get("team_domain", ""),
            },
            "timestamp": datetime.now().isoformat(),
            "type": "message",
            # reply_url allows the bot service to POST the reply back to this
            # adapter, which then forwards it to Mattermost.
            "reply_url": f"{self.adapter_url}/send",
        }

    def _standardize_slash(self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert a Mattermost slash-command payload to the standardised format."""
        user_id = data.get("user_id", "")
        user_name = data.get("user_name", "")
        command = data.get("command", "")
        text = data.get("text", "")

        # Reconstruct the full command text the way other adapters see it
        full_text = f"{command} {text}".strip() if text else command

        return {
            "platform": "mattermost",
            "user_id": user_id,
            "chat_id": data.get("channel_id", ""),
            "text": full_text,
            "message_id": "",
            "user_info": {
                "first_name": user_name,
                "last_name": "",
                "username": user_name,
                "language_code": "en",
                "channel_name": data.get("channel_name", ""),
                "team_id": data.get("team_id", ""),
                "team_domain": data.get("team_domain", ""),
            },
            "timestamp": datetime.now().isoformat(),
            "type": "slash_command",
            "reply_url": f"{self.adapter_url}/send",
        }

    def _standardize_action(self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert a Mattermost interactive-button payload to the standardised format."""
        # Action payloads arrive as: {"user_id": ..., "user_name": ...,
        #   "channel_id": ..., "post_id": ..., "context": {"action": ...}}
        user_id = data.get("user_id", "")
        user_name = data.get("user_name", "")
        context = data.get("context", {})
        callback_data = context.get("action", "")

        return {
            "platform": "mattermost",
            "user_id": user_id,
            "callback_data": callback_data,
            "message_id": data.get("post_id", ""),
            "user_info": {
                "first_name": user_name,
                "last_name": "",
                "username": user_name,
                "language_code": "en",
                "channel_name": data.get("channel_name", ""),
                "team_id": data.get("team_id", ""),
                "team_domain": data.get("team_domain", ""),
            },
            "timestamp": datetime.now().isoformat(),
            "type": "callback",
        }

    # ------------------------------------------------------------------
    # REST API helpers
    # ------------------------------------------------------------------
    def _rest_headers(self) -> dict[str, str]:
        """Return HTTP headers for Mattermost REST API requests."""
        return {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json",
        }

    async def get_user_info(self, user_id: str) -> Optional[dict[str, Any]]:
        """
        Fetch user information from the Mattermost REST API.

        Requires ``MATTERMOST_URL`` and ``MATTERMOST_BOT_TOKEN`` to be set.
        Returns ``None`` when the REST API is unavailable or the request fails.
        """
        if not self.mattermost_url or not self.bot_token:
            logger.debug(
                "get_user_info: MATTERMOST_URL or MATTERMOST_BOT_TOKEN not set, skipping"
            )
            return None

        url = f"{self.mattermost_url}/api/v4/users/{user_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._rest_headers()) as response:
                    if response.status != 200:
                        body = await response.text()
                        logger.error(
                            "get_user_info: REST API returned %d: %s",
                            response.status,
                            body,
                        )
                        return None
                    user = await response.json()
                    return {
                        "id": user.get("id", ""),
                        "first_name": user.get("first_name", ""),
                        "last_name": user.get("last_name", ""),
                        "username": user.get("username", ""),
                        "email": user.get("email", ""),
                        "nickname": user.get("nickname", ""),
                    }
        except Exception as exc:
            logger.error("Error fetching Mattermost user info: %s", exc)
            return None

    async def _get_direct_channel_id(
        self, session: aiohttp.ClientSession, user_id: str
    ) -> Optional[str]:
        """
        Create or fetch the direct-message channel between the bot and *user_id*.

        Uses the Mattermost REST API ``POST /api/v4/channels/direct``.
        Returns ``None`` when the REST API is unavailable.
        """
        if not self.mattermost_url or not self.bot_token:
            return None

        # First, look up the bot's own user ID
        url_me = f"{self.mattermost_url}/api/v4/users/me"
        try:
            async with session.get(url_me, headers=self._rest_headers()) as resp:
                if resp.status != 200:
                    return None
                me = await resp.json()
                bot_user_id = me.get("id", "")
        except Exception as exc:
            logger.error("Error fetching bot user ID: %s", exc)
            return None

        url_dm = f"{self.mattermost_url}/api/v4/channels/direct"
        try:
            async with session.post(
                url_dm,
                headers=self._rest_headers(),
                json=[bot_user_id, user_id],
            ) as resp:
                if resp.status not in (200, 201):
                    body = await resp.text()
                    logger.error(
                        "_get_direct_channel_id: REST API returned %d: %s",
                        resp.status,
                        body,
                    )
                    return None
                channel = await resp.json()
                return channel.get("id")
        except Exception as exc:
            logger.error("Error creating DM channel: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Sending messages back to Mattermost
    # ------------------------------------------------------------------
    async def send_message(
        self,
        user_id: str,
        text: str,
        parse_mode: Optional[str] = None,
        disable_web_page_preview: bool = False,
    ) -> bool:
        """
        Send a plain-text message to a Mattermost user.

        Prefers the REST API (when ``MATTERMOST_BOT_TOKEN`` and
        ``MATTERMOST_URL`` are set) which opens/reuses a proper DM channel.
        Falls back to the incoming-webhook approach (@username addressing).
        """
        if self.mattermost_url and self.bot_token:
            return await self._send_via_rest(user_id, {"message": text})
        return await self._post_to_mattermost({"text": text, "channel": f"@{user_id}"})

    async def send_message_with_keyboard(
        self,
        user_id: str,
        text: str,
        keyboard: dict[str, Any],
        parse_mode: Optional[str] = None,
    ) -> bool:
        """
        Send a message with interactive buttons using Mattermost message attachments.

        The standardised keyboard format uses:
          { "buttons": [ [ {"text": ..., "callback_data": ..., "url": ...} ], … ] }
        Each inner list becomes one row of action buttons.

        Prefers the REST API when ``MATTERMOST_BOT_TOKEN`` is available.
        """
        attachments = self._convert_keyboard_to_attachments(keyboard, text)

        if self.mattermost_url and self.bot_token:
            return await self._send_via_rest(
                user_id, {"message": text, "props": {"attachments": attachments}}
            )

        payload: dict[str, Any] = {
            "channel": f"@{user_id}",
            "attachments": attachments,
        }
        return await self._post_to_mattermost(payload)

    def _convert_keyboard_to_attachments(
        self, keyboard: dict[str, Any], fallback_text: str
    ) -> list[dict[str, Any]]:
        """Convert the standardised keyboard to Mattermost attachment actions."""
        buttons = keyboard.get("buttons", [])
        actions: list[dict[str, Any]] = []

        for row in buttons:
            for button in row:
                button_text = button.get("text", "")
                callback_data = button.get("callback_data", "")
                url = button.get("url", "")

                # The integration URL must be reachable by the Mattermost server.
                # When Mattermost runs on a different host, bot_service_url
                # (e.g. http://bot:8001) is not publicly accessible.  Use the
                # adapter's own public URL instead — the adapter already exposes
                # the /mattermost_action route and forwards the action to the bot.
                action: dict[str, Any] = {
                    "name": button_text,
                    "integration": {
                        "url": f"{self.adapter_url}/mattermost_action",
                        "context": {"action": callback_data or url},
                    },
                }
                if url:
                    action["type"] = "button"
                    action["integration"]["context"]["url"] = url
                else:
                    action["type"] = "button"

                actions.append(action)

        return [
            {
                "fallback": fallback_text,
                "text": fallback_text,
                "actions": actions,
            }
        ]

    async def _send_via_rest(self, user_id: str, post_body: dict[str, Any]) -> bool:
        """
        Post a message to a user's DM channel via the Mattermost REST API.

        ``post_body`` is merged with ``{"channel_id": <dm_channel_id>}`` before
        being POSTed to ``POST /api/v4/posts``.
        """
        try:
            async with aiohttp.ClientSession() as session:
                channel_id = await self._get_direct_channel_id(session, user_id)
                if not channel_id:
                    logger.warning(
                        "_send_via_rest: could not get DM channel for user %s, "
                        "falling back to incoming webhook",
                        user_id,
                    )
                    return await self._post_to_mattermost(
                        {**post_body, "channel": f"@{user_id}"}
                    )

                payload = {**post_body, "channel_id": channel_id}
                url = f"{self.mattermost_url}/api/v4/posts"
                async with session.post(
                    url, headers=self._rest_headers(), json=payload
                ) as response:
                    if response.status not in (200, 201):
                        body = await response.text()
                        logger.error(
                            "_send_via_rest: REST API returned %d: %s",
                            response.status,
                            body,
                        )
                        return False
                    return True
        except Exception as exc:
            logger.error("Error sending message via REST API: %s", exc)
            return False

    async def _post_to_mattermost(self, payload: dict[str, Any]) -> bool:
        """POST a JSON payload to the Mattermost incoming webhook URL."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status != 200:
                        body = await response.text()
                        logger.error(
                            "Mattermost webhook returned %d: %s",
                            response.status,
                            body,
                        )
                        return False
                    return True
        except Exception as exc:
            logger.error("Error posting to Mattermost: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Queue processor – routes messages to the internal bot service
    # ------------------------------------------------------------------
    async def process_queue(self) -> None:
        """Continuously drain the message queue and forward to bot service."""
        while self.is_running:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await self._route_message(message)
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                logger.error("Error in queue processor: %s", exc)

    async def _route_message(self, message: dict[str, Any]) -> None:
        """Forward a standardised message to the bot service."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.bot_service_url}/message", json=message
                ) as response:
                    if response.status != 200:
                        body = await response.text()
                        logger.warning("Bot service error: %s", body)
        except Exception as exc:
            logger.error("Error routing message to bot service: %s", exc)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """Start the adapter: launch the queue processor and the HTTP server."""
        self.is_running = True
        asyncio.create_task(self.process_queue())

        host = os.getenv("ADAPTER_HOST", "0.0.0.0")
        port = int(os.getenv("ADAPTER_PORT", "8002"))

        logger.info("Starting Mattermost adapter on %s:%d …", host, port)
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()

        # Keep the coroutine alive
        while self.is_running:
            await asyncio.sleep(1)

        await runner.cleanup()

    async def stop(self) -> None:
        """Stop the adapter gracefully."""
        self.is_running = False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def main() -> None:
    adapter = MattermostAdapter()
    try:
        await adapter.start()
    except KeyboardInterrupt:
        await adapter.stop()


if __name__ == "__main__":
    asyncio.run(main())
