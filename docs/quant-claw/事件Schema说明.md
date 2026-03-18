# Quant Claw 事件 Schema 说明

## 1. 文档目的

本文档整理 `quant-claw` 当前事件驱动链路中涉及的核心数据模型，帮助开发者快速理解：

- 事件信封长什么样
- 各阶段 payload 里应该放什么
- 当前模型之间如何衔接

## 2. 总体结构

系统中的事件统一由两部分组成：

1. **事件信封 `Event`**
2. **业务载荷模型**（如 `StrategyProposal`、`RiskDecision`、`ExecutionOrder` 等）

也就是说，传输时是：

```text
Event(topic, source, payload=<某个业务模型序列化结果>)
```

## 3. Event 信封

位置：`src/quant_claw/models/event.py`

### 字段定义

| 字段 | 类型 | 含义 |
|---|---|---|
| `event_id` | `str` | 事件唯一标识 |
| `topic` | `str` | 事件主题 |
| `ts` | `int` | 事件时间戳（毫秒） |
| `source` | `str` | 事件来源 |
| `payload` | `dict` | 业务数据 |

### 设计意义

- `Event` 负责传输统一性
- `payload` 负责承载阶段性业务数据
- 所有 Agent 只关心自己订阅的 topic 和对应 payload 结构

## 4. 市场数据载荷

当前市场资金费率事件由 `MarketDataService.publish_mock_funding()` 生成，payload 类似：

```json
{
  "exchange": "binance",
  "symbol": "BTCUSDT",
  "funding_rate": 0.00016,
  "annualized_rate": 0.18,
  "next_funding_ts": 1773774600000
}
```

建议后续将其抽象为显式模型，例如 `FundingUpdate` 文档化后单独维护字段说明。

## 5. StrategyProposal

位置：`src/quant_claw/models/proposal.py`

### 用途

表示策略 Agent 产生的一次正式提案，尚未进入执行。

### 字段说明

| 字段 | 类型 | 含义 |
|---|---|---|
| `proposal_id` | `str` | 提案 ID |
| `signal_id` | `str` | 信号 ID |
| `team_id` | `str` | 所属策略团队 |
| `strategy_id` | `str` | 策略标识 |
| `symbol` | `str` | 交易标的 |
| `action` | `str` | 动作类型 |
| `legs` | `List[TradeLeg]` | 分腿交易结构 |
| `entry_constraints` | `Dict[str, float]` | 入场约束 |
| `risk_context` | `Dict[str, float]` | 风控上下文 |
| `status` | `ProposalStatus` | 提案状态 |
| `ts` | `int` | 生成时间 |
| `note` | `Optional[str]` | 备注 |

### TradeLeg 子结构

| 字段 | 类型 | 含义 |
|---|---|---|
| `venue` | `str` | 执行 venue |
| `side` | `str` | 买卖方向 |
| `qty` | `float` | 数量 |

## 6. RiskDecision

位置：`src/quant_claw/models/risk.py`

### 用途

表示风控对某个提案给出的正式决策结果。

### 字段说明

| 字段 | 类型 | 含义 |
|---|---|---|
| `decision_id` | `str` | 风控决策 ID |
| `proposal_id` | `str` | 对应提案 ID |
| `status` | `RiskDecisionStatus` | 通过 / 拒绝 |
| `approved_notional_usd` | `float` | 通过的名义本金 |
| `max_leverage` | `float` | 最大杠杆 |
| `constraints` | `Dict[str, float]` | 执行约束 |
| `reason_codes` | `List[str]` | 决策原因码 |
| `ts` | `int` | 决策时间 |

## 7. ExecutionOrder

位置：`src/quant_claw/models/order.py`

### 用途

表示执行层真正消费的订单请求。

### 字段说明

| 字段 | 类型 | 含义 |
|---|---|---|
| `order_request_id` | `str` | 订单请求 ID |
| `proposal_id` | `str` | 来源提案 ID |
| `idempotency_key` | `str` | 幂等键 |
| `mode` | `str` | 运行模式，例如 paper |
| `venue` | `str` | 执行 venue |
| `symbol` | `str` | 交易标的 |
| `side` | `str` | 方向 |
| `order_type` | `str` | 订单类型 |
| `qty` | `float` | 数量 |
| `price` | `Optional[float]` | 价格 |
| `constraints` | `Dict[str, float]` | 执行约束 |
| `status` | `OrderStatus` | 订单状态 |
| `ts` | `int` | 创建时间 |

## 8. 成交后扩展字段

`ExecutionGateway` 在成交后会输出 `execution.order.filled`，其 payload 基于 `ExecutionOrder` 扩展出：

- `fill_price`
- `filled_qty`
- `fee`
- `slippage_bps`

也就是说，成交事件本质上是：

```text
ExecutionOrder + Fill Result
```

## 9. PositionSnapshot

位置：`src/quant_claw/models/position.py`

从当前组合更新逻辑可以看出，持仓侧至少包含这些字段：

- `account_id`
- `strategy_id`
- `symbol`
- `net_qty`
- `gross_long_qty`
- `gross_short_qty`
- `avg_entry_price`
- `realized_pnl`
- `margin_used`

这是 `portfolio.position.updated` 的核心输出。

## 10. Schema 之间的衔接关系

```text
Funding Update Payload
  -> StrategyProposal
     -> RiskDecision
        -> ExecutionOrder
           -> Filled Order Payload
              -> PositionSnapshot
```

这条链条就是当前 MVP 的主业务数据演化路径。

## 11. 当前 Schema 的优点与缺口

### 优点

- 模型分层清晰
- 事件信封统一
- 风控、执行、持仓各阶段有独立模型
- 基于 Pydantic，便于验证和序列化

### 缺口

- 市场数据模型文档化不充分
- 成交事件还是“订单 + 扩展字段”的轻量拼接
- 缺少显式 schema version 字段
- 缺少拒绝原因码和执行状态码的规范文档

## 12. 后续建议

1. 为市场数据、成交结果、审计事件补独立模型
2. 为关键 payload 增加版本号
3. 输出 reason code / status code 字典文档
4. 为每类 topic 提供 JSON 样例
