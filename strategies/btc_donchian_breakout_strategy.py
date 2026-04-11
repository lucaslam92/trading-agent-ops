"""
strategies/btc_donchian_breakout_strategy.py

BTC Donchian 通道突破策略。

逻辑：
- 突破过去 N 根 K 线最高点 -> 做多
- 跌破过去 N 根 K 线最低点 -> 做空
- ATR 倍数止损
- 可选 exit_window 做较短通道离场
"""

from typing import Any, Dict, Optional

from vnpy.trader.object import BarData, TickData
from vnpy.trader.utility import ArrayManager

from strategies.adaptive_cta_template import AdaptiveCtaTemplate


class BtcDonchianBreakoutStrategy(AdaptiveCtaTemplate):
    author = "BTC-AI-System"

    parameters = [
        "breakout_window",
        "exit_window",
        "atr_window",
        "atr_multiplier",
        "adx_window",
        "adx_threshold",
        "breakout_atr_buffer",
        "min_channel_width_ratio",
        "min_atr_ratio",
        "max_atr_ratio",
        "stop_loss_pct",
    ]
    variables = [
        "donchian_high",
        "donchian_low",
        "exit_high",
        "exit_low",
        "atr_value",
        "adx_value",
        "pos",
        "_config_version",
        "_daily_pnl",
        "_consecutive_loss",
    ]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        self.breakout_window: int = 20
        self.exit_window: int = 10
        self.atr_window: int = 14
        self.atr_multiplier: float = 2.0
        self.adx_window: int = 14
        self.adx_threshold: float = 20.0
        self.breakout_atr_buffer: float = 0.0
        self.min_channel_width_ratio: float = 0.01
        self.min_atr_ratio: float = 0.002
        self.max_atr_ratio: float = 0.05

        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.donchian_high: float = 0.0
        self.donchian_low: float = 0.0
        self.exit_high: float = 0.0
        self.exit_low: float = 0.0
        self.atr_value: float = 0.0
        self.adx_value: float = 0.0
        self._stop_price: float = 0.0
        self._am = ArrayManager(size=max(self.breakout_window, self.exit_window, self.atr_window, self.adx_window) + 20)
        self._debug_logged = False

    def _apply_params(self, params: Dict[str, Any], risk: Dict[str, Any]) -> None:
        self.breakout_window = int(params.get("breakout_window", self.breakout_window))
        self.exit_window = int(params.get("exit_window", self.exit_window))
        self.atr_window = int(params.get("atr_window", self.atr_window))
        self.atr_multiplier = float(params.get("atr_multiplier", self.atr_multiplier))
        self.adx_window = int(params.get("adx_window", self.adx_window))
        self.adx_threshold = float(params.get("adx_threshold", self.adx_threshold))
        self.breakout_atr_buffer = float(params.get("breakout_atr_buffer", self.breakout_atr_buffer))
        self.min_channel_width_ratio = float(params.get("min_channel_width_ratio", self.min_channel_width_ratio))
        self.min_atr_ratio = float(params.get("min_atr_ratio", self.min_atr_ratio))
        self.max_atr_ratio = float(params.get("max_atr_ratio", self.max_atr_ratio))
        needed = max(self.breakout_window, self.exit_window, self.atr_window, self.adx_window) + 20
        if self._am.size < needed:
            self._am = ArrayManager(size=needed)

    def _calc_signal(self, bar: BarData) -> Optional[str]:
        am = self._am
        am.update_bar(bar)
        if not am.inited:
            return None

        if not self._debug_logged:
            print(
                f"DEBUG donchian params: breakout={self.breakout_window} exit={self.exit_window} atr_window={self.atr_window} atr_multiplier={self.atr_multiplier} adx_window={self.adx_window} adx_threshold={self.adx_threshold} breakout_atr_buffer={self.breakout_atr_buffer} min_channel_width_ratio={self.min_channel_width_ratio} min_atr_ratio={self.min_atr_ratio} max_atr_ratio={self.max_atr_ratio} stop_loss_pct={self._stop_loss_pct}"
            )
            self._debug_logged = True

        highs = am.high_array
        lows = am.low_array
        closes = am.close_array

        self.donchian_high = max(highs[-self.breakout_window-1:-1])
        self.donchian_low = min(lows[-self.breakout_window-1:-1])
        self.exit_high = max(highs[-self.exit_window-1:-1])
        self.exit_low = min(lows[-self.exit_window-1:-1])
        self.atr_value = am.atr(self.atr_window)
        self.adx_value = am.adx(self.adx_window)

        close = closes[-1]
        if close <= 0:
            return None

        channel_width_ratio = (self.donchian_high - self.donchian_low) / close if close else 0.0
        atr_ratio = self.atr_value / close if close else 0.0

        if self.pos > 0:
            trailing_stop = max(self._stop_price, self.exit_low)
            if close < trailing_stop:
                self.sell(bar.close_price, abs(self.pos))
                self._stop_price = 0.0
                return None

        if self.pos < 0:
            trailing_stop = min(self._stop_price, self.exit_high) if self._stop_price else self.exit_high
            if close > trailing_stop:
                self.cover(bar.close_price, abs(self.pos))
                self._stop_price = 0.0
                return None

        if self.pos == 0:
            if self.adx_value < self.adx_threshold:
                return None
            if channel_width_ratio < self.min_channel_width_ratio:
                return None
            if atr_ratio < self.min_atr_ratio or atr_ratio > self.max_atr_ratio:
                return None
            long_trigger = self.donchian_high + self.breakout_atr_buffer * self.atr_value
            short_trigger = self.donchian_low - self.breakout_atr_buffer * self.atr_value
            if close > long_trigger:
                self._stop_price = close - self.atr_multiplier * self.atr_value
                return "long"
            if close < short_trigger:
                self._stop_price = close + self.atr_multiplier * self.atr_value
                return "short"

        return None

    def on_tick(self, tick: TickData) -> None:
        pass
