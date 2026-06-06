/* ──────────────────────────────────────────────────────────────────────────
   data.js — shared market data layer for 金融市场监控
   · Real Eastmoney JSONP logic (attempted once on load)
   · Rich mock dataset as the always-on heartbeat / fallback
   · Live ticking simulation so sector rotation visibly animates
   · Convention: 绿涨红跌 (green up / red down) — UP=green, DOWN=red
   Exposes window.MarketData
   ────────────────────────────────────────────────────────────────────────── */
(function () {
  'use strict';

  // ── small utils ───────────────────────────────────────────────────────────
  const rnd = (a, b) => a + Math.random() * (b - a);
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const round = (v, d = 2) => +v.toFixed(d);

  // ── JSONP (real API) ────────────────────────────────────────────────────────
  function jsonp(url, timeout = 6000) {
    return new Promise((resolve, reject) => {
      const id = `_em${Date.now()}_${Math.random().toString(36).slice(2)}`;
      const timer = setTimeout(() => { cleanup(); reject(new Error('timeout')); }, timeout);
      function cleanup() { clearTimeout(timer); delete window[id]; document.getElementById(id)?.remove(); }
      window[id] = (data) => { cleanup(); resolve(data); };
      const s = document.createElement('script');
      s.id = id; s.src = `${url}&cb=${id}&_=${Date.now()}`;
      s.onerror = () => { cleanup(); reject(new Error('script error')); };
      document.head.appendChild(s);
    });
  }

  const INDEX_LIST = [
    { secid: '1.000001', label: '上证指数', code: 'SH000001' },
    { secid: '0.399001', label: '深证成指', code: 'SZ399001' },
    { secid: '0.399006', label: '创业板指', code: 'SZ399006' },
    { secid: '1.000688', label: '科创50',  code: 'SH000688' },
    { secid: '0.399330', label: '深证100', code: 'SZ399330' },
  ];

  async function fetchOneIndex({ secid, label, code }) {
    const fields = 'f43,f57,f58,f169,f170,f47,f48';
    const url = `https://push2.eastmoney.com/api/qt/stock/get?secid=${secid}&fields=${fields}&fltt=2&invt=2`;
    const res = await jsonp(url);
    const d = res?.data;
    if (!d || d.f43 === undefined) throw new Error('no data');
    return { code, label, price: d.f43, changePct: round(d.f170 / 100), amount: d.f48 };
  }
  async function fetchIndices() {
    const r = await Promise.allSettled(INDEX_LIST.map(fetchOneIndex));
    if (!r.some((x) => x.status === 'fulfilled')) throw new Error('all failed');
    return r.map((x, i) => (x.status === 'fulfilled' ? x.value : null)).filter(Boolean);
  }
  async function fetchSectorFlow() {
    const fields = 'f12,f14,f62,f184,f3';
    const url = `https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=30&po=1&np=1&fltt=2&invt=2&fid=f62&fs=m:90+t:2&fields=${fields}`;
    const res = await jsonp(url);
    const list = res?.data?.diff;
    if (!list) throw new Error('no sector data');
    return list.map((d) => ({ name: d.f14, changePct: round(d.f3 / 100), netInflow: d.f62 / 1e8 }));
  }

  // ── MOCK seed ─────────────────────────────────────────────────────────────
  // changePct in %, netInflow in 亿元 (signed). theme groups sectors for rotation read.
  const SECTOR_SEED = [
    { name: '光模块',   changePct: 4.8, netInflow: 41.2, theme: 'AI算力' },
    { name: '算力租赁', changePct: 3.9, netInflow: 28.6, theme: 'AI算力' },
    { name: '通信设备', changePct: 3.1, netInflow: 33.4, theme: 'AI算力' },
    { name: '半导体',   changePct: 2.4, netInflow: 24.1, theme: '科技' },
    { name: 'CPO',      changePct: 5.6, netInflow: 19.8, theme: 'AI算力' },
    { name: '消费电子', changePct: 1.6, netInflow: 9.2,  theme: '科技' },
    { name: '软件开发', changePct: 1.9, netInflow: 12.7, theme: '科技' },
    { name: '机器人',   changePct: 0.4, netInflow: -6.3, theme: '题材' },
    { name: '电池',     changePct: 0.9, netInflow: 4.1,  theme: '新能源' },
    { name: '光伏',     changePct: -0.7, netInflow: -8.4, theme: '新能源' },
    { name: '军工',     changePct: 1.2, netInflow: 3.3,  theme: '题材' },
    { name: '医药商业', changePct: -0.3, netInflow: -2.1, theme: '医药' },
    { name: '白酒',     changePct: -1.4, netInflow: -15.6, theme: '消费' },
    { name: '证券',     changePct: 0.6, netInflow: 5.5,  theme: '金融' },
    { name: '银行',     changePct: -0.5, netInflow: -11.2, theme: '红利' },
    { name: '电力',     changePct: -0.9, netInflow: -7.8, theme: '红利' },
    { name: '煤炭',     changePct: -1.1, netInflow: -9.1, theme: '红利' },
    { name: '房地产',   changePct: -1.8, netInflow: -5.4, theme: '周期' },
  ];

  const LEADER_SEED = [
    { code: '300308', name: '中际旭创', sector: '光模块', price: 168.4, changePct: 6.2, volRatio: 1.4, theme: 'AI算力' },
    { code: '300394', name: '天孚通信', sector: '光模块', price: 92.7, changePct: 5.1, volRatio: 1.3, theme: 'AI算力' },
    { code: '601138', name: '工业富联', sector: '算力租赁', price: 31.2, changePct: 4.4, volRatio: 1.2, theme: 'AI算力' },
    { code: '002371', name: '北方华创', sector: '半导体', price: 412.5, changePct: 2.1, volRatio: 0.9, theme: '科技' },
    { code: '688981', name: '中芯国际', sector: '半导体', price: 58.9, changePct: 1.7, volRatio: 1.1, theme: '科技' },
    { code: '603728', name: '鸣志电器', sector: '机器人', price: 44.6, changePct: -3.2, volRatio: 2.1, theme: '题材' },
    { code: '688017', name: '绿的谐波', sector: '机器人', price: 96.1, changePct: -1.8, volRatio: 1.6, theme: '题材' },
    { code: '600900', name: '长江电力', sector: '电力', price: 28.3, changePct: -0.6, volRatio: 0.7, theme: '红利' },
    { code: '601088', name: '中国神华', sector: '煤炭', price: 39.8, changePct: -1.0, volRatio: 0.8, theme: '红利' },
    { code: '601398', name: '工商银行', sector: '银行', price: 6.42, changePct: -0.4, volRatio: 0.6, theme: '红利' },
  ];

  const INDEX_SEED = [
    { code: 'SH000001', label: '上证指数', price: 3284.6, changePct: 0.82 },
    { code: 'SZ399001', label: '深证成指', price: 10512.3, changePct: 1.14 },
    { code: 'SZ399006', label: '创业板指', price: 2118.7, changePct: 1.63 },
    { code: 'SH000688', label: '科创50',  price: 1042.9, changePct: 2.21 },
    { code: 'SZ399330', label: '深证100', price: 6201.4, changePct: 1.05 },
  ];

  const GLOBAL_SEED = [
    { code: 'NDX', label: '纳斯达克', changePct: 0.54, note: '收盘' },
    { code: 'HSTECH', label: '恒生科技', changePct: 0.81, note: '收盘' },
    { code: 'CN00Y', label: 'A50期指', changePct: 0.23, note: '实时' },
    { code: 'US10Y', label: '美10年债', changePct: 4.30, note: '收益率', isLevel: true },
    { code: 'GC', label: '黄金', changePct: 0.12, note: '隔夜' },
    { code: 'CL', label: '原油', changePct: -0.34, note: '隔夜' },
    { code: 'NVDA', label: 'NVDA盘后', changePct: 1.21, note: '盘后' },
  ];

  // ── live state ──────────────────────────────────────────────────────────────
  const HIST = 40;
  const state = {
    source: 'mock',           // 'mock' | 'live'
    updatedAt: Date.now(),
    indices: INDEX_SEED.map((d) => ({ ...d, prevClose: round(d.price / (1 + d.changePct / 100)) })),
    sectors: SECTOR_SEED.map((d, i) => ({
      ...d, id: i,
      hist: Array.from({ length: HIST }, () => d.changePct + rnd(-0.4, 0.4)),
      flowHist: Array.from({ length: HIST }, () => d.netInflow + rnd(-2, 2)),
    })),
    leaders: LEADER_SEED.map((d) => ({
      ...d,
      open: round(d.price / (1 + d.changePct / 100)),
      spark: Array.from({ length: 30 }, (_, k) => d.changePct * (0.3 + 0.7 * (k / 29)) + rnd(-0.5, 0.5)),
    })),
    globals: GLOBAL_SEED.map((d) => ({ ...d })),
    breadth: { up: 3142, down: 1684, flat: 220, limitUp: 58, limitDown: 4 },
  };

  // ── ticking simulation (the heartbeat) ────────────────────────────────────
  const subs = new Set();
  function notify() { state.updatedAt = Date.now(); subs.forEach((cb) => { try { cb(state); } catch (e) {} }); }

  function tick() {
    // sectors random-walk; theme cohesion makes rotation legible
    const themeDrift = {};
    state.sectors.forEach((s) => { if (!(s.theme in themeDrift)) themeDrift[s.theme] = rnd(-0.18, 0.18); });
    state.sectors.forEach((s) => {
      const drift = themeDrift[s.theme] + rnd(-0.22, 0.22);
      s.changePct = round(clamp(s.changePct + drift, -6, 8));
      s.netInflow = round(clamp(s.netInflow + drift * 3 + rnd(-1.2, 1.2), -40, 60), 1);
      s.hist.push(s.changePct); if (s.hist.length > HIST) s.hist.shift();
      s.flowHist.push(s.netInflow); if (s.flowHist.length > HIST) s.flowHist.shift();
    });
    // leaders follow their sector loosely
    state.leaders.forEach((l) => {
      const sec = state.sectors.find((s) => s.name === l.sector);
      const pull = sec ? (sec.changePct - l.changePct) * 0.15 : 0;
      l.changePct = round(clamp(l.changePct + pull + rnd(-0.35, 0.35), -10, 12));
      l.price = round(l.open * (1 + l.changePct / 100), 2);
      l.volRatio = round(clamp(l.volRatio + rnd(-0.05, 0.05), 0.3, 3), 2);
      l.spark.push(l.changePct); if (l.spark.length > 30) l.spark.shift();
    });
    // indices = breadth of their constituents (loosely from sector avg)
    const avg = state.sectors.reduce((a, s) => a + s.changePct, 0) / state.sectors.length;
    state.indices.forEach((idx, i) => {
      const w = [0.7, 0.85, 1.25, 1.5, 0.95][i];
      idx.changePct = round(clamp(avg * w + rnd(-0.15, 0.15), -5, 6));
      idx.price = round(idx.prevClose * (1 + idx.changePct / 100), 2);
    });
    // breadth drifts
    const b = state.breadth;
    b.up = clamp(Math.round(b.up + rnd(-60, 60) + avg * 30), 200, 5000);
    b.down = clamp(5046 - b.up - b.flat, 0, 5000);
    b.limitUp = clamp(Math.round(b.limitUp + rnd(-3, 3) + avg * 2), 0, 200);
    b.limitDown = clamp(Math.round(b.limitDown + rnd(-1, 1) - avg), 0, 100);
    notify();
  }

  let timer = null;
  function start(interval = 2200) { if (timer) return; tick(); timer = setInterval(tick, interval); }
  function stop() { clearInterval(timer); timer = null; }

  // ── try real API once, swap in if it works ────────────────────────────────
  async function tryLive() {
    try {
      const [idx, sec] = await Promise.all([fetchIndices(), fetchSectorFlow()]);
      if (idx?.length) {
        idx.forEach((d) => { const m = state.indices.find((x) => x.label === d.label); if (m) { m.price = d.price; m.changePct = d.changePct; } });
      }
      if (sec?.length) {
        // map onto known sectors where names match; keep mock rotation for the rest
        sec.forEach((d) => { const m = state.sectors.find((x) => x.name === d.name); if (m) { m.changePct = d.changePct; m.netInflow = round(d.netInflow, 1); } });
      }
      state.source = 'live';
      notify();
    } catch (e) {
      state.source = 'mock';
    }
  }

  // ── derived helpers ─────────────────────────────────────────────────────────
  const themeAgg = () => {
    const m = {};
    state.sectors.forEach((s) => {
      m[s.theme] ??= { theme: s.theme, flow: 0, chg: 0, n: 0 };
      m[s.theme].flow += s.netInflow; m[s.theme].chg += s.changePct; m[s.theme].n++;
    });
    return Object.values(m).map((t) => ({ ...t, chg: round(t.chg / t.n), flow: round(t.flow, 1) }))
      .sort((a, b) => b.flow - a.flow);
  };

  window.MarketData = {
    state, start, stop, tick, tryLive,
    subscribe(cb) { subs.add(cb); cb(state); return () => subs.delete(cb); },
    themeAgg,
    fmtFlow(v) { const s = v >= 0 ? '+' : '−'; return s + Math.abs(v).toFixed(1) + '亿'; },
    fmtPct(v) { return (v > 0 ? '+' : '') + v.toFixed(2) + '%'; },
    cls(v) { return v > 0.001 ? 'up' : v < -0.001 ? 'down' : 'flat'; },
  };
})();
