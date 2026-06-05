import { db } from './db.js';
import { fetchIndices, fetchSectorFlow, MOCK_INDICES, MOCK_SECTORS } from './api.js';

// ─── Helpers ─────────────────────────────────────────────────────────────────
const today = () => new Date().toISOString().slice(0, 10);
const $ = id => document.getElementById(id);
const fmtAmt = v => {
  if (!v || v === '--') return '--';
  const n = Math.abs(v);
  const sign = v < 0 ? '-' : '+';
  if (n >= 1e12) return sign + (n / 1e12).toFixed(2) + '万亿';
  if (n >= 1e8)  return sign + (n / 1e8).toFixed(2)  + '亿';
  if (n >= 1e4)  return sign + (n / 1e4).toFixed(2)  + '万';
  return sign + n.toFixed(0);
};
const pctClass = p => p > 0 ? 'up' : p < 0 ? 'down' : 'flat';
const pctStr   = p => (p > 0 ? '+' : '') + p + '%';

// ─── Tab routing ─────────────────────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => {
      const target = el.dataset.tab;
      document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      el.classList.add('active');
      $(target)?.classList.add('active');
    });
  });
}

// ─── Section 1: 行情监控 ──────────────────────────────────────────────────────
let marketTimer = null;

function renderIndices(list) {
  $('index-grid').innerHTML = list.map(d => `
    <div class="index-card ${pctClass(d.changePct)}">
      <div class="idx-label">${d.label}</div>
      <div class="idx-price">${d.price}</div>
      <div class="idx-change">${pctStr(d.changePct)}</div>
      ${d.mock ? '<div class="mock-badge">模拟</div>' : ''}
    </div>`).join('');
}

function renderSectors(list) {
  const top    = [...list].sort((a, b) => b.netInflow - a.netInflow).slice(0, 5);
  const bottom = [...list].sort((a, b) => a.netInflow - b.netInflow).slice(0, 5);

  const rows = arr => arr.map(d => `
    <tr>
      <td>${d.name}</td>
      <td class="${pctClass(d.changePct)}">${pctStr(d.changePct)}</td>
      <td class="${d.netInflow >= 0 ? 'up' : 'down'}">${fmtAmt(d.netInflow)}</td>
    </tr>`).join('');

  $('sector-inflow').innerHTML  = rows(top);
  $('sector-outflow').innerHTML = rows(bottom);
}

async function refreshMarket() {
  $('market-status').textContent = '更新中…';
  try {
    const [indices, sectors] = await Promise.all([fetchIndices(), fetchSectorFlow()]);
    renderIndices(indices);
    renderSectors(sectors);
    $('market-status').textContent = '更新时间 ' + new Date().toLocaleTimeString('zh-CN');
  } catch {
    renderIndices(MOCK_INDICES);
    renderSectors(MOCK_SECTORS);
    $('market-status').textContent = '行情接口未响应，显示模拟数据';
  }
}

function isMarketHours() {
  const now = new Date();
  const h = now.getHours(), m = now.getMinutes();
  const mins = h * 60 + m;
  return (mins >= 9 * 60 + 25 && mins <= 11 * 60 + 35) ||
         (mins >= 13 * 60    && mins <= 15 * 60 + 5);
}

function startMarketPoll() {
  refreshMarket();
  if (marketTimer) clearInterval(marketTimer);
  marketTimer = setInterval(() => {
    if (isMarketHours()) refreshMarket();
  }, 15000);
}

// ─── Section 2: 今日清单 ──────────────────────────────────────────────────────
const CHECKLIST_DEF = {
  pre: [
    { id: 'p1', label: '第1步：全球行情记录（纳指/恒科/A50/美债/黄金/原油/NVDA）' },
    { id: 'p2', label: '第2步：风险偏好基准（进攻ETF vs 防守ETF 集合竞价）' },
    { id: 'p3', label: '第3步：关键词新闻扫描（≤3条，过滤噪音）' },
    { id: 'p4', label: '第4步：建立今日观察表（4个方向填好）' },
  ],
  mid: [
    { id: 'm1', label: '9:30 开盘5分钟扫描（板块涨幅榜 + 昨日龙头 + 涨跌家数）' },
    { id: 'm2', label: '10:30 第一关键点（主线是否持续 + 大盘分时位置）' },
    { id: 'm3', label: '13:15 下午开盘确认（上午强势是否回落 + 有无新异动）' },
    { id: 'm4', label: '14:30 尾盘评估（放量/缩量 + 龙头是否抗跌）' },
    { id: 'm5', label: '全天资金流向记录（哪些板块净流入/流出）' },
  ],
  post: [
    { id: 'q1', label: '第8步：填写市场结构日记' },
    { id: 'q2', label: '第9步：识别假强板块（高开低走/无跟随/净流出）' },
    { id: 'q3', label: '第10步：龙头健康度评估' },
  ],
};

async function loadChecklist() {
  const data = await db.get('checklists', today()) || { date: today(), checks: {} };
  return data;
}

async function saveChecklist(state) {
  await db.save('checklists', state);
}

function renderChecklist(state) {
  const render = (group, items) => `
    <div class="cl-group">
      <div class="cl-group-title">${
        group === 'pre' ? '盘前准备（30 分钟）' :
        group === 'mid' ? '盘中观察' : '盘后复盘'
      }</div>
      ${items.map(item => `
        <label class="cl-item ${state.checks?.[item.id] ? 'checked' : ''}">
          <input type="checkbox" data-id="${item.id}" ${state.checks?.[item.id] ? 'checked' : ''}>
          <span>${item.label}</span>
        </label>`).join('')}
    </div>`;

  $('checklist-wrap').innerHTML =
    render('pre', CHECKLIST_DEF.pre) +
    render('mid', CHECKLIST_DEF.mid) +
    render('post', CHECKLIST_DEF.post);

  $('checklist-wrap').addEventListener('change', async e => {
    if (e.target.type !== 'checkbox') return;
    state.checks = state.checks || {};
    state.checks[e.target.dataset.id] = e.target.checked;
    e.target.closest('.cl-item').classList.toggle('checked', e.target.checked);
    await saveChecklist(state);
    updateChecklistProgress(state);
  });

  updateChecklistProgress(state);
}

function updateChecklistProgress(state) {
  const total   = Object.values(CHECKLIST_DEF).flat().length;
  const done    = Object.values(state.checks || {}).filter(Boolean).length;
  const pct     = Math.round(done / total * 100);
  $('cl-progress-bar').style.width = pct + '%';
  $('cl-progress-txt').textContent = `${done} / ${total} 完成`;
}

// ─── Section 3: 每日日记 ──────────────────────────────────────────────────────
async function loadJournal(date) {
  return await db.get('journals', date) || {
    date, mainLine: '', leaders: '', topSectors: '',
    sentiment: '', riskPreference: '', analysis: '', mistakes: '无',
  };
}

async function saveJournal() {
  const date = $('journal-date').value || today();
  const data = {
    date,
    mainLine:       $('j-mainline').value,
    leaders:        $('j-leaders').value,
    topSectors:     $('j-sectors').value,
    sentiment:      $('j-sentiment').value,
    riskPreference: $('j-risk').value,
    analysis:       $('j-analysis').value,
    mistakes:       $('j-mistakes').value,
  };
  await db.save('journals', data);
  showToast('日记已保存');
  renderJournalHistory();
}

async function renderJournalHistory() {
  const all = await db.getAll('journals');
  all.sort((a, b) => b.date.localeCompare(a.date));
  $('journal-history').innerHTML = all.slice(0, 30).map(j => `
    <div class="hist-item" data-date="${j.date}">
      <span class="hist-date">${j.date}</span>
      <span class="hist-main">${j.mainLine || '—'}</span>
      <span class="hist-sentiment badge-${sentimentClass(j.sentiment)}">${j.sentiment || '—'}</span>
    </div>`).join('') || '<div class="empty-hint">暂无记录</div>';

  $('journal-history').querySelectorAll('.hist-item').forEach(el => {
    el.addEventListener('click', async () => {
      const d = await loadJournal(el.dataset.date);
      fillJournalForm(d);
    });
  });
}

function sentimentClass(s) {
  const map = { '主升': 'green', '修复': 'blue', '高潮': 'orange', '退潮': 'red', '冰点': 'gray' };
  return map[s] || 'gray';
}

function fillJournalForm(d) {
  $('journal-date').value   = d.date;
  $('j-mainline').value     = d.mainLine     || '';
  $('j-leaders').value      = d.leaders      || '';
  $('j-sectors').value      = d.topSectors   || '';
  $('j-sentiment').value    = d.sentiment    || '';
  $('j-risk').value         = d.riskPreference || '';
  $('j-analysis').value     = d.analysis     || '';
  $('j-mistakes').value     = d.mistakes     || '';
}

// ─── Section 4: 工具箱 ────────────────────────────────────────────────────────
function initHealthChecker() {
  $('health-form').addEventListener('change', () => {
    const checks = {
      price:   +$('hc-price').value   || 0,
      volume:  +$('hc-volume').value  || 0,
      intraday:+$('hc-intraday').value|| 0,
      sector:  +$('hc-sector').value  || 0,
    };
    const score = Object.values(checks).reduce((s, v) => s + v, 0);
    let verdict, cls;
    if (score >= 7)      { verdict = '健康'; cls = 'verdict-green'; }
    else if (score >= 4) { verdict = '分歧'; cls = 'verdict-yellow'; }
    else                 { verdict = '见顶信号'; cls = 'verdict-red'; }
    $('health-verdict').textContent = verdict;
    $('health-verdict').className   = 'verdict ' + cls;
  });
}

function initFalseStrong() {
  $('false-strong-form').addEventListener('change', () => {
    const hit = ['fs1', 'fs2', 'fs3'].filter(id => $(id)?.checked).length;
    let verdict, cls;
    if (hit === 0)      { verdict = '无假强信号'; cls = 'verdict-green'; }
    else if (hit === 1) { verdict = '轻微疑问，观察'; cls = 'verdict-yellow'; }
    else                { verdict = `假强板块（命中${hit}条）`; cls = 'verdict-red'; }
    $('fs-verdict').textContent = verdict;
    $('fs-verdict').className   = 'verdict ' + cls;
  });
}

// ─── Alarms ───────────────────────────────────────────────────────────────────
function initAlarms() {
  const ALARMS = [
    { hm: '09:25', label: '9:25 盘前集合竞价开始' },
    { hm: '09:30', label: '9:30 开盘' },
    { hm: '10:30', label: '10:30 第一关键时间点' },
    { hm: '13:15', label: '13:15 下午关键点' },
    { hm: '14:30', label: '14:30 尾盘关键点' },
  ];

  function tick() {
    const now  = new Date();
    const hhmm = now.toTimeString().slice(0, 5);
    const next = ALARMS.find(a => a.hm > hhmm) || ALARMS[0];
    const [h, m]   = next.hm.split(':').map(Number);
    const nextDate = new Date(now);
    nextDate.setHours(h, m, 0, 0);
    if (nextDate <= now) nextDate.setDate(nextDate.getDate() + 1);
    const diff = Math.floor((nextDate - now) / 1000);
    const mm = String(Math.floor(diff / 60)).padStart(2, '0');
    const ss = String(diff % 60).padStart(2, '0');
    $('alarm-next').textContent  = `下一个提醒：${next.label}`;
    $('alarm-countdown').textContent = `${mm}:${ss}`;
  }

  setInterval(tick, 1000);
  tick();

  $('alarm-enable').addEventListener('click', async () => {
    if (!('Notification' in window)) { showToast('浏览器不支持通知'); return; }
    const perm = await Notification.requestPermission();
    if (perm === 'granted') {
      setupNotifications(ALARMS);
      showToast('提醒已开启');
    }
  });
}

function setupNotifications(alarms) {
  alarms.forEach(({ hm, label }) => {
    const [h, m] = hm.split(':').map(Number);
    function schedule() {
      const now  = new Date();
      const fire = new Date(now);
      fire.setHours(h, m, 0, 0);
      if (fire <= now) fire.setDate(fire.getDate() + 1);
      setTimeout(() => {
        new Notification('交易提醒', { body: label, icon: '/favicon.ico' });
        schedule();
      }, fire - now);
    }
    schedule();
  });
}

// ─── Toast ────────────────────────────────────────────────────────────────────
function showToast(msg) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

// ─── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  await db.open();
  initTabs();
  startMarketPoll();
  initAlarms();
  initHealthChecker();
  initFalseStrong();

  // Checklist
  const clState = await loadChecklist();
  renderChecklist(clState);

  // Journal
  const jData = await loadJournal(today());
  fillJournalForm(jData);
  $('journal-date').value = today();
  renderJournalHistory();

  $('journal-save-btn').addEventListener('click', saveJournal);
  $('journal-new-btn').addEventListener('click', () => {
    fillJournalForm({ date: today(), mainLine: '', leaders: '', topSectors: '',
      sentiment: '', riskPreference: '', analysis: '', mistakes: '无' });
    $('journal-date').value = today();
  });

  $('market-refresh-btn').addEventListener('click', refreshMarket);
}

init();
