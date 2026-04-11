"""
ai/parameter_provider.py

根据当前 regime 和策略类型输出对应参数配置。

输出格式（dict）：
{
    "regime": "trend_up",
    "strategy": "trend_following",
    "params": { ... },
    "risk": { ... }
}
"""

from typing import Any, Dict

# ---------- 各 regime 下的默认参数配置 ----------

_TREND_FOLLOWING_BASE = {
    "fast_window": 10,
    "slow_window": 30,
    "atr_window": 14,
    "atr_multiplier": 1.5,
}

_MEAN_REVERSION_BASE = {
    "rsi_window": 14,
    "rsi_long_threshold": 30.0,
    "rsi_short_threshold": 70.0,
    "boll_window": 20,
    "boll_dev": 2.0,
}

_RISK_NORMAL = {
    "max_position_pct": 0.20,
    "stop_loss_pct": 0.015,
    "take_profit_pct": 0.030,
}

_RISK_HIGH_VOL = {
    "max_position_pct": 0.10,   # 高波动时仓位减半
    "stop_loss_pct": 0.020,
    "take_profit_pct": 0.040,
}

# regime -> (strategy, params, risk)
_REGIME_CONFIGS: Dict[str, Dict[str, Any]] = {
    "trend_up": {
        "strategy": "trend_following",
        "params": _TREND_FOLLOWING_BASE,
        "risk": _RISK_NORMAL,
    },
    "trend_down": {
        "strategy": "trend_following",
        "params": _TREND_FOLLOWING_BASE,
        "risk": _RISK_NORMAL,
    },
    "range": {
        "strategy": "mean_reversion",
        "params": _MEAN_REVERSION_BASE,
        "risk": _RISK_NORMAL,
    },
    "high_volatility": {
        "strategy": "trend_following",
        "params": _TREND_FOLLOWING_BASE,
        "risk": _RISK_HIGH_VOL,
    },
}

_DEFAULT_CONFIG = _REGIME_CONFIGS["range"]


class ParameterProvider:
    """
    根据 regime 输出完整策略参数配置（dict）。

    调用方式：
        provider = ParameterProvider()
        config = provider.get(regime="trend_up")
    """

    def get(self, regime: str) -> Dict[str, Any]:
        """
        Parameters
        ----------
        regime : str
            来自 RegimeDetector 的市场状态标识。

        Returns
        -------
        dict : 包含 regime / strategy / params / risk 的完整配置
        """
        base = _REGIME_CONFIGS.get(regime, _DEFAULT_CONFIG)
        return {
            "regime": regime,
            "strategy": base["strategy"],
            "params": dict(base["params"]),   # 浅拷贝，防止外部修改
            "risk": dict(base["risk"]),
        }
