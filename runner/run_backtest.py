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
import sys
from datetime import datetime, date
from pathlib import Path

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
    stats = engine.calculate_statistics()

    logger.info("=== 回测结果 ===")
    for k, v in stats.items():
        logger.info("  %s: %s", k, v)

    # 保存每日 PnL 曲线到 CSV（供后续分析）
    if df is not None and not df.empty:
        out_csv = ROOT / "logs" / f"backtest_{cfg['strategy']}_{cfg['start']}_{cfg['end']}.csv"
        df.to_csv(out_csv)
        logger.info("每日净值已保存: %s", out_csv)

    # 尝试显示图表（无头环境下跳过）
    try:
        engine.show_chart()
    except Exception as e:
        logger.info("show_chart 跳过（无头环境）: %s", e)


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
