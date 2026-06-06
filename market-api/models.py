from pydantic import BaseModel
from typing import Optional


class JournalIn(BaseModel):
    date: str
    mainLine: str = ""
    leaders: str = ""
    topSectors: str = ""
    sentiment: str = ""
    risk: str = ""
    analysis: str = ""
    mistakes: str = "无"


class JournalOut(BaseModel):
    date: str
    mainLine: str
    leaders: str
    topSectors: str
    sentiment: str
    risk: str
    analysis: str
    mistakes: str
    updatedAt: int


class JournalSummary(BaseModel):
    date: str
    mainLine: str
    sentiment: str


class ChecklistIn(BaseModel):
    date: str
    checks: dict = {}
    notes: dict = {}


class ChecklistOut(BaseModel):
    date: str
    checks: dict
    notes: dict
    updatedAt: int
