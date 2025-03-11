from fastapi import WebSocket
from typing import List, Dict
from uuid import UUID
import logging
import json
from src.models.dc_models import ClientDataModel


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[UUID, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, match_id: UUID):
        """Connects a websocket to a match_id

        Args:
            websocket (WebSocket): 
            match_id (UUID): _description_
        """
        await websocket.accept()
        if match_id not in self.active_connections:
            self.active_connections[match_id] = []
        self.active_connections[match_id].append(websocket)

    def disconnect(self, websocket: WebSocket, match_id: UUID):
        """Disconnects a websocket from a match_id

        Args:
            websocket (WebSocket): 
            match_id (UUID): _description_
        """        
        if match_id in self.active_connections:
            self.active_connections[match_id].remove(websocket)
            # Clean up if there are no more connections for this match_id
            if not self.active_connections[match_id]:
                del self.active_connections[match_id]

    async def send_personal_message(self, message: json, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(self, message: json, match_id: UUID):
        logging.info(f"Broadcasting message to match_id: {match_id}")
        if match_id in self.active_connections:
            for connection in self.active_connections[match_id]:
                await connection.send_json(message)

    async def receive_json(self, websocket: WebSocket):
        data = await websocket.receive_json()
        return json.loads(data)
