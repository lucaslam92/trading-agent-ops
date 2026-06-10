# 市场监控终端 · 后端服务执行计划

版本：v1.0  
日期：2026-06-06  
依赖：market-backend-design.md

---

## 阶段总览

```
Phase 1  后端骨架 + 持久化 REST          约 1–2 天
Phase 2  前端持久化迁移                  约 0.5 天
Phase 3  SSE 行情推送（Mock 数据源）     约 1–2 天
Phase 4  接入真实数据源                  约 1–2 天
```

每个 Phase 结束后可独立验收，不依赖后续 Phase。

---

## Phase 1：后端骨架 + 持久化 REST

**目标**：建立项目结构，完成日记/清单的增删改查接口，前端暂不改动。

### 1.1 项目结构初始化

```
trading-agent-ops/
└── market-api/                  ← 新建目录
    ├── main.py                  ← FastAPI app 入口
    ├── database.py              ← SQLite 连接 + 建表
    ├── routers/
    │   ├── journal.py           ← /api/journal 路由
    │   └── checklist.py         ← /api/checklist 路由
    ├── models.py                ← Pydantic 数据模型
    ├── requirements.txt
    └── market.db                ← SQLite 文件（运行后自动生成）
```

### 1.2 依赖安装

```
# requirements.txt
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
aiosqlite>=0.20.0
httpx>=0.27.0
tushare>=1.4.0
```

```bash
cd trading-agent-ops/market-api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 1.3 数据库初始化（database.py）

- 建立 aiosqlite 连接池
- `CREATE TABLE IF NOT EXISTS journals ...`
- `CREATE TABLE IF NOT EXISTS checklists ...`
- 表结构见 design.md §四

### 1.4 Pydantic 模型（models.py）

需定义以下模型，字段与 design.md §三 API 契约完全对应：

- `JournalIn`：POST body
- `JournalOut`：GET 响应（含 updatedAt）
- `JournalSummary`：history 列表项（date / mainLine / sentiment）
- `ChecklistIn`：POST body
- `ChecklistOut`：GET 响应

### 1.5 日记路由（routers/journal.py）

| 端点 | 逻辑要点 |
|------|---------|
| `GET /api/journal?date=` | 查无返回 404 |
| `POST /api/journal` | INSERT OR REPLACE，自动写 updated_at = now() |
| `GET /api/journal/history?limit=30` | ORDER BY date DESC，只返回 JournalSummary 字段 |
| `DELETE /api/journal?date=` | 删无返回 404 |

### 1.6 清单路由（routers/checklist.py）

| 端点 | 逻辑要点 |
|------|---------|
| `GET /api/checklist?date=` | 查无返回空结构（`checks: {}`, `notes: {}`）而非 404，方便前端 |
| `POST /api/checklist` | checks / notes 字段 JSON 序列化后写 TEXT 列 |

### 1.7 CORS 配置（main.py）

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 本地开发，后续可收窄为 127.0.0.1
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 1.8 启动与验收

```bash
uvicorn main:app --reload --port 8000
```

验收清单：
- [ ] `GET /api/journal?date=2026-06-06` → 404（无记录时）
- [ ] `POST /api/journal` 写入后再 GET → 数据一致
- [ ] `GET /api/journal/history?limit=5` → 返回列表
- [ ] `DELETE /api/journal?date=` → 再 GET 返回 404
- [ ] `GET /api/checklist?date=` → 返回空结构（非 404）
- [ ] `POST /api/checklist` 保存后再 GET → checks/notes 一致
- [ ] SQLite 文件可直接用 DB Browser 打开查看数据

---

## Phase 2：前端持久化迁移

**目标**：日记/清单读写全部切换到后端 API，删除 IndexedDB 依赖。

### 2.1 抽取请求工具函数（新建 lib/api.js）

```js
const BASE = 'http://localhost:8000';

export const api = {
  async getJournal(date)     { return fetch(`${BASE}/api/journal?date=${date}`).then(r => r.ok ? r.json() : null); },
  async saveJournal(body)    { return fetch(`${BASE}/api/journal`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) }).then(r => r.json()); },
  async journalHistory(n=30) { return fetch(`${BASE}/api/journal/history?limit=${n}`).then(r => r.json()); },
  async getChecklist(date)   { return fetch(`${BASE}/api/checklist?date=${date}`).then(r => r.json()); },
  async saveChecklist(body)  { return fetch(`${BASE}/api/checklist`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) }).then(r => r.json()); },
};
```

在 `金融市场监控终端.html` 中 `<script src="lib/api.js">` 替换掉 `store.js`。

### 2.2 改造 ChecklistScreen（review-screens.jsx）

| 原代码 | 改为 |
|--------|------|
| `_store().get('checklists', date)` | `api.getChecklist(date)` |
| `_store().save('checklists', ...)` | `api.saveChecklist(...)` |
| `persist()` 函数 | 直接 `api.saveChecklist({ date, checks, notes })`（不再需要先读再写，消除竞争） |

关键：`setNote` 和 `toggle` 都直接传当前最新 state 给 API，不需要从数据库读旧值再合并。

### 2.3 改造 JournalScreen（review-screens.jsx）

| 原代码 | 改为 |
|--------|------|
| `_store().get('journals', date)` | `api.getJournal(date)` |
| `_store().save('journals', form)` | `api.saveJournal(form)` |
| `_store().getAll('journals')` | `api.journalHistory(30)` |

### 2.4 删除 store.js 引用

- `金融市场监控终端.html` 中删除 `<script src="lib/store.js">`
- 如需保留离线回退，可保留文件但不引用

### 2.5 验收

- [ ] 日记保存后刷新页面数据仍在
- [ ] 历史记录列表正常显示
- [ ] 切换日期加载对应记录
- [ ] 清单勾选状态跨 tab 同步（两个窗口打开同一页面，一边保存另一边刷新可见）
- [ ] 快速输入时不丢数据（原 IndexedDB 竞争问题已消除）

---

## Phase 3：SSE 行情推送（Mock 数据源）

**目标**：用 Python Mock Adapter 驱动 SSE，前端改为监听 EventSource，删除 tick 模拟逻辑。

### 3.1 Mock Adapter（adapters/mock.py）

将 `lib/data.js` 中的以下内容移植到 Python：

- `SECTOR_SEED`、`LEADER_SEED`、`INDEX_SEED`、`GLOBAL_SEED`、`BREADTH_SEED`（直接翻译为 Python dict）
- `tick()` 逻辑：theme drift 随机游走（`random.uniform`）
- `clamp()` / `round()` 工具函数

`MockAdapter.fetch()` 每次调用执行一次 tick，返回 `RawSnapshot`（当前值，不含 hist）。

### 3.2 Scheduler（scheduler.py）

```python
from collections import deque

class Scheduler:
    def __init__(self, adapter, sse_manager, interval=2.2):
        self.adapter = adapter
        self.sse = sse_manager
        self.interval = interval
        # 为每个 sector / leader 维护滑窗
        self._sector_hist  = {}   # name → deque(maxlen=40) for changePct
        self._sector_flow  = {}   # name → deque(maxlen=40) for netInflow
        self._leader_spark = {}   # code → deque(maxlen=30)

    async def run(self):
        while True:
            raw = await self.adapter.fetch()
            snapshot = self._build_snapshot(raw)
            self.sse.broadcast(snapshot)
            await asyncio.sleep(self.interval)

    def _build_snapshot(self, raw) -> dict:
        # 1. 更新滑窗
        for s in raw.sectors:
            self._sector_hist.setdefault(s['name'], deque(maxlen=40)).append(s['changePct'])
            self._sector_flow.setdefault(s['name'], deque(maxlen=40)).append(s['netInflow'])
        for l in raw.leaders:
            self._leader_spark.setdefault(l['code'], deque(maxlen=30)).append(l['changePct'])
        # 2. 组装 snapshot（含 hist 列表）
        ...
        return snapshot
```

### 3.3 SSE Manager（sse_manager.py）

实现 `connect()` / `disconnect()` / `broadcast()` 方法，见 design.md §5.3。

### 3.4 SSE 路由（routers/stream.py）

```python
@router.get("/api/stream")
async def stream(request: Request):
    q = sse_manager.connect()
    async def generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"event: snapshot\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"   # 防止代理/浏览器断连
        finally:
            sse_manager.disconnect(q)
    return StreamingResponse(generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

### 3.5 改造前端 lib/data.js

删除：
- `jsonp()` 函数
- `fetchOneIndex()` / `fetchIndices()` / `fetchSectorFlow()`
- `SECTOR_SEED`、`LEADER_SEED`、`INDEX_SEED`、`GLOBAL_SEED` 所有 seed 数据
- `tick()` 函数和 `setInterval` 逻辑
- `start()` / `stop()` 函数
- `subs`、`notify`、`timer` 内部状态

保留并改写：
- `state` 对象（初始值改为空结构）
- `subscribe()` / `notify()`（逻辑不变）
- `themeAgg()` / `fmtFlow()` / `fmtPct()` / `cls()`（工具函数不变）

新增：

```js
function connectSSE() {
  const es = new EventSource('http://localhost:8000/api/stream');
  es.addEventListener('snapshot', (e) => {
    const snap = JSON.parse(e.data);
    Object.assign(state, snap);
    notify();
  });
  es.onerror = () => {
    // 可选：重连逻辑，或显示断线提示
    state.source = 'disconnected';
    notify();
  };
  return es;
}

window.MarketData = {
  state, subscribe, themeAgg,
  connect: connectSSE,   // 由 App 在 useEffect 中调用
  fmtFlow, fmtPct, cls,
};
```

在 `金融市场监控终端.html` 的 App 组件中：

```js
useEffect(() => {
  const es = window.MarketData.connect();
  return () => es.close();
}, []);
// 删除原来的 MarketData.stop() / start() / tryLive() 调用
```

### 3.6 验收

- [ ] 浏览器 DevTools → Network → `stream` 请求保持连接，EventStream 标签持续收到事件
- [ ] 行情数据每 2.2 秒更新，旋转图气泡动起来
- [ ] LiveChip 显示"模拟数据"（source: "mock"）
- [ ] 关闭后端进程，前端 onerror 触发，LiveChip 状态变化
- [ ] 多个浏览器 Tab 同时打开，数据同步

---

## Phase 4：接入真实数据源

**目标**：实现 EastmoneyAdapter，通过环境变量切换数据源，LiveChip 显示"实时行情"。

### 4.1 EastmoneyAdapter（adapters/eastmoney.py）

将前端 `data.js` 中的 JSONP URL 改为服务端 `httpx.AsyncClient` 请求，相同接口，无 CORS 问题：

| 数据 | URL |
|------|-----|
| 指数 | `https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f170,f48&fltt=2&invt=2` |
| 板块资金流 | `https://push2.eastmoney.com/api/qt/clist/get?fs=m:90+t:2&fields=f12,f14,f62,f3&fid=f62&pn=1&pz=30&fltt=2&invt=2` |
| 龙头个股 | `https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f57,f58,f169,f170,f47&fltt=2&invt=2` |

注意事项：
- 使用单个 `httpx.AsyncClient` 实例（连接复用）
- 设置 `timeout=6.0`，请求失败时 raise，由 Scheduler 捕获并回退 mock
- `source` 字段返回 `"eastmoney"`

### 4.2 全球参考补充（可选）

东方财富无法覆盖的 NVDA / 原油 / 美债，可接 Yahoo Finance 非官方接口：

```
https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d
```

服务端调用无 CORS 问题。此接口不稳定，建议包装 try/except，失败时保留上次值。

### 4.3 Tushare Adapter（adapters/tushare_adapter.py）

主要用于盘后补充：

| 功能 | Tushare 接口 |
|------|-------------|
| 板块资金流历史 | `moneyflow_ths`（需 2000 积分） |
| 涨跌停列表 | `limit_list`（需 2000 积分） |
| 个股日频行情 | `daily` |

建议用法：盘后 15:30 之后，定时任务调用 Tushare 拉取当日真实数据，写入 SQLite 供日记"带入今日盘面"功能使用，而非实时推送。

### 4.4 环境变量配置

```bash
# .env
ADAPTER=eastmoney      # eastmoney | tushare | mock
TICK_INTERVAL=5.0      # 秒，真实数据可适当放宽
TUSHARE_TOKEN=xxxx
```

```python
# config.py
import os
ADAPTER = os.getenv("ADAPTER", "mock")
TICK_INTERVAL = float(os.getenv("TICK_INTERVAL", "2.2"))
```

```python
# main.py startup
if ADAPTER == "eastmoney":
    adapter = EastmoneyAdapter()
elif ADAPTER == "tushare":
    adapter = TushareAdapter()
else:
    adapter = MockAdapter()
```

### 4.5 验收

- [ ] `ADAPTER=eastmoney uvicorn main:app --port 8000` 启动后无报错
- [ ] LiveChip 显示"实时行情"（source: "eastmoney"）
- [ ] 上证指数价格与东方财富 App 误差 < 0.1
- [ ] 板块资金流排序与东财基本一致
- [ ] 东财接口超时时 Scheduler 不崩溃，自动用上次数据重发

---

## 附：文件变更清单

### 新增（后端）

```
market-api/
├── main.py
├── config.py
├── database.py
├── models.py
├── scheduler.py
├── sse_manager.py
├── adapters/
│   ├── base.py
│   ├── mock.py
│   ├── eastmoney.py
│   └── tushare_adapter.py
├── routers/
│   ├── journal.py
│   ├── checklist.py
│   └── stream.py
├── requirements.txt
└── .env.example
```

### 修改（前端）

```
market-terminal/
├── lib/
│   ├── data.js          ← 大改：删除 mock/tick，改为 SSE EventSource
│   ├── api.js           ← 新增：REST 请求封装（替换 store.js）
│   └── store.js         ← 删除引用（文件可保留）
├── review-screens.jsx   ← 改：load/save 调用 api.js
└── 金融市场监控终端.html ← 小改：调整 script 引用顺序，删除 store.js
```

### 不动

```
market-terminal/
├── lib/components.jsx   ← 不动
├── lib/tokens.css       ← 不动
├── app-screens.jsx      ← 不动
├── tweaks-panel.jsx     ← 不动
└── review-screens.jsx   ← 仅改数据请求，组件结构不动
```
