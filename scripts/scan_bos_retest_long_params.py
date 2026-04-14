import itertools
import json
import re
import subprocess
from pathlib import Path

ROOT = Path('/root/.openclaw/workspace')
CFGDIR = ROOT / 'configs'
OUT = Path('/tmp/scan_bos_retest_long_params_2024.json')

GRID = {
    'adx_threshold': [18, 20, 22],
    'swing_window': [20, 30, 40],
    'retest_tolerance_atr': [0.3, 0.5, 0.7],
    'stop_atr_multiplier': [1.2, 1.5, 1.8],
    'trailing_atr_multiplier': [2.0, 2.5, 3.0],
}

PATS = {
    'total_return': re.compile(r'total_return:\s*(-?[\d.]+%)', re.I),
    'annual_return': re.compile(r'annual_return:\s*(-?[\d.]+%)', re.I),
    'max_drawdown': re.compile(r'max_drawdown:\s*(-?[\d.]+%)', re.I),
    'sharpe': re.compile(r'sharpe:\s*(-?[\d.]+)', re.I),
    'calmar': re.compile(r'calmar:\s*(-?[\d.]+)', re.I),
    'total_trades': re.compile(r'total_trades:\s*(\d+)', re.I),
    'win_rate': re.compile(r'win_rate:\s*(-?[\d.]+%)', re.I),
    'avg_win': re.compile(r'avg_win:\s*(-?[\d.]+)', re.I),
    'avg_loss': re.compile(r'avg_loss:\s*(-?[\d.]+)', re.I),
    'profit_factor': re.compile(r'profit_factor:\s*(-?[\d.]+)', re.I),
    'gross_pnl': re.compile(r'gross_pnl:\s*(-?[\d.]+)', re.I),
    'net_pnl': re.compile(r'net_pnl:\s*(-?[\d.]+)', re.I),
    'total_fee': re.compile(r'total_fee:\s*(-?[\d.]+)', re.I),
    'avg_holding_time': re.compile(r'avg_holding_time:\s*([^\n]+)', re.I),
    'long_pnl': re.compile(r'long_pnl:\s*(-?[\d.]+)', re.I),
    'short_pnl': re.compile(r'short_pnl:\s*(-?[\d.]+)', re.I),
}

BASE = {
    'mode': 'backtest',
    'symbol': 'BTC-USDT-SWAP',
    'exchange': 'LOCAL',
    'interval': '1h',
    'start': '2024-01-01',
    'end': '2025-01-01',
    'rate': 0.0005,
    'slippage': 5.0,
    'size': 0.01,
    'pricetick': 0.1,
    'capital': 100000,
    'strategy': 'BtcBosRetestLongStrategy',
    'strategy_setting': {
        'ma_window': 50,
        'adx_window': 14,
        'adx_threshold': 20,
        'swing_window': 20,
        'retest_tolerance_atr': 0.5,
        'stop_atr_multiplier': 1.5,
        'trailing_atr_multiplier': 2.0,
        'min_holding_bars': 24,
    }
}


def parse_output(text: str):
    item = {}
    for k, p in PATS.items():
        m = p.search(text)
        if m:
            item[k] = m.group(1)
    for key in ['sharpe', 'calmar', 'avg_win', 'avg_loss', 'profit_factor', 'gross_pnl', 'net_pnl', 'total_fee', 'long_pnl', 'short_pnl']:
        if key in item:
            item[key] = float(item[key])
    if 'total_trades' in item:
        item['total_trades'] = int(item['total_trades'])
    return item


def main():
    results = []
    keys = list(GRID.keys())
    for i, values in enumerate(itertools.product(*(GRID[k] for k in keys)), start=1):
        cfg = json.loads(json.dumps(BASE))
        params = dict(zip(keys, values))
        cfg['strategy_setting'].update(params)
        cfg_path = CFGDIR / f'_tmp_bos_scan_{i:03d}.json'
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')
        proc = subprocess.run(['python3', 'runner/run_backtest.py', '--config', str(cfg_path)], cwd=ROOT, capture_output=True, text=True)
        text = (proc.stdout or '') + '\n' + (proc.stderr or '')
        parsed = parse_output(text)
        parsed['params'] = params
        parsed['exit_code'] = proc.returncode
        results.append(parsed)

    ranked = sorted(
        [r for r in results if r.get('exit_code') == 0 or r.get('net_pnl') is not None],
        key=lambda x: (x.get('net_pnl', -1e18), x.get('profit_factor', -1e18), x.get('sharpe', -1e18)),
        reverse=True,
    )
    OUT.write_text(json.dumps(ranked[:20], indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(ranked[:10], ensure_ascii=False))


if __name__ == '__main__':
    main()
