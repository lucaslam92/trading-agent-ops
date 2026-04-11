"""
strategies/btc_trend_strategy.py

BTC 趋势跟随策略。

逻辑：
- 快均线上穿慢均线 -> 做多
- 快均线下穿慢均线 -> 做空
- ATR 倍数止损
- 成交量确认（可选）

参数由 strategy_runtime.json 动态注入。
"""

from typing import Any, Dict, Optional

from vnpy.trader.object import BarData, TickData
from vnpy.trader.utility import ArrayManager

from strategies.adaptive_cta_template import AdaptiveCtaTemplate


class BtcTrendStrategy(AdaptiveCtaTemplate):
    """
    BTC 趋势跟随策略。

    默认参数（可被 AI 配置覆盖）：
        fast_window    : 快均线周期
        slow_window    : 慢均线周期
        atr_window     : ATR 计算周期
        atr_multiplier : 止损 ATR 倍数
    """

    author = "BTC-AI-System"

    # vn.py 要求在类级别声明参数名（不含值，值由配置注入）
    parameters = [
        "fast_window",
        "slow_window",
        "atr_window",
        "atr_multiplier",
        "stop_loss_pct",
    ]
    variables = [
        "fast_ma",
        "slow_ma",
        "atr_value",
        "pos",
        "_config_version",
        "_daily_pnl",
        "_consecutive_loss",
    ]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        # 先设置默认值，再让 vn.py 用 setting 覆盖，避免外部参数被默认值反向覆盖。
        self.fast_window: int = 10
        self.slow_window: int = 30
        self.atr_window: int = 14
        self.atr_multiplier: float = 1.5

        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        # 指标输出（用于界面显示）
        self.fast_ma: float = 0.0
        self.slow_ma: float = 0.0
        self.atr_value: float = 0.0

        # 止损价追踪
        self._stop_price: float = 0.0

        # K 线数组管理器
        self._am = ArrayManager(size=max(self.slow_window, self.atr_window) + 10)
        self._debug_logged = False

    # ------------------------------------------------------------------
    # 实现基类接口
    # ------------------------------------------------------------------

    def _apply_params(self, params: Dict[str, Any], risk: Dict[str, Any]) -> None:
        """AI 配置刷新时写入策略参数。"""
        self.fast_window = int(params.get("fast_window", self.fast_window))
        self.slow_window = int(params.get("slow_window", self.slow_window))
        self.atr_window = int(params.get("atr_window", self.atr_window))
        self.atr_multiplier = float(params.get("atr_multiplier", self.atr_multiplier))
        # 同步调整 ArrayManager 容量
        needed = max(self.slow_window, self.atr_window) + 10
        if self._am.size < needed:
            self._am = ArrayManager(size=needed)

    def _calc_signal(self, bar: BarData) -> Optional[str]:
        """
        计算趋势信号。

        Returns
        -------
        "long"  : 快线上穿慢线
        "short" : 快线下穿慢线
        None    : 无信号
        """
        am = self._am
        am.update_bar(bar)

        if not am.inited:
            return None

        if not self._debug_logged:
            print(
                f"DEBUG trend params: fast={self.fast_window} slow={self.slow_window} atr_window={self.atr_window} atr_multiplier={self.atr_multiplier} stop_loss_pct={self._stop_loss_pct}"
            )
            self._debug_logged = True

        fast_ma_array = am.sma(self.fast_window, array=True)
        slow_ma_array = am.sma(self.slow_window, array=True)
        atr = am.atr(self.atr_window)

        self.fast_ma = fast_ma_array[-1]
        self.slow_ma = slow_ma_array[-1]
        self.atr_value = atr

        # 当前持仓止损检查
        if self.pos > 0 and bar.close_price < self._stop_price:
            self.sell(bar.close_price, abs(self.pos))
            self._stop_price = 0.0
            return None

        if self.pos < 0 and bar.close_price > self._stop_price:
            self.cover(bar.close_price, abs(self.pos))
            self._stop_price = 0.0
            return None

        prev_fast = fast_ma_array[-2]
        prev_slow = slow_ma_array[-2]

        # 金叉：做多
        if prev_fast <= prev_slow and self.fast_ma > self.slow_ma:
            if self.pos < 0:
                self.cover(bar.close_price, abs(self.pos))
            self._stop_price = bar.close_price - self.atr_multiplier * atr
            return "long"

        # 死叉：做空
        if prev_fast >= prev_slow and self.fast_ma < self.slow_ma:
            if self.pos > 0:
                self.sell(bar.close_price, abs(self.pos))
            self._stop_price = bar.close_price + self.atr_multiplier * atr
            return "short"

        return None

    # ------------------------------------------------------------------
    # Tick（不使用，保留接口）
    # ------------------------------------------------------------------

    def on_tick(self, tick: TickData) -> None:
        pass
