/* ─────────────────────────────────────────────────────────────────────────
   components.jsx — shared terminal UI atoms + viz, exported to window
   Requires: React, lib/data.js (window.MarketData)
   ───────────────────────────────────────────────────────────────────────── */
const { useState, useEffect, useRef, useMemo } = React;
const MD = () => window.MarketData;

/* live subscription hook — re-renders on every tick */
function useMarket() {
  const [, force] = useState(0);
  useEffect(() => MD().subscribe(() => force((n) => n + 1)), []);
  return MD().state;
}

const fmtPct = (v) => (v > 0 ? '+' : '') + v.toFixed(2) + '%';
const fmtFlow = (v) => (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(1);
const cls = (v) => (v > 0.001 ? 'up' : v < -0.001 ? 'down' : 'flat');
const cssVar = (v) => (v > 0.001 ? 'var(--up)' : v < -0.001 ? 'var(--down)' : 'var(--flat)');

/* ── Pct: colored percentage ──────────────────────────────────────────────── */
function Pct({ v, size = 13, arrow = false, weight = 600 }) {
  return (
    <span className={'mono ' + cls(v)} style={{ fontSize: size, fontWeight: weight, whiteSpace: 'nowrap' }}>
      {arrow ? (v > 0 ? '▲ ' : v < 0 ? '▼ ' : '· ') : ''}{fmtPct(v)}
    </span>
  );
}

/* ── Sparkline ────────────────────────────────────────────────────────────── */
function Spark({ data, w = 64, h = 22, color, strokeW = 1.5, fill = false }) {
  if (!data || data.length < 2) return <svg width={w} height={h} />;
  const min = Math.min(...data), max = Math.max(...data), span = max - min || 1;
  const x = (i) => (i / (data.length - 1)) * w;
  const y = (d) => h - ((d - min) / span) * (h - 3) - 1.5;
  const pts = data.map((d, i) => `${x(i).toFixed(1)},${y(d).toFixed(1)}`).join(' ');
  const c = color || cssVar(data[data.length - 1]);
  const zeroY = min < 0 && max > 0 ? y(0) : null;
  return (
    <svg width={w} height={h} style={{ display: 'block', overflow: 'visible' }}>
      {zeroY != null && <line x1="0" y1={zeroY} x2={w} y2={zeroY} stroke="var(--line)" strokeWidth="1" strokeDasharray="2 2" />}
      {fill && <polygon points={`0,${h} ${pts} ${w},${h}`} fill={c} opacity="0.12" />}
      <polyline points={pts} fill="none" stroke={c} strokeWidth={strokeW} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/* ── Diverging bar (net flow) ─────────────────────────────────────────────── */
function FlowBar({ v, max, h = 8 }) {
  const pct = Math.min(100, (Math.abs(v) / max) * 100);
  const pos = v >= 0;
  return (
    <div style={{ display: 'flex', alignItems: 'center', height: h, width: '100%' }}>
      <div style={{ flex: 1, display: 'flex', justifyContent: 'flex-end', height: '100%' }}>
        {!pos && <div style={{ width: pct + '%', height: '100%', background: 'var(--down)', borderRadius: '3px 0 0 3px', opacity: 0.85, transition: 'width .7s cubic-bezier(.4,0,.2,1)' }} />}
      </div>
      <div style={{ width: 1, height: h + 4, background: 'var(--line)' }} />
      <div style={{ flex: 1, height: '100%' }}>
        {pos && <div style={{ width: pct + '%', height: '100%', background: 'var(--up)', borderRadius: '0 3px 3px 0', opacity: 0.85, transition: 'width .7s cubic-bezier(.4,0,.2,1)' }} />}
      </div>
    </div>
  );
}

/* ── Index ticker strip ───────────────────────────────────────────────────── */
function IndexStrip({ compact = false }) {
  const s = useMarket();
  return (
    <div style={{ display: 'flex', gap: compact ? 0 : 1, background: 'var(--line-soft)', borderRadius: 'var(--r-md)', overflow: 'hidden' }}>
      {s.indices.map((idx) => (
        <div key={idx.code} style={{ flex: 1, background: 'var(--panel)', padding: compact ? '8px 12px' : '11px 14px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          <div style={{ fontSize: 11, color: 'var(--ink-3)', letterSpacing: '0.04em' }}>{idx.label}</div>
          <div className="mono" style={{ fontSize: compact ? 16 : 19, fontWeight: 700, color: cssVar(idx.changePct), lineHeight: 1.1 }}>
            {idx.price.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </div>
          <Pct v={idx.changePct} size={12} arrow />
        </div>
      ))}
    </div>
  );
}

/* ── Breadth bar (涨跌家数 + 涨跌停) ───────────────────────────────────────── */
function BreadthBar() {
  const s = useMarket();
  const { up, down, flat, limitUp, limitDown } = s.breadth;
  const tot = up + down + flat;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', height: 10, borderRadius: 5, overflow: 'hidden', background: 'var(--panel-2)' }}>
        <div style={{ width: (up / tot) * 100 + '%', background: 'var(--up)', transition: 'width .7s' }} />
        <div style={{ width: (flat / tot) * 100 + '%', background: 'var(--flat)', opacity: 0.5 }} />
        <div style={{ width: (down / tot) * 100 + '%', background: 'var(--down)', transition: 'width .7s' }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }} className="mono">
        <span className="up">↑ {up} 家</span>
        <span style={{ color: 'var(--ink-3)' }}>平 {flat}</span>
        <span className="down">↓ {down} 家</span>
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <div style={{ flex: 1, textAlign: 'center', padding: '6px 0', background: 'var(--up-bg)', borderRadius: 'var(--r-sm)' }}>
          <div className="mono up" style={{ fontSize: 17, fontWeight: 700 }}>{limitUp}</div>
          <div style={{ fontSize: 10, color: 'var(--ink-3)' }}>涨停</div>
        </div>
        <div style={{ flex: 1, textAlign: 'center', padding: '6px 0', background: 'var(--down-bg)', borderRadius: 'var(--r-sm)' }}>
          <div className="mono down" style={{ fontSize: 17, fontWeight: 700 }}>{limitDown}</div>
          <div style={{ fontSize: 10, color: 'var(--ink-3)' }}>跌停</div>
        </div>
      </div>
    </div>
  );
}

/* ── Sector rotation map: scatter quadrant (THE centerpiece) ───────────────── */
function RotationMap({ width = 460, height = 360, labeled = true }) {
  const s = useMarket();
  const pad = 38;
  const xMin = -6, xMax = 8, yMin = -40, yMax = 60;
  const px = (chg) => pad + ((chg - xMin) / (xMax - xMin)) * (width - pad * 2);
  const py = (flow) => height - pad - ((flow - yMin) / (yMax - yMin)) * (height - pad * 2);
  const x0 = px(0), y0 = py(0);
  const rOf = (flow) => 5 + Math.min(22, Math.sqrt(Math.abs(flow)) * 3);

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      {/* quadrant tints */}
      <rect x={x0} y={pad} width={width - pad - x0} height={y0 - pad} fill="var(--up)" opacity="0.05" />
      <rect x={x0} y={y0} width={width - pad - x0} height={height - pad - y0} fill="var(--warn)" opacity="0.04" />
      <rect x={pad} y={pad} width={x0 - pad} height={y0 - pad} fill="var(--accent)" opacity="0.04" />
      <rect x={pad} y={y0} width={x0 - pad} height={height - pad - y0} fill="var(--down)" opacity="0.05" />
      {/* axes */}
      <line x1={pad} y1={y0} x2={width - pad} y2={y0} stroke="var(--line)" strokeWidth="1" />
      <line x1={x0} y1={pad} x2={x0} y2={height - pad} stroke="var(--line)" strokeWidth="1" />
      {/* axis labels */}
      <text x={width - pad} y={y0 - 6} textAnchor="end" fontSize="9.5" fill="var(--ink-4)" fontFamily="var(--mono)">涨跌幅 →</text>
      <text x={x0 + 6} y={pad + 4} fontSize="9.5" fill="var(--ink-4)" fontFamily="var(--mono)">↑ 净流入</text>
      {labeled && (<>
        <text x={width - pad - 4} y={pad + 14} textAnchor="end" fontSize="10.5" fill="var(--up)" fontWeight="700" opacity="0.8">强势吸金</text>
        <text x={pad + 4} y={pad + 14} fontSize="10.5" fill="var(--accent)" fontWeight="700" opacity="0.8">超跌承接</text>
        <text x={width - pad - 4} y={height - pad - 6} textAnchor="end" fontSize="10.5" fill="var(--warn)" fontWeight="700" opacity="0.75">滞涨派发</text>
        <text x={pad + 4} y={height - pad - 6} fontSize="10.5" fill="var(--down)" fontWeight="700" opacity="0.8">弱势出逃</text>
      </>)}
      {/* bubbles */}
      {s.sectors.map((sec) => {
        const cx = px(sec.changePct), cy = py(sec.netInflow), r = rOf(sec.netInflow);
        const c = cssVar(sec.changePct);
        const big = Math.abs(sec.netInflow) > 18 || Math.abs(sec.changePct) > 3;
        return (
          <g key={sec.id} style={{ transition: 'transform .9s cubic-bezier(.4,0,.2,1)', transform: `translate(${cx}px,${cy}px)` }}>
            <circle r={r} fill={c} opacity="0.16" />
            <circle r={r} fill="none" stroke={c} strokeWidth="1.4" opacity="0.9" />
            <circle r="2" fill={c} />
            {big && <text y={-r - 4} textAnchor="middle" fontSize="10.5" fill="var(--ink)" fontWeight="600">{sec.name}</text>}
          </g>
        );
      })}
    </svg>
  );
}

/* ── Sector flow ranking (diverging bars) ─────────────────────────────────── */
function SectorFlowRanking({ limit = 12, showSpark = false }) {
  const s = useMarket();
  const sorted = useMemo(() => [...s.sectors].sort((a, b) => b.netInflow - a.netInflow), [s.updatedAt]);
  const top = [...sorted.slice(0, Math.ceil(limit / 2)), ...sorted.slice(-Math.floor(limit / 2))];
  const max = Math.max(...s.sectors.map((x) => Math.abs(x.netInflow)), 1);
  return (
    <div>
      {top.map((sec, i) => (
        <div key={sec.id} style={{ display: 'grid', gridTemplateColumns: showSpark ? '78px 1fr 56px 60px' : '88px 1fr 64px', alignItems: 'center', gap: 10, padding: '7px 0', borderBottom: i < top.length - 1 ? '1px solid var(--line-soft)' : 'none' }}>
          <div style={{ fontSize: 12.5, color: 'var(--ink)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{sec.name}</div>
          <FlowBar v={sec.netInflow} max={max} />
          {showSpark && <Spark data={sec.flowHist} w={50} h={16} />}
          <div className="mono" style={{ textAlign: 'right', fontSize: 12.5, fontWeight: 600, color: cssVar(sec.netInflow) }}>{fmtFlow(sec.netInflow)}<span style={{ fontSize: 10, color: 'var(--ink-4)' }}>亿</span></div>
        </div>
      ))}
    </div>
  );
}

/* ── Theme rotation tape (aggregated by theme) ────────────────────────────── */
function ThemeTape() {
  const s = useMarket();
  const themes = useMemo(() => MD().themeAgg(), [s.updatedAt]);
  const max = Math.max(...themes.map((t) => Math.abs(t.flow)), 1);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
      {themes.map((t) => (
        <div key={t.theme} style={{ display: 'grid', gridTemplateColumns: '64px 1fr 62px', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 12, color: 'var(--ink-2)' }}>{t.theme}</span>
          <div style={{ height: 18, background: 'var(--panel-2)', borderRadius: 4, overflow: 'hidden', position: 'relative' }}>
            <div style={{ position: 'absolute', inset: 0, width: (Math.abs(t.flow) / max) * 100 + '%', background: cssVar(t.flow), opacity: 0.28, transition: 'width .7s' }} />
            <div style={{ position: 'absolute', left: 8, top: 0, bottom: 0, display: 'flex', alignItems: 'center', fontSize: 11 }} className={'mono ' + cls(t.chg)}>{fmtPct(t.chg)}</div>
          </div>
          <span className="mono" style={{ fontSize: 12, fontWeight: 600, textAlign: 'right', color: cssVar(t.flow) }}>{fmtFlow(t.flow)}亿</span>
        </div>
      ))}
    </div>
  );
}

/* ── Leader board ─────────────────────────────────────────────────────────── */
function LeaderBoard({ dense = false, spark = true }) {
  const s = useMarket();
  const rows = useMemo(() => [...s.leaders].sort((a, b) => b.changePct - a.changePct), [s.updatedAt]);
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: dense ? 12 : 13 }}>
      <thead>
        <tr style={{ color: 'var(--ink-3)', fontSize: 10.5, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          <th style={{ textAlign: 'left', padding: '4px 6px', fontWeight: 600 }}>龙头</th>
          <th style={{ textAlign: 'right', padding: '4px 6px', fontWeight: 600 }}>现价</th>
          {spark && <th style={{ width: 60 }}></th>}
          <th style={{ textAlign: 'right', padding: '4px 6px', fontWeight: 600 }}>涨跌</th>
          <th style={{ textAlign: 'right', padding: '4px 6px', fontWeight: 600 }}>量比</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((l) => (
          <tr key={l.code} style={{ borderTop: '1px solid var(--line-soft)' }}>
            <td style={{ padding: dense ? '5px 6px' : '8px 6px' }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 7 }}>
                <span style={{ fontWeight: 600 }}>{l.name}</span>
                <span className="mono" style={{ fontSize: 10.5, color: 'var(--ink-4)' }}>{l.code}</span>
              </div>
              {!dense && <div style={{ fontSize: 10.5, color: 'var(--ink-3)' }}>{l.sector}</div>}
            </td>
            <td className="mono" style={{ textAlign: 'right', padding: '5px 6px', color: cssVar(l.changePct) }}>{l.price.toFixed(2)}</td>
            {spark && <td style={{ padding: '5px 4px' }}><Spark data={l.spark} w={52} h={16} /></td>}
            <td style={{ textAlign: 'right', padding: '5px 6px' }}><Pct v={l.changePct} size={12.5} /></td>
            <td className="mono" style={{ textAlign: 'right', padding: '5px 6px', fontSize: 12, color: l.volRatio > 1.5 ? 'var(--warn)' : 'var(--ink-2)' }}>{l.volRatio.toFixed(2)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ── Global reference strip ───────────────────────────────────────────────── */
function GlobalStrip() {
  const s = useMarket();
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      {s.globals.map((g) => (
        <div key={g.code} style={{ display: 'flex', flexDirection: 'column', gap: 1, padding: '6px 11px', background: 'var(--panel-2)', borderRadius: 'var(--r-sm)', minWidth: 84 }}>
          <span style={{ fontSize: 10.5, color: 'var(--ink-3)' }}>{g.label}</span>
          {g.isLevel
            ? <span className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{g.changePct.toFixed(2)}<span style={{ fontSize: 9, color: 'var(--ink-4)' }}>%</span></span>
            : <Pct v={g.changePct} size={13} />}
        </div>
      ))}
    </div>
  );
}

/* ── live status chip ─────────────────────────────────────────────────────── */
function LiveChip() {
  const s = useMarket();
  const live = s.source === 'live';
  return (
    <span className={'chip ' + (live ? 'live' : 'mock')}>
      <span className={'dot' + (live ? '' : ' warn')} style={{ width: 6, height: 6 }} />
      {live ? '实时行情' : '模拟数据'}
    </span>
  );
}

function Clock() {
  const [t, setT] = useState('');
  useEffect(() => { const f = () => setT(new Date().toLocaleTimeString('zh-CN', { hour12: false })); f(); const i = setInterval(f, 1000); return () => clearInterval(i); }, []);
  return <span className="mono" style={{ fontSize: 12, color: 'var(--ink-2)' }}>{t}</span>;
}

Object.assign(window, {
  useMarket, Pct, Spark, FlowBar, IndexStrip, BreadthBar, RotationMap,
  SectorFlowRanking, ThemeTape, LeaderBoard, GlobalStrip, LiveChip, Clock,
  fmtPct, fmtFlow, cls, cssVar,
});
