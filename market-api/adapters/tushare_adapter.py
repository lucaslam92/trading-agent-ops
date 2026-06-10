"""
TushareAdapter — post-market daily data supplement.

Intended usage:
  - ADAPTER=tushare: suitable for after-market enrichment (15:30+)
  - During trading hours data reflects the previous completed trading day
  - Requires TUSHARE_TOKEN with ≥2000 points for sector money-flow data

For real-time tick use, prefer EastmoneyAdapter.
"""

import asyncio
import concurrent.futures
import datetime

import tushare as ts

from config import TUSHARE_TOKEN
from .base import DataAdapter, RawSnapshot

# (tushare_code, terminal_code, label)
_INDICES = [
    ("000001.SH", "SH000001", "上证指数"),
    ("399001.SZ", "SZ399001", "深证成指"),
    ("399006.SZ", "SZ399006", "创业板指"),
    ("000688.SH", "SH000688", "科创50"),
    ("399330.SZ", "SZ399330", "深证100"),
]

# (tushare_code, terminal_code, name, sector, theme)
_LEADERS = [
    ("300308.SZ", "300308", "中际旭创", "光模块",   "AI算力"),
    ("300394.SZ", "300394", "天孚通信", "光模块",   "AI算力"),
    ("601138.SH", "601138", "工业富联", "算力租赁", "AI算力"),
    ("002371.SZ", "002371", "北方华创", "半导体",   "科技"),
    ("688981.SH", "688981", "中芯国际", "半导体",   "科技"),
    ("603728.SH", "603728", "鸣志电器", "机器人",   "题材"),
    ("688017.SH", "688017", "绿的谐波", "机器人",   "题材"),
    ("600900.SH", "600900", "长江电力", "电力",     "红利"),
    ("601088.SH", "601088", "中国神华", "煤炭",     "红利"),
    ("601398.SH", "601398", "工商银行", "银行",     "红利"),
]

_THEME_KW: dict[str, str] = {
    "AI": "AI算力", "算力": "AI算力", "光模块": "AI算力",
    "半导体": "科技", "芯片": "科技", "软件": "科技", "电子": "科技",
    "机器人": "题材", "军工": "题材",
    "电池": "新能源", "光伏": "新能源", "储能": "新能源", "新能源": "新能源",
    "医药": "医药", "生物": "医药",
    "白酒": "消费", "食品": "消费",
    "证券": "金融", "保险": "金融",
    "银行": "红利", "电力": "红利", "煤炭": "红利",
    "房地产": "周期", "建材": "周期", "钢铁": "周期",
}


def _guess_theme(name: str) -> str:
    for kw, theme in _THEME_KW.items():
        if kw in name:
            return theme
    return "其他"


def _latest_trade_date() -> str:
    d = datetime.date.today()
    while d.weekday() >= 5:  # skip weekends; does not account for holidays
        d -= datetime.timedelta(days=1)
    return d.strftime("%Y%m%d")


class TushareAdapter(DataAdapter):
    def __init__(self) -> None:
        if not TUSHARE_TOKEN:
            raise ValueError("TUSHARE_TOKEN must be set to use TushareAdapter")
        self._pro = ts.pro_api(TUSHARE_TOKEN)
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="tushare")

    async def fetch(self) -> RawSnapshot:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self._fetch_sync)

    # ── post-market helper (can be called directly from background tasks) ────

    def fetch_sector_flow(self, trade_date: str) -> list[dict]:
        """Fetch sector money-flow for a completed trading day (requires 2000 pts)."""
        return self._get_sectors(trade_date)

    def fetch_limit_list(self, trade_date: str) -> dict:
        """Fetch limit-up/limit-down counts for a completed trading day."""
        return self._get_breadth(trade_date)

    # ── internals ────────────────────────────────────────────────────────────

    def _fetch_sync(self) -> RawSnapshot:
        trade_date = _latest_trade_date()
        return RawSnapshot(
            indices=self._get_indices(trade_date),
            sectors=self._get_sectors(trade_date),
            leaders=self._get_leaders(trade_date),
            globals=[],
            breadth=self._get_breadth(trade_date),
            source="tushare",
        )

    def _get_indices(self, trade_date: str) -> list[dict]:
        ts_codes = ",".join(c for c, _, _ in _INDICES)
        try:
            df = self._pro.index_daily(
                ts_code=ts_codes, trade_date=trade_date,
                fields="ts_code,close,pre_close,pct_chg",
            )
        except Exception:
            return []
        if df is None or df.empty:
            return []
        code_map = {row["ts_code"]: row for _, row in df.iterrows()}
        out = []
        for ts_code, term_code, label in _INDICES:
            row = code_map.get(ts_code)
            if row is None:
                continue
            out.append({
                "code": term_code, "label": label,
                "price": round(float(row["close"]), 2),
                "changePct": round(float(row["pct_chg"]), 2),
                "prevClose": round(float(row["pre_close"]), 2),
            })
        return out

    def _get_sectors(self, trade_date: str) -> list[dict]:
        # moneyflow_ths requires ≥2000 Tushare points
        try:
            df = self._pro.moneyflow_ths(
                trade_date=trade_date,
                fields="name,pct_change,net_amount",
            )
        except Exception:
            return []
        if df is None or df.empty:
            return []
        df = df.nlargest(30, "net_amount")
        return [
            {
                "name": str(row["name"]),
                "changePct": round(float(row["pct_change"]), 2),
                # net_amount is in 万元; convert to 亿元
                "netInflow": round(float(row["net_amount"]) / 10000, 1),
                "theme": _guess_theme(str(row["name"])),
            }
            for _, row in df.iterrows()
        ]

    def _get_leaders(self, trade_date: str) -> list[dict]:
        ts_codes = ",".join(c for c, *_ in _LEADERS)
        try:
            df = self._pro.daily(
                ts_code=ts_codes, trade_date=trade_date,
                fields="ts_code,open,close,pct_chg",
            )
        except Exception:
            return []
        if df is None or df.empty:
            return []
        code_map = {row["ts_code"]: row for _, row in df.iterrows()}
        out = []
        for ts_code, term_code, name, sector, theme in _LEADERS:
            row = code_map.get(ts_code)
            if row is None:
                continue
            out.append({
                "code": term_code, "name": name, "sector": sector,
                "price": round(float(row["close"]), 2),
                "changePct": round(float(row["pct_chg"]), 2),
                "open": round(float(row["open"]), 2),
                "volRatio": 1.0, "theme": theme,
            })
        return out

    def _get_breadth(self, trade_date: str) -> dict:
        # limit_list requires ≥2000 Tushare points
        try:
            df = self._pro.limit_list(trade_date=trade_date, fields="direction")
        except Exception:
            return {"up": 0, "down": 0, "flat": 0, "limitUp": 0, "limitDown": 0}
        if df is None or df.empty:
            return {"up": 0, "down": 0, "flat": 0, "limitUp": 0, "limitDown": 0}
        limit_up = int((df["direction"] == "U").sum())
        limit_dn = int((df["direction"] == "D").sum())
        return {"up": 0, "down": 0, "flat": 0, "limitUp": limit_up, "limitDown": limit_dn}
