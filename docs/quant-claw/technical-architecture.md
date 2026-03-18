# Quant Claw 技术架构

## 1. 架构概览

`quant-claw` 当前采用的是**事件驱动、多 Agent 协同**的结构。核心设计思想不是把所有逻辑堆进一个大服务，而是按决策阶段拆分职责。

主要层次包括：

- `agents/`：负责决策与动作触发
- `services/`：负责编排、执行、持仓、持久化等服务能力
- `events/`：负责事件总线抽象与 topic 定义
- `models/`：负责统一的数据结构与载荷模型
- `configs/`：负责 runtime、strategy、risk、team 配置
- `api/`：负责查询接口与模拟触发入口

## 2. 当前服务拆分

### Agents

- `ClawQuantAgent`
  - 订阅 `market.funding.updated`
  - 输出 `strategy.proposal.created`

- `ClawRiskAgent`
  - 订阅 `strategy.proposal.created`
  - 输出 `risk.check.approved` 或 `risk.check.rejected`

- `ClawTraderAgent`
  - 订阅 `risk.check.approved`
  - 输出 `execution.order.requested`

### Services

- `Orchestrator`
  - 实例化各 Agent
  - 注册订阅关系
  - 连接持久化和其他服务钩子

- `ExecutionGateway`
  - 处理执行请求
  - 调用 `PaperBroker`
  - 输出 `execution.order.filled`

- `PortfolioEngine`
  - 处理成交事件
  - 输出 `portfolio.position.updated`

- `PersistenceService`
  - 保存事件与业务实体

## 3. Topic 设计

当前已实现的 topics 包括：

- `market.funding.updated`
- `strategy.proposal.created`
- `risk.check.approved`
- `risk.check.rejected`
- `execution.order.requested`
- `execution.order.filled`
- `portfolio.position.updated`

## 4. 事件流

```text
MarketDataService / simulator
    -> market.funding.updated
        -> ClawQuantAgent
            -> strategy.proposal.created
                -> ClawRiskAgent
                    -> risk.check.approved
                        -> ClawTraderAgent
                            -> execution.order.requested
                                -> ExecutionGateway
                                    -> execution.order.filled
                                        -> PortfolioEngine
                                            -> portfolio.position.updated
```

拒绝分支如下：

```text
strategy.proposal.created
    -> ClawRiskAgent
        -> risk.check.rejected
```

## 5. 数据模型

### Event

这是系统统一的事件信封，字段包括：

- `event_id`
- `topic`
- `ts`
- `source`
- `payload`

所有 Agent 间通信都通过这个包裹结构传递。

### StrategyProposal

用于表达一个“尚未进入执行”的策略提案。主要字段包括：

- `proposal_id`
- `signal_id`
- `team_id`
- `strategy_id`
- `symbol`
- `action`
- `legs[]`
- `entry_constraints`
- `risk_context`
- `status`
- `ts`
- `note`

### RiskDecision

用于把提案转化为正式风控决策。主要字段包括：

- `decision_id`
- `proposal_id`
- `status`
- `approved_notional_usd`
- `max_leverage`
- `constraints`
- `reason_codes`
- `ts`

### ExecutionOrder

用于表达最终执行请求。主要字段包括：

- `order_request_id`
- `proposal_id`
- `idempotency_key`
- `mode`
- `venue`
- `symbol`
- `side`
- `order_type`
- `qty`
- `price`
- `constraints`
- `status`
- `ts`

## 6. 配置结构

### 基础运行配置

`configs/base.yaml`

定义：
- 应用名称与环境
- runtime mode
- 默认 team
- bus backend
- database URL
- logging level

### Team 配置

`configs/teams/btc-eth-focus.yaml`

定义：
- team id / name
- market
- symbols
- enabled agents
- enabled strategies

### 风控 / 策略配置

位于：
- `configs/risk/`
- `configs/strategies/`

这些目录后续应该成为“通过配置扩展系统”的主入口。

## 7. 环境隔离建议

### Backtest

- 使用历史数据离线回放
- 强调可重复性
- 不接真实 broker
- 需要完整事件记录能力

### Simulation / Demo

- 使用模拟或回放市场事件
- 使用 paper broker 执行
- 本地 Redis / Postgres 可选
- 用于集成验证

### Paper Trading

- 使用真实市场数据
- 不动真资金
- 但尽量保留生产形态的风控与观测能力

### Live Trading

- 接真实交易所适配器
- 加强风控、熔断、审批、审计

## 8. Topic 命名建议

当前 topic 风格是对的，建议保持：

`domain.entity.action`

例如：
- `market.funding.updated`
- `strategy.proposal.created`
- `execution.order.filled`

后续新增 topic 也建议遵循同样风格，例如：
- `market.price.tick`
- `risk.limit.triggered`
- `execution.order.cancel_requested`
- `portfolio.pnl.updated`

## 9. Schema 治理建议

随着系统变大，为避免契约漂移，建议：

- 使用 Pydantic model 作为唯一可信契约
- 避免在边界之外大量传裸 dict
- 有破坏性修改时做版本化
- 每次 schema 变化都配套 replay / simulation 测试

## 10. 部署拓扑

当前本地运行形态：

- Python 应用进程
- Redis 作为事件总线候选
- Postgres 作为持久化存储
- FastAPI 提供查询 / 操作接口

后续更像生产的部署形态建议为：

- Agent runtime 容器
- Redis / Stream 作为消息主干
- Postgres 主存储
- 日志 / 指标系统
- 运维控制台或管理 API

## 11. 当前待补齐的高优先级缺口

1. 明确 market data service 契约
2. 扩展订单生命周期状态机
3. 增加 replay / 幂等处理策略
4. 输出更正式的 API 文档
5. 抽象 live mode 交易所适配边界
6. 增加 team 级 / account 级风险聚合能力
