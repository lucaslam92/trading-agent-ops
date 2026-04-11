import json, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / 'configs'
OUT = ROOT / 'logs' / 'donchian_regime_filter_compare_3years.json'
years = [('2022','2022-01-01','2023-01-01'),('2023','2023-01-01','2024-01-01'),('2024','2024-01-01','2025-01-01')]
patterns={
 'end_balance': re.compile(r'End Balance:\s*([\d,]+\.\d+)'),
 'total_return': re.compile(r'Total Return:\s*(-?[\d.]+)%'),
 'max_ddpercent': re.compile(r'Max Ddpercent:\s*(-?[\d.]+)%'),
 'sharpe_ratio': re.compile(r'Sharpe Ratio[:：]\s*(-?[\d.]+)'),
 'trade_count': re.compile(r'Total Trade Count:\s*(\d+)'),
}
results=[]
for label,start,end in years:
    cfg={
      'mode':'backtest','symbol':'BTC-USDT-SWAP','exchange':'LOCAL','interval':'1h',
      'start':start,'end':end,'rate':0.0005,'slippage':5.0,'size':0.01,'pricetick':0.1,'capital':100000,
      'strategy':'BtcDonchianBreakoutStrategy',
      'strategy_setting':{
        'breakout_window':50,'exit_window':20,'atr_window':14,'atr_multiplier':1.5,
        'adx_window':10,'adx_threshold':25,'breakout_atr_buffer':0.1,
        'min_channel_width_ratio':0.01,'min_atr_ratio':0.002,'max_atr_ratio':0.05,
        'stop_loss_pct':0.015,'next_bar_entry':True,'base_slippage':5.0,'atr_slippage_multiplier':0.05
      }
    }
    path=CONFIG_DIR/f'regime_donchian_{label}.json'
    path.write_text(json.dumps(cfg,indent=2),encoding='utf-8')
    proc=subprocess.run(['python3','runner/run_backtest.py','--config',str(path)],cwd=ROOT,capture_output=True,text=True)
    text=(proc.stdout or '')+'\n'+(proc.stderr or '')
    row={'year':label,'exit_code':proc.returncode}
    for k,p in patterns.items():
        m=p.search(text)
        if m:
            v=m.group(1).replace(',','')
            row[k]=int(v) if k=='trade_count' else float(v)
    results.append(row)
    print(row)
OUT.write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
print(f'saved to {OUT}')
