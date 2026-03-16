"""
============================================================
AKSHAY AI CORE — WebSocket Manager
============================================================
Real-time communication for live updates and streaming.
============================================================
"""

import asyncio
import json
from typing import Dict, Set, Optional, Any
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

from core.config import settings
from core.utils.logger import get_logger
from core.security.auth_manager import auth_manager

logger = get_logger("websocket")


class ConnectionManager:
    """
    Manages WebSocket connections for real-time communication.
    
    Features:
    - Connection pooling
    - Channel-based messaging
    - Heartbeat monitoring
    - Authenticated connections
    """
    
    def __init__(self):
        # Active connections by user ID
        self._connections: Dict[str, Set[WebSocket]] = {}
        # Channel subscriptions
        self._channels: Dict[str, Set[str]] = {}  # channel -> user_ids
        # Connection metadata
        self._metadata: Dict[WebSocket, Dict] = {}
    
    async def handle_connection(self, websocket: WebSocket) -> None:
        """
        Handle a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
        """
        await websocket.accept()
        
        try:
            # Wait for authentication message
            auth_message = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=30.0,
            )
            
            # Verify token
            token = auth_message.get("token")
            if not token:
                await websocket.send_json({"error": "Authentication required"})
                await websocket.close(code=1008)
                return
            
            payload = auth_manager.verify_session_token(token)
            if not payload:
                await websocket.send_json({"error": "Invalid token"})
                await websocket.close(code=1008)
                return
            
            user_id = payload["sub"]
            
            # Register connection
            await self._register_connection(websocket, user_id)
            
            # Send welcome message
            await websocket.send_json({
                "type": "connected",
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
            })
            
            logger.info("WebSocket connected", user_id=user_id)
            
            # Handle messages
            await self._message_loop(websocket, user_id)
            
        except asyncio.TimeoutError:
            logger.warning("WebSocket auth timeout")
            await websocket.close(code=1008)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error("WebSocket error", error=str(e))
        finally:
            await self._unregister_connection(websocket)
    
    async def _register_connection(self, websocket: WebSocket, user_id: str) -> None:
        """Register a new connection."""
        if user_id not in self._connections:
            self._connections[user_id] = set()
        
        self._connections[user_id].add(websocket)
        self._metadata[websocket] = {
            "user_id": user_id,
            "connected_at": datetime.utcnow(),
            "channels": set(),
        }
    
    async def _unregister_connection(self, websocket: WebSocket) -> None:
        """Unregister a connection."""
        metadata = self._metadata.get(websocket)
        if not metadata:
            return
        
        user_id = metadata["user_id"]
        
        # Remove from user connections
        if user_id in self._connections:
            self._connections[user_id].discard(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]
        
        # Remove from channels
        for channel in metadata["channels"]:
            if channel in self._channels:
                self._channels[channel].discard(user_id)
        
        # Remove metadata
        del self._metadata[websocket]
        
        logger.info("WebSocket disconnected", user_id=user_id)
    
    async def _message_loop(self, websocket: WebSocket, user_id: str) -> None:
        """Main message handling loop."""
        while True:
            try:
                message = await websocket.receive_json()
                await self._handle_message(websocket, user_id, message)
            except WebSocketDisconnect:
                break
    
    async def _handle_message(
        self,
        websocket: WebSocket,
        user_id: str,
        message: dict,
    ) -> None:
        """Handle an incoming WebSocket message."""
        msg_type = message.get("type")
        
        if msg_type == "ping":
            await websocket.send_json({"type": "pong"})
        
        elif msg_type == "subscribe":
            channel = message.get("channel")
            if channel:
                await self._subscribe(user_id, channel)
                await websocket.send_json({
                    "type": "subscribed",
                    "channel": channel,
                })
        
        elif msg_type == "unsubscribe":
            channel = message.get("channel")
            if channel:
                await self._unsubscribe(user_id, channel)
                await websocket.send_json({
                    "type": "unsubscribed",
                    "channel": channel,
                })
        
        elif msg_type == "command":
            # Handle AI commands via WebSocket
            await self._handle_command(websocket, user_id, message)
        
        else:
            await websocket.send_json({
                "type": "error",
                "error": f"Unknown message type: {msg_type}",
            })
    
    async def _subscribe(self, user_id: str, channel: str) -> None:
        """Subscribe user to a channel."""
        if channel not in self._channels:
            self._channels[channel] = set()
        self._channels[channel].add(user_id)
        
        # Update connection metadata
        for ws in self._connections.get(user_id, []):
            if ws in self._metadata:
                self._metadata[ws]["channels"].add(channel)
    
    async def _unsubscribe(self, user_id: str, channel: str) -> None:
        """Unsubscribe user from a channel."""
        if channel in self._channels:
            self._channels[channel].discard(user_id)
        
        # Update connection metadata
        for ws in self._connections.get(user_id, []):
            if ws in self._metadata:
                self._metadata[ws]["channels"].discard(channel)
    
    async def _handle_command(
        self,
        websocket: WebSocket,
        user_id: str,
        message: dict,
    ) -> None:
        """Handle an AI command via WebSocket for streaming responses."""
        from core.brain import brain_engine
        
        command = message.get("command")
        if not command:
            await websocket.send_json({"type": "error", "error": "No command provided"})
            return
        
        # Stream response
        try:
            async for chunk in brain_engine.stream_response(user_id, command):
                await websocket.send_json({
                    "type": "response_chunk",
                    "content": chunk,
                })
            
            await websocket.send_json({"type": "response_complete"})
            
        except Exception as e:
            await websocket.send_json({
                "type": "error",
                "error": str(e),
            })
    
    # Public methods for sending messages
    
    async def send_to_user(self, user_id: str, message: dict) -> int:
        """
        Send a message to all connections of a user.
        
        Args:
            user_id: Target user
            message: Message to send
            
        Returns:
            Number of connections message was sent to
        """
        connections = self._connections.get(user_id, set())
        sent = 0
        
        for ws in connections:
            try:
                await ws.send_json(message)
                sent += 1
            except Exception:
                pass
        
        return sent
    
    async def broadcast_to_channel(self, channel: str, message: dict) -> int:
        """
        Broadcast a message to all users in a channel.
        
        Args:
            channel: Target channel
            message: Message to send
            
        Returns:
            Number of users message was sent to
        """
        users = self._channels.get(channel, set())
        sent = 0
        
        for user_id in users:
            count = await self.send_to_user(user_id, message)
            if count > 0:
                sent += 1
        
        return sent
    
    async def broadcast_all(self, message: dict) -> int:
        """
        Broadcast a message to all connected users.
        
        Args:
            message: Message to send
            
        Returns:
            Number of users message was sent to
        """
        sent = 0
        
        for user_id in self._connections:
            count = await self.send_to_user(user_id, message)
            if count > 0:
                sent += 1
        
        return sent
    
    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return sum(len(conns) for conns in self._connections.values())
    
    def get_user_count(self) -> int:
        """Get number of connected users."""
        return len(self._connections)


# Global WebSocket manager
websocket_manager = ConnectionManager()
