# Quant Claw API 接口说明

## 1. 文档目的

本文档说明 `quant-claw` 当前已经提供的 API 接口，包括用途、请求方式、参数和响应示例。

当前 API 主要面向：

- 健康检查
- 事件查询
- 持仓查询
- 模拟资金费率触发

## 2. 服务信息

默认应用：

- 框架：FastAPI
- 服务名：`quant-claw`
- 默认端口：`8000`

本地访问示例：

```text
http://127.0.0.1:8000
```

## 3. 接口列表

### 3.1 健康检查

#### `GET /health`

用途：确认 API 服务是否正常运行。

示例请求：

```bash
curl http://127.0.0.1:8000/health
```

示例响应：

```json
{
  "status": "ok"
}
```

---

### 3.2 查询事件列表

#### `GET /events`

用途：查询最近的事件记录。

说明：
- 当前默认返回最近 100 条事件
- 按时间倒序返回

示例请求：

```bash
curl http://127.0.0.1:8000/events
```

示例响应：

```json
[
  {
    "event_id": "evt_order_fill_001",
    "topic": "execution.order.filled",
    "source": "execution_gateway",
    "payload": {
      "order_request_id": "ordreq_001",
      "proposal_id": "prop_001",
      "symbol": "BTCUSDT"
    },
    "ts": 1773790005000
  },
  {
    "event_id": "evt_order_req_001",
    "topic": "execution.order.requested",
    "source": "claw_trader",
    "payload": {
      "proposal_id": "prop_001"
    },
    "ts": 1773790004000
  }
]
```

---

### 3.3 查询持仓

#### `GET /positions`

用途：查询当前持仓结果。

示例请求：

```bash
curl http://127.0.0.1:8000/positions
```

示例响应：

```json
[
  {
    "account_id": "sim_main",
    "strategy_id": "funding_rate_arb",
    "symbol": "BTCUSDT",
    "net_qty": -0.1,
    "gross_long_qty": 0.0,
    "gross_short_qty": 0.1,
    "avg_entry_price": 70000.0,
    "realized_pnl": -2.8,
    "margin_used": 4000,
    "ts": 1773790006000
  }
]
```

---

### 3.4 触发模拟资金费率事件

#### `POST /simulate/funding`

用途：手动触发一次模拟资金费率更新，用于驱动主链路。

#### Query 参数

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `symbol` | `str` | `BTCUSDT` | 交易标的 |
| `annualized_rate` | `float` | `0.18` | 年化资金费率 |

示例请求：

```bash
curl -X POST "http://127.0.0.1:8000/simulate/funding?symbol=BTCUSDT&annualized_rate=0.18"
```

示例响应：

```json
{
  "accepted": true,
  "symbol": "BTCUSDT",
  "annualized_rate": 0.18
}
```

说明：
- 当前策略中，若 `annualized_rate` 低于阈值，则可能不会触发提案
- 建议使用较高值验证完整闭环，例如 `0.18`

## 4. 推荐联调流程

建议按以下顺序使用 API：

1. 调用 `/health` 检查服务可用性
2. 调用 `/simulate/funding` 触发模拟事件
3. 调用 `/events` 检查事件链路是否生成
4. 调用 `/positions` 检查持仓是否更新

## 5. 当前限制

当前 API 仍然偏 MVP 级，存在以下限制：

- 没有分页
- 没有过滤条件
- 没有鉴权
- 没有 OpenAPI 风格的业务级文档整理
- 没有 proposal / risk / order 的独立查询接口

## 6. 后续建议补充接口

建议后续增加：

- `GET /proposals`
- `GET /risk-decisions`
- `GET /orders`
- `GET /positions/{symbol}`
- `POST /simulate/price`
- `POST /simulate/replay`

## 7. 后续建议补充能力

为了更适合测试和运维，API 层建议逐步增加：

- 分页与过滤
- 时间范围查询
- topic 过滤
- symbol 过滤
- structured error response
- API 认证与权限控制
