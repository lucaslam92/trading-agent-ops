import asyncio
import json


class SSEManager:
    def __init__(self):
        self._clients: set[asyncio.Queue] = set()

    def connect(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._clients.add(q)
        return q

    def disconnect(self, q: asyncio.Queue):
        self._clients.discard(q)

    def broadcast(self, snapshot: dict):
        payload = json.dumps(snapshot, ensure_ascii=False)
        for q in self._clients:
            q.put_nowait(payload)

    @property
    def client_count(self) -> int:
        return len(self._clients)
