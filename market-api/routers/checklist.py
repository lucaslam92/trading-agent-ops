import json
import time
from fastapi import APIRouter, Query
from database import get_db
from models import ChecklistIn, ChecklistOut

router = APIRouter()

_EMPTY = ChecklistOut(date="", checks={}, notes={}, updatedAt=0)


@router.get("/api/checklist", response_model=ChecklistOut)
async def get_checklist(date: str = Query(...)):
    db = await get_db()
    async with db.execute(
        "SELECT * FROM checklists WHERE date = ?", (date,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return ChecklistOut(date=date, checks={}, notes={}, updatedAt=0)
    return ChecklistOut(
        date=row["date"],
        checks=json.loads(row["checks"]),
        notes=json.loads(row["notes"]),
        updatedAt=row["updated_at"],
    )


@router.post("/api/checklist", response_model=ChecklistOut)
async def save_checklist(body: ChecklistIn):
    now = int(time.time() * 1000)
    db = await get_db()
    await db.execute(
        """
        INSERT INTO checklists (date, checks, notes, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            checks=excluded.checks,
            notes=excluded.notes,
            updated_at=excluded.updated_at
        """,
        (body.date, json.dumps(body.checks, ensure_ascii=False),
         json.dumps(body.notes, ensure_ascii=False), now),
    )
    await db.commit()
    return ChecklistOut(date=body.date, checks=body.checks, notes=body.notes, updatedAt=now)
