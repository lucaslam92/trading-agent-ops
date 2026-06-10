import { useEffect, useState } from 'react';
import { MarketData } from './lib/data.js';
import { Clock, LiveChip } from './components/components.jsx';
import {
  TweakRadio,
  TweakSection,
  TweakSlider,
  TweaksPanel,
  useTweaks,
} from './components/tweaks-panel.jsx';
import { MarketScreen, ToolboxScreen } from './screens/app-screens.jsx';
import {
  ChecklistScreen,
  HeaderCountdown,
  JournalScreen,
} from './screens/review-screens.jsx';

const TWEAK_DEFAULTS = {
  colorConv: '红涨绿跌',
  accent: '青蓝',
  tick: 2.2,
};

const ACCENTS = {
  青蓝: { '--accent': 'oklch(0.74 0.115 232)', '--accent-bg': 'oklch(0.32 0.05 232)' },
  琥珀: { '--accent': 'oklch(0.80 0.135 78)', '--accent-bg': 'oklch(0.33 0.06 78)' },
  靛紫: { '--accent': 'oklch(0.72 0.13 295)', '--accent-bg': 'oklch(0.32 0.06 295)' },
  青绿: { '--accent': 'oklch(0.76 0.11 178)', '--accent-bg': 'oklch(0.31 0.05 178)' },
};

const GREEN = {
  up: 'oklch(0.76 0.16 150)',
  upDim: 'oklch(0.50 0.10 150)',
  upBg: 'oklch(0.30 0.06 150)',
  down: 'oklch(0.68 0.205 22)',
  downDim: 'oklch(0.46 0.13 22)',
  downBg: 'oklch(0.30 0.085 22)',
};

function colorVars(conv) {
  const a = GREEN;
  const upSet = {
    '--up': a.up,
    '--up-dim': a.upDim,
    '--up-bg': a.upBg,
    '--down': a.down,
    '--down-dim': a.downDim,
    '--down-bg': a.downBg,
  };
  if (conv === '绿涨红跌') return upSet;
  return {
    '--up': a.down,
    '--up-dim': a.downDim,
    '--up-bg': a.downBg,
    '--down': a.up,
    '--down-dim': a.upDim,
    '--down-bg': a.upBg,
  };
}

export default function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [tab, setTab] = useState(() => localStorage.getItem('mm_tab') || 'market');

  useEffect(() => {
    localStorage.setItem('mm_tab', tab);
  }, [tab]);

  useEffect(() => {
    const es = MarketData.connect();
    return () => es.close();
  }, []);

  const overrides = { ...colorVars(t.colorConv), ...(ACCENTS[t.accent] || ACCENTS['青蓝']) };

  return (
    <div className="term" style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg)', ...overrides }}>
      <header style={{ display: 'flex', alignItems: 'center', gap: 20, padding: '0 18px', height: 56, borderBottom: '1px solid var(--line-soft)', flexShrink: 0, background: 'var(--panel)' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 9 }}>
          <span style={{ fontSize: 16, fontWeight: 700, letterSpacing: '0.04em' }}>市场监控终端</span>
          <span className="mono" style={{ fontSize: 10.5, color: 'var(--ink-4)' }}>MARKET&nbsp;DESK</span>
        </div>
        <nav style={{ display: 'flex', gap: 4 }}>
          <button className={'navtab' + (tab === 'market' ? ' on' : '')} onClick={() => setTab('market')}>行情监控</button>
          <button className={'navtab' + (tab === 'tools' ? ' on' : '')} onClick={() => setTab('tools')}>工具箱</button>
          <button className={'navtab' + (tab === 'checklist' ? ' on' : '')} onClick={() => setTab('checklist')}>今日清单</button>
          <button className={'navtab' + (tab === 'journal' ? ' on' : '')} onClick={() => setTab('journal')}>每日日记</button>
        </nav>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 14 }}>
          <HeaderCountdown />
          <Clock />
          <LiveChip />
        </div>
      </header>

      <main style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: 16, display: 'flex', flexDirection: 'column' }}>
        {tab === 'market' && <MarketScreen />}
        {tab === 'tools' && <ToolboxScreen />}
        {tab === 'checklist' && <ChecklistScreen />}
        {tab === 'journal' && <JournalScreen />}
      </main>

      <TweaksPanel title="Tweaks">
        <TweakSection label="配色" />
        <TweakRadio label="涨跌配色" value={t.colorConv} options={['绿涨红跌', '红涨绿跌']} onChange={(v) => setTweak('colorConv', v)} />
        <TweakRadio label="强调色" value={t.accent} options={['青蓝', '琥珀', '靛紫', '青绿']} onChange={(v) => setTweak('accent', v)} />
        <TweakSection label="行情" />
        <TweakSlider label="刷新频率" value={t.tick} min={1} max={6} step={0.2} unit="s" onChange={(v) => setTweak('tick', v)} />
      </TweaksPanel>
    </div>
  );
}
