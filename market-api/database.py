import aiosqlite
from config import DB_PATH

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    return _db


async def init_db():
    global _db
    _db = await aiosqlite.connect(DB_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS journals (
            date        TEXT PRIMARY KEY,
            main_line   TEXT NOT NULL DEFAULT '',
            leaders     TEXT NOT NULL DEFAULT '',
            top_sectors TEXT NOT NULL DEFAULT '',
            sentiment   TEXT NOT NULL DEFAULT '',
            risk        TEXT NOT NULL DEFAULT '',
            analysis    TEXT NOT NULL DEFAULT '',
            mistakes    TEXT NOT NULL DEFAULT '无',
            updated_at  INTEGER NOT NULL
        )
    """)
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS checklists (
            date       TEXT PRIMARY KEY,
            checks     TEXT NOT NULL DEFAULT '{}',
            notes      TEXT NOT NULL DEFAULT '{}',
            updated_at INTEGER NOT NULL
        )
    """)
    await _db.commit()


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None
