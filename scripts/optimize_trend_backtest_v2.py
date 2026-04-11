import itertools
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "configs"
RESULT_PATH = ROOT / "logs" / "trend_optimization_results_v2.json"

fast_windows = [5, 10, 15]
slow_windows = [20, 30, 50]
atr_multipliers = [1.0, 1.5, 2.0]
stop_losses = [0.01, 0.015, 0.02]

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
for fast, slow, atr, stop in itertools.product(fast_windows, slow_windows, atr_multipliers, stop_losses):
    if fast >= slow:
        continue
    combo_id += 1
    name = f"opt_trend_{combo_id:03d}"
    cfg = {
        "mode": "backtest",
        "symbol": "BTC-USDT-SWAP",
        "exchange": "LOCAL",
        "interval": "1h",
        "start": "2023-01-01",
        "end": "2024-01-01",
        "rate": 0.0005,
        "slippage": 5.0,
        "size": 0.01,
        "pricetick": 0.1,
        "capital": 100000,
        "strategy": "BtcTrendStrategy",
        "strategy_setting": {
            "fast_window": fast,
            "slow_window": slow,
            "atr_window": 14,
            "atr_multiplier": atr,
            "stop_loss_pct": stop,
        },
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
        "fast_window": fast,
        "slow_window": slow,
        "atr_multiplier": atr,
        "stop_loss_pct": stop,
        "exit_code": proc.returncode,
    }
    for key, pattern in patterns.items():
        m = pattern.search(text)
        if m:
            val = m.group(1).replace(",", "")
            item[key] = float(val) if key != "trade_count" else int(val)
    results.append(item)
    print(f"[{combo_id:03d}] fast={fast} slow={slow} atr={atr} stop={stop} -> return={item.get('total_return')} sharpe={item.get('sharpe_ratio')} dd={item.get('max_ddpercent')}")

results = [r for r in results if "total_return" in r]
results.sort(key=lambda x: (
    x.get("total_return", -999),
    x.get("sharpe_ratio", -999),
    x.get("max_ddpercent", -999),
), reverse=True)

RESULT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"saved {len(results)} parsed results to {RESULT_PATH}")
print("top 10:")
for row in results[:10]:
    print(row)
