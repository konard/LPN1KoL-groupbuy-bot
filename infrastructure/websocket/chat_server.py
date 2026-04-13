"""
WebSocket Chat Server for GroupBuy Bot
Provides real-time messaging in procurement chats
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, Set, Optional

import aiohttp
from aiohttp import web
import jwt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChatServer:
    """WebSocket server for procurement chats"""

    # Heartbeat interval (seconds) between server-sent pings
    PING_INTERVAL = 30
    # Number of consecutive missed pongs before a connection is considered dead
    MAX_MISSED_PONGS = 2

    def __init__(self, host: str = '0.0.0.0', port: int = 8765):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.setup_routes()

        # Connection storage: {procurement_id: {websocket1, websocket2, ...}}
        self.connections: Dict[int, Set[web.WebSocketResponse]] = {}

        # Tracks missed pong count per websocket to detect dead connections
        self._missed_pongs: Dict[web.WebSocketResponse, int] = {}

        # Message history (in production, use Redis)
        self.message_history: Dict[int, list] = {}

        # Core API URL
        self.core_api_url = os.getenv('CORE_API_URL', 'http://localhost:8000/api')

        # JWT secret (in production, use env var)
        self.jwt_secret = os.getenv('JWT_SECRET', 'your-secret-key')

    def setup_routes(self):
        """Setup HTTP and WebSocket routes"""
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/ws/procurement/{procurement_id}/', self.websocket_handler)

    async def health_check(self, request):
        """Health check endpoint"""
        return web.json_response({'status': 'healthy'})

    async def websocket_handler(self, request):
        """Handle WebSocket connections"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        procurement_id = int(request.match_info['procurement_id'])
        token = request.query.get('token')

        # Authenticate user
        user_id = await self.authenticate_user(token)
        if not user_id:
            await ws.close(code=1008, message=b'Unauthorized')
            return ws

        # Check access to procurement
        has_access = await self.check_procurement_access(user_id, procurement_id)
        if not has_access:
            await ws.close(code=1008, message=b'No access to procurement')
            return ws

        # Register connection
        await self.register_connection(procurement_id, ws, user_id)

        try:
            # Send message history
            await self.send_message_history(procurement_id, ws)

            # Notify about connection
            await self.broadcast_system_message(
                procurement_id,
                f"User {user_id} joined the chat",
                exclude_ws=ws
            )

            # Handle incoming messages
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self.handle_message(procurement_id, user_id, msg.data, ws)
                elif msg.type == aiohttp.WSMsgType.PONG:
                    # Client is alive — reset the missed-pong counter
                    self._missed_pongs[ws] = 0
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f'WebSocket error: {ws.exception()}')

        except Exception as e:
            logger.error(f"WebSocket handler error: {e}")
        finally:
            # Unregister connection
            await self.unregister_connection(procurement_id, ws, user_id)

            # Notify about disconnection
            await self.broadcast_system_message(
                procurement_id,
                f"User {user_id} left the chat"
            )

        return ws

    async def authenticate_user(self, token: str) -> Optional[int]:
        """Authenticate user by JWT token"""
        if not token:
            return None

        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            return payload.get('user_id')
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    async def check_procurement_access(self, user_id: int, procurement_id: int) -> bool:
        """Check if user has access to procurement chat"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.core_api_url}/procurements/{procurement_id}/check_access/',
                    json={'user_id': user_id}
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Error checking access: {e}")
            return False

    async def _heartbeat_loop(self, ws: web.WebSocketResponse, procurement_id: int):
        """Send periodic pings and terminate connections that miss too many pongs.

        aiohttp's WebSocketResponse automatically tracks pong responses; we count
        how many consecutive intervals pass without a pong and close stale sockets.
        """
        try:
            while not ws.closed:
                await asyncio.sleep(self.PING_INTERVAL)
                if ws.closed:
                    break
                try:
                    await ws.ping()
                    # Give the client one interval to reply before incrementing counter
                    # aiohttp resets pong tracking on each ping; we maintain our own counter
                    self._missed_pongs[ws] = self._missed_pongs.get(ws, 0) + 1
                    if self._missed_pongs[ws] > self.MAX_MISSED_PONGS:
                        logger.warning(
                            f"No pong from user {getattr(ws, 'user_id', '?')} in "
                            f"chat {procurement_id} after {self.MAX_MISSED_PONGS} pings — closing."
                        )
                        await ws.close(code=1001, message=b'Ping timeout')
                        break
                except Exception as e:
                    logger.debug(f"Heartbeat ping failed: {e}")
                    break
        except asyncio.CancelledError:
            pass

    async def register_connection(
        self,
        procurement_id: int,
        ws: web.WebSocketResponse,
        user_id: int
    ):
        """Register a new WebSocket connection"""
        if procurement_id not in self.connections:
            self.connections[procurement_id] = set()

        # Store user_id on the websocket object
        ws.user_id = user_id
        self.connections[procurement_id].add(ws)
        self._missed_pongs[ws] = 0

        # Start per-connection heartbeat task
        asyncio.ensure_future(self._heartbeat_loop(ws, procurement_id))

        logger.info(f"User {user_id} connected to chat {procurement_id}")

    async def unregister_connection(
        self,
        procurement_id: int,
        ws: web.WebSocketResponse,
        user_id: int
    ):
        """Remove a WebSocket connection"""
        if procurement_id in self.connections:
            self.connections[procurement_id].discard(ws)

            # Remove empty rooms
            if not self.connections[procurement_id]:
                del self.connections[procurement_id]

        self._missed_pongs.pop(ws, None)

        logger.info(f"User {user_id} disconnected from chat {procurement_id}")

    async def send_message_history(
        self,
        procurement_id: int,
        ws: web.WebSocketResponse
    ):
        """Send message history to a new connection"""
        if procurement_id in self.message_history:
            # Send last 50 messages
            history = self.message_history[procurement_id][-50:]
            for msg in history:
                try:
                    await ws.send_json(msg)
                except Exception as e:
                    logger.error(f"Error sending history: {e}")

    async def handle_message(
        self,
        procurement_id: int,
        user_id: int,
        message_data: str,
        sender_ws: web.WebSocketResponse
    ):
        """Handle incoming message from client"""
        try:
            data = json.loads(message_data)
            message_type = data.get('type', 'message')

            if message_type == 'message':
                text = data.get('text', '').strip()
                if not text:
                    return

                # Create message object
                message = {
                    'type': 'message',
                    'user_id': user_id,
                    'text': text,
                    'timestamp': datetime.now().isoformat(),
                    'message_id': f"{user_id}_{datetime.now().timestamp()}"
                }

                # Save to history
                if procurement_id not in self.message_history:
                    self.message_history[procurement_id] = []
                self.message_history[procurement_id].append(message)

                # Broadcast to all participants
                await self.broadcast_message(procurement_id, message)

                # Save to database via API
                await self.save_message_to_db(procurement_id, user_id, text)

            elif message_type == 'typing':
                # Broadcast typing indicator
                typing_msg = {
                    'type': 'typing',
                    'user_id': user_id,
                    'is_typing': data.get('is_typing', False)
                }
                await self.broadcast_message(
                    procurement_id,
                    typing_msg,
                    exclude_ws=sender_ws
                )

        except json.JSONDecodeError:
            logger.error("Invalid JSON in message")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def broadcast_message(
        self,
        procurement_id: int,
        message: dict,
        exclude_ws: web.WebSocketResponse = None
    ):
        """Broadcast message to all connections in a chat"""
        if procurement_id not in self.connections:
            return

        message_json = json.dumps(message)

        for ws in list(self.connections[procurement_id]):
            if ws is exclude_ws:
                continue

            try:
                await ws.send_str(message_json)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                # Remove broken connection
                self.connections[procurement_id].discard(ws)

    async def broadcast_system_message(
        self,
        procurement_id: int,
        text: str,
        exclude_ws: web.WebSocketResponse = None
    ):
        """Broadcast system message"""
        system_message = {
            'type': 'system',
            'text': text,
            'timestamp': datetime.now().isoformat()
        }
        await self.broadcast_message(procurement_id, system_message, exclude_ws)

    async def save_message_to_db(
        self,
        procurement_id: int,
        user_id: int,
        text: str
    ):
        """Save message to database via Core API"""
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f'{self.core_api_url}/chat/messages/',
                    json={
                        'procurement_id': procurement_id,
                        'user_id': user_id,
                        'text': text
                    }
                )
        except Exception as e:
            logger.error(f"Failed to save message to DB: {e}")

    async def run(self):
        """Run the WebSocket server"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

        logger.info(f"Chat server started on {self.host}:{self.port}")

        # Keep running
        await asyncio.Event().wait()


async def main():
    """Main entry point"""
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8765))

    server = ChatServer(host, port)
    await server.run()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped")
