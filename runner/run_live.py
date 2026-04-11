"""
runner/run_live.py

实盘运行入口。

与 run_paper.py 逻辑基本相同，区别在于：
1. 需要配置真实的 Gateway API Key / Secret
2. 风控参数更保守（来自 live_config.json）
3. 启动前有安全确认提示

用法：
    python runner/run_live.py --config configs/live_config.json

警告：实盘模式会真实下单，请确保：
    - API Key 已正确配置
    - 资金量在可接受范围内
    - 风控参数已充分验证
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
from services.risk_service import RiskService

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_live")

_EXCHANGE_MAP = {
    "OKX": Exchange.OKX,
}
_INTERVAL_MAP = {
    "1m": Interval.MINUTE, "5m": Interval.MINUTE_5, "15m": Interval.MINUTE_15,
    "30m": Interval.MINUTE_30, "1h": Interval.HOUR, "4h": Interval.HOUR_4,
    "1d": Interval.DAILY,
}


def run(config_path: str = "configs/live_config.json", skip_confirm: bool = False) -> None:
    cfg_svc = ConfigService()
    cfg = cfg_svc.load(Path(config_path).stem)
    if not cfg:
        logger.error("配置加载失败: %s", config_path)
        return

    # --- 安全确认 ---
    if not skip_confirm:
        print("\n" + "=" * 60)
        print("  警告：即将启动【实盘模式】，真实资金将参与交易！")
        print(f"  策略: {cfg['strategy']}")
        print(f"  品种: {cfg['symbol']}.{cfg['exchange']}")
        print("=" * 60)
        confirm = input("  请输入 'YES' 确认启动: ")
        if confirm.strip() != "YES":
            print("已取消启动。")
            return

    symbol = cfg["symbol"]
    exchange = _EXCHANGE_MAP[cfg["exchange"]]
    interval = _INTERVAL_MAP[cfg["interval"]]
    ai_cfg = cfg.get("ai", {})
    risk_cfg = cfg.get("risk", {})
    ai_enabled = ai_cfg.get("enabled", True)
    update_interval_bars = ai_cfg.get("update_interval_bars", 4)
    lookback_bars = ai_cfg.get("lookback_bars", 100)

    # 全局风控服务（实盘更保守）
    risk_svc = RiskService(
        max_position_pct=risk_cfg.get("max_position_pct", 0.10),
        daily_loss_limit=risk_cfg.get("daily_loss_limit", 0.03),
    )

    logger.warning("=== BTC OKX 实盘启动 ===")
    logger.warning("品种: %s  周期: %s", cfg["symbol"], cfg["interval"])

    # --- 启动 vn.py 主引擎 ---
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)

    # --- 连接 OKX Gateway（实盘，server=REAL）---
    _connect_okx_gateway(main_engine, server=cfg.get("server", "REAL"))

    cta_engine: CtaEngine = main_engine.add_app(CtaStrategyApp)
    _load_strategy(cta_engine, cfg)

    if ai_enabled:
        _start_ai_thread(
            symbol=symbol,
            exchange=exchange,
            interval=interval,
            bar_interval_seconds=_bar_to_seconds(cfg["interval"]),
            update_every_n_bars=update_interval_bars,
            lookback=lookback_bars,
        )

    logger.warning("实盘运行中，按 Ctrl+C 退出")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.warning("收到退出信号，关闭引擎")
    finally:
        main_engine.close()


def _load_strategy(cta_engine: "CtaEngine", cfg: dict) -> None:
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
    logger.warning("策略已启动: %s @ %s", strategy_name, vt_symbol)


def _start_ai_thread(
    symbol: str,
    exchange: Exchange,
    interval: Interval,
    bar_interval_seconds: int,
    update_every_n_bars: int,
    lookback: int,
) -> threading.Thread:
    detector = RegimeDetector()
    provider = ParameterProvider()
    output = ConfigOutput()
    data_svc = MarketDataService()

    sleep_seconds = bar_interval_seconds * update_every_n_bars

    def _loop() -> None:
        while True:
            try:
                features = data_svc.get_bar_features(symbol, exchange, interval, count=lookback)
                if features:
                    regime = detector.detect(features)
                    config = provider.get(regime)
                    version = output.write(config)
                    logger.warning("AI 更新: v%d regime=%s strategy=%s", version, regime, config["strategy"])
            except Exception as e:
                logger.error("AI 线程异常: %s", e)
            time.sleep(sleep_seconds)

    t = threading.Thread(target=_loop, daemon=True, name="AI-Updater-Live")
    t.start()
    return t


def _connect_okx_gateway(main_engine, server: str = "REAL") -> None:
    """
    加载并连接 OKX Gateway（实盘）。

    从环境变量读取凭证：
        OKX_API_KEY      - API Key
        OKX_SECRET_KEY   - Secret Key
        OKX_PASSPHRASE   - Passphrase

    server="REAL" 为实盘，server="TEST" 为模拟盘。
    """
    import os
    try:
        from vnpy_okx import OkxGateway
    except ImportError:
        logger.error("vnpy_okx 未安装，请运行: pip install vnpy_okx")
        return

    api_key    = os.environ.get("OKX_API_KEY", "")
    secret_key = os.environ.get("OKX_SECRET_KEY", "")
    passphrase = os.environ.get("OKX_PASSPHRASE", "")

    if not all([api_key, secret_key, passphrase]):
        logger.error(
            "OKX 凭证未配置！请设置环境变量:\n"
            "  export OKX_API_KEY=your_key\n"
            "  export OKX_SECRET_KEY=your_secret\n"
            "  export OKX_PASSPHRASE=your_passphrase"
        )
        raise RuntimeError("OKX 凭证未配置，实盘无法启动")

    main_engine.add_gateway(OkxGateway)
    main_engine.connect(
        setting={
            "API Key":    api_key,
            "Secret Key": secret_key,
            "Passphrase": passphrase,
            "Server":     server,
            "Proxy Host": os.environ.get("PROXY_HOST", ""),
            "Proxy Port": int(os.environ.get("PROXY_PORT", 0)),
        },
        gateway_name="OKX",
    )
    logger.warning("OKX Gateway 已连接 (server=%s)", server)


def _bar_to_seconds(interval_str: str) -> int:
    mapping = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800,
               "1h": 3600, "4h": 14400, "1d": 86400}
    return mapping.get(interval_str, 3600)


def _camel_to_snake(name: str) -> str:
    import re
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BTC CTA 实盘")
    parser.add_argument("--config", default="configs/live_config.json")
    parser.add_argument("--yes", action="store_true", help="跳过确认提示（CI / 自动化场景使用）")
    args = parser.parse_args()
    run(args.config, skip_confirm=args.yes)
