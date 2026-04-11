"""
services/market_data_service.py

行情数据服务。

职责：
- 从 vn.py 数据库或交易所接口获取历史 K 线
- 计算基础指标特征（供 AI 模块使用）
- 提供标准化的 BarFeature 列表输出

依赖 vn.py 的 database_manager 接口，在回测与实盘中统一调用。
"""

import logging
from datetime import datetime
from typing import List, Optional

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import BarData

from ai.regime_detector import BarFeature

logger = logging.getLogger(__name__)


class MarketDataService:
    """
    行情数据服务。

    调用方式：
        svc = MarketDataService()
        bars = svc.get_bar_features("BTC-USDT-SWAP", Exchange.OKX, Interval.HOUR, count=100)
    """

    def get_bar_features(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        count: int = 100,
        end: Optional[datetime] = None,
    ) -> List[BarFeature]:
        """
        获取最近 count 根 K 线并计算指标特征。

        Parameters
        ----------
        symbol   : 合约代码，如 "BTCUSDT"
        exchange : 交易所，如 Exchange.OKX
        interval : K 线周期，如 Interval.HOUR
        count    : 获取根数
        end      : 截止时间，默认为当前时间

        Returns
        -------
        List[BarFeature] : 时间升序排列
        """
        bars = self._load_bars(symbol, exchange, interval, count, end)
        if len(bars) < 2:
            logger.warning("MarketDataService: K线数量不足 %d", len(bars))
            return []

        return self._calc_features(bars)

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _load_bars(
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        count: int,
        end: Optional[datetime],
    ) -> List[BarData]:
        """从 vn.py 数据库加载历史 K 线。"""
        try:
            database = get_database()
            bars = database.load_bar_data(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                start=None,
                end=end,
            )
            # 只取最新的 count 根
            return bars[-count:] if len(bars) > count else bars
        except Exception as e:
            logger.error("MarketDataService._load_bars: %s", e)
            return []

    @staticmethod
    def _calc_features(bars: List[BarData]) -> List[BarFeature]:
        """
        计算指标特征列表。

        使用简单滚动窗口计算（不依赖 talib），保持轻量。
        窗口参数与 regime_detector 中的默认配置对齐：
            fast_ma  : 10
            slow_ma  : 30
            atr      : 14
            rsi      : 14
            boll     : 20, dev=2.0
        """
        N = len(bars)
        features: List[BarFeature] = []

        closes = [b.close_price for b in bars]
        highs = [b.high_price for b in bars]
        lows = [b.low_price for b in bars]
        volumes = [b.volume for b in bars]

        for i in range(N):
            # --- ATR（14）---
            atr = _rolling_atr(highs, lows, closes, i, period=14)

            # --- RSI（14）---
            rsi = _rolling_rsi(closes, i, period=14)

            # --- 快/慢均线 ---
            ma_fast = _sma(closes, i, period=10)
            ma_slow = _sma(closes, i, period=30)

            # --- 布林带宽度（20, 2.0）---
            boll_width = _boll_width(closes, i, period=20, dev=2.0)

            features.append(BarFeature(
                close=closes[i],
                volume=volumes[i],
                atr=atr,
                rsi=rsi,
                ma_fast=ma_fast,
                ma_slow=ma_slow,
                boll_width=boll_width,
            ))

        return features


# ------------------------------------------------------------------
# 纯函数指标计算工具（无外部依赖）
# ------------------------------------------------------------------

def _sma(closes: List[float], idx: int, period: int) -> float:
    start = max(0, idx - period + 1)
    window = closes[start:idx + 1]
    return sum(window) / len(window)


def _rolling_atr(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    idx: int,
    period: int,
) -> float:
    trs = []
    for i in range(max(1, idx - period + 1), idx + 1):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    return sum(trs) / len(trs) if trs else 0.0


def _rolling_rsi(closes: List[float], idx: int, period: int) -> float:
    if idx < period:
        return 50.0
    changes = [closes[i] - closes[i - 1] for i in range(idx - period + 1, idx + 1)]
    gains = [c for c in changes if c > 0]
    losses = [-c for c in changes if c < 0]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _boll_width(closes: List[float], idx: int, period: int, dev: float) -> float:
    start = max(0, idx - period + 1)
    window = closes[start:idx + 1]
    if len(window) < 2:
        return 0.0
    mid = sum(window) / len(window)
    variance = sum((c - mid) ** 2 for c in window) / len(window)
    std = variance ** 0.5
    upper = mid + dev * std
    lower = mid - dev * std
    return (upper - lower) / mid if mid > 0 else 0.0
