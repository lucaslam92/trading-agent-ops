import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import ADAPTER, TICK_INTERVAL
from database import init_db, close_db
from sse_manager import SSEManager
from scheduler import Scheduler
from routers.journal import router as journal_router
from routers.checklist import router as checklist_router
from routers import stream as stream_router


def _make_adapter():
    if ADAPTER == "eastmoney":
        from adapters.eastmoney import EastmoneyAdapter
        return EastmoneyAdapter()
    if ADAPTER == "tushare":
        from adapters.tushare_adapter import TushareAdapter
        return TushareAdapter()
    from adapters.mock import MockAdapter
    return MockAdapter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    mgr = SSEManager()
    stream_router.init(mgr)
    adapter = _make_adapter()
    scheduler = Scheduler(adapter, mgr, interval=TICK_INTERVAL)
    task = asyncio.create_task(scheduler.run())
    yield
    task.cancel()
    await close_db()


app = FastAPI(title="Market Terminal API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(journal_router)
app.include_router(checklist_router)
app.include_router(stream_router.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
