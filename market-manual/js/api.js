// ─── JSONP helper ────────────────────────────────────────────────────────────
function jsonp(url, timeout = 8000) {
  return new Promise((resolve, reject) => {
    const id  = `_em${Date.now()}_${Math.random().toString(36).slice(2)}`;
    const timer = setTimeout(() => { cleanup(); reject(new Error('timeout')); }, timeout);

    function cleanup() {
      clearTimeout(timer);
      delete window[id];
      document.getElementById(id)?.remove();
    }

    window[id] = data => { cleanup(); resolve(data); };

    const s  = document.createElement('script');
    s.id     = id;
    s.src    = `${url}&cb=${id}&_=${Date.now()}`;
    s.onerror = () => { cleanup(); reject(new Error('script error')); };
    document.head.appendChild(s);
  });
}

// ─── A股主要指数 ──────────────────────────────────────────────────────────────
// secid format: {market}.{code}  market 1=SH 0=SZ
export const INDEX_LIST = [
  { secid: '1.000001', label: '上证指数' },
  { secid: '0.399001', label: '深证成指' },
  { secid: '0.399006', label: '创业板指' },
  { secid: '1.000688', label: '科创50'   },
  { secid: '0.899050', label: '北证50'   },
];

// With fltt=2: f43=price, f170=pct*100 (need /100), f169=change, f47=vol, f48=amount
async function fetchOneIndex({ secid, label }) {
  const fields = 'f43,f57,f58,f169,f170,f47,f48';
  const url    = `https://push2.eastmoney.com/api/qt/stock/get?secid=${secid}&fields=${fields}&fltt=2&invt=2`;
  const res    = await jsonp(url);
  const d      = res?.data;
  if (!d || d.f43 === undefined) throw new Error('no data');
  return {
    secid, label,
    price:     d.f43,
    change:    d.f169,
    changePct: +(d.f170 / 100).toFixed(2),  // eastmoney stores as pct×100
    volume:    d.f47,
    amount:    d.f48,
  };
}

export async function fetchIndices() {
  const results = await Promise.allSettled(INDEX_LIST.map(fetchOneIndex));
  return results.map((r, i) =>
    r.status === 'fulfilled'
      ? r.value
      : { ...INDEX_LIST[i], error: true, price: '--', changePct: 0 }
  );
}

// ─── 行业板块资金流向 ─────────────────────────────────────────────────────────
// fid=f62  fs=m:90+t:2(行业板块)
// f12=代码 f14=名称 f62=今日净流入(元) f184=今日净流入占比(%)
export async function fetchSectorFlow() {
  const fields = 'f12,f14,f62,f184,f3';
  const url    = `https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=20&po=1&np=1&fltt=2&invt=2&fid=f62&fs=m:90+t:2&fields=${fields}`;
  const res    = await jsonp(url);
  const list   = res?.data?.diff;
  if (!list) throw new Error('no sector data');
  return list.map(d => ({
    code:      d.f12,
    name:      d.f14,
    netInflow: d.f62,           // 元
    netPct:    d.f184,          // %
    changePct: +(d.f3 / 100).toFixed(2),
  }));
}

// ─── Mock fallback data (for offline / API blocked) ──────────────────────────
export const MOCK_INDICES = INDEX_LIST.map((idx, i) => ({
  ...idx,
  price:     [3200, 10500, 2100, 1050, 1200][i],
  change:    [0, 0, 0, 0, 0][i],
  changePct: 0,
  volume:    0,
  amount:    0,
  mock:      true,
}));

export const MOCK_SECTORS = [
  { name: '通信设备', changePct:  2.1, netInflow:  52e8, netPct:  1.2 },
  { name: '半导体',   changePct:  1.8, netInflow:  38e8, netPct:  0.9 },
  { name: '计算机应用', changePct:  1.3, netInflow:  21e8, netPct:  0.5 },
  { name: '白酒',     changePct: -0.6, netInflow: -18e8, netPct: -0.4 },
  { name: '银行',     changePct: -0.3, netInflow: -12e8, netPct: -0.3 },
].map(d => ({ ...d, mock: true }));
