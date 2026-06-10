/* ─────────────────────────────────────────────────────────────────────────
   app-screens.jsx — full-app screens (chosen variants B + B, made fluid)
   行情监控 = 终端密集 · 工具箱 = 集成诊断工作台
   Requires: components.jsx (window.*), toolbox bits re-declared minimally here
   Exports: MarketScreen, ToolboxScreen
   ───────────────────────────────────────────────────────────────────────── */
const { useState: _aS, useEffect: _aE, useRef: _aR, useMemo: _aM } = React;

/* measure container width for responsive SVG */
function useWidth() {
  const ref = _aR(null);
  const [w, setW] = _aS(0);
  _aE(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setW(el.clientWidth);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

function Panel({ title, right, children, style, bodyStyle }) {
  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0, ...style }}>
      {title && (
        <div className="panel-head">
          <span className="panel-title">{title}</span>
          {right}
        </div>
      )}
      <div style={{ padding: 14, flex: 1, minHeight: 0, overflow: 'auto', ...bodyStyle }}>{children}</div>
    </div>
  );
}

function useRotationRead() {
  const s = useMarket();
  return _aM(() => {
    const t = window.MarketData.themeAgg();
    const _empty = { theme: '—', flow: 0, chg: 0, n: 0 };
    const lead = t[0] || _empty, lag = t[t.length - 1] || _empty;
    const techFlow = t.filter((x) => ['AI算力', '科技'].includes(x.theme)).reduce((a, b) => a + b.flow, 0);
    const defFlow = t.filter((x) => ['红利', '金融'].includes(x.theme)).reduce((a, b) => a + b.flow, 0);
    const bias = techFlow > defFlow + 4 ? '科技成长' : defFlow > techFlow + 4 ? '避险红利' : '震荡混沌';
    return { lead, lag, bias };
  }, [s.updatedAt]);
}

/* ════════════════════════════════════════════════════════════════════════
   行情监控 — 终端密集 (fluid)
   ════════════════════════════════════════════════════════════════════════ */
function MarketScreen() {
  const read = useRotationRead();
  const [mapRef, mapW] = useWidth();
  const mh = Math.min(440, Math.max(260, (mapW || 420) * 0.74));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, height: '100%', minHeight: 0 }}>
      <IndexStrip compact />

      <div className="panel" style={{ padding: '8px 14px', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          <span className="panel-title">全球参考</span>
          <GlobalStrip />
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--ink-2)' }}>
            <span className="dot" />资金主线 <b style={{ color: 'var(--up)' }}>{read.lead.theme}</b>
            <span style={{ color: 'var(--line)' }}>·</span>偏好 <b style={{ color: 'var(--accent)' }}>{read.bias}</b>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(300px, 1fr) minmax(440px, 1.35fr) minmax(300px, 1fr)', gap: 14, flex: 1, minHeight: 0 }}>
        <Panel title="板块资金流向 · 净额排序" right={<span className="mono" style={{ fontSize: 10, color: 'var(--ink-4)' }}>今日(亿)</span>} bodyStyle={{ padding: '4px 14px' }}>
          <SectorFlowRanking limit={16} showSpark />
        </Panel>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, minHeight: 0 }}>
          <Panel title="板块轮动地图 · 涨跌 × 资金" right={<span className="mono" style={{ fontSize: 10, color: 'var(--ink-4)' }}>气泡=净流入</span>}
            bodyStyle={{ padding: 12, display: 'flex', justifyContent: 'center', alignItems: 'center', overflow: 'hidden' }} style={{ flex: '1 1 auto' }}>
            <div ref={mapRef} style={{ width: '100%', display: 'flex', justifyContent: 'center' }}>
              <RotationMap width={Math.min(mapW || 440, 640)} height={mh} />
            </div>
          </Panel>
          <Panel title="题材资金潮汐" bodyStyle={{ padding: 12 }} style={{ flexShrink: 0 }}><ThemeTape /></Panel>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, minHeight: 0 }}>
          <Panel title="市场宽度" bodyStyle={{ padding: 14 }} style={{ flexShrink: 0 }}><BreadthBar /></Panel>
          <Panel title="龙头监控" style={{ flex: 1, minHeight: 0 }} bodyStyle={{ padding: '4px 12px' }}><LeaderBoard dense spark /></Panel>
        </div>
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════════════
   工具箱 — 集成诊断工作台 (fluid)
   ════════════════════════════════════════════════════════════════════════ */
const _HEALTH_DIMS = [
  { key: 'price', label: '收盘价位置', opts: [['创20日新高', 3], ['仍在5日线上', 1], ['跌破10日线', 0]] },
  { key: 'volume', label: '成交量', opts: [['温和放大 20–50%', 2], ['缩量上涨', 1], ['爆量 >100% 且收阴', 0]] },
  { key: 'intraday', label: '分时表现', opts: [['大盘跌时横盘抗跌', 2], ['跟随大盘', 1], ['大盘稳却独自下跌', 0]] },
  { key: 'sector', label: '板块带动', opts: [['≥3只涨停或涨超7%', 3], ['板块内只有它涨', 1], ['板块跌多涨少', 0]] },
];
const _FS_RULES = [
  '高开低走：开盘涨幅 >3%，收盘不足 1%',
  '无板块跟随：仅 1 只个股涨，同板块其他不动',
  '资金净流出：板块涨幅为正，但资金显示净流出',
];
const _OBS_ROWS = [
  { key: 'ai', dir: 'AI算力', tgt: '中际旭创 300308', strong: '9:35前涨幅>3% 且全天不破开盘价', weak: '高开>5% 后回落到1%以下' },
  { key: 'semi', dir: '半导体设备', tgt: '北方华创 002371', strong: '低开后10分钟内翻红', weak: '高开>4% 后持续走低' },
  { key: 'robot', dir: '机器人', tgt: '鸣志电器 603728', strong: '断板股反包 涨幅>5%', weak: '龙头跌停或跌超7%' },
  { key: 'div', dir: '高股息避险', tgt: '长江电力 600900', strong: '大盘跌时逆势涨0.5%以上', weak: '大盘涨时跌超1%' },
];

function _Gauge({ score, max = 10, size = 128 }) {
  const r = size / 2 - 12, c = 2 * Math.PI * r, frac = score / max;
  const color = score >= 7 ? 'var(--up)' : score >= 4 ? 'var(--warn)' : 'var(--down)';
  const verdict = score >= 7 ? '健康' : score >= 4 ? '分歧' : '见顶信号';
  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--panel-3)" strokeWidth="9" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="9" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - frac)} style={{ transition: 'stroke-dashoffset .6s cubic-bezier(.4,0,.2,1), stroke .4s' }} />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2 }}>
        <span className="mono" style={{ fontSize: 29, fontWeight: 700, color }}>{score}<span style={{ fontSize: 13, color: 'var(--ink-4)' }}>/{max}</span></span>
        <span style={{ fontSize: 13, fontWeight: 700, color }}>{verdict}</span>
      </div>
    </div>
  );
}

function _Sel({ value, onChange, children }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} style={{
      background: 'var(--panel-2)', border: '1px solid var(--line)', color: 'var(--ink)',
      padding: '6px 8px', borderRadius: 'var(--r-sm)', fontSize: 12, fontFamily: 'var(--cjk)', width: '100%', cursor: 'pointer' }}>
      {children}
    </select>
  );
}

function HealthScorer() {
  const [v, setV] = _aS({ price: 3, volume: 2, intraday: 2, sector: 3 });
  const score = _HEALTH_DIMS.reduce((a, d) => a + Number(v[d.key]), 0);
  return (
    <div style={{ display: 'flex', gap: 18, alignItems: 'center', flexWrap: 'wrap' }}>
      <_Gauge score={score} />
      <div style={{ flex: 1, minWidth: 240, display: 'flex', flexDirection: 'column', gap: 9 }}>
        {_HEALTH_DIMS.map((d) => (
          <div key={d.key} style={{ display: 'grid', gridTemplateColumns: '74px 1fr', gap: 10, alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: 'var(--ink-2)' }}>{d.label}</span>
            <_Sel value={v[d.key]} onChange={(val) => setV({ ...v, [d.key]: val })}>
              {d.opts.map(([label, sc]) => <option key={sc} value={sc}>{label}（{sc}分）</option>)}
            </_Sel>
          </div>
        ))}
      </div>
    </div>
  );
}

function FalseStrength() {
  const [hit, setHit] = _aS([false, false, false]);
  const n = hit.filter(Boolean).length;
  const verdict = n === 0 ? '无假强信号' : n === 1 ? '轻微疑问 · 继续观察' : `假强板块 · 命中 ${n} 条`;
  const color = n === 0 ? 'var(--up)' : n === 1 ? 'var(--warn)' : 'var(--down)';
  return (
    <div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {_FS_RULES.map((r, i) => (
          <label key={i} onClick={() => setHit(hit.map((x, j) => (j === i ? !x : x)))}
            style={{ display: 'flex', gap: 11, alignItems: 'flex-start', padding: '10px', borderRadius: 'var(--r-sm)', cursor: 'pointer', background: hit[i] ? 'var(--down-bg)' : 'transparent', transition: 'background .15s' }}>
            <span style={{ width: 16, height: 16, borderRadius: 4, border: '1.5px solid ' + (hit[i] ? 'var(--down)' : 'var(--line)'), background: hit[i] ? 'var(--down)' : 'transparent', flexShrink: 0, marginTop: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 11 }}>{hit[i] ? '✓' : ''}</span>
            <span style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.45 }}>{r}</span>
          </label>
        ))}
      </div>
      <div style={{ marginTop: 12, padding: '11px 14px', borderRadius: 'var(--r-md)', background: 'var(--panel-2)', borderLeft: '3px solid ' + color, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 11, color: 'var(--ink-3)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>结论</span>
        <span style={{ fontSize: 15, fontWeight: 700, color }}>{verdict}</span>
      </div>
    </div>
  );
}

const _OBS_STATES = { '': { label: '未观察', color: 'var(--ink-4)', bg: 'transparent' }, strong: { label: '强', color: 'var(--up)', bg: 'var(--up-bg)' }, weak: { label: '弱', color: 'var(--down)', bg: 'var(--down-bg)' }, neutral: { label: '中性', color: 'var(--ink-2)', bg: 'var(--panel-2)' } };
function ObservationTable() {
  const [obs, setObs] = _aS({});
  const cycle = (k) => { const order = ['', 'strong', 'weak', 'neutral']; const cur = obs[k] || ''; setObs({ ...obs, [k]: order[(order.indexOf(cur) + 1) % order.length] }); };
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
      <thead>
        <tr style={{ color: 'var(--ink-3)', fontSize: 10.5, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600 }}>方向 / 标的</th>
          <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600, color: 'var(--up-dim)' }}>强信号</th>
          <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600, color: 'var(--down-dim)' }}>弱信号</th>
          <th style={{ textAlign: 'center', padding: '6px 8px', fontWeight: 600, width: 78 }}>今日</th>
        </tr>
      </thead>
      <tbody>
        {_OBS_ROWS.map((r) => {
          const st = _OBS_STATES[obs[r.key] || ''];
          return (
            <tr key={r.key} style={{ borderTop: '1px solid var(--line-soft)' }}>
              <td style={{ padding: '9px 8px', verticalAlign: 'top' }}>
                <div style={{ fontWeight: 600 }}>{r.dir}</div>
                <div className="mono" style={{ fontSize: 10.5, color: 'var(--ink-4)', marginTop: 2 }}>{r.tgt}</div>
              </td>
              <td style={{ padding: '9px 8px', color: 'var(--ink-3)', fontSize: 11.5, lineHeight: 1.5, verticalAlign: 'top' }}>{r.strong}</td>
              <td style={{ padding: '9px 8px', color: 'var(--ink-3)', fontSize: 11.5, lineHeight: 1.5, verticalAlign: 'top' }}>{r.weak}</td>
              <td style={{ padding: '9px 8px', textAlign: 'center', verticalAlign: 'top' }}>
                <button onClick={() => cycle(r.key)} style={{ background: st.bg, border: '1px solid ' + (obs[r.key] ? st.color : 'var(--line)'), color: st.color, borderRadius: 999, padding: '4px 14px', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'var(--cjk)', minWidth: 60, whiteSpace: 'nowrap', transition: 'all .15s' }}>{st.label}</button>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function ToolboxScreen() {
  const s = useMarket();
  const [sel, setSel] = _aS(s.leaders[0].code);
  const leader = s.leaders.find((l) => l.code === sel) || s.leaders[0];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {s.leaders.map((l) => (
          <button key={l.code} onClick={() => setSel(l.code)} style={{
            display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'flex-start', padding: '7px 12px', cursor: 'pointer',
            background: l.code === sel ? 'var(--accent-bg)' : 'var(--panel)', border: '1px solid ' + (l.code === sel ? 'var(--accent)' : 'var(--line-soft)'),
            borderRadius: 'var(--r-md)', fontFamily: 'var(--cjk)', minWidth: 88 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)' }}>{l.name}</span>
            <Pct v={l.changePct} size={11} />
          </button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(420px, 1.1fr) minmax(320px, 1fr)', gap: 14 }}>
        <Panel title={`龙头健康度 · ${leader.name}`} right={<span className="mono" style={{ fontSize: 12, color: cssVar(leader.changePct), whiteSpace: 'nowrap' }}>{leader.price.toFixed(2)} {fmtPct(leader.changePct)}</span>} bodyStyle={{ overflow: 'visible' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14, padding: '10px 12px', background: 'var(--panel-2)', borderRadius: 'var(--r-md)' }}>
            <Spark data={leader.spark} w={120} h={34} fill />
            <div style={{ fontSize: 11.5, color: 'var(--ink-3)', lineHeight: 1.5 }}>
              所属板块 <b style={{ color: 'var(--ink-2)' }}>{leader.sector}</b><br />量比 <b className="mono" style={{ color: leader.volRatio > 1.5 ? 'var(--warn)' : 'var(--ink-2)' }}>{leader.volRatio.toFixed(2)}</b>
            </div>
          </div>
          <HealthScorer />
        </Panel>
        <Panel title="假强板块快速判断" bodyStyle={{ overflow: 'visible' }}><FalseStrength /></Panel>
      </div>

      <Panel title="今日观察对照表" right={<span style={{ fontSize: 11, color: 'var(--ink-4)' }}>点击「今日」切换 强/弱/中性</span>} bodyStyle={{ padding: '4px 14px 12px', overflow: 'visible' }}>
        <ObservationTable />
      </Panel>
    </div>
  );
}

Object.assign(window, { MarketScreen, ToolboxScreen });
