"""
scripts/download_data.py

从 OKX 公开 REST API 下载 BTC K 线数据，
保存到 vn.py 本地 SQLite 数据库，供回测使用。

特点：
- 无需 API Key（公开行情数据）
- 自动分页，支持任意时间跨度
- 自动初始化 vn.py SQLite 配置（首次运行时）
- 支持现货（BTC-USDT）和永续合约（BTC-USDT-SWAP，推荐）

用法：
    # 下载 2023 年全年 BTC 永续合约 1H 数据（默认）
    python scripts/download_data.py

    # 指定时间范围
    python scripts/download_data.py --start 2022-01-01 --end 2024-01-01

    # 检查数据库中已有多少根 K 线
    python scripts/download_data.py --check

    # 下载现货数据
    python scripts/download_data.py --inst-type spot

    # 下载其他周期
    python scripts/download_data.py --interval 4h
"""

import argparse
import json
import logging
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone, date
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("download_data")

# ---------- OKX API 配置 ----------
OKX_HISTORY_CANDLES = "https://www.okx.com/api/v5/market/history-candles"
MAX_LIMIT = 300       # OKX 单次最多返回 300 根
RETRY_TIMES = 3
RETRY_DELAY = 2.0

# OKX 周期格式（注意 1h -> 1H，与 Binance 不同）
_OKX_BAR_MAP = {
    "1m":  "1m",
    "5m":  "5m",
    "15m": "15m",
    "30m": "30m",
    "1h":  "1H",
    "4h":  "4H",
    "1d":  "1D",
}

# 每根 K 线对应的毫秒数（分页用）
_INTERVAL_MS = {
    "1m":  60_000,
    "5m":  300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h":  3_600_000,
    "4h":  14_400_000,
    "1d":  86_400_000,
}

# ---------- vn.py 数据库配置 ----------
VNTRADER_DIR = Path.home() / ".vntrader"
VT_SETTING_PATH = VNTRADER_DIR / "vt_setting.json"


# ======================================================================
# 入口
# ======================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="从 OKX 下载 BTC K 线数据到 vn.py 数据库")
    parser.add_argument("--symbol",    default="BTC-USDT-SWAP",
                        help="OKX instId，默认 BTC-USDT-SWAP（永续合约）")
    parser.add_argument("--interval",  default="1h",
                        help="K 线周期：1m/5m/15m/30m/1h/4h/1d，默认 1h")
    parser.add_argument("--start",     default="2023-01-01",
                        help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end",       default="2024-01-01",
                        help="结束日期 YYYY-MM-DD")
    parser.add_argument("--inst-type", default="swap",
                        choices=["swap", "spot"],
                        help="swap=永续合约（默认），spot=现货")
    parser.add_argument("--check",     action="store_true",
                        help="只检查数据库数量，不下载")
    args = parser.parse_args()

    # 根据 inst-type 选择默认 symbol
    if args.inst_type == "spot" and args.symbol == "BTC-USDT-SWAP":
        args.symbol = "BTC-USDT"

    # 1. 初始化 vn.py SQLite 环境
    _ensure_vntrader_config()

    # 2. 导入 vn.py
    try:
        import vnpy_sqlite  # noqa: F401 — 注册 SQLite 驱动
        from vnpy.trader.constant import Exchange, Interval
        from vnpy.trader.database import get_database
    except ImportError as e:
        logger.error("依赖缺失：%s\n请运行：pip install vnpy vnpy_ctastrategy vnpy_sqlite", e)
        sys.exit(1)

    db = get_database()
    exchange = Exchange.OKX
    interval = Interval(args.interval)

    if args.check:
        _check_db(db, args.symbol, exchange, interval)
        return

    # 3. 解析时间范围（毫秒时间戳）
    start_ms = _date_to_ms(args.start)
    end_ms   = _date_to_ms(args.end)
    okx_bar  = _OKX_BAR_MAP.get(args.interval)
    if okx_bar is None:
        logger.error("不支持的周期: %s，可选: %s", args.interval, list(_OKX_BAR_MAP))
        sys.exit(1)

    logger.info("开始下载 %s %s [%s -> %s]", args.symbol, args.interval, args.start, args.end)
    logger.info("预计请求次数: ~%d 次",
                max(1, (_date_to_ms(args.end) - _date_to_ms(args.start))
                    // (_INTERVAL_MS[args.interval] * MAX_LIMIT)))

    # 4. 分页下载（OKX 返回数据为从新到旧，用 after 参数向前翻页）
    all_bars = []
    cursor = end_ms   # 从结束时间开始，向前（更早）翻页

    while cursor > start_ms:
        raw = _fetch_candles(args.symbol, okx_bar, after_ms=cursor, limit=MAX_LIMIT)
        if not raw:
            break

        # OKX 返回的是 从新到旧，反转为 从旧到新
        raw = list(reversed(raw))

        # 过滤掉 start_ms 之前的数据
        raw = [r for r in raw if int(r[0]) >= start_ms]
        if not raw:
            break

        bars = _to_bar_data(raw, args.symbol, exchange, interval)
        all_bars.extend(bars)

        # 翻页游标移到本批最旧的那根
        cursor = int(raw[0][0])
        bar_ms = _INTERVAL_MS[args.interval]

        logger.info("  已获取 %d 根（累计 %d）最早: %s",
                    len(bars), len(all_bars),
                    bars[0].datetime.strftime("%Y-%m-%d %H:%M") if bars else "-")

        # 防止死循环（已到最早边界）
        if len(raw) < MAX_LIMIT:
            break

        time.sleep(0.3)   # OKX 限速：约 20次/2s

    if not all_bars:
        logger.warning("未获取到任何数据，请检查 symbol 和时间范围")
        return

    # 5. 按时间排序后批量写入数据库
    all_bars.sort(key=lambda b: b.datetime)
    db.save_bar_data(all_bars)
    logger.info("下载完成，共保存 %d 根 K 线", len(all_bars))
    _check_db(db, args.symbol, exchange, interval)


# ======================================================================
# 工具函数
# ======================================================================

def _ensure_vntrader_config() -> None:
    """确保 ~/.vntrader/vt_setting.json 存在且包含 SQLite 配置。"""
    VNTRADER_DIR.mkdir(exist_ok=True)
    if VT_SETTING_PATH.exists():
        try:
            with open(VT_SETTING_PATH, encoding="utf-8") as f:
                setting = json.load(f)
        except json.JSONDecodeError:
            setting = {}
    else:
        setting = {}

    if "database.name" not in setting:
        setting["database.name"] = "sqlite"
        with open(VT_SETTING_PATH, "w", encoding="utf-8") as f:
            json.dump(setting, f, indent=2)
        logger.info("已初始化 vn.py SQLite 配置: %s", VT_SETTING_PATH)


def _date_to_ms(date_str: str) -> int:
    """将 YYYY-MM-DD 字符串转为 UTC 毫秒时间戳。"""
    d = date.fromisoformat(date_str)
    dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _fetch_candles(
    inst_id: str,
    bar: str,
    after_ms: int,
    limit: int = MAX_LIMIT,
) -> list:
    """
    请求 OKX 历史 K 线接口。

    参数 after：返回 after 时间戳之前（更旧）的数据。
    返回数据为 从新到旧 排列。
    """
    url = (
        f"{OKX_HISTORY_CANDLES}"
        f"?instId={inst_id}&bar={bar}&after={after_ms}&limit={limit}"
    )

    for attempt in range(1, RETRY_TIMES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode())
                if payload.get("code") == "0":
                    return payload.get("data", [])
                logger.warning("OKX 返回错误: code=%s msg=%s",
                               payload.get("code"), payload.get("msg"))
                return []
        except Exception as e:
            logger.warning("请求失败（第 %d/%d 次）: %s", attempt, RETRY_TIMES, e)
            if attempt < RETRY_TIMES:
                time.sleep(RETRY_DELAY * attempt)

    return []


def _to_bar_data(raw: list, symbol: str, exchange, interval) -> list:
    """
    将 OKX K 线原始数据转换为 vn.py BarData 列表。

    OKX 数据格式：
    [ts, open, high, low, close, vol, volCcy, volCcyQuote, confirm]
      0    1     2    3    4      5     6         7           8
    - vol:          合约张数（SWAP: 1张=0.01 BTC）
    - volCcy:       标的数量（BTC）
    - volCcyQuote:  计价货币成交额（USDT）
    """
    from vnpy.trader.object import BarData

    bars = []
    for item in raw:
        ts = int(item[0])
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        bar = BarData(
            symbol=symbol,
            exchange=exchange,
            datetime=dt,
            interval=interval,
            open_price=float(item[1]),
            high_price=float(item[2]),
            low_price=float(item[3]),
            close_price=float(item[4]),
            volume=float(item[6]),      # volCcy：BTC 数量
            turnover=float(item[7]),    # volCcyQuote：USDT 成交额
            gateway_name="OKX",
        )
        bars.append(bar)
    return bars


def _check_db(db, symbol: str, exchange, interval) -> None:
    """查询数据库中已有的 K 线数量和时间范围。"""
    try:
        bars = db.load_bar_data(
            symbol=symbol,
            exchange=exchange,
            interval=interval,
            start=datetime(2000, 1, 1, tzinfo=timezone.utc),
            end=datetime(2100, 1, 1, tzinfo=timezone.utc),
        )
        if not bars:
            logger.info("数据库中暂无 %s %s 数据", symbol, interval)
        else:
            logger.info(
                "数据库中共有 %d 根 %s %s K 线  [%s -> %s]",
                len(bars), symbol, interval,
                bars[0].datetime.strftime("%Y-%m-%d"),
                bars[-1].datetime.strftime("%Y-%m-%d"),
            )
    except Exception as e:
        logger.error("查询数据库失败: %s", e)


if __name__ == "__main__":
    main()
