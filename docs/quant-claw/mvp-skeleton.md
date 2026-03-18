# Quant Claw MVP 工程骨架

## 1. 文档目的

这份文档用于把当前仓库从“能看概念”转换成“能开工实现”的工程视角，明确现有结构分别承担什么职责，以及下一步应该补哪些骨架能力。

## 2. 当前仓库结构

```text
quant-claw/
├── configs/
│   ├── base.yaml
│   ├── risk/
│   ├── strategies/
│   └── teams/
├── src/quant_claw/
│   ├── adapters/
│   ├── agents/
│   ├── api/
│   ├── apps/
│   ├── core/
│   ├── events/
│   ├── models/
│   └── services/
├── tests/
│   └── simulation/
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## 3. 模块职责说明

### `configs/`

配置层，负责 runtime mode、team 编排、strategy 参数、risk 限制等。

### `adapters/`

外部系统边界层。

当前示例：
- `paper_broker.py`
- `storage.py`

后续可扩展为：
- 交易所连接器
- 市场数据连接器
- 通知或告警适配器

### `agents/`

决策型角色层。

当前包括：
- `base.py`
- `quant.py`
- `risk.py`
- `trader.py`

### `events/`

事件传输层。

当前包括：
- `bus.py`
- `redis_bus.py`
- `topics.py`

### `models/`

核心业务模型和事件载荷模型。

当前包括：
- `event.py`
- `market.py`
- `proposal.py`
- `risk.py`
- `order.py`
- `position.py`

### `services/`

编排和副作用执行层。

当前包括：
- `orchestrator.py`
- `execution_gateway.py`
- `portfolio_engine.py`
- `market_data_service.py`
- `audit_service.py`
- `persistence_service.py`

### `api/`

查询和操作入口层。

### `apps/`

应用启动入口，例如 demo runner。

### `tests/simulation/`

模拟环境下的端到端验证。

## 4. 当前基础抽象

### BaseAgent

位置：`agents/base.py`

当前提供：
- `agent_id`
- bus / logger 注入
- 统一 `emit()` 方法
- 强制实现的 `start()` 生命周期入口

这已经构成所有 Agent 的最小复用基类。

### Event Schema

位置：`models/event.py`

这是系统统一事件信封。

### Strategy 接口

当前还没有显式抽象出来，主要隐含在：

- `StrategyProposal`
- `ClawQuantAgent`

建议下一步补成独立接口，例如：
- `strategies/base.py`
- `strategies/funding_rate_arb.py`

把“信号生成”与“提案构建”分开。

### Risk 接口

当前也仍然是隐式实现，主要体现在：

- `ClawRiskAgent`
- `RiskDecision`

建议后续拆成：
- 风控规则接口
- 风控策略组合器
- 风控结果标准化输出

### Execution Gateway 接口

当前由 `services/execution_gateway.py` + `PaperBroker` 共同承担。

建议后续正式抽象 paper / live 两类 broker 接口边界。

## 5. 当前示例 Team

结合现有配置，当前可作为示例 team 的是：

- runtime mode: `paper`
- team: `btc-eth-focus`
- strategy: `funding_rate_arb`
- symbols: `BTCUSDT`, `ETHUSDT`

这套配置很适合作为 demo、集成测试和最初 MVP 的默认运行样例。

## 6. 建议补充的下一层骨架

为了让 MVP 更容易扩展，建议下一步新增如下结构：

```text
src/quant_claw/
├── strategies/
│   ├── base.py
│   └── funding_rate_arb.py
├── risk/
│   ├── base.py
│   └── notional_limit.py
├── execution/
│   ├── broker_base.py
│   └── paper.py
└── schemas/
    └── versions.py
```

## 7. 建议开发顺序

1. 冻结 event 与核心 domain schema
2. 抽离 strategy interface
3. 抽离 risk policy interface
4. 正式定义 execution adapter interface
5. 扩充 simulation tests
6. 增加 backtest / paper / live 环境切换

## 8. 什么叫“够用的 MVP 仓库”

当前阶段不需要追求“生产级全能”，而应该达到下面这个标准：

- 新成员能装好依赖
- 能启动本地基础设施
- 能跑通 demo flow
- 能查看事件和持仓结果
- 能看明白策略、风控、执行代码应该往哪里扩展

只要做到这一点，这个仓库就已经是一个**真正能开工**的 MVP 仓库，而不是停留在 PPT 或蓝图层面。
