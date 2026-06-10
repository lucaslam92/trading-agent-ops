# 市场监控终端 · 后端服务设计文档

版本：v1.0  
日期：2026-06-06

---

## 一、目标与约束

| 目标 | 说明 |
|------|------|
| 数据源解耦 | 前端只认自定义 API 契约，换数据源不动前端代码 |
| 实时推送 | 用 SSE 替代前端 tick 模拟，由后端控制推送节奏 |
| 持久化迁移 | 日记/清单从浏览器 IndexedDB 迁移到后端 SQLite |
| 保持简单 | 个人工具，单进程部署，无需容器编排 |

---

## 二、整体架构

```
┌─────────────────────────────────────────────────┐
│                    Browser                       │
│  EventSource /api/stream  ←─── 行情推送 (SSE)   │
│  fetch /api/journal       ←──→ 日记 CRUD         │
│  fetch /api/checklist     ←──→ 清单 CRUD         │
└───────────────────┬─────────────────────────────┘
                    │ HTTP / localhost
┌───────────────────▼─────────────────────────────┐
│              FastAPI 后端                        │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  SSE Manager                             │   │
│  │  · 维护已连接客户端的 asyncio.Queue 集合 │   │
│  │  · Scheduler 有新快照时广播到全部客户端  │   │
│  └──────────────┬───────────────────────────┘   │
│                 │                                │
│  ┌──────────────▼───────────────────────────┐   │
│  │  Scheduler（asyncio 后台任务）           │   │
│  │  · 每 N 秒调用 DataAdapter.fetch()       │   │
│  │  · 维护 hist / spark 滑动窗口（内存）    │   │
│  │  · 生成完整 Snapshot，触发 SSE 广播      │   │
│  └──────────────┬───────────────────────────┘   │
│                 │                                │
│  ┌──────────────▼───────────────────────────┐   │
│  │  DataAdapter（抽象层）                   │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ │   │
│  │  │Eastmoney │ │ Tushare  │ │  Mock    │ │   │
│  │  │ httpx    │ │ SDK      │ │ 开发用   │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  REST Router  /journal  /checklist       │   │
│  └──────────────┬───────────────────────────┘   │
│                 │                                │
│  ┌──────────────▼───────────────────────────┐   │
│  │  SQLite  (aiosqlite)                     │   │
│  │  journals 表 + checklists 表             │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

---

## 三、API 契约

> 本节内容一旦确定不再修改字段名，只允许新增字段。后端实现可随时替换，前端代码不感知。

### 3.1 SSE 行情流

```
GET /api/stream
Accept: text/event-stream
```

前端订阅方式：

```js
const es = new EventSource('/api/stream');
es.addEventListener('snapshot', (e) => {
  const snapshot = JSON.parse(e.data);
  // 替换原 window.MarketData.state，调用 notify()
});
es.addEventListener('error', () => {
  // 降级：切回 mock 模拟
});
```

**Snapshot 完整 Schema：**

```jsonc
{
  // A 股指数
  "indices": [
    {
      "code": "SH000001",
      "label": "上证指数",
      "price": 3284.6,
      "changePct": 0.82,      // 百分比值，如 0.82 表示 +0.82%
      "prevClose": 3258.0
    }
  ],

  // 板块资金流
  "sectors": [
    {
      "name": "光模块",
      "changePct": 4.8,
      "netInflow": 41.2,       // 单位：亿元，正=流入，负=流出
      "theme": "AI算力",
      "hist": [4.1, 4.3, 4.8],        // 最近 40 个快照的 changePct
      "flowHist": [38.0, 40.1, 41.2]  // 最近 40 个快照的 netInflow
    }
  ],

  // 龙头个股
  "leaders": [
    {
      "code": "300308",
      "name": "中际旭创",
      "sector": "光模块",
      "price": 168.4,
      "changePct": 6.2,
      "open": 158.6,
      "volRatio": 1.4,
      "theme": "AI算力",
      "spark": [5.1, 5.5, 6.0, 6.2]  // 最近 30 个快照的 changePct
    }
  ],

  // 全球参考
  "globals": [
    {
      "code": "NDX",
      "label": "纳斯达克",
      "changePct": 0.54,
      "note": "收盘",
      "isLevel": false    // true 时 changePct 实为绝对值（如美债收益率）
    }
  ],

  // 市场宽度
  "breadth": {
    "up": 3142,
    "down": 1684,
    "flat": 220,
    "limitUp": 58,
    "limitDown": 4
  },

  // 元信息
  "source": "eastmoney",     // "eastmoney" | "tushare" | "mock"
  "updatedAt": 1717632000000 // unix 毫秒时间戳
}
```

---

### 3.2 日记接口

```
GET    /api/journal?date=2026-06-06        # 读取单条
POST   /api/journal                         # 新建或覆盖保存（body 见下）
GET    /api/journal/history?limit=30        # 最近 N 条简要列表
DELETE /api/journal?date=2026-06-06        # 删除单条
```

**单条 Journal 结构（GET / POST body）：**

```jsonc
{
  "date": "2026-06-06",
  "mainLine": "AI算力、光模块",
  "leaders": "中际旭创 300308",
  "topSectors": "通信设备、半导体",
  "sentiment": "主升",       // 枚举：冰点 | 修复 | 主升 | 高潮 | 退潮
  "risk": "科技成长",        // 枚举：科技成长 | 避险红利 | 小盘投机 | 混沌
  "analysis": "资金主线流入 AI算力（+41.2亿），流出银行。",
  "mistakes": "无",
  "updatedAt": 1717632000000
}
```

**History 列表结构（仅摘要，减少传输量）：**

```jsonc
[
  { "date": "2026-06-06", "mainLine": "AI算力", "sentiment": "主升" },
  { "date": "2026-06-05", "mainLine": "半导体", "sentiment": "修复" }
]
```

---

### 3.3 清单接口

```
GET  /api/checklist?date=2026-06-06        # 读取今日清单
POST /api/checklist                         # 保存（整体覆盖）
```

**Checklist 结构：**

```jsonc
{
  "date": "2026-06-06",
  "checks": {
    "p1": true,
    "p2": false,
    "m1": true
  },
  "notes": {
    "p1": "纳指+0.5 恒科+0.8 美债4.30 一句话：科技偏强",
    "m1": "前三=光模块/通信/算力 龙头高开+3 涨家3200"
  },
  "updatedAt": 1717632000000
}
```

---

## 四、数据库 Schema

```sql
-- journals 表
CREATE TABLE IF NOT EXISTS journals (
  date         TEXT PRIMARY KEY,   -- "YYYY-MM-DD"
  main_line    TEXT NOT NULL DEFAULT '',
  leaders      TEXT NOT NULL DEFAULT '',
  top_sectors  TEXT NOT NULL DEFAULT '',
  sentiment    TEXT NOT NULL DEFAULT '',
  risk         TEXT NOT NULL DEFAULT '',
  analysis     TEXT NOT NULL DEFAULT '',
  mistakes     TEXT NOT NULL DEFAULT '无',
  updated_at   INTEGER NOT NULL     -- unix 毫秒
);

-- checklists 表
CREATE TABLE IF NOT EXISTS checklists (
  date       TEXT PRIMARY KEY,
  checks     TEXT NOT NULL DEFAULT '{}',   -- JSON 字符串
  notes      TEXT NOT NULL DEFAULT '{}',   -- JSON 字符串
  updated_at INTEGER NOT NULL
);
```

---

## 五、核心模块设计

### 5.1 DataAdapter（抽象基类）

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class RawSnapshot:
    """Adapter 返回的原始数据，不含滑窗历史"""
    indices: list[dict]
    sectors: list[dict]   # 只含当前 changePct / netInflow
    leaders: list[dict]
    globals: list[dict]
    breadth: dict
    source: str

class DataAdapter(ABC):
    @abstractmethod
    async def fetch(self) -> RawSnapshot: ...
```

每个 Adapter 只负责从数据源取一次当前值，归一化成 `RawSnapshot`。**不持有历史**，hist/spark 滑窗由 Scheduler 统一维护。

---

### 5.2 Scheduler（滑窗 + 广播）

```
启动时：
  · 初始化各板块/龙头的 hist deque（maxlen=40/30）

每次 tick：
  1. await adapter.fetch() → RawSnapshot
  2. 将新值追加进各 deque
  3. 组装完整 Snapshot（含 hist 列表）
  4. 调用 sse_manager.broadcast(snapshot)
  5. 等待 interval 秒
```

关键点：
- `hist` / `spark` 使用 `collections.deque(maxlen=N)`，自动丢弃最旧值
- 服务重启后历史清零（重新从当前值开始积累），属预期行为

---

### 5.3 SSE Manager

```python
class SSEManager:
    def __init__(self):
        self._clients: set[asyncio.Queue] = set()

    def connect(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._clients.add(q)
        return q

    def disconnect(self, q: asyncio.Queue):
        self._clients.discard(q)

    def broadcast(self, snapshot: dict):
        payload = json.dumps(snapshot, ensure_ascii=False)
        for q in self._clients:
            q.put_nowait(payload)
```

SSE 端点：

```python
@router.get("/api/stream")
async def stream(request: Request):
    q = sse_manager.connect()
    async def generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                payload = await asyncio.wait_for(q.get(), timeout=30)
                yield f"event: snapshot\ndata: {payload}\n\n"
        finally:
            sse_manager.disconnect(q)
    return StreamingResponse(generator(), media_type="text/event-stream")
```

---

### 5.4 Eastmoney Adapter

与前端 JSONP 调用的接口完全相同，改为服务端 `httpx` 请求（无 CORS 限制）：

- 指数：`push2.eastmoney.com/api/qt/stock/get`
- 板块资金流：`push2.eastmoney.com/api/qt/clist/get`
- 龙头个股：同指数接口，批量 secid

---

### 5.5 Mock Adapter

将 `lib/data.js` 中的 seed 数据和 tick 随机游走逻辑移植到 Python，用于本地开发和无网络环境。`source` 字段固定返回 `"mock"`。

---

## 六、前端改动范围

| 文件 | 改动 |
|------|------|
| `lib/data.js` | 删除 JSONP / tick 模拟；改为 EventSource 监听 `/api/stream`，收到 snapshot 后更新 state 并 notify |
| `lib/store.js` | 删除；IndexedDB 逻辑全部下线 |
| `review-screens.jsx` | `ChecklistScreen` / `JournalScreen` 的 load/save 改为 `fetch /api/*` |
| 其他文件 | **不动** |

---

## 七、技术栈汇总

| 层 | 选型 | 说明 |
|----|------|------|
| Web 框架 | FastAPI | 原生 async，SSE StreamingResponse 支持好 |
| ASGI 服务器 | Uvicorn | 配套，`--reload` 开发模式 |
| 数据库驱动 | aiosqlite | 异步 SQLite，无需 ORM |
| HTTP 客户端 | httpx（async） | 服务端调东方财富 / 全球行情接口 |
| 数据源 A | 东方财富 HTTP | 实时指数 + 板块资金流 |
| 数据源 B | Tushare SDK | 日频补充、盘后核验 |
| 数据源 C | Mock（内置） | 开发 / 无网络回退 |
| 前端框架 | React 18（不变） | 只改数据层，组件层不动 |
