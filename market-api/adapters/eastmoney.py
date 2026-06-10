import asyncio
import time

import httpx

from .base import DataAdapter, RawSnapshot

_EM_BASE = "https://push2delay.eastmoney.com/api/qt"
_YF_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

# (secid, terminal_code, label)
_INDICES = [
    ("1.000001", "SH000001", "上证指数"),
    ("0.399001", "SZ399001", "深证成指"),
    ("0.399006", "SZ399006", "创业板指"),
    ("1.000688", "SH000688", "科创50"),
    ("0.399330", "SZ399330", "深证100"),
]

# (secid, terminal_code, name, sector, theme)
_LEADERS = [
    ("0.300308", "300308", "中际旭创", "光模块",   "AI算力"),
    ("0.300394", "300394", "天孚通信", "光模块",   "AI算力"),
    ("1.601138", "601138", "工业富联", "算力租赁", "AI算力"),
    ("0.002371", "002371", "北方华创", "半导体",   "科技"),
    ("1.688981", "688981", "中芯国际", "半导体",   "科技"),
    ("1.603728", "603728", "鸣志电器", "机器人",   "题材"),
    ("1.688017", "688017", "绿的谐波", "机器人",   "题材"),
    ("1.600900", "600900", "长江电力", "电力",     "红利"),
    ("1.601088", "601088", "中国神华", "煤炭",     "红利"),
    ("1.601398", "601398", "工商银行", "银行",     "红利"),
]

# (terminal_code, label, yahoo_symbol, isLevel)
_GLOBALS = [
    ("NDX",    "纳斯达克", "^NDX",  False),
    ("HSTECH", "恒生科技", "^HSI",  False),
    ("US10Y",  "美10年债", "^TNX",  True),
    ("GC",     "黄金",     "GC=F",  False),
    ("CL",     "原油",     "CL=F",  False),
    ("NVDA",   "NVDA盘后", "NVDA",  False),
]

_THEME_KW: dict[str, str] = {
    "AI": "AI算力", "算力": "AI算力", "光模块": "AI算力", "CPO": "AI算力",
    "通信": "AI算力", "数据中心": "AI算力", "服务器": "AI算力",
    "半导体": "科技", "芯片": "科技", "软件": "科技", "消费电子": "科技", "电子": "科技",
    "机器人": "题材", "军工": "题材", "航天": "题材",
    "电池": "新能源", "光伏": "新能源", "储能": "新能源", "新能源": "新能源", "风电": "新能源",
    "医药": "医药", "生物": "医药", "医疗": "医药",
    "白酒": "消费", "食品": "消费", "饮料": "消费",
    "证券": "金融", "保险": "金融",
    "银行": "红利", "电力": "红利", "煤炭": "红利", "油气": "红利",
    "房地产": "周期", "建材": "周期", "钢铁": "周期", "化工": "周期",
}


def _guess_theme(name: str) -> str:
    for kw, theme in _THEME_KW.items():
        if kw in name:
            return theme
    return "其他"


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class EastmoneyAdapter(DataAdapter):
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=6.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://quote.eastmoney.com/",
            },
        )
        self._globals_cache: list[dict] = []
        self._globals_ts: float = 0.0

    async def fetch(self) -> RawSnapshot:
        indices, sectors, leaders, globals_, breadth = await asyncio.gather(
            self._fetch_indices(),
            self._fetch_sectors(),
            self._fetch_leaders(),
            self._fetch_globals(),
            self._fetch_breadth(),
            return_exceptions=True,
        )

        def _safe(name, val, fallback):
            if isinstance(val, Exception):
                print(f"[EastmoneyAdapter] {name} error: {val}")
                return fallback
            return val

        return RawSnapshot(
            indices=_safe("indices", indices, []),
            sectors=_safe("sectors", sectors, []),
            leaders=_safe("leaders", leaders, []),
            globals=_safe("globals", globals_, self._globals_cache),
            breadth=_safe("breadth", breadth, {"up": 0, "down": 0, "flat": 0, "limitUp": 0, "limitDown": 0}),
            source="eastmoney",
        )

    # ── A-share indices ──────────────────────────────────────────────────────

    async def _fetch_indices(self) -> list[dict]:
        results = await asyncio.gather(
            *[self._get_stock(secid) for secid, _, _ in _INDICES],
            return_exceptions=True,
        )
        out = []
        for (secid, code, label), raw in zip(_INDICES, results):
            if isinstance(raw, Exception) or not raw:
                continue
            price  = _to_float(raw.get("f43"))
            change = _to_float(raw.get("f170"))
            prev   = _to_float(raw.get("f18"))
            if prev == 0 and price and change != -100:
                prev = round(price / (1 + change / 100), 2)
            out.append({
                "code": code, "label": label,
                "price": round(price, 2),
                "changePct": round(change, 2),
                "prevClose": round(prev, 2),
            })
        return out

    async def _get_stock(self, secid: str) -> dict:
        r = await self._client.get(
            f"{_EM_BASE}/stock/get",
            params={"secid": secid, "fields": "f43,f170,f18,f46,f47", "fltt": "2", "invt": "2"},
        )
        r.raise_for_status()
        return r.json().get("data") or {}

    # ── Sector capital flows ─────────────────────────────────────────────────

    async def _fetch_sectors(self) -> list[dict]:
        # Fetch top 15 by inflow AND top 15 by outflow for a balanced view
        top_in, top_out = await asyncio.gather(
            self._client.get(f"{_EM_BASE}/clist/get", params={
                "fs": "m:90+t:2", "fields": "f14,f3,f62",
                "fid": "f62", "po": "1", "pn": "1", "pz": "15",
                "fltt": "2", "invt": "2",
            }),
            self._client.get(f"{_EM_BASE}/clist/get", params={
                "fs": "m:90+t:2", "fields": "f14,f3,f62",
                "fid": "f62", "po": "0", "pn": "1", "pz": "15",
                "fltt": "2", "invt": "2",
            }),
        )
        top_in.raise_for_status()
        top_out.raise_for_status()

        def _parse(r):
            diff = r.json().get("data", {}).get("diff") or {}
            return diff if isinstance(diff, list) else list(diff.values())

        seen, items = set(), []
        for x in _parse(top_in) + _parse(top_out):
            name = x.get("f14") or ""
            if name and name not in seen:
                seen.add(name)
                items.append(x)

        items.sort(key=lambda x: _to_float(x.get("f62")), reverse=True)
        return [
            {
                "name": x.get("f14") or "",
                "changePct": round(_to_float(x.get("f3")), 2),
                "netInflow": round(_to_float(x.get("f62")) / 1e8, 1),
                "theme": _guess_theme(x.get("f14") or ""),
            }
            for x in items
        ]

    # ── Leader stocks ────────────────────────────────────────────────────────

    async def _fetch_leaders(self) -> list[dict]:
        results = await asyncio.gather(
            *[self._get_stock(secid) for secid, *_ in _LEADERS],
            return_exceptions=True,
        )
        out = []
        for (secid, code, name, sector, theme), raw in zip(_LEADERS, results):
            if isinstance(raw, Exception) or not raw:
                continue
            price  = _to_float(raw.get("f43"))
            change = _to_float(raw.get("f170"))
            open_  = _to_float(raw.get("f46"))
            out.append({
                "code": code, "name": name, "sector": sector,
                "price": round(price, 2), "changePct": round(change, 2),
                "open": round(open_, 2), "volRatio": 1.0, "theme": theme,
            })
        return out

    # ── Global references (Yahoo Finance, cached 60 s) ───────────────────────

    async def _fetch_globals(self) -> list[dict]:
        now = time.time()
        if self._globals_cache and now - self._globals_ts < 60:
            return self._globals_cache

        fetched = await asyncio.gather(
            *[self._get_yahoo(sym, code, label, is_lvl) for code, label, sym, is_lvl in _GLOBALS],
            return_exceptions=True,
        )

        result = []
        for i, (code, label, sym, is_lvl) in enumerate(_GLOBALS):
            item = fetched[i]
            if isinstance(item, Exception) or item is None:
                fallback = next((g for g in self._globals_cache if g["code"] == code), None)
                result.append(fallback or {
                    "code": code, "label": label, "price": 0.0, "changePct": 0.0,
                    "note": "离线", "isLevel": is_lvl,
                })
            else:
                result.append(item)

        self._globals_cache = result
        self._globals_ts = now
        return result

    async def _get_yahoo(self, symbol: str, code: str, label: str, is_level: bool) -> dict:
        r = await self._client.get(
            f"{_YF_BASE}/{symbol}",
            params={"interval": "1d", "range": "2d"},
        )
        r.raise_for_status()
        meta = r.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
        price = meta.get("regularMarketPrice") or 0
        prev  = meta.get("chartPreviousClose") or meta.get("previousClose") or price
        display_price = round(float(price), 2)
        if is_level:
            change = display_price
        else:
            change = round((price - prev) / prev * 100, 2) if prev else 0.0
        state = meta.get("marketState", "CLOSED")
        note  = "实时" if state in ("REGULAR", "POST") else "收盘"
        return {"code": code, "label": label, "price": display_price, "changePct": change, "note": note, "isLevel": is_level}

    # ── Market breadth ───────────────────────────────────────────────────────

    async def _fetch_breadth(self) -> dict:
        r = await self._client.get(
            f"{_EM_BASE}/clist/get",
            params={
                "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
                "fields": "f3", "pn": "1", "pz": "8000",
                "fltt": "2", "invt": "2",
            },
        )
        r.raise_for_status()
        diff_raw = r.json().get("data", {}).get("diff") or {}
        items = diff_raw if isinstance(diff_raw, list) else list(diff_raw.values())
        up   = sum(1 for x in items if _to_float(x.get("f3")) > 0)
        down = sum(1 for x in items if _to_float(x.get("f3")) < 0)
        flat = len(items) - up - down
        return {"up": up, "down": down, "flat": flat, "limitUp": 0, "limitDown": 0}
