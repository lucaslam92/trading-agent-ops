"""
ai/strategy_router.py

根据 regime 决定使用哪个策略类型。

输出：
    "trend_following"   趋势跟随策略
    "mean_reversion"    震荡回归策略
"""

# regime -> 策略类型映射表
_REGIME_TO_STRATEGY = {
    "trend_up": "trend_following",
    "trend_down": "trend_following",
    "range": "mean_reversion",
    "high_volatility": "trend_following",  # 趋势策略，但风控层会降低仓位
}

_DEFAULT_STRATEGY = "mean_reversion"


class StrategyRouter:
    """
    策略路由器：将 regime 映射为策略类型标识。

    调用方式：
        router = StrategyRouter()
        strategy_name = router.route("trend_up")  # -> "trend_following"
    """

    def route(self, regime: str) -> str:
        """
        Parameters
        ----------
        regime : str
            来自 RegimeDetector 的市场状态标识。

        Returns
        -------
        str : 策略类型标识
        """
        strategy = _REGIME_TO_STRATEGY.get(regime, _DEFAULT_STRATEGY)
        return strategy
