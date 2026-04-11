"""
services/risk_service.py

风险控制服务。

提供全局风控状态追踪，供策略层和 runner 层共同使用。

功能：
- 单日 PnL 累计与限额检查
- 连续亏损次数计数
- 仓位比例上限校验
- 波动率异常检查（ATR 急剧放大）
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RiskState:
    """当前风控状态快照。"""
    daily_pnl: float = 0.0
    consecutive_loss: int = 0
    is_paused: bool = False          # 是否暂停开仓
    pause_reason: str = ""           # 暂停原因


class RiskService:
    """
    全局风控服务（单例使用）。

    配置参数在初始化时传入，也可以在运行时通过 update_config() 动态更新。

    调用方式：
        risk = RiskService(max_position_pct=0.2, daily_loss_limit=0.05)
        risk.on_trade(pnl=100.0)
        ok = risk.allow_open(price=50000, lot=1, capital=1_000_000)
    """

    def __init__(
        self,
        max_position_pct: float = 0.20,
        stop_loss_pct: float = 0.015,
        take_profit_pct: float = 0.030,
        daily_loss_limit: float = 0.05,
        max_consecutive_loss: int = 5,
        atr_spike_multiplier: float = 3.0,
    ) -> None:
        self.max_position_pct = max_position_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.daily_loss_limit = daily_loss_limit
        self.max_consecutive_loss = max_consecutive_loss
        self.atr_spike_multiplier = atr_spike_multiplier

        self._state = RiskState()
        self._avg_atr: Optional[float] = None

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def update_config(self, risk: dict) -> None:
        """运行时动态更新风控参数（来自 AI 配置刷新）。"""
        self.max_position_pct = float(risk.get("max_position_pct", self.max_position_pct))
        self.stop_loss_pct = float(risk.get("stop_loss_pct", self.stop_loss_pct))
        self.take_profit_pct = float(risk.get("take_profit_pct", self.take_profit_pct))

    def on_trade(self, pnl: float) -> None:
        """每次成交后更新 PnL 和连续亏损状态。"""
        self._state.daily_pnl += pnl
        if pnl < 0:
            self._state.consecutive_loss += 1
        else:
            self._state.consecutive_loss = 0
        self._check_pause()

    def on_bar_atr(self, atr: float) -> None:
        """每根 K 线更新 ATR，用于波动率异常检测。"""
        if self._avg_atr is None:
            self._avg_atr = atr
        else:
            self._avg_atr = self._avg_atr * 0.95 + atr * 0.05  # 指数平滑

        if self._avg_atr > 0 and atr > self._avg_atr * self.atr_spike_multiplier:
            self._pause("ATR急剧放大: {:.2f} > {:.2f}".format(atr, self._avg_atr * self.atr_spike_multiplier))

    def allow_open(self, price: float, lot: int, capital: float) -> bool:
        """
        开仓前检查。返回 False 表示当前不允许开仓。

        Parameters
        ----------
        price   : 当前价格
        lot     : 拟开手数
        capital : 当前可用资金
        """
        if self._state.is_paused:
            return False

        exposure = price * lot
        max_exposure = capital * self.max_position_pct
        if exposure > max_exposure:
            logger.warning(
                "RiskService: 风险敞口 %.2f 超过上限 %.2f，已拒绝开仓",
                exposure, max_exposure,
            )
            return False

        return True

    def reset_daily(self) -> None:
        """每日收盘后调用，重置当日计数。"""
        logger.info(
            "RiskService: 当日重置 daily_pnl=%.4f consecutive_loss=%d",
            self._state.daily_pnl,
            self._state.consecutive_loss,
        )
        self._state.daily_pnl = 0.0
        self._state.consecutive_loss = 0
        self._state.is_paused = False
        self._state.pause_reason = ""

    @property
    def state(self) -> RiskState:
        return self._state

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _check_pause(self) -> None:
        """检查是否需要触发暂停。"""
        if self._state.daily_pnl < -self.daily_loss_limit:
            self._pause(f"单日亏损 {self._state.daily_pnl:.4f} 超过限额 {-self.daily_loss_limit:.4f}")

        if self._state.consecutive_loss >= self.max_consecutive_loss:
            self._pause(f"连续亏损 {self._state.consecutive_loss} 次")

    def _pause(self, reason: str) -> None:
        if not self._state.is_paused:
            logger.warning("RiskService: 触发暂停 - %s", reason)
        self._state.is_paused = True
        self._state.pause_reason = reason
