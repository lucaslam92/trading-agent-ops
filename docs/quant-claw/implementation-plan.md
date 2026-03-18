# Quant Claw 实施方案

## 1. 项目目标

`quant-claw` 是一个多 Agent 协同的量化交易 MVP，当前聚焦在一条窄而完整、可以真正跑通的闭环路径：

- 市场：Crypto
- 标的：BTC / ETH
- 运行环境：模拟盘 / 纸面交易优先
- 控制流：市场事件 -> 策略提案 -> 风控审批 -> 执行请求 -> 成交回报 -> 持仓更新

现阶段目标不是一次性做成完整生产级交易平台，而是先验证一个**可测试、可评审、可扩展**的执行框架：

- 证明核心交易闭环可运行
- 明确不同 Agent / Service 的职责边界
- 为后续回测、模拟盘、实盘扩展打下干净结构

## 2. 范围边界

### 当前纳入范围

- 事件驱动的 Agent 协同模式
- 基于资金费率的示例策略链路
- 执行前的风控审批
- 基于 paper broker 的模拟执行
- 持仓落库与状态更新
- 用于健康检查、持仓查询、事件查询、模拟触发的 API
- 基于配置的 team / strategy / runtime 选择机制

### 当前不纳入范围

- 真实交易所下单
- 完整的 OMS / EMS 能力
- 多账户生产级对账
- 高级组合优化
- 跨 venue 智能路由
- 完整合规审批流与审计留痕体系
- 策略市场或自动化 Alpha 研究平台

## 3. 角色职责

### Claw Quant Agent

消费市场资金费率更新事件，在满足阈值条件时生成结构化策略提案。

### Claw Risk Agent

对策略提案进行风控评估，并输出通过或拒绝结果。

### Claw Trader Agent

把风控通过的结果转为可执行订单请求。

### Execution Gateway

接收订单请求，调用 paper broker 执行，产生成交事件，并负责订单侧落库。

### Portfolio Engine

消费成交事件，更新当前持仓状态。

### Orchestrator

负责组装 Agent 与 Service，注册订阅关系，并挂接持久化逻辑。

## 4. 系统主流程

1. 市场侧产生 `market.funding.updated`
2. `ClawQuantAgent` 输出 `strategy.proposal.created`
3. `ClawRiskAgent` 对提案做风控检查
4. 风控输出以下两类结果之一：
   - `risk.check.approved`
   - `risk.check.rejected`
5. `ClawTraderAgent` 将通过结果转换为 `execution.order.requested`
6. `ExecutionGateway` 在 paper 模式下执行，并输出 `execution.order.filled`
7. `PortfolioEngine` 基于成交结果更新 `portfolio.position.updated`

## 5. 风控体系

当前已实现的风控能力比较轻，但结构上是正确的，主要包括：

- 按提案请求名义本金进行限额判断
- 明确区分通过 / 拒绝两类事件
- 在风控决策中附带杠杆和滑点限制
- 在风控结果里附带 reason codes

当前示例默认值：

- 单策略最大名义本金：`30000`
- 允许最大杠杆：`1.5`
- 最大滑点限制：`10 bps`

建议后续补强的风控层：

- 单标的敞口上限
- team 级 gross / net 敞口约束
- 账户级回撤熔断
- venue 健康状态 / 停机保护
- 重复信号 / 重复订单抑制
- 实盘模式下人工审批或更高等级控制

## 6. 分阶段实施

### 阶段 1：跑通 MVP 闭环

交付内容：
- 可用事件总线
- quant / risk / trader 三类 Agent
- paper execution gateway
- position update engine
- simulation demo flow

### 阶段 2：架构加固

交付内容：
- Redis 作为默认事件总线
- 更完整的持久化模型
- 更丰富的事件 Schema
- 幂等与回放支持
- 更完善的观测与审计能力

### 阶段 3：策略与环境扩展

交付内容：
- 多策略 / 多 team 配置
- 回测 / 模拟 / 纸面交易隔离
- 交易所适配器扩展
- 更完整的组合与风险控制体系

### 阶段 4：走向生产可用

交付内容：
- 实盘保护措施
- 监控与告警
- 运维 runbook
- 治理 / 审批 / 合规流程

## 7. 验收标准

MVP 可视为通过的标准包括：

- 一次资金费率更新可以自动触发策略提案
- 提案能被风控稳定地判定通过或拒绝
- 风控通过后能生成执行请求
- 执行请求能在 paper 模式产生成交事件
- 成交后能稳定更新持仓
- API 能查询关键状态
- demo flow 测试可端到端通过

## 8. 风险与控制

### 交付风险

- 架构在核心闭环稳定前就过度发散
- Agent 之间的数据契约不一致
- 风控逻辑长期停留在隐式状态
- paper 模式假设污染后续实盘架构

### 控制建议

- 尽早冻结事件 Schema
- 保持每个 Agent 的职责单一
- 对配置和事件载荷进行版本管理
- 每新增一条策略路径都配套 simulation 测试

## 9. 下一步建议产物

下一批最值得补充的项目文档应包括：

1. 技术架构说明文档
2. Topic / Payload 协议文档
3. MVP 工程骨架说明
4. 从 sim -> paper -> live 的分阶段演进路线
