import itertools
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "configs"
RESULT_PATH = ROOT / "logs" / "donchian_adx_2024_optimization_results.json"

adx_windows = [10, 14, 20]
adx_thresholds = [15, 20, 25, 30]

patterns = {
    "end_balance": re.compile(r"End Balance:\s*([\d,]+\.\d+)"),
    "total_return": re.compile(r"Total Return:\s*(-?[\d.]+)%"),
    "annual_return": re.compile(r"Annual Return:\s*(-?[\d.]+)%"),
    "max_drawdown": re.compile(r"Max Drawdown:\s*(-?[\d.]+)"),
    "max_ddpercent": re.compile(r"Max Ddpercent:\s*(-?[\d.]+)%"),
    "sharpe_ratio": re.compile(r"Sharpe Ratio[:：]\s*(-?[\d.]+)"),
    "trade_count": re.compile(r"Total Trade Count:\s*(\d+)"),
}

results = []
combo_id = 0
for adx_window, adx_threshold in itertools.product(adx_windows, adx_thresholds):
    combo_id += 1
    name = f"opt_donchian_adx_2024_{combo_id:03d}"
    cfg = {
        "mode": "backtest",
        "symbol": "BTC-USDT-SWAP",
        "exchange": "LOCAL",
        "interval": "1h",
        "start": "2024-01-01",
        "end": "2025-01-01",
        "rate": 0.0005,
        "slippage": 5.0,
        "size": 0.01,
        "pricetick": 0.1,
        "capital": 100000,
        "strategy": "BtcDonchianBreakoutStrategy",
        "strategy_setting": {
            "breakout_window": 50,
            "exit_window": 20,
            "atr_window": 14,
            "atr_multiplier": 1.5,
            "adx_window": adx_window,
            "adx_threshold": adx_threshold,
            "stop_loss_pct": 0.015,
            "next_bar_entry": True,
            "base_slippage": 5.0,
            "atr_slippage_multiplier": 0.05
        }
    }
    cfg_path = CONFIG_DIR / f"{name}.json"
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    proc = subprocess.run(
        ["python3", "runner/run_backtest.py", "--config", str(cfg_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    item = {
        "config_name": name,
        "adx_window": adx_window,
        "adx_threshold": adx_threshold,
        "exit_code": proc.returncode,
    }
    for key, pattern in patterns.items():
        m = pattern.search(text)
        if m:
            val = m.group(1).replace(",", "")
            item[key] = float(val) if key != "trade_count" else int(val)
    results.append(item)
    print(f"[{combo_id:03d}] adx_window={adx_window} adx_threshold={adx_threshold} -> return={item.get('total_return')} sharpe={item.get('sharpe_ratio')} trades={item.get('trade_count')}")

results = [r for r in results if "total_return" in r]
results.sort(key=lambda x: (
    x.get("total_return", -999),
    x.get("sharpe_ratio", -999),
    -x.get("trade_count", 999999)
), reverse=True)

RESULT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"saved {len(results)} parsed results to {RESULT_PATH}")
print("top results:")
for row in results[:12]:
    print(row)
