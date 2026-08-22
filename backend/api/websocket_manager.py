import json
import asyncio
from typing import List, Dict, Any
from fastapi import WebSocket

class WebSocketConnectionManager:
    """Manages active WebSocket connections for live investigation and eval streaming."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, event_type: str, agent: str, message: str, data: Dict[str, Any] = None):
        data = data or {}
        payload = {
            "event_type": event_type,
            # BUG #4 FIX: hoist 'stage' to top-level so frontend reads payload.stage directly
            "stage": data.get("stage", ""),
            "agent": agent,
            "message": message,
            "data": data,
            "timestamp": asyncio.get_event_loop().time()
        }
        dead_conns = []
        for connection in self.active_connections:
            try:
                await connection.send_json(payload)
            except Exception:
                dead_conns.append(connection)
        for dead in dead_conns:
            self.disconnect(dead)


ws_manager = WebSocketConnectionManager()
