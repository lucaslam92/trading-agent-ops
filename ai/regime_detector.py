"""
ai/regime_detector.py

市场状态识别模块（第一版：规则模型）

输入：最近 N 根 K 线的指标特征
输出：regime 字符串
    - "trend_up"        上升趋势
    - "trend_down"      下降趋势
    - "range"           震荡横盘
    - "high_volatility" 高波动异常
"""

from dataclasses import dataclass
from typing import List


@dataclass
class BarFeature:
    """单根 K 线的关键特征"""
    close: float
    volume: float
    atr: float          # 平均真实波幅
    rsi: float          # RSI
    ma_fast: float      # 快均线
    ma_slow: float      # 慢均线
    boll_width: float   # 布林带宽度（(upper - lower) / mid）


# ---------- 可调阈值 ----------
ATR_HIGH_VOLATILITY_MULT = 2.0   # ATR 超过均值多少倍判定为高波动
ADX_TREND_THRESHOLD = 25.0       # 趋势强度阈值（若有 ADX）
BOLL_RANGE_THRESHOLD = 0.03      # 布林带宽度低于此值视为震荡收敛
RSI_UPPER = 60.0                 # RSI 高于此值辅助确认上升
RSI_LOWER = 40.0                 # RSI 低于此值辅助确认下降
LOOKBACK = 5                     # 判断均线斜率所用回溯根数


class RegimeDetector:
    """
    规则式市场状态识别器。

    调用方式：
        detector = RegimeDetector()
        regime = detector.detect(bars)  # bars: List[BarFeature]
    """

    def detect(self, bars: List[BarFeature]) -> str:
        """
        根据最近若干根 K 线特征判断市场状态。

        Parameters
        ----------
        bars : List[BarFeature]
            时间升序排列，最新 bar 在末尾。至少需要 LOOKBACK 根。

        Returns
        -------
        str : regime 标识
        """
        if len(bars) < LOOKBACK:
            return "range"

        latest = bars[-1]

        # --- 1. 高波动检测（优先级最高）---
        avg_atr = sum(b.atr for b in bars) / len(bars)
        if avg_atr > 0 and latest.atr > avg_atr * ATR_HIGH_VOLATILITY_MULT:
            return "high_volatility"

        # --- 2. 震荡检测：布林带收窄 ---
        if latest.boll_width < BOLL_RANGE_THRESHOLD:
            return "range"

        # --- 3. 趋势检测：均线方向 + RSI 辅助 ---
        ma_slope_up = self._is_slope_up(bars, attr="ma_fast")

        if latest.ma_fast > latest.ma_slow:
            if ma_slope_up and latest.rsi >= RSI_UPPER:
                return "trend_up"
        elif latest.ma_fast < latest.ma_slow:
            if not ma_slope_up and latest.rsi <= RSI_LOWER:
                return "trend_down"

        # --- 4. 默认震荡 ---
        return "range"

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _is_slope_up(bars: List[BarFeature], attr: str) -> bool:
        """判断最近 LOOKBACK 根的某均线是否整体向上。"""
        values = [getattr(b, attr) for b in bars[-LOOKBACK:]]
        return values[-1] > values[0]
