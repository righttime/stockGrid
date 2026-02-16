from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    """WebSocket 연결 관리 및 메시지 브로드캐스트"""
    def __init__(self):
        # 활성 연결 목록
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Client disconnected. Total clients: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(self, message: dict):
        """모든 클라이언트에게 메시지 전송 (멀티플렉싱 데이터)"""
        if not self.active_connections:
            return

        # 연결이 끊긴 소켓을 처리하기 위한 복사본 사용
        for connection in self.active_connections[:]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {str(e)}")
                self.disconnect(connection)

ws_manager = ConnectionManager()
