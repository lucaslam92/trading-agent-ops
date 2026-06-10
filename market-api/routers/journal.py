import time
from fastapi import APIRouter, HTTPException, Query
from database import get_db
from models import JournalIn, JournalOut, JournalSummary

router = APIRouter()


@router.get("/api/journal", response_model=JournalOut)
async def get_journal(date: str = Query(...)):
    db = await get_db()
    async with db.execute(
        "SELECT * FROM journals WHERE date = ?", (date,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return JournalOut(
        date=row["date"],
        mainLine=row["main_line"],
        leaders=row["leaders"],
        topSectors=row["top_sectors"],
        sentiment=row["sentiment"],
        risk=row["risk"],
        analysis=row["analysis"],
        mistakes=row["mistakes"],
        updatedAt=row["updated_at"],
    )


@router.post("/api/journal", response_model=JournalOut)
async def save_journal(body: JournalIn):
    now = int(time.time() * 1000)
    db = await get_db()
    await db.execute(
        """
        INSERT INTO journals (date, main_line, leaders, top_sectors, sentiment, risk, analysis, mistakes, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            main_line=excluded.main_line,
            leaders=excluded.leaders,
            top_sectors=excluded.top_sectors,
            sentiment=excluded.sentiment,
            risk=excluded.risk,
            analysis=excluded.analysis,
            mistakes=excluded.mistakes,
            updated_at=excluded.updated_at
        """,
        (body.date, body.mainLine, body.leaders, body.topSectors,
         body.sentiment, body.risk, body.analysis, body.mistakes, now),
    )
    await db.commit()
    return JournalOut(**body.model_dump(), updatedAt=now)


@router.get("/api/journal/history", response_model=list[JournalSummary])
async def journal_history(limit: int = Query(30, ge=1, le=200)):
    db = await get_db()
    async with db.execute(
        "SELECT date, main_line, sentiment FROM journals ORDER BY date DESC LIMIT ?",
        (limit,),
    ) as cur:
        rows = await cur.fetchall()
    return [JournalSummary(date=r["date"], mainLine=r["main_line"], sentiment=r["sentiment"]) for r in rows]


@router.delete("/api/journal")
async def delete_journal(date: str = Query(...)):
    db = await get_db()
    async with db.execute("DELETE FROM journals WHERE date = ?", (date,)) as cur:
        affected = cur.rowcount
    await db.commit()
    if affected == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}
