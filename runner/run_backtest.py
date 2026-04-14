"""
runner/run_backtest.py

回测运行入口。

使用 vn.py BacktestingEngine 执行策略回测，
回测前先运行一次 AI 模块生成初始配置，
回测中策略通过 on_bar 读取该配置（与实盘一致）。

用法：
    python runner/run_backtest.py
    python runner/run_backtest.py --config configs/backtest_config.json
"""

import argparse
import json
import logging
import math
import sys
from datetime import datetime, date
from pathlib import Path

import pandas as pd

# 确保项目根目录在 PYTHONPATH
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from vnpy.trader.constant import Exchange, Interval
from vnpy_ctastrategy.backtesting import BacktestingEngine

# 兼容不同 vn.py 版本：部分版本没有 Exchange.OKX，回测链路退化为 LOCAL 存储标识。
if not hasattr(Exchange, "OKX"):
    Exchange.OKX = Exchange.LOCAL

from ai.regime_detector import RegimeDetector
from ai.strategy_router import StrategyRouter
from ai.parameter_provider import ParameterProvider
from ai.config_output import ConfigOutput
from services.config_service import ConfigService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_backtest")

_EXCHANGE_MAP = {
    "OKX": Exchange.OKX,
}

_STRATEGY_MAP = {
    "BtcTrendStrategy": "strategies.btc_trend_strategy.BtcTrendStrategy",
    "BtcMeanReversionStrategy": "strategies.btc_mean_reversion_strategy.BtcMeanReversionStrategy",
    "BtcDonchianBreakoutStrategy": "strategies.btc_donchian_breakout_strategy.BtcDonchianBreakoutStrategy",
    "BtcSupertrendStrategy": "strategies.btc_supertrend_strategy.BtcSupertrendStrategy",
    "BtcSqueezeBreakoutStrategy": "strategies.btc_squeeze_breakout_strategy.BtcSqueezeBreakoutStrategy",
    "BtcMtfConfirmationStrategy": "strategies.btc_mtf_confirmation_strategy.BtcMtfConfirmationStrategy",
    "BtcTimeFilteredTrendStrategy": "strategies.btc_time_filtered_trend_strategy.BtcTimeFilteredTrendStrategy",
    "BtcMaEmaMtfStrategy": "strategies.btc_ma_ema_mtf_strategy.BtcMaEmaMtfStrategy",
    "BtcMaEmaTrueMtfStrategy": "strategies.btc_ma_ema_true_mtf_strategy.BtcMaEmaTrueMtfStrategy",
    "BtcMaEmaMtfPullbackStrategy": "strategies.btc_ma_ema_mtf_pullback_strategy.BtcMaEmaMtfPullbackStrategy",
    "BtcMaEmaTrueMtfPullbackStrategy": "strategies.btc_ma_ema_true_mtf_pullback_strategy.BtcMaEmaTrueMtfPullbackStrategy",
    "BtcBoxBreakoutVolumeStrategy": "strategies.btc_box_breakout_volume_strategy.BtcBoxBreakoutVolumeStrategy",
    "BtcStateMachineBoxStrategy": "strategies.btc_state_machine_box_strategy.BtcStateMachineBoxStrategy",
    "BtcStateMachineBoxRetestStrategy": "strategies.btc_state_machine_box_retest_strategy.BtcStateMachineBoxRetestStrategy",
    "BtcStateMachineSwingRetestStrategy": "strategies.btc_state_machine_swing_retest_strategy.BtcStateMachineSwingRetestStrategy",
    "BtcStructureTrendV2Strategy": "strategies.btc_structure_trend_v2_strategy.BtcStructureTrendV2Strategy",
    "BtcBosRetestLongStrategy": "strategies.btc_bos_retest_long_strategy.BtcBosRetestLongStrategy",
}


def run(config_path: str = "configs/backtest_config.json") -> None:
    # --- 1. 加载回测配置 ---
    cfg_svc = ConfigService()
    cfg = cfg_svc.load(Path(config_path).stem)
    if not cfg:
        logger.error("回测配置加载失败: %s", config_path)
        return

    logger.info("=== BTC 回测启动 ===")
    logger.info("时间区间: %s -> %s", cfg["start"], cfg["end"])

    # --- 2. 初始化 AI 模块，生成初始策略配置 ---
    _init_ai_config()

    # --- 3. 动态导入策略类 ---
    strategy_cls_path = _STRATEGY_MAP.get(cfg["strategy"])
    if strategy_cls_path is None:
        logger.error("未知策略: %s", cfg["strategy"])
        return

    module_path, cls_name = strategy_cls_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    strategy_cls = getattr(module, cls_name)

    # --- 4. 构建 BacktestingEngine ---
    engine = BacktestingEngine()
    exchange = _EXCHANGE_MAP.get(cfg["exchange"], Exchange.OKX)
    engine.set_parameters(
        vt_symbol=f"{cfg['symbol']}.{cfg['exchange']}",
        interval=Interval(cfg["interval"]),
        start=_parse_dt(cfg["start"]),
        end=_parse_dt(cfg["end"]),
        rate=cfg.get("rate", 0.0005),
        slippage=cfg.get("slippage", 10.0),
        size=cfg.get("size", 1),
        pricetick=cfg.get("pricetick", 0.01),
        capital=cfg.get("capital", 1_000_000),
    )

    engine.add_strategy(strategy_cls, cfg.get("strategy_setting", {}))

    # --- 5. 运行回测 ---
    logger.info("加载历史数据 ...")
    engine.load_data()

    logger.info("开始回测 ...")
    engine.run_backtesting()

    # --- 6. 输出结果 ---
    df = engine.calculate_result()
    stats = engine.calculate_statistics(output=False)

    # 保存每日 PnL 曲线到 CSV（供后续分析）
    if df is not None and not df.empty:
        out_csv = ROOT / "logs" / f"backtest_{cfg['strategy']}_{cfg['start']}_{cfg['end']}.csv"
        df.to_csv(out_csv)
        logger.info("每日净值已保存: %s", out_csv)

    analysis = _build_analysis(df, stats, cfg)
    logger.info("=== 回测结果分析 ===")
    for label, value in analysis:
        logger.info("  %s: %s", label, value)

    # 尝试显示图表（无头环境下跳过）
    try:
        engine.show_chart()
    except Exception as e:
        logger.info("show_chart 跳过（无头环境）: %s", e)


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except (TypeError, ValueError):
        return default


def _fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def _fmt_num(value: float) -> str:
    return f"{value:.2f}"


def _fmt_count(value: int) -> str:
    return str(int(value))


def _fmt_duration(hours: float) -> str:
    if hours <= 0:
        return "0h"
    days = int(hours // 24)
    remain_hours = int(round(hours - days * 24))
    if days > 0 and remain_hours > 0:
        return f"{days}d {remain_hours}h"
    if days > 0:
        return f"{days}d"
    return f"{int(round(hours))}h"


def _extract_trade_pairs(df: pd.DataFrame, size: float) -> list[dict]:
    if df is None or df.empty or "trades" not in df.columns:
        return []

    pairs: list[dict] = []
    open_trade = None
    daily_rows = list(df.itertuples(index=False))

    for idx, row in enumerate(daily_rows):
        trades = getattr(row, "trades", None)
        if not trades:
            continue
        row_commission = _safe_float(getattr(row, "commission", 0.0))
        row_slippage = _safe_float(getattr(row, "slippage", 0.0))
        row_trade_count = int(_safe_float(getattr(row, "trade_count", 0), 0))
        fee_per_trade = ((row_commission + row_slippage) / row_trade_count) if row_trade_count > 0 else 0.0

        for trade in trades:
            direction = str(getattr(trade, "direction", ""))
            offset = str(getattr(trade, "offset", ""))
            price = _safe_float(getattr(trade, "price", 0.0))
            dt = getattr(trade, "datetime", None)
            volume = _safe_float(getattr(trade, "volume", 1.0), 1.0)

            if "OPEN" in offset.upper():
                side = "long" if "LONG" in direction.upper() else "short"
                open_trade = {
                    "side": side,
                    "entry_price": price,
                    "entry_dt": dt,
                    "volume": volume,
                    "entry_fee": fee_per_trade,
                }
            elif "CLOSE" in offset.upper() and open_trade:
                multiplier = size * open_trade["volume"]
                gross = ((price - open_trade["entry_price"]) if open_trade["side"] == "long" else (open_trade["entry_price"] - price)) * multiplier
                total_fee = open_trade["entry_fee"] + fee_per_trade
                hold_hours = 0.0
                if open_trade["entry_dt"] and dt:
                    hold_hours = max((dt - open_trade["entry_dt"]).total_seconds() / 3600.0, 0.0)
                pairs.append({
                    "side": open_trade["side"],
                    "gross_pnl": gross,
                    "net_pnl": gross - total_fee,
                    "fee": total_fee,
                    "hold_hours": hold_hours,
                })
                open_trade = None

    return pairs


def _build_analysis(df: pd.DataFrame | None, stats: dict, cfg: dict) -> list[tuple[str, str]]:
    capital = _safe_float(cfg.get("capital", 0.0), 0.0)
    total_return = _safe_float(stats.get("total_return"), 0.0)
    annual_return = _safe_float(stats.get("annual_return"), total_return)
    max_dd = abs(_safe_float(stats.get("max_ddpercent"), 0.0))
    sharpe = _safe_float(stats.get("sharpe_ratio"), 0.0)
    total_trade_count = int(_safe_float(stats.get("total_trade_count"), 0))

    total_commission = _safe_float(df["commission"].sum(), 0.0) if df is not None and not df.empty else 0.0
    total_slippage = _safe_float(df["slippage"].sum(), 0.0) if df is not None and not df.empty else 0.0
    total_fee = total_commission + total_slippage
    net_pnl = _safe_float(df["net_pnl"].sum(), 0.0) if df is not None and not df.empty else 0.0
    gross_pnl = _safe_float(df["total_pnl"].sum(), 0.0) if df is not None and not df.empty else 0.0

    trades = _extract_trade_pairs(df, _safe_float(cfg.get("size", 1.0), 1.0)) if df is not None and not df.empty else []
    closed_trades = len(trades)
    wins = [t for t in trades if t["net_pnl"] > 0]
    losses = [t for t in trades if t["net_pnl"] < 0]
    long_trades = [t for t in trades if t["side"] == "long"]
    short_trades = [t for t in trades if t["side"] == "short"]

    win_rate = (len(wins) / closed_trades * 100.0) if closed_trades else 0.0
    avg_win = sum(t["net_pnl"] for t in wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(t["net_pnl"] for t in losses) / len(losses)) if losses else 0.0
    gross_profit = sum(t["net_pnl"] for t in wins)
    gross_loss = abs(sum(t["net_pnl"] for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0
    avg_hold_hours = sum(t["hold_hours"] for t in trades) / closed_trades if closed_trades else 0.0
    long_pnl = sum(t["net_pnl"] for t in long_trades)
    short_pnl = sum(t["net_pnl"] for t in short_trades)
    calmar = (annual_return / max_dd) if max_dd > 0 else 0.0

    return [
        ("total_return", _fmt_pct(total_return)),
        ("annual_return", _fmt_pct(annual_return)),
        ("max_drawdown", _fmt_pct(max_dd)),
        ("sharpe", _fmt_num(sharpe)),
        ("calmar", _fmt_num(calmar)),
        ("total_trades", _fmt_count(total_trade_count)),
        ("win_rate", _fmt_pct(win_rate)),
        ("avg_win", _fmt_num(avg_win)),
        ("avg_loss", _fmt_num(avg_loss)),
        ("profit_factor", _fmt_num(profit_factor)),
        ("gross_pnl", _fmt_num(gross_pnl)),
        ("net_pnl", _fmt_num(net_pnl)),
        ("total_fee", _fmt_num(total_fee)),
        ("avg_holding_time", _fmt_duration(avg_hold_hours)),
        ("long_pnl", _fmt_num(long_pnl)),
        ("short_pnl", _fmt_num(short_pnl)),
    ]


def _parse_dt(s: str) -> datetime:
    """兼容 'YYYY-MM-DD' 和 'YYYY-MM-DDTHH:MM:SS' 两种格式。"""
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.combine(date.fromisoformat(s), datetime.min.time())


def _init_ai_config() -> None:
    """在回测开始前用规则 AI 生成一份初始配置（使用默认 range 状态）。"""
    provider = ParameterProvider()
    output = ConfigOutput()
    config = provider.get("range")
    output.write(config)
    logger.info("AI 初始配置已写入: regime=%s strategy=%s", config["regime"], config["strategy"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BTC CTA 回测")
    parser.add_argument(
        "--config",
        default="configs/backtest_config.json",
        help="回测配置文件路径",
    )
    args = parser.parse_args()
    run(args.config)
