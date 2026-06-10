/* ─────────────────────────────────────────────────────────────────────────
   review-screens.jsx — 今日清单 / 提醒计时 / 每日日记
   ───────────────────────────────────────────────────────────────────────── */
import { useEffect as _rE, useState as _rS } from 'react';
import { MarketData } from '../lib/data.js';
import { MarketStore } from '../lib/store.js';
import { fmtFlow } from '../lib/market-utils.js';
import { useMarket } from '../components/components.jsx';

/* ── alarm schedule ──────────────────────────────────────────────────────── */
const ALARMS = [
  { hm: '09:25', label: '集合竞价结束 · 看高开低开' },
  { hm: '09:30', label: '开盘 · 5分钟快速扫描' },
  { hm: '10:30', label: '第一关键点 · 主线是否持续' },
  { hm: '13:15', label: '午后关键点 · 强势是否回落' },
  { hm: '14:30', label: '尾盘关键点 · 放量/缩量 · 龙头抗跌' },
  { hm: '15:00', label: '收盘 · 开始复盘填日记' },
];

function useAlarmClock() {
  const [now, setNow] = _rS(() => new Date());
  _rE(() => { const i = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(i); }, []);
  const hhmm = now.toTimeString().slice(0, 5);
  const next = ALARMS.find((a) => a.hm > hhmm) || ALARMS[0];
  const [h, m] = next.hm.split(':').map(Number);
  const nd = new Date(now); nd.setHours(h, m, 0, 0);
  if (nd <= now) nd.setDate(nd.getDate() + 1);
  const diff = Math.max(0, Math.floor((nd - now) / 1000));
  const HH = String(Math.floor(diff / 3600)).padStart(2, '0');
  const MM = String(Math.floor((diff % 3600) / 60)).padStart(2, '0');
  const SS = String(diff % 60).padStart(2, '0');
  const text = diff >= 3600 ? `${HH}:${MM}:${SS}` : `${MM}:${SS}`;
  return { now, hhmm, next, text, diff };
}

/* ── header countdown chip (always visible) ──────────────────────────────── */
export function HeaderCountdown() {
  const { next, text, diff } = useAlarmClock();
  const soon = diff < 300;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 11px', borderRadius: 999, border: '1px solid ' + (soon ? 'var(--warn)' : 'var(--line)'), background: soon ? 'var(--warn-bg)' : 'transparent' }}>
      <span className={'dot' + (soon ? ' warn' : '')} style={{ width: 6, height: 6, background: soon ? 'var(--warn)' : 'var(--accent)' }} />
      <span style={{ fontSize: 11, color: 'var(--ink-3)' }}>下一提醒 {next.hm}</span>
      <span className="mono" style={{ fontSize: 12.5, fontWeight: 700, color: soon ? 'var(--warn)' : 'var(--ink)' }}>{text}</span>
    </div>
  );
}

/* ── checklist definition ────────────────────────────────────────────────── */
const CHECKLIST_DEF = {
  pre: { title: '盘前准备 · 30分钟', items: [
    { id: 'p1', label: '全球行情记录（纳指 / 恒科 / A50 / 美债 / 黄金 / 原油 / NVDA）', hint: '如：纳指+0.5 恒科+0.8 A50+0.2 美债4.30 一句话：科技偏强' },
    { id: 'p2', label: '风险偏好基准（进攻ETF vs 防守ETF 集合竞价对比）', hint: '如：进攻+0.6 防守+0.1 → 偏科技' },
    { id: 'p3', label: '关键词新闻扫描（≤3条，过滤噪音与个股大V）', hint: '如：工信部算力政策 / 英伟达新驱动 / 无其他' },
    { id: 'p4', label: '建立今日观察表（4个方向填好强弱信号）', hint: '如：AI / 半导体 / 机器人 / 红利 已填' },
  ] },
  mid: { title: '盘中观察', items: [
    { id: 'm1', label: '9:30 开盘5分钟扫描（涨幅榜 + 昨日龙头 + 涨跌家数）', hint: '如：前三=光模块/通信/算力 龙头高开+3 涨家3200' },
    { id: 'm2', label: '10:30 第一关键点（主线是否持续 + 大盘分时位置）', hint: '如：主线仍是AI 大盘在白线上方' },
    { id: 'm3', label: '13:15 午后确认（上午强势是否回落 + 有无新异动）', hint: '如：光模块未回落 / 出现机器人异动' },
    { id: 'm4', label: '14:30 尾盘评估（放量 / 缩量 + 龙头是否抗跌）', hint: '如：放量上涨 龙头抗跌 健康' },
    { id: 'm5', label: '全天资金流向记录（哪些板块净流入 / 流出）', hint: '如：流入 AI算力/半导体 流出 银行/白酒' },
  ] },
  post: { title: '盘后复盘', items: [
    { id: 'q1', label: '填写市场结构日记', hint: '如：已在「每日日记」填写并保存' },
    { id: 'q2', label: '识别假强板块（高开低走 / 无跟随 / 净流出）', hint: '如：机器人 高开低走 假强' },
    { id: 'q3', label: '龙头健康度评估', hint: '如：中际旭创 健康（创新高+放量+抗跌）' },
  ] },
};
const ALL_ITEMS = Object.values(CHECKLIST_DEF).flatMap((g) => g.items);

/* ── 今日清单 + 提醒计时 ─────────────────────────────────────────────────── */
export function ChecklistScreen() {
  const { hhmm, next, text, diff } = useAlarmClock();
  const [checks, setChecks] = _rS({});
  const [notes, setNotes] = _rS({});
  const [perm, setPerm] = _rS(typeof Notification !== 'undefined' ? Notification.permission : 'unsupported');
  const date = MarketStore.today();

  _rE(() => { MarketStore.get('checklists', date).then((d) => { setChecks(d?.checks || {}); setNotes(d?.notes || {}); }); }, [date]);

  const persist = async (nextChecks, nextNotes) => {
    const existing = (await MarketStore.get('checklists', date)) || { date };
    existing.checks = nextChecks; existing.notes = nextNotes;
    await MarketStore.save('checklists', existing);
  };

  const toggle = async (id) => {
    const hasNote = (notes[id] || '').trim().length > 0;
    if (!checks[id] && !hasNote) return; // 必须先记录才能标记完成
    const nc = { ...checks, [id]: !checks[id] };
    setChecks(nc);
    await persist(nc, notes);
  };
  const setNote = (id, val) => {
    const nn = { ...notes, [id]: val };
    setNotes(nn);
    // 清空内容时自动取消完成
    const nc = val.trim().length === 0 && checks[id] ? { ...checks, [id]: false } : checks;
    if (nc !== checks) setChecks(nc);
    persist(nc, nn);
  };
  const done = ALL_ITEMS.filter((it) => checks[it.id]).length;
  const pct = Math.round((done / ALL_ITEMS.length) * 100);

  const enableNotify = async () => {
    if (typeof Notification === 'undefined') { setPerm('unsupported'); return; }
    const p = await Notification.requestPermission();
    setPerm(p);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* alarm timeline */}
      <div className="panel">
        <div className="panel-head">
          <span className="panel-title">提醒计时 · 交易时段节奏</span>
          <button onClick={enableNotify} style={btnStyle(perm === 'granted')}>
            {perm === 'granted' ? '✓ 提醒已开启' : perm === 'unsupported' ? '浏览器不支持通知' : '开启浏览器通知'}
          </button>
        </div>
        <div style={{ padding: 16, display: 'grid', gridTemplateColumns: '200px 1fr', gap: 20, alignItems: 'center' }}>
          <div style={{ textAlign: 'center', padding: '6px 0' }}>
            <div style={{ fontSize: 11, color: 'var(--ink-3)', marginBottom: 4 }}>距「{next.label.split(' · ')[0]}」</div>
            <div className="mono" style={{ fontSize: 40, fontWeight: 700, color: diff < 300 ? 'var(--warn)' : 'var(--accent)', lineHeight: 1 }}>{text}</div>
            <div className="mono" style={{ fontSize: 12, color: 'var(--ink-4)', marginTop: 6 }}>现在 {hhmm} · 下一节点 {next.hm}</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {ALARMS.map((a) => {
              const isNext = a.hm === next.hm;
              const passed = a.hm <= hhmm && !isNext;
              return (
                <div key={a.hm} style={{ flex: 1, padding: '10px 8px', borderRadius: 'var(--r-md)', border: '1px solid ' + (isNext ? 'var(--accent)' : 'var(--line-soft)'), background: isNext ? 'var(--accent-bg)' : passed ? 'transparent' : 'var(--panel-2)', opacity: passed ? 0.45 : 1 }}>
                  <div className="mono" style={{ fontSize: 14, fontWeight: 700, color: isNext ? 'var(--accent)' : 'var(--ink)' }}>{a.hm}</div>
                  <div style={{ fontSize: 10.5, color: 'var(--ink-3)', marginTop: 4, lineHeight: 1.4 }}>{a.label.split(' · ').slice(1).join(' ') || a.label}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* checklist */}
      <div className="panel">
        <div className="panel-head">
          <span className="panel-title">今日操作清单</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 160, height: 5, background: 'var(--panel-3)', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ width: pct + '%', height: '100%', background: 'var(--up)', transition: 'width .3s' }} />
            </div>
            <span className="mono" style={{ fontSize: 12, color: 'var(--ink-2)' }}>{done} / {ALL_ITEMS.length}</span>
          </div>
        </div>
        <div style={{ padding: 16, display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
          {Object.entries(CHECKLIST_DEF).map(([key, group]) => (
            <div key={key}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent)', marginBottom: 10, paddingBottom: 8, borderBottom: '1px solid var(--line-soft)' }}>{group.title}</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {group.items.map((it) => {
                  const on = !!checks[it.id];
                  const note = notes[it.id] || '';
                  const hasNote = note.trim().length > 0;
                  return (
                    <div key={it.id} style={{ padding: '10px 11px', borderRadius: 'var(--r-md)', background: on ? 'var(--up-bg)' : 'var(--panel-2)', border: '1px solid ' + (on ? 'var(--up-dim)' : 'var(--line-soft)'), transition: 'background .15s, border-color .15s' }}>
                      <div style={{ fontSize: 12, lineHeight: 1.5, color: on ? 'var(--ink-2)' : 'var(--ink)', marginBottom: 8 }}>{it.label}</div>
                      <div style={{ display: 'flex', gap: 6, alignItems: 'stretch' }}>
                        <input
                          value={note}
                          onChange={(e) => setNote(it.id, e.target.value)}
                          placeholder={it.hint}
                          style={{ flex: 1, minWidth: 0, background: 'var(--panel-3)', border: '1px solid var(--line)', borderRadius: 'var(--r-sm)', color: 'var(--ink)', padding: '6px 8px', fontSize: 11.5, fontFamily: 'var(--cjk)' }}
                        />
                        <button
                          onClick={() => toggle(it.id)}
                          disabled={!on && !hasNote}
                          title={!on && !hasNote ? '先在左侧记录内容，才能标记完成' : ''}
                          style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 5, padding: '0 10px', borderRadius: 'var(--r-sm)', fontSize: 11.5, fontWeight: 600, fontFamily: 'var(--cjk)', whiteSpace: 'nowrap', cursor: (!on && !hasNote) ? 'not-allowed' : 'pointer', border: '1px solid ' + (on ? 'var(--up)' : hasNote ? 'var(--line)' : 'var(--line-soft)'), background: on ? 'var(--up)' : 'transparent', color: on ? 'var(--bg)' : hasNote ? 'var(--ink-2)' : 'var(--ink-4)', opacity: (!on && !hasNote) ? 0.55 : 1, transition: 'all .15s' }}
                        >
                          <span style={{ fontSize: 12 }}>{on ? '✓' : '○'}</span>{on ? '已完成' : '完成'}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── journal ─────────────────────────────────────────────────────────────── */
const SENTIMENTS = ['冰点', '修复', '主升', '高潮', '退潮'];
const RISKS = ['科技成长', '避险红利', '小盘投机', '混沌'];
const sentColor = (s) => ({ 主升: 'var(--up)', 修复: 'var(--accent)', 高潮: 'var(--warn)', 退潮: 'var(--down)', 冰点: 'var(--ink-3)' }[s] || 'var(--ink-3)');
const EMPTY = (date) => ({ date, mainLine: '', leaders: '', topSectors: '', sentiment: '', risk: '', analysis: '', mistakes: '无' });

const fieldLabel = { fontSize: 11, color: 'var(--ink-3)', fontWeight: 600, marginBottom: 5, display: 'block' };
const inputStyle = { width: '100%', background: 'var(--panel-2)', border: '1px solid var(--line)', borderRadius: 'var(--r-sm)', color: 'var(--ink)', padding: '8px 10px', fontSize: 13, fontFamily: 'var(--cjk)' };
function btnStyle(primary) {
  return { padding: '6px 14px', borderRadius: 'var(--r-sm)', border: '1px solid ' + (primary ? 'var(--accent)' : 'var(--line)'), background: primary ? 'var(--accent-bg)' : 'var(--panel-2)', color: primary ? 'var(--accent)' : 'var(--ink-2)', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'var(--cjk)' };
}

export function JournalScreen() {
  const s = useMarket();
  const [form, setForm] = _rS(() => EMPTY(MarketStore.today()));
  const [history, setHistory] = _rS([]);
  const [flash, setFlash] = _rS('');

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const loadHistory = async () => { const all = await MarketStore.getAll('journals'); all.sort((a, b) => b.date.localeCompare(a.date)); setHistory(all.slice(0, 30)); };

  _rE(() => { MarketStore.get('journals', form.date).then((d) => { if (d) setForm({ ...EMPTY(form.date), ...d }); }); loadHistory(); }, []);

  const onDate = async (date) => { const d = await MarketStore.get('journals', date); setForm(d ? { ...EMPTY(date), ...d } : EMPTY(date)); };
  const saveJournal = async () => { await MarketStore.save('journals', form); setFlash('已保存'); setTimeout(() => setFlash(''), 1800); loadHistory(); };
  const newToday = () => setForm(EMPTY(MarketStore.today()));

  // pull live market read into the form
  const pullLive = () => {
    const themes = MarketData.themeAgg();
    const topSec = [...s.sectors].sort((a, b) => b.netInflow - a.netInflow).slice(0, 3);
    const topLead = [...s.leaders].sort((a, b) => b.changePct - a.changePct).slice(0, 2);
    const leadTheme = themes[0] || { theme: '—', flow: 0 };
    const lagTheme = themes[themes.length - 1] || { theme: '—' };
    setForm((f) => ({
      ...f,
      mainLine: themes.slice(0, 2).map((t) => t.theme).join('、'),
      topSectors: topSec.map((x) => x.name).join('、'),
      leaders: topLead.map((x) => `${x.name} ${x.code}`).join('、'),
      analysis: f.analysis || `资金主线流入 ${leadTheme.theme}（${fmtFlow(leadTheme.flow)}亿），流出 ${lagTheme.theme}。`,
    }));
    setFlash('已带入今日盘面'); setTimeout(() => setFlash(''), 1800);
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 14, alignItems: 'start' }}>
      <div className="panel">
        <div className="panel-head">
          <span className="panel-title">市场结构日记</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {flash && <span style={{ fontSize: 11, color: 'var(--up)' }}>{flash}</span>}
            <button onClick={pullLive} style={btnStyle(false)}>↻ 带入今日盘面</button>
            <button onClick={newToday} style={btnStyle(false)}>新建今日</button>
            <button onClick={saveJournal} style={btnStyle(true)}>保存</button>
          </div>
        </div>
        <div style={{ padding: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <div><label style={fieldLabel}>日期</label><input type="date" value={form.date} onChange={(e) => { set('date', e.target.value); onDate(e.target.value); }} style={inputStyle} /></div>
          <div><label style={fieldLabel}>今日主线（1–2个）</label><input value={form.mainLine} onChange={(e) => set('mainLine', e.target.value)} placeholder="如 AI算力、光模块" style={inputStyle} /></div>
          <div><label style={fieldLabel}>龙头股（代码+名称）</label><input value={form.leaders} onChange={(e) => set('leaders', e.target.value)} placeholder="如 中际旭创 300308" style={inputStyle} /></div>
          <div><label style={fieldLabel}>净流入板块（前3）</label><input value={form.topSectors} onChange={(e) => set('topSectors', e.target.value)} placeholder="如 通信设备、半导体" style={inputStyle} /></div>
          <div><label style={fieldLabel}>市场情绪</label>
            <div style={{ display: 'flex', gap: 4 }}>
              {SENTIMENTS.map((x) => <button key={x} onClick={() => set('sentiment', x)} style={{ flex: 1, padding: '7px 0', borderRadius: 'var(--r-sm)', border: '1px solid ' + (form.sentiment === x ? sentColor(x) : 'var(--line)'), background: form.sentiment === x ? 'var(--panel-3)' : 'var(--panel-2)', color: form.sentiment === x ? sentColor(x) : 'var(--ink-3)', fontSize: 11.5, fontWeight: 600, cursor: 'pointer', fontFamily: 'var(--cjk)' }}>{x}</button>)}
            </div>
          </div>
          <div><label style={fieldLabel}>风险偏好</label>
            <div style={{ display: 'flex', gap: 4 }}>
              {RISKS.map((x) => <button key={x} onClick={() => set('risk', x)} style={{ flex: 1, padding: '7px 0', borderRadius: 'var(--r-sm)', border: '1px solid ' + (form.risk === x ? 'var(--accent)' : 'var(--line)'), background: form.risk === x ? 'var(--accent-bg)' : 'var(--panel-2)', color: form.risk === x ? 'var(--accent)' : 'var(--ink-3)', fontSize: 11, fontWeight: 600, cursor: 'pointer', fontFamily: 'var(--cjk)' }}>{x}</button>)}
            </div>
          </div>
          <div style={{ gridColumn: '1 / -1' }}><label style={fieldLabel}>今日市场理解（在交易什么？资金为何流向主线？哪些是假强？龙头健康吗？）</label><textarea value={form.analysis} onChange={(e) => set('analysis', e.target.value)} rows={5} style={{ ...inputStyle, resize: 'vertical', minHeight: 90 }} /></div>
          <div style={{ gridColumn: '1 / -1' }}><label style={fieldLabel}>今日错误判断 / 错误操作</label><textarea value={form.mistakes} onChange={(e) => set('mistakes', e.target.value)} rows={2} style={{ ...inputStyle, resize: 'vertical' }} /></div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head"><span className="panel-title">历史复盘 · 最近30天</span></div>
        <div style={{ padding: 8, maxHeight: 560, overflow: 'auto' }}>
          {history.length === 0 && <div style={{ padding: 24, textAlign: 'center', fontSize: 12, color: 'var(--ink-4)' }}>暂无记录 · 保存后出现在这里</div>}
          {history.map((j) => (
            <div key={j.date} onClick={() => onDate(j.date)} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 10px', borderRadius: 'var(--r-sm)', cursor: 'pointer', background: j.date === form.date ? 'var(--panel-2)' : 'transparent' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--panel-2)')} onMouseLeave={(e) => (e.currentTarget.style.background = j.date === form.date ? 'var(--panel-2)' : 'transparent')}>
              <span className="mono" style={{ fontSize: 11, color: 'var(--ink-3)', width: 74, flexShrink: 0 }}>{j.date.slice(5)}</span>
              <span style={{ flex: 1, fontSize: 12.5, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>{j.mainLine || '—'}</span>
              {j.sentiment && <span style={{ fontSize: 10.5, padding: '2px 8px', borderRadius: 999, color: sentColor(j.sentiment), border: '1px solid ' + sentColor(j.sentiment), flexShrink: 0 }}>{j.sentiment}</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
