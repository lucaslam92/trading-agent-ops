# Strategy Evolution Engine 实施说明

## 目标
实现一套 MVP 自动调参框架，接入现有回测系统，完成：

- 随机生成参数
- 多训练区间评估
- 硬过滤 + 综合评分
- Top N 候选筛选
- 多窗口 OOS 验证
- 候选策略 JSON 落库

---

## 模块清单

### 1. 数据结构
实现以下模型：

- `StrategySpec`
- `StrategyParams`
- `BacktestTask`
- `Metrics`
- `TradeRecord`
- `BacktestResult`
- `PeriodResult`
- `CandidateEvaluation`
- `WalkForwardWindow`
- `WalkForwardResult`
- `StrategySnapshot`
- `NamedPeriod`

---

### 2. 参数生成器
实现：

- `CandidateGenerator`
- `StrategySpecs.bosRetestLongSpec()`

要求：
- 使用随机搜索
- 参数去重
- 参数范围按 BOS retest long 策略设定

---

### 3. 回测适配层
实现：

- `BacktestRunner`
- `ExistingBacktestEngine`
- `ExistingBacktestRunner`

要求：
- 不重写现有回测引擎
- 只做适配
- `strategyName` 必须透传
- 返回 `BacktestResult`

---

### 4. 策略评估器
实现：

- `EvaluationConfig`
- `StrategyEvaluator`

能力：
- 多训练区间指标聚合
- 硬过滤
- 综合打分
- 输出 `CandidateEvaluation`

默认硬过滤：
- `profitFactor >= 1.25`
- `sharpe >= 0.3`
- `totalTrades >= 15`
- `avgHoldingHours >= 18`
- `feeRatio <= 0.35`
- `longPnl > 0`

---

### 5. 筛选器
实现：

- `StrategySelector.selectTop(...)`

逻辑：
- 只保留通过硬过滤的候选
- 按 `score` 降序取前 `N`

---

### 6. 多窗口 OOS 验证器
实现：

- `WalkForwardValidator`

当前版本说明：
- 这版先做 **多窗口 out-of-sample 验证**
- 暂不做“每个 train window 内重新优化参数”的完整 WFO

---

### 7. 注册表
实现：

- `StrategyRegistry`

当前要求：
- JSON 文件存储
- `save(snapshot)` 先实现
- 存储目录自动创建

推荐后续补：
- `load`
- `list`
- `updateStatus`

---

### 8. 主流程编排器
实现：

- `StrategyEvolutionEngine`

主流程：
1. 生成参数候选
2. 在 train periods 上逐个评估
3. 选出 topN
4. 在 OOS windows 上验证
5. 通过者写入 registry
6. 返回验证通过结果

---

### 9. 运行入口
实现 `main()`：

默认配置建议：
- `spec = bosRetestLongSpec()`
- `candidateCount = 100`
- `topN = 20`
- 训练区间：2023、2024
- OOS 窗口：至少 2 个

---

## 第一阶段验收标准

工程完成后，至少满足：

1. 能成功生成 100 组不重复参数
2. 能对每组参数调用现有回测系统
3. 能输出候选评分结果
4. 能筛选 topN
5. 能完成 OOS 验证
6. 能在 `strategy_registry/` 下生成 JSON 快照
7. `main()` 可直接运行并打印前 5 名结果

---

## 当前版本边界
这版先**不做**：

- 完整 walk-forward train-optimize-test
- 并发调度
- 失败恢复机制
- 数据库注册表
- UI 展示

先把 MVP 跑通。

---

## 推荐实施顺序

1. 数据结构
2. 回测适配器
3. 参数生成器
4. 评估器
5. Selector
6. EvolutionEngine
7. Registry
8. main() 联调

---

## 备注
当前最适合先落地的策略是：

- `bos_retest_long`

不要一开始把多个策略一起塞进进化引擎。
先把一套策略闭环跑通，再扩展。
