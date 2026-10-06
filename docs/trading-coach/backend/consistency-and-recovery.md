# Trading Coach 版本一致性与恢复设计

状态：设计约定，尚未实现。与 [后端架构](architecture.md)、[接口契约](../shared/api-contracts.md)、[运行维护](operations.md) 配套。

职责归属：以下发布 / 恢复流程由应用层用例协调，ChartSession 和 ReadContextManager 属于应用层；数据库读快照、单 writer 与事务由基础设施实现应用层端口。Controller 只能调用查询 / 订阅用例，不能直接读库或安装状态；领域引擎只返回独立 nextState 与计算结果。包与依赖规则见 [后端分层](architecture.md#2-分层架构与代码组织)。

## 1. 版本与不变量

每个 `instrumentId + timeframe` 是独立序列。`datasetRevision` 表示一代完整分析数据，`epoch` 表示本次运行中的推送会话，`seq` 表示该 epoch 内的发布顺序。正常追加 K 线不改变 datasetRevision；历史修正、分析起点、算法配置或分析用元数据变化会创建新代。

- 每代固定 `engineVersion / parametersHash / instrumentMetadataVersion / analysisStartTime`。
- 同一序列最多有一个 ACTIVE 代和一个 BUILDING 代。版本号在创建 BUILDING 时由持久化计数器分配，失败后不复用；恢复旧备份后用新 epoch 隔离客户端旧 token。
- 公开接口只读 ACTIVE 代。BUILDING / FAILED / RETIRED 代不接受用户查询；保留旧代用于排错和发布恢复，不等于提供历史版本查询 API。
- 已发布代的既有已收盘 OHLCV 不原地修正；正常追加及分析起点之前的缺失历史插入可以写入 ACTIVE 代。发现同键冲突进入新代重建。
- 每次 REST 响应属于一个 epoch 和 datasetRevision；多个独立请求之间不保证相同 seq，持续变化的 Pattern 详情返回其实际读取的 seq。

存储使用分代完整副本，首版用空间换取清晰的读取边界。Candle 的业务键仍是品种、周期、openTime，物理主键增加 dataset_revision。后续采用增量存储时必须保持相同的外部一致性保证。

## 2. 重建与原子发布

1. session 串行处理器记录当前 ACTIVE 版本 R、最后已处理收盘边界和任务标识，暂停确认算法及 provisional 更新。上游连接继续接收并更新 freshness，后续行情放入有界暂存。
2. writer 分配 R+ 的版本号并建立 BUILDING 行，session 发布 `processing.state=REBUILDING` 和 pendingDatasetRevision；分配失败则直接 DEGRADED。随后分块复制 R 的 Candle。复制期间 R 停止写入；历史查询只读已有缓存，缓存缺失返回 503 `SERIES_REBUILDING`，不写入冻结的源代。R 中旧快照、旧 Pattern 和元数据继续可读。
3. 所有修正仅写入 BUILDING 代。后台引擎使用该代固定的配置和元数据，从 analysisStartTime 起顺序回放；结果、Swing、Pattern、转换写到该代。分析起点之前的缓存只用于展示。
4. session 顺序对账暂存、补齐到明确的收盘边界，再由后台完成追赶。追赶期间的新消息继续暂存。出现另一项修正时使旧任务失效、废弃旧 BUILDING 并重建；不得悄悄改变一个正在回放的输入集。
5. 准备好 nextState 和完整新快照后，session 取得发布锁。所有读取入口获取此锁的短期读许可来取得一致 ReadContext；发布期间暂时阻止新读取登记。writer 在一个短事务中验证旧指针仍为 R、任务仍有效，更新 ACTIVE 指针与元数据，将 R 标记 RETIRED、新代标记 ACTIVE。writer 不获取 session 锁。
6. 数据库提交成功后，session 在同一发布临界区安装 nextState、固定元数据和快照，生成新 epoch，seq 从 0 开始，清空旧 ring。给已连接客户端排入 reset 控制帧和新 snapshot，再释放锁。之后按序处理剩余暂存，恢复 READY。

HTTP 网络发送和 SSE 写 socket 不占用发布锁。在切换前已经取得 ReadContext 的请求可以返回完整旧版响应；客户端按响应版本丢弃迟到数据。带结果转换的数据库读取要在短读事务中完成，不持有连接跨网络写入。

普通收盘追加也在发布临界区内完成“数据库事务提交 → 内存状态 / seq 安装”，避免读到已提交的新 Pattern 却带旧 seq。涉及数据库的 ReadContext 在释放读许可前建立读取快照，并固定代、epoch 和 seq；请求结束释放事务和代引用。需要网络回补时先释放上下文，回补完成后重新取上下文并校验版本，不持锁等待上游。

读取 `/chart`、`/candles`、`/annotations`、`/patterns` 都必须通过同一 ReadContext 入口，不能直接读“最新一行”。Watchlist 为每个条目分别获取上下文并附版本，不承诺不同品种之间同一时刻的事务快照。

## 3. 失败与重启

| 失败点 | 处理 |
| --- | --- |
| BUILDING 写入或计算失败 | ACTIVE 指针不变；标记 FAILED，保留旧快照并发布 DEGRADED，有限重试 |
| 发布事务回滚 | 丢弃待安装状态，继续使用 R；不能发新 epoch / snapshot |
| 提交结果不明，或提交后内存安装失败 | 当前序列停止新数据读取，返回 503 `SERIES_UNAVAILABLE`；status 尽力报告 DEGRADED，并终止订阅。读取数据库 ACTIVE 指针重建，换新 epoch 后再提供数据 |
| 正常收盘提交成功、进程在推送前退出 | 重启以已提交代和收盘边界重建，新 epoch 全量同步；不依赖内存 ring 恢复 |
| 启动发现 BUILDING / FAILED 代 | 不对外发布，也不直接继续旧任务；以 ACTIVE 代恢复，再重新拉取并对账，重新分配重建版本 |
| 暂存溢出 / REST 回补未完成 | 保持 REBUILDING 或 DEGRADED，reason=INPUT_OVERFLOW / DATA_GAP；旧数据仍标明状态，不推进跨缺口算法 |

重试受 [资源预算](operations.md#1-资源预算与超时) 约束。人工重新启动不能跳过 metadata、版本和缺口校验。退休代至少保留最近一代至下一次成功备份，且不能删除仍有 ReadContext 引用的代；每次只分块清理无引用的退休 / 失败代，不删除 ACTIVE 的分析历史。

## 4. 品种元数据版本

`instrumentMetadataVersion` 是品种标识、市场、base / quote、tickSize 和成交量单位的规范化 JSON 的 SHA-256；十进制规范化规则与 parametersHash 相同。symbol 展示名、抓取时间不参与 hash。`instrument_metadata_versions` 保存不可变内容、observedAt、provider 和来源记录。

首版每一代固定一份分析用元数据，并在 ChartSnapshot 和 Pattern 中返回该版本。历史回放使用它，重启不能用刚下载的最新 tickSize 替换已保存的值。`/instruments` 可列出最新观测版本；`/chart` 的 instrument 始终是该分析代固定的版本。

Collector 在启动、重连和每 6 小时刷新元数据；无实质变化不触发重建。发现 tickSize 或单位变化时保存新版本，相关序列进入 `DEGRADED / METADATA_CHANGED`，停止算法与 preview，保留旧结果。维护者通过版本化配置选择新元数据，执行完整重建并发布新代；首版没有用户端管理写 API。部署工具应记录该决定、前后版本及操作者。

这一定义表示“使用一套固定精度规则分析整段历史”，不声称还原每个历史时点的交易所精度。若未来需要历史交易规则复原，须接入带 effectiveFrom 的元数据时间线并升级 engineVersion。已有 Pattern 的冻结阈值在当前代内不变；新代重新生成，ID 包含元数据版本，避免把不同条件视作同一实例。

## 5. 验收场景

| 场景 | 必须观察到的结果 |
| --- | --- |
| 重建每个阶段同时请求图表、历史、详情、标注 | 每个响应内部只含一个版本；BUILDING 不可见，旧 token 在发布后被拒绝 |
| 发布事务前后注入失败 / 强制退出 | 恢复后只选择持久化 ACTIVE 指针，没有半代结果，SSE 使用新 epoch |
| 旧 HTTP 请求在新 snapshot 后才返回 | 前端丢弃响应，不覆盖新图表或历史缓存 |
| 两次修正相继到达 | 旧后台任务不能安装结果，失败版本号不复用 |
| 行情连接正常、数据库写入失败 | processing=DEGRADED，lastProcessedCloseTime 停止；UI 明确显示识别暂停 |
| 元数据从 tickSize=0.1 变为 0.5 | 旧代重放结果不变；明确采用新版本后新建 datasetRevision、epoch 和相关 Pattern ID |

以上是后续自动化测试的验收标准，本次文档更新不代表这些场景已通过运行验证。
