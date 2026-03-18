# Quant Claw MVP 待办与里程碑

## 1. 文档目的

本文档用于把 `quant-claw` 从“方向明确”推进到“任务可执行”，将当前阶段应做的事情拆成 backlog、优先级和里程碑。

## 2. 当前阶段目标

当前目标不是直接上线实盘，而是完成以下三件事：

1. 跑稳核心闭环
2. 冻结关键协议与 Schema
3. 为后续扩展留出清晰边界

## 3. MVP Backlog

### P0：必须优先完成

#### 1）主链路稳定性

- [ ] 补齐 simulation 主链路测试覆盖
- [ ] 增加 risk reject 分支测试
- [ ] 增加 execution fill 异常路径测试
- [ ] 增加重复事件 / 幂等性测试

#### 2）契约冻结

- [ ] 冻结核心 topic 列表
- [ ] 冻结 `Event / StrategyProposal / RiskDecision / ExecutionOrder` 字段定义
- [ ] 为关键 payload 补 JSON 示例
- [ ] 明确 reason code / status code 文档

#### 3）工程边界清晰化

- [ ] 抽离 strategy interface
- [ ] 抽离 risk policy interface
- [ ] 抽离 broker / execution adapter interface
- [ ] 明确 market data service 契约

### P1：应尽快完成

#### 4）可观测性与运维基础

- [ ] 增加结构化日志字段规范
- [ ] 增加事件追踪 ID 关联策略
- [ ] 增加基础 metrics 设计
- [ ] 增加审计事件说明

#### 5）持久化增强

- [ ] 统一事件落库格式
- [ ] 增加 proposal / risk / order / position 的查询接口说明
- [ ] 明确历史事件保留策略
- [ ] 设计回放所需的数据保留模型

#### 6）配置能力增强

- [ ] 补充 strategy 配置说明
- [ ] 补充 risk 配置说明
- [ ] 支持多 team 配置示例
- [ ] 增加 sim / paper / live 环境配置模板

### P2：后续扩展项

#### 7）环境扩展

- [ ] 增加 backtest 模式设计文档
- [ ] 增加 paper trading 真实行情接入边界说明
- [ ] 增加 live trading 安全控制方案

#### 8）策略扩展

- [ ] 除 funding rate 之外增加第二个示例策略
- [ ] 设计 strategy registry
- [ ] 支持 team 内多策略并行

## 4. 建议里程碑

### Milestone 1：闭环稳态版

目标：现有 demo 路径稳定可复现。

验收标准：
- 主链路测试通过
- reject 分支测试通过
- API 可查询事件与持仓
- 文档能支撑新成员理解系统

### Milestone 2：契约固化版

目标：Topic、Schema、接口边界不再随意漂移。

验收标准：
- 核心 topic 清单冻结
- 核心模型字段冻结
- JSON 示例齐备
- 契约文档覆盖完整

### Milestone 3：工程增强版

目标：系统从“能跑”提升为“可维护”。

验收标准：
- strategy / risk / execution 抽象完成
- 日志和持久化模型补强
- 回放与幂等策略有设计方案

### Milestone 4：多环境演进版

目标：支持从 sim 迈向更真实运行环境。

验收标准：
- backtest / sim / paper 边界清楚
- 配置体系支持多环境
- live 路径约束条件被文档化

## 5. 推荐执行顺序

建议按下面顺序推进：

1. 先补测试
2. 再冻结契约
3. 再做模块抽象
4. 再补可观测性和持久化
5. 最后扩多环境和多策略

## 6. 当前判断

`quant-claw` 最怕的不是“功能少”，而是“闭环未稳就四处扩张”。

所以现阶段的正确做法是：

- 少做花活
- 先把主链路钉死
- 让 schema、topic、接口先稳定
- 再逐步往更复杂的交易系统演进
