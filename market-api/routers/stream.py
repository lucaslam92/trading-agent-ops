import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sse_manager import SSEManager

router = APIRouter()
sse_manager: SSEManager | None = None


def init(mgr: SSEManager):
    global sse_manager
    sse_manager = mgr


@router.get("/api/stream")
async def stream(request: Request):
    q = sse_manager.connect()

    async def generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"event: snapshot\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            sse_manager.disconnect(q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
