"""
strategies/adaptive_cta_template.py

自适应 CTA 策略基类模板。

封装：
- 配置文件加载与版本检测
- 参数刷新（仅当 version 变化时）
- 基础风控检查（持仓方向、最大仓位、单日亏损）
- 公共日志输出格式
- on_init / on_start / on_stop 生命周期钩子

子类只需实现：
    _calc_signal(bar) -> Optional[str]  返回 "long"/"short"/None
    _apply_params(params, risk)          将参数写入自身属性
"""

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from vnpy_ctastrategy import CtaTemplate, StopOrder
from vnpy.trader.object import BarData, TickData, TradeData, OrderData
from vnpy.trader.constant import Direction, Offset

logger = logging.getLogger(__name__)

_RUNTIME_CONFIG_PATH = Path(__file__).parent.parent / "configs" / "strategy_runtime.json"


class AdaptiveCtaTemplate(CtaTemplate, ABC):
    """
    自适应 CTA 策略基类。

    子类需要：
    1. 定义 author / parameters / variables（vn.py 约定）
    2. 实现 _apply_params(params, risk)
    3. 实现 _calc_signal(bar) -> Optional[str]
    """

    author = "BTC-AI-System"

    # vn.py 要求在类级别声明可序列化参数
    parameters = []
    variables = ["_config_version", "_daily_pnl", "_consecutive_loss"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        # 配置版本追踪（用于检测文件变化）
        self._config_version: int = -1

        # 风控状态
        self._daily_pnl: float = 0.0
        self._consecutive_loss: int = 0

        # 风控参数（从配置文件中读入，提供安全默认值）
        self._max_position_pct: float = 0.10
        self._stop_loss_pct: float = 0.015
        self._take_profit_pct: float = 0.030
        self._daily_loss_limit: float = 0.05   # 5% 净值单日最大亏损

    # ------------------------------------------------------------------
    # vn.py 生命周期
    # ------------------------------------------------------------------

    def on_init(self) -> None:
        self.write_log("on_init: 加载历史K线")
        self._refresh_config(force=True)
        self.load_bar(10)   # 预加载 10 天历史 K 线

    def on_start(self) -> None:
        self.write_log("on_start: 策略启动")
        self._daily_pnl = 0.0
        self._consecutive_loss = 0

    def on_stop(self) -> None:
        self.write_log("on_stop: 策略停止")

    def on_bar(self, bar: BarData) -> None:
        """
        主驱动循环。子类一般不覆盖此方法，
        而是实现 _calc_signal()。
        """
        # 1. 读取最新 AI 配置（版本变化时刷新参数）
        self._refresh_config()

        # 2. 始终执行子类信号计算（含止损/止盈平仓逻辑）
        signal = self._calc_signal(bar)

        # 3. 风控检查：仅限制开仓，不阻止平仓
        if signal in ("long", "short") and not self._risk_allow_open():
            return

        # 4. 执行开仓
        if signal == "long":
            self._open_long(bar)
        elif signal == "short":
            self._open_short(bar)

    def on_order(self, order: OrderData) -> None:
        pass

    def on_trade(self, trade: TradeData) -> None:
        """成交回调：更新日内 PnL 和连续亏损计数。"""
        # 开仓时记录入场价，不计 PnL
        if trade.offset == Offset.OPEN:
            self._entry_price = trade.price
            return

        # 平仓时计算 PnL
        if not hasattr(self, "_entry_price") or self._entry_price == 0:
            return

        if trade.direction == Direction.LONG:
            # 平空（cover）：买入价 < 入场空单价 才盈利
            pnl = (self._entry_price - trade.price) * trade.volume
        else:
            # 平多（sell）：卖出价 > 入场多单价 才盈利
            pnl = (trade.price - self._entry_price) * trade.volume

        self._daily_pnl += pnl
        if pnl < 0:
            self._consecutive_loss += 1
        else:
            self._consecutive_loss = 0
        self._entry_price = 0.0

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass

    # ------------------------------------------------------------------
    # 子类必须实现的接口
    # ------------------------------------------------------------------

    @abstractmethod
    def _apply_params(self, params: Dict[str, Any], risk: Dict[str, Any]) -> None:
        """将 params / risk 写入子类自身属性。"""

    @abstractmethod
    def _calc_signal(self, bar: BarData) -> Optional[str]:
        """计算交易信号。返回 "long"/"short"/None。"""

    # ------------------------------------------------------------------
    # 配置刷新
    # ------------------------------------------------------------------

    def _refresh_config(self, force: bool = False) -> None:
        """读取 strategy_runtime.json，版本变化时更新参数。"""
        if not _RUNTIME_CONFIG_PATH.exists():
            return
        try:
            with open(_RUNTIME_CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("_refresh_config: 读取配置失败 %s", e)
            return

        version = cfg.get("version", 0)
        if not force and version == self._config_version:
            return

        self._config_version = version
        params = cfg.get("params", {})
        risk = cfg.get("risk", {})

        self._max_position_pct = risk.get("max_position_pct", self._max_position_pct)
        self._stop_loss_pct = risk.get("stop_loss_pct", self._stop_loss_pct)
        self._take_profit_pct = risk.get("take_profit_pct", self._take_profit_pct)

        self._apply_params(params, risk)
        self.write_log(f"参数已更新: version={version} strategy={cfg.get('strategy')} regime={cfg.get('regime')}")

    # ------------------------------------------------------------------
    # 风控
    # ------------------------------------------------------------------

    def _risk_allow_open(self) -> bool:
        """返回 False 则当前 bar 不允许开仓。"""
        # 单日亏损超限：用绝对金额与资本比例比较
        capital = self._get_capital()
        loss_limit = capital * self._daily_loss_limit if capital > 0 else float("inf")
        if self._daily_pnl < -loss_limit:
            self.write_log(f"风控触发: 单日亏损 {self._daily_pnl:.2f} 超过限额 {loss_limit:.2f}")
            return False
        # 连续亏损超限（5 次）
        if self._consecutive_loss >= 5:
            self.write_log(f"风控触发: 连续亏损 {self._consecutive_loss} 次")
            return False
        return True

    def _calc_lot(self, price: float) -> int:
        """
        根据 max_position_pct 计算开仓手数（最小 1 手）。

        资金获取策略：
        - 回测模式：从 BacktestingEngine.capital 读取
        - 实盘/模拟盘：从 OMS 账户余额读取，失败则返回 1 手
        """
        if price <= 0:
            return 1

        capital = self._get_capital()
        if capital <= 0:
            return 1

        lot = max(1, int(capital * self._max_position_pct / price))
        return lot

    def _get_capital(self) -> float:
        """获取可用资金。兼容回测和实盘两种模式。"""
        # 回测模式：BacktestingEngine 有 capital 属性
        if hasattr(self.cta_engine, "capital"):
            return float(self.cta_engine.capital)
        # 实盘/模拟盘：从账户余额查询
        try:
            accounts = self.cta_engine.main_engine.get_all_accounts()
            if accounts:
                return float(accounts[0].available)
        except Exception:
            pass
        return 0.0

    # ------------------------------------------------------------------
    # 下单辅助
    # ------------------------------------------------------------------

    def _open_long(self, bar: BarData) -> None:
        if self.pos == 0:
            lot = self._calc_lot(bar.close_price)
            self.buy(bar.close_price, lot)
            self._entry_price = bar.close_price

    def _open_short(self, bar: BarData) -> None:
        if self.pos == 0:
            lot = self._calc_lot(bar.close_price)
            self.short(bar.close_price, lot)
            self._entry_price = bar.close_price
