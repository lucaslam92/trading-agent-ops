# Trading Agent Ops

一个面向量化交易 Agent 系统的项目文档仓库，当前重点围绕 `quant-claw` 这条 MVP 路线进行梳理、设计和沉淀。

## 当前目标

现阶段聚焦于构建一套**多 Agent 协同、事件驱动、可从模拟盘逐步演进到实盘**的量化交易系统方案，先把最小闭环做通，再逐步工程化。

当前 MVP 路径聚焦：

- 市场：Crypto
- 标的：BTC / ETH
- 环境：Simulation / Paper 优先
- 链路：行情 -> 提案 -> 风控 -> 执行 -> 持仓

## 文档导航

### 核心方案文档

- [实施方案](docs/quant-claw/implementation-plan.md)
- [技术架构](docs/quant-claw/technical-architecture.md)
- [MVP 工程骨架](docs/quant-claw/mvp-skeleton.md)

### 协议与工程文档

- [消息协议说明](docs/quant-claw/消息协议说明.md)
- [事件 Schema 说明](docs/quant-claw/事件Schema说明.md)
- [开发启动手册](docs/quant-claw/开发启动手册.md)
- [演进路线图](docs/quant-claw/演进路线图.md)

### 规划与执行文档

- [MVP 待办与里程碑](docs/quant-claw/MVP待办与里程碑.md)

## 项目范围

当前仓库主要承载：

- 项目方案设计
- 技术架构整理
- 协议 / Schema 说明
- 开发和启动文档
- MVP 里程碑和 backlog

当前**不以“完整代码托管仓库”作为唯一目标**，而是先把项目相关文档、架构和推进路径沉淀清楚。

## 推荐阅读顺序

如果第一次看这个项目，建议按下面顺序阅读：

1. 实施方案
2. 技术架构
3. MVP 工程骨架
4. 消息协议说明
5. 事件 Schema 说明
6. 开发启动手册
7. 演进路线图
8. MVP 待办与里程碑

## 当前阶段判断

这套项目已经有了一个可运行的 MVP 雏形，但距离可持续扩展、可维护、可走向实盘，还有明显工程化工作要补。

因此当前最合理的策略不是“功能无限加法”，而是：

- 先稳住主闭环
- 再补齐契约和文档
- 再推进工程化能力
- 最后再碰更复杂的生产级问题
