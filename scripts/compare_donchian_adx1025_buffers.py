import itertools
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / 'configs'
OUT = ROOT / 'logs' / 'donchian_adx1025_buffers_compare.json'

buffers = [0.0, 0.1, 0.2]
years = [
    ('2023', '2023-01-01', '2024-01-01'),
    ('2024', '2024-01-01', '2025-01-01'),
]
patterns = {
    'end_balance': re.compile(r'End Balance:\s*([\d,]+\.\d+)'),
    'total_return': re.compile(r'Total Return:\s*(-?[\d.]+)%'),
    'max_ddpercent': re.compile(r'Max Ddpercent:\s*(-?[\d.]+)%'),
    'sharpe_ratio': re.compile(r'Sharpe Ratio[:：]\s*(-?[\d.]+)'),
    'trade_count': re.compile(r'Total Trade Count:\s*(\d+)'),
}
results = []
for buffer in buffers:
    for label, start, end in years:
        name = f'cmp_donchian_adx1025_buffer_{str(buffer).replace('.', '_')}_{label}'
        cfg = {
            'mode': 'backtest', 'symbol': 'BTC-USDT-SWAP', 'exchange': 'LOCAL', 'interval': '1h',
            'start': start, 'end': end, 'rate': 0.0005, 'slippage': 5.0, 'size': 0.01, 'pricetick': 0.1,
            'capital': 100000, 'strategy': 'BtcDonchianBreakoutStrategy',
            'strategy_setting': {
                'breakout_window': 50, 'exit_window': 20, 'atr_window': 14, 'atr_multiplier': 1.5,
                'adx_window': 10, 'adx_threshold': 25, 'breakout_atr_buffer': buffer,
                'stop_loss_pct': 0.015, 'next_bar_entry': True, 'base_slippage': 5.0,
                'atr_slippage_multiplier': 0.05
            }
        }
        cfg_path = CONFIG_DIR / f'{name}.json'
        cfg_path.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
        proc = subprocess.run(['python3', 'runner/run_backtest.py', '--config', str(cfg_path)], cwd=ROOT, capture_output=True, text=True)
        text = (proc.stdout or '') + '\n' + (proc.stderr or '')
        row = {'buffer': buffer, 'year': label, 'exit_code': proc.returncode}
        for k, p in patterns.items():
            m = p.search(text)
            if m:
                v = m.group(1).replace(',', '')
                row[k] = int(v) if k == 'trade_count' else float(v)
        results.append(row)
        print(row)
OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
print(f'saved to {OUT}')
