"""
scripts/download_data.py

从 Binance 公开 REST API 下载 BTC/USDT K 线数据，
保存到 vn.py 本地 SQLite 数据库，供回测使用。

特点：
- 无需 API Key（公开行情数据）
- 自动分页，支持任意时间跨度
- 自动初始化 vn.py SQLite 配置（首次运行时）
- 支持增量更新（已有数据不重复写入）

用法：
    # 下载 2023 年全年 BTC 1h 数据
    python scripts/download_data.py

    # 指定时间范围
    python scripts/download_data.py --start 2022-01-01 --end 2024-01-01

    # 下载完后检查数据库里有多少根 K 线
    python scripts/download_data.py --check

    # 下载合约数据（默认现货）
    python scripts/download_data.py --market futures
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
from typing import List

# 把项目根目录加入 PYTHONPATH
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("download_data")

# ---------- Binance API 配置 ----------
SPOT_URL = "https://api.binance.com/api/v3/klines"
FUTURES_URL = "https://fapi.binance.com/fapi/v1/klines"
MAX_LIMIT = 1000      # Binance 单次最多返回 1000 根
RETRY_TIMES = 3       # 请求失败重试次数
RETRY_DELAY = 2.0     # 重试等待秒数

# ---------- vn.py 数据库配置 ----------
VNTRADER_DIR = Path.home() / ".vntrader"
VT_SETTING_PATH = VNTRADER_DIR / "vt_setting.json"

_INTERVAL_MS = {
    "1m":  60_000,
    "5m":  300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h":  3_600_000,
    "4h":  14_400_000,
    "1d":  86_400_000,
}


# ======================================================================
# 入口
# ======================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="下载 BTC K 线数据到 vn.py 数据库")
    parser.add_argument("--symbol",   default="BTCUSDT",    help="交易对，默认 BTCUSDT")
    parser.add_argument("--interval", default="1h",         help="K 线周期，默认 1h")
    parser.add_argument("--start",    default="2023-01-01", help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end",      default="2024-01-01", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--market",   default="spot",       choices=["spot", "futures"],
                        help="spot（现货）或 futures（合约）")
    parser.add_argument("--check",    action="store_true",  help="只检查数据库数量，不下载")
    args = parser.parse_args()

    # 1. 初始化 vn.py SQLite 环境
    _ensure_vntrader_config()

    # 2. 导入 vn.py（必须在配置写入后）
    try:
        import vnpy_sqlite  # noqa: F401 — 注册 SQLite 驱动
        from vnpy.trader.constant import Exchange, Interval
        from vnpy.trader.database import get_database
        from vnpy.trader.object import BarData
    except ImportError as e:
        logger.error("依赖缺失：%s\n请运行：pip install vnpy vnpy_ctastrategy vnpy_sqlite", e)
        sys.exit(1)

    db = get_database()
    exchange = Exchange.BINANCE
    interval = Interval(args.interval)

    # 仅检查模式
    if args.check:
        _check_db(db, args.symbol, exchange, interval)
        return

    # 3. 解析时间范围
    start_ms = _date_to_ms(args.start)
    end_ms   = _date_to_ms(args.end)
    base_url = FUTURES_URL if args.market == "futures" else SPOT_URL

    logger.info("开始下载 %s %s [%s -> %s] (%s)",
                args.symbol, args.interval, args.start, args.end, args.market)

    # 4. 分页下载
    total_saved = 0
    cursor = start_ms
    bar_ms = _INTERVAL_MS.get(args.interval, 3_600_000)

    while cursor < end_ms:
        raw = _fetch_klines(
            url=base_url,
            symbol=args.symbol,
            interval=args.interval,
            start_ms=cursor,
            end_ms=min(cursor + bar_ms * MAX_LIMIT, end_ms),
            limit=MAX_LIMIT,
        )
        if not raw:
            break

        bars = _to_bar_data(raw, args.symbol, exchange, interval)
        if bars:
            db.save_bar_data(bars)
            total_saved += len(bars)
            logger.info("  已保存 %d 根（累计 %d）最新: %s",
                        len(bars), total_saved, bars[-1].datetime.strftime("%Y-%m-%d %H:%M"))

        # 推进游标到最后一根 K 线的下一个时间点
        cursor = raw[-1][0] + bar_ms

        # 礼貌性限速，避免触发 Binance IP 限制
        time.sleep(0.2)

    logger.info("下载完成，共保存 %d 根 K 线", total_saved)
    _check_db(db, args.symbol, exchange, interval)


# ======================================================================
# 工具函数
# ======================================================================

def _ensure_vntrader_config() -> None:
    """确保 ~/.vntrader/vt_setting.json 存在且包含 SQLite 配置。"""
    VNTRADER_DIR.mkdir(exist_ok=True)

    if VT_SETTING_PATH.exists():
        with open(VT_SETTING_PATH, encoding="utf-8") as f:
            try:
                setting = json.load(f)
            except json.JSONDecodeError:
                setting = {}
    else:
        setting = {}

    # 如果已有 database.name 配置则不覆盖
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


def _fetch_klines(
    url: str,
    symbol: str,
    interval: str,
    start_ms: int,
    end_ms: int,
    limit: int,
) -> list:
    """请求 Binance K 线接口，返回原始列表（带重试）。"""
    params = (
        f"symbol={symbol}&interval={interval}"
        f"&startTime={start_ms}&endTime={end_ms}&limit={limit}"
    )
    full_url = f"{url}?{params}"

    for attempt in range(1, RETRY_TIMES + 1):
        try:
            with urllib.request.urlopen(full_url, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                if isinstance(data, list):
                    return data
                # Binance 返回错误时是 dict
                logger.warning("Binance 返回错误: %s", data)
                return []
        except Exception as e:
            logger.warning("请求失败（第 %d/%d 次）: %s", attempt, RETRY_TIMES, e)
            if attempt < RETRY_TIMES:
                time.sleep(RETRY_DELAY * attempt)

    return []


def _to_bar_data(raw: list, symbol: str, exchange, interval) -> list:
    """将 Binance K 线原始数据转换为 vn.py BarData 列表。"""
    from vnpy.trader.object import BarData

    bars = []
    for item in raw:
        # item 格式: [open_time, open, high, low, close, volume, close_time, ...]
        dt = datetime.fromtimestamp(item[0] / 1000, tz=timezone.utc)
        bar = BarData(
            symbol=symbol,
            exchange=exchange,
            datetime=dt,
            interval=interval,
            open_price=float(item[1]),
            high_price=float(item[2]),
            low_price=float(item[3]),
            close_price=float(item[4]),
            volume=float(item[5]),
            turnover=float(item[7]),  # quote asset volume
            gateway_name="BINANCE",
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
