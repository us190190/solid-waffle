"""WebSocket connection manager. File: app/core/ws_manager.py:1"""
import asyncio
import json
from typing import Dict, Set

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, Set[WebSocket]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            conns = self.active.get(job_id)
            if conns is None:
                self.active[job_id] = set()
            self.active[job_id].add(websocket)

    async def disconnect(self, job_id: str, websocket: WebSocket):
        async with self.lock:
            conns = self.active.get(job_id)
            if conns and websocket in conns:
                conns.remove(websocket)
                if not conns:
                    del self.active[job_id]

    async def broadcast(self, job_id: str, message: dict):
        data = json.dumps(message, ensure_ascii=False)
        async with self.lock:
            conns = list(self.active.get(job_id, set()))
        for ws in conns:
            try:
                await ws.send_text(data)
            except Exception:
                pass


manager = ConnectionManager()
