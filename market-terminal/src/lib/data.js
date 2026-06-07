/* ──────────────────────────────────────────────────────────────────────────
   data.js — market data layer (SSE edition)
   · Connects to backend via EventSource /api/stream
   · subscribe/notify pattern unchanged — components don't need rewiring
   ────────────────────────────────────────────────────────────────────────── */

const API_BASE = import.meta.env.VITE_API_BASE || '';
const SSE_URL = `${API_BASE}/api/stream`;

const state = {
  source: 'disconnected',
  updatedAt: 0,
  indices: [],
  sectors: [],
  leaders: [],
  globals: [],
  breadth: { up: 0, down: 0, flat: 0, limitUp: 0, limitDown: 0 },
};

const subs = new Set();

function notify() {
  state.updatedAt = Date.now();
  subs.forEach((cb) => {
    try {
      cb(state);
    } catch (e) {
      // Subscribers should not break the market data fan-out.
    }
  });
}

function connectSSE() {
  const es = new EventSource(SSE_URL);
  es.addEventListener('snapshot', (e) => {
    const snap = JSON.parse(e.data);
    Object.assign(state, snap);
    notify();
  });
  es.onerror = () => {
    state.source = 'disconnected';
    notify();
  };
  return es;
}

const themeAgg = () => {
  const m = {};
  state.sectors.forEach((s) => {
    m[s.theme] ??= { theme: s.theme, flow: 0, chg: 0, n: 0 };
    m[s.theme].flow += s.netInflow;
    m[s.theme].chg += s.changePct;
    m[s.theme].n++;
  });
  return Object.values(m)
    .map((t) => ({ ...t, chg: +(t.chg / t.n).toFixed(2), flow: +t.flow.toFixed(1) }))
    .sort((a, b) => b.flow - a.flow);
};

export const MarketData = {
  state,
  connect: connectSSE,
  subscribe(cb) {
    subs.add(cb);
    cb(state);
    return () => subs.delete(cb);
  },
  themeAgg,
  fmtFlow(v) {
    const s = v >= 0 ? '+' : '−';
    return s + Math.abs(v).toFixed(1) + '亿';
  },
  fmtPct(v) {
    return (v > 0 ? '+' : '') + v.toFixed(2) + '%';
  },
  cls(v) {
    return v > 0.001 ? 'up' : v < -0.001 ? 'down' : 'flat';
  },
};
