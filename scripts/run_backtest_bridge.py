import argparse
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path('/root/.openclaw/workspace')

FIELDS = [
    'total_return', 'annual_return', 'max_drawdown', 'sharpe', 'calmar',
    'total_trades', 'win_rate', 'avg_win', 'avg_loss', 'profit_factor',
    'gross_pnl', 'net_pnl', 'total_fee', 'avg_holding_time', 'long_pnl', 'short_pnl'
]


def parse_metrics(text: str) -> dict:
    metrics = {}
    for line in text.splitlines():
        if 'run_backtest:' not in line:
            continue
        for field in FIELDS:
            token = f'{field}:'
            if token in line:
                value = line.split(token, 1)[1].strip()
                metrics[field] = value
    return metrics


def main():
    parser = argparse.ArgumentParser(description='Bridge script for Kotlin Strategy Evolution Engine')
    parser.add_argument('--config-json', help='raw json config payload')
    parser.add_argument('--config-path', help='existing config path')
    args = parser.parse_args()

    if not args.config_json and not args.config_path:
        raise SystemExit('either --config-json or --config-path is required')

    temp_path = None
    config_path = args.config_path
    if args.config_json:
        payload = json.loads(args.config_json)
        fd, tmp = tempfile.mkstemp(suffix='.json', prefix='bridge_backtest_', dir=str(ROOT / 'configs'))
        Path(tmp).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        temp_path = Path(tmp)
        config_path = str(temp_path)

    proc = subprocess.run(
        ['python3', 'runner/run_backtest.py', '--config', config_path],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    text = (proc.stdout or '') + '\n' + (proc.stderr or '')
    metrics = parse_metrics(text)

    result = {
        'exit_code': proc.returncode,
        'metrics': metrics,
        'stdout': proc.stdout,
        'stderr': proc.stderr,
    }
    print(json.dumps(result, ensure_ascii=False))

    if temp_path and temp_path.exists():
        temp_path.unlink()


if __name__ == '__main__':
    main()
