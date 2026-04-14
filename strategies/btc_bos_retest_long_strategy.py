from typing import Any, Dict, Optional

from vnpy.trader.object import BarData, TickData
from vnpy.trader.utility import ArrayManager

from strategies.adaptive_cta_template import AdaptiveCtaTemplate


class BtcBosRetestLongStrategy(AdaptiveCtaTemplate):
    author = "BTC-AI-System"

    parameters = [
        "ma_window", "adx_window", "adx_threshold",
        "swing_window", "retest_tolerance_atr", "stop_atr_multiplier",
        "trailing_atr_multiplier", "min_holding_bars", "stop_loss_pct",
    ]
    variables = [
        "ma_value", "adx_value", "atr_value", "breakout_level",
        "pending_retest", "pending_retest_age", "entry_price_ref",
        "trailing_stop", "highest_price", "holding_bars", "pos",
    ]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        self.ma_window = 50
        self.adx_window = 14
        self.adx_threshold = 20.0
        self.swing_window = 20
        self.retest_tolerance_atr = 0.5
        self.stop_atr_multiplier = 1.5
        self.trailing_atr_multiplier = 2.0
        self.min_holding_bars = 24

        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.ma_value = 0.0
        self.adx_value = 0.0
        self.atr_value = 0.0
        self.breakout_level = 0.0
        self.pending_retest = False
        self.pending_retest_age = 0
        self.entry_price_ref = 0.0
        self.trailing_stop = 0.0
        self.highest_price = 0.0
        self.holding_bars = 0
        self._stop_price = 0.0
        self._last_higher_low = 0.0
        self._am = ArrayManager(size=max(self.ma_window, self.adx_window, self.swing_window) + 50)

    def _apply_params(self, params: Dict[str, Any], risk: Dict[str, Any]) -> None:
        self.ma_window = int(params.get("ma_window", self.ma_window))
        self.adx_window = int(params.get("adx_window", self.adx_window))
        self.adx_threshold = float(params.get("adx_threshold", self.adx_threshold))
        self.swing_window = int(params.get("swing_window", self.swing_window))
        self.retest_tolerance_atr = float(params.get("retest_tolerance_atr", self.retest_tolerance_atr))
        self.stop_atr_multiplier = float(params.get("stop_atr_multiplier", self.stop_atr_multiplier))
        self.trailing_atr_multiplier = float(params.get("trailing_atr_multiplier", self.trailing_atr_multiplier))
        self.min_holding_bars = int(params.get("min_holding_bars", self.min_holding_bars))

    def _calc_signal(self, bar: BarData) -> Optional[str]:
        am = self._am
        am.update_bar(bar)
        if not am.inited:
            return None

        highs = am.high_array
        lows = am.low_array
        opens = am.open_array
        closes = am.close_array

        self.ma_value = am.sma(self.ma_window)
        self.adx_value = am.adx(self.adx_window)
        self.atr_value = am.atr(14)

        close = bar.close_price
        low = bar.low_price
        high = bar.high_price
        open_price = bar.open_price
        if close <= 0 or self.atr_value <= 0:
            return None

        prev_high = max(highs[-self.swing_window - 1:-1])
        prev_low = min(lows[-self.swing_window - 1:-1])
        self.breakout_level = prev_high

        trend_ok = close > self.ma_value and self.adx_value > self.adx_threshold
        bull_confirm = close > open_price and close >= closes[-2]

        recent_lows = lows[-6:-1]
        self._last_higher_low = min(recent_lows) if len(recent_lows) else prev_low

        if self.pos > 0:
            self.holding_bars += 1
            self.highest_price = max(self.highest_price, high) if self.highest_price else high
            trail = self.highest_price - self.trailing_atr_multiplier * self.atr_value
            self.trailing_stop = max(self.trailing_stop, trail) if self.trailing_stop else trail

            # 硬止损始终有效
            if close <= self._stop_price:
                self.sell(close, abs(self.pos))
                self._reset_position_state()
                return None

            # 前24h仅忽略止盈/移动止损触发，不忽略硬止损
            if self.holding_bars < self.min_holding_bars:
                return None

            if close <= self.trailing_stop:
                self.sell(close, abs(self.pos))
                self._reset_position_state()
                return None
            return None

        if not trend_ok:
            self.pending_retest = False
            self.pending_retest_age = 0
            return None

        bos = close > prev_high
        if bos and not self.pending_retest:
            self.pending_retest = True
            self.pending_retest_age = 0
            self.breakout_level = prev_high
            return None

        if self.pending_retest:
            self.pending_retest_age += 1
            tolerance = self.retest_tolerance_atr * self.atr_value
            retest_zone_low = self.breakout_level - tolerance
            retest_zone_high = self.breakout_level + tolerance
            touched = low <= retest_zone_high and high >= retest_zone_low
            not_broken = close >= self.breakout_level and low >= retest_zone_low

            if touched and not_broken and bull_confirm:
                self.entry_price_ref = close
                self.highest_price = close
                hl_stop = self._last_higher_low if self._last_higher_low > 0 else close - self.stop_atr_multiplier * self.atr_value
                atr_stop = close - self.stop_atr_multiplier * self.atr_value
                self._stop_price = max(hl_stop, atr_stop)
                self.trailing_stop = close - self.trailing_atr_multiplier * self.atr_value
                self.holding_bars = 0
                self.pending_retest = False
                self.pending_retest_age = 0
                return "long"

            if close < retest_zone_low or self.pending_retest_age > 12:
                self.pending_retest = False
                self.pending_retest_age = 0

        return None

    def _reset_position_state(self) -> None:
        self.entry_price_ref = 0.0
        self.trailing_stop = 0.0
        self.highest_price = 0.0
        self.holding_bars = 0
        self._stop_price = 0.0

    def on_tick(self, tick: TickData) -> None:
        pass
