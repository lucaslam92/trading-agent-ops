"""
strategies/btc_mean_reversion_strategy.py

BTC 震荡回归策略。

逻辑：
- RSI 低于低阈值（超卖）-> 做多
- RSI 高于高阈值（超买）-> 做空
- 同时检查布林带确认：价格触及布林下轨做多、上轨做空

参数由 strategy_runtime.json 动态注入。
"""

from typing import Any, Dict, Optional

from vnpy.trader.object import BarData, TickData
from vnpy.trader.utility import ArrayManager

from strategies.adaptive_cta_template import AdaptiveCtaTemplate


class BtcMeanReversionStrategy(AdaptiveCtaTemplate):
    """
    BTC 震荡回归策略。

    默认参数（可被 AI 配置覆盖）：
        rsi_window           : RSI 计算周期
        rsi_long_threshold   : RSI 低于此值做多
        rsi_short_threshold  : RSI 高于此值做空
        boll_window          : 布林带计算周期
        boll_dev             : 布林带标准差倍数
    """

    author = "BTC-AI-System"

    parameters = [
        "rsi_window",
        "rsi_long_threshold",
        "rsi_short_threshold",
        "boll_window",
        "boll_dev",
        "stop_loss_pct",
    ]
    variables = [
        "rsi_value",
        "boll_upper",
        "boll_lower",
        "boll_mid",
        "pos",
        "_config_version",
        "_daily_pnl",
        "_consecutive_loss",
    ]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        # 策略参数（安全默认值）
        self.rsi_window: int = 14
        self.rsi_long_threshold: float = 30.0
        self.rsi_short_threshold: float = 70.0
        self.boll_window: int = 20
        self.boll_dev: float = 2.0

        # 指标输出（用于界面显示）
        self.rsi_value: float = 50.0
        self.boll_upper: float = 0.0
        self.boll_lower: float = 0.0
        self.boll_mid: float = 0.0

        # K 线数组管理器
        self._am = ArrayManager(size=max(self.boll_window, self.rsi_window) + 10)

    # ------------------------------------------------------------------
    # 实现基类接口
    # ------------------------------------------------------------------

    def _apply_params(self, params: Dict[str, Any], risk: Dict[str, Any]) -> None:
        """AI 配置刷新时写入策略参数。"""
        self.rsi_window = int(params.get("rsi_window", self.rsi_window))
        self.rsi_long_threshold = float(params.get("rsi_long_threshold", self.rsi_long_threshold))
        self.rsi_short_threshold = float(params.get("rsi_short_threshold", self.rsi_short_threshold))
        self.boll_window = int(params.get("boll_window", self.boll_window))
        self.boll_dev = float(params.get("boll_dev", self.boll_dev))
        needed = max(self.boll_window, self.rsi_window) + 10
        if self._am.size < needed:
            self._am = ArrayManager(size=needed)

    def _calc_signal(self, bar: BarData) -> Optional[str]:
        """
        计算震荡回归信号。

        Returns
        -------
        "long"  : RSI 超卖 + 价格触及布林下轨
        "short" : RSI 超买 + 价格触及布林上轨
        None    : 无信号
        """
        am = self._am
        am.update_bar(bar)

        if not am.inited:
            return None

        self.rsi_value = am.rsi(self.rsi_window)
        upper, self.boll_mid, lower = am.boll(self.boll_window, self.boll_dev)
        self.boll_upper = upper
        self.boll_lower = lower

        close = bar.close_price

        # 止损检查（固定止损比例）
        if self.pos > 0:
            stop = self._entry_price * (1 - self._stop_loss_pct) if hasattr(self, "_entry_price") else 0
            if close < stop:
                self.sell(close, abs(self.pos))
                return None

        if self.pos < 0:
            stop = self._entry_price * (1 + self._stop_loss_pct) if hasattr(self, "_entry_price") else float("inf")
            if close > stop:
                self.cover(close, abs(self.pos))
                return None

        # 止盈：价格回归中轨
        if self.pos > 0 and close >= self.boll_mid:
            self.sell(close, abs(self.pos))
            return None

        if self.pos < 0 and close <= self.boll_mid:
            self.cover(close, abs(self.pos))
            return None

        # 开仓信号
        if self.pos == 0:
            if self.rsi_value < self.rsi_long_threshold and close <= self.boll_lower:
                return "long"
            if self.rsi_value > self.rsi_short_threshold and close >= self.boll_upper:
                return "short"

        return None

    # ------------------------------------------------------------------
    # Tick（不使用，保留接口）
    # ------------------------------------------------------------------

    def on_tick(self, tick: BarData) -> None:
        pass
