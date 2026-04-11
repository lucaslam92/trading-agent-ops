"""
runner/run_paper.py

模拟盘运行入口。

在真实行情下运行策略，但不实际下单。
AI 模块以固定时间间隔（update_interval_bars 根 K 线）运行一次，
更新 strategy_runtime.json，策略在 on_bar 中读取最新配置。

用法：
    python runner/run_paper.py
    python runner/run_paper.py --config configs/paper_config.json
"""

import argparse
import importlib
import logging
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.constant import Exchange, Interval
from vnpy_ctastrategy import CtaStrategyApp
from vnpy_ctastrategy.engine import CtaEngine

from ai.regime_detector import RegimeDetector
from ai.strategy_router import StrategyRouter
from ai.parameter_provider import ParameterProvider
from ai.config_output import ConfigOutput
from services.config_service import ConfigService
from services.market_data_service import MarketDataService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_paper")

_EXCHANGE_MAP = {"BINANCE": Exchange.BINANCE}
_INTERVAL_MAP = {"1h": Interval.HOUR, "15m": Interval.MINUTE_15, "1d": Interval.DAILY}


def run(config_path: str = "configs/paper_config.json") -> None:
    cfg_svc = ConfigService()
    cfg = cfg_svc.load(Path(config_path).stem)
    if not cfg:
        logger.error("配置加载失败: %s", config_path)
        return

    symbol = cfg["symbol"]
    exchange = _EXCHANGE_MAP[cfg["exchange"]]
    interval = _INTERVAL_MAP[cfg["interval"]]
    ai_cfg = cfg.get("ai", {})
    ai_enabled = ai_cfg.get("enabled", True)
    update_interval_bars = ai_cfg.get("update_interval_bars", 4)
    lookback_bars = ai_cfg.get("lookback_bars", 100)

    logger.info("=== BTC 模拟盘启动 ===")

    # --- 1. 启动 vn.py 主引擎 ---
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)

    # 根据配置动态加载 Gateway（此处仅为示意，实盘需配置 API Key）
    # main_engine.add_gateway(BinanceGateway)  # 取消注释并配置 key/secret

    cta_engine: CtaEngine = main_engine.add_app(CtaStrategyApp)

    # --- 2. 加载并初始化策略 ---
    _load_strategy(cta_engine, cfg)

    # --- 3. 如果 AI 已启用，在后台线程定时更新配置 ---
    if ai_enabled:
        ai_thread = _start_ai_thread(
            symbol=symbol,
            exchange=exchange,
            interval=interval,
            bar_interval_seconds=_bar_to_seconds(cfg["interval"]),
            update_every_n_bars=update_interval_bars,
            lookback=lookback_bars,
        )

    # --- 4. 运行（阻塞主线程）---
    logger.info("模拟盘运行中，按 Ctrl+C 退出")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("收到退出信号，关闭引擎")
    finally:
        main_engine.close()


def _load_strategy(cta_engine: "CtaEngine", cfg: dict) -> None:
    """加载 CTA 策略到引擎。"""
    strategy_name = cfg["strategy"]
    module_path = f"strategies.{_camel_to_snake(strategy_name)}.{strategy_name}"
    try:
        module, cls_name = module_path.rsplit(".", 1)
        mod = importlib.import_module(module)
        strategy_cls = getattr(mod, cls_name)
    except (ImportError, AttributeError) as e:
        logger.error("策略加载失败: %s - %s", strategy_name, e)
        return

    vt_symbol = f"{cfg['symbol']}.{cfg['exchange']}"
    cta_engine.add_strategy(strategy_cls, strategy_name, vt_symbol, cfg.get("strategy_setting", {}))
    cta_engine.init_strategy(strategy_name)
    cta_engine.start_strategy(strategy_name)
    logger.info("策略已启动: %s @ %s", strategy_name, vt_symbol)


def _start_ai_thread(
    symbol: str,
    exchange: Exchange,
    interval: Interval,
    bar_interval_seconds: int,
    update_every_n_bars: int,
    lookback: int,
) -> threading.Thread:
    """启动 AI 更新后台线程。"""
    detector = RegimeDetector()
    router = StrategyRouter()
    provider = ParameterProvider()
    output = ConfigOutput()
    data_svc = MarketDataService()

    sleep_seconds = bar_interval_seconds * update_every_n_bars

    def _loop() -> None:
        logger.info("AI 线程启动，更新间隔: %d 秒", sleep_seconds)
        while True:
            try:
                features = data_svc.get_bar_features(symbol, exchange, interval, count=lookback)
                if features:
                    regime = detector.detect(features)
                    config = provider.get(regime)
                    version = output.write(config)
                    logger.info("AI 更新: v%d regime=%s strategy=%s", version, regime, config["strategy"])
                else:
                    logger.warning("AI 线程: 未获取到足够 K 线数据")
            except Exception as e:
                logger.error("AI 线程异常: %s", e)
            time.sleep(sleep_seconds)

    t = threading.Thread(target=_loop, daemon=True, name="AI-Updater")
    t.start()
    return t


def _bar_to_seconds(interval_str: str) -> int:
    """将 K 线周期字符串转为秒数。"""
    mapping = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}
    return mapping.get(interval_str, 3600)


def _camel_to_snake(name: str) -> str:
    """BtcTrendStrategy -> btc_trend_strategy"""
    import re
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BTC CTA 模拟盘")
    parser.add_argument("--config", default="configs/paper_config.json")
    args = parser.parse_args()
    run(args.config)
