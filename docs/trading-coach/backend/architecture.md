# Trading Coach 后端技术架构

状态：设计提案。依据：[数据源参考](market-data-design.md)、[API 契约](../shared/api-contracts.md)、[算法规则](technical-engine-spec.md)。

## 1. 技术选择与运行边界

推荐 Python 3.11+、FastAPI、Pydantic v2、Uvicorn、httpx、WebSocket 客户端、aiosqlite。MVP 一个 API 进程、一个 worker、一个 SQLite WAL 数据库。

后端负责上游数据接入、归一化、收盘确认、技术计算、快照一致性和实时推送。应用只读公共行情，不需要交易账户、不接订单执行。Python 选型基于现有分支，不限制未来按同一契约替换实现。

## 2. 模块结构

```text
trading-coach/backend/
  pyproject.toml
  src/trading_coach/
    app.py / config.py
    api/                  # instruments、candles、chart、stream、patterns、watchlist、health
    contracts/            # Pydantic 请求 / 响应 / SSE DTO，统一 camelCase alias
    domain/               # Candle、Swing、Structure、Pattern、规则配置
    market_data/
      adapters/           # Protocol、OKX、Fixture；Binance 后续
      normalizer.py
      validator.py
      reconciler.py       # 历史 / 实时接续、断线补齐
      collector.py        # 上游连接与限流
    technical/
      swing.py / structure.py / levels.py / breakout.py
      state_machine.py / engine.py
    sessions/
      chart_session.py    # 顺序处理、原子快照、seq / epoch
      stream_hub.py       # ring buffer、有界客户端队列
    repositories/         # Candle、Pattern、转换事件、规则版本
    storage/              # SQLite、schema migration、事务
    observability/        # 结构化日志、健康状态、指标
  tests/                  # unit、contract、integration、fixtures
```

domain / technical 不导入 api、storage、market_data 或图表代码。DTO 转换集中在 contracts；Provider payload 不能直接进入算法。

## 3. 服务职责

| 模块 | 输入 / 输出 | 关键约束 |
| --- | --- | --- |
| MarketDataAdapter | REST / WS → NormalizedCandleUpdate | 交易所字段、周期、成交量单位映射；无业务形态判断 |
| Reconciler | 历史与实时 → 有序数据变更 | 去重、缺口补齐、closed 不退回 open、识别修正 |
| CandleRepository | 校验 Candle → 缓存 / SQLite | 唯一键为 instrument + timeframe + openTime |
| TechnicalEngine | 顺序收盘 Candle → 确认结果 | 纯逻辑；规则版本、参数固定；无未来数据 |
| ChartSession | Candle / 技术结果 → ChartSnapshot | 每序列串行处理；同一事务逻辑生成原子视图 |
| StreamHub | 快照 / 增量 → SSE | seq、epoch、ring buffer、有界队列、重同步 |
| PatternRepository | 生命周期 → 查询结果 | 稳定 ID；相同转换幂等；保存证据 |

## 4. 运行模型与启动

- 固定 instrument allowlist：OKX Spot BTC-USDT / ETH-USDT，六个周期，共 12 个序列。
- Collector 共享上游连接与 REST 限流器；不为每个浏览器建立交易所连接。
- 每个序列有独立 ChartSession 和处理锁，不同序列可并发 I/O。
- Watchlist 首版固定查询 `15m` 摘要，每 5 秒 REST 刷新，不另建大量订阅。
- UI 订阅只控制下游推送；固定序列持续采集，保证没有用户连接时形态仍连续。

启动顺序：配置验证 → 数据库 migration → 加载已收盘历史与规则版本 → 建立实时连接并暂存 → 历史回补 → 重建引擎 → 合并暂存与对账 → 标记可用。第一次历史准备允许各序列独立完成；未准备好的序列返回 `SERIES_WARMING_UP`。

停止顺序：拒绝新订阅 → 标记断线 → 取消并 await 后台任务 → 关闭 WS/httpx 客户端 → 刷新待写数据 → 关闭数据库。生命周期使用 FastAPI lifespan，明确资源 owner。

## 5. 历史与实时一致性

1. 先启动实时连接并暂存更新，后拉历史，避免两者之间的空窗。
2. 历史数据校验后升序 upsert；缓存末尾允许一根未收盘 Candle。
3. 合并暂存数据、补齐 overlap，按 provider finality 与 revision 决定更新。
4. 对每个新收盘 Candle：以该 bar 开始前已知关键位计算突破 → 推进 Swing / Structure → 写入数据与状态 → 增加 seq → 发布批次。
5. 未收盘更新用于 Candle 与 provisional Pattern 展示，不推进确认 Swing，也不提前持久化确认事件。
6. 确认 Candle 的重复到达不重复计算或生成转换。

实时断线时保留最后图表，进入 `STALE`；从最后确认位置进行带重叠的 REST 回补，补齐后按顺序推进。新周期消息本身不足以证明前一根已收盘，优先取上游收盘标识，否则补请求确认。

历史已收盘数据修正会使 `datasetRevision` 增加、引擎重建、session epoch 变化，并发送 reset / snapshot。修正前后结果不能在同一快照中混用。

## 6. 算法状态与重建

- 从数据库的完整已保留历史顺序重建，首版不保存不可验证的 Python 对象 pickle。
- 初次 bootstrap 获取最近 2,000 根/序列作为 analysis 起点；至少要满足 Swing 和可选成交量窗口。
- `analysisStartTime` 记录实际起点。滚动图表展示 500 根不改变引擎历史；历史分页也不改变 analysis 起点。
- 增加更早的 analysis 历史是显式重建操作：revision / epoch 更新，重新生成当前算法版本的结果。
- 首版保留已采集闭合 Candle；未来清理历史时必须先设计可恢复 checkpoint，不按图表缓存窗口删除引擎依赖数据。
- `engineVersion + parametersHash + datasetRevision + analysisStartTime` 共同界定结果；UI 能查看规则版本。

技术识别的完整默认参数及双向规则见算法文档。新增形态通过 detector 接口和状态规则注册，不新增 Agent。

## 7. 存储设计

| 表 | 唯一键 / 主要字段 | 用途 |
| --- | --- | --- |
| instruments | instrument_id；provider、market、provider_symbol、base、quote、tick_size | 品种与精度 |
| candles | instrument_id + timeframe + open_time；OHLC、base_volume、quote_volume、revision、confirmed_at | 已收盘行情；十进制文本保存 |
| pattern_instances | pattern_id + result_revision；type、anchor、状态、证据 JSON、规则版本 | 生命周期当前结果与修正后的结果版本 |
| pattern_transitions | pattern_id + result_revision + transition_index | 按顺序记录 canonical 状态转换，幂等写入 |
| series_metadata | instrument_id + timeframe；dataset_revision、analysis_start_time、last_closed_time | 数据版本与重建边界 |
| engine_configs | engine_version + parameters_hash；规范化配置 JSON | 固定判定配置 |

未收盘数据存内存，闭合后落库；重启重新从交易所获取未收盘 bar。Pattern provisional 只在内存，不进入 canonical 转换表。

单序列收盘写入在一个 SQLite 事务中完成：Candle + Pattern + transition + metadata。成功后才更新权威快照并发布事件；失败时保留上一版，进入 degraded 状态，不能先广播后声称已持久化。

sqlite 异步 I/O 与写入串行化；历史批量导入分块，避免长事务阻塞收盘处理。图表摘要缓存内存，API 查询不每次扫描全部 Candle。

## 8. REST 与 SSE

REST 提供 instruments、历史分页、ChartSnapshot、Pattern Detail、Watchlist 和健康检查。SSE 推送一个序列的 Candle 与算法变化，协议见契约文档。

- ChartSession 维护 boot/session epoch、递增 seq 和最近 512 个事件批次。
- 从 snapshot 到订阅之间通过 resume token 消除竞态；无法补齐时直接发完整快照。
- 每客户端队列最多 128 个批次；队列溢出时断开该客户端，由重连 + snapshot 恢复，不无限堆积，也不阻塞 collector。
- 未收盘行情在进入 session 发布前可以合并到每秒最多 4 批；收盘、转换、quality/reset 不被合并丢弃。
- SSE 每 15 秒发注释心跳；客户端断开释放队列。
- 日志记录 stream key / epoch / seq，客户端数、队列深度、重建次数与拒绝数。

SSE 满足首版单向更新。以后若需要双向实时命令，可增加客户端 WebSocket Adapter，保持事件载荷语义。

## 9. 部署与配置

生产：Nginx / Caddy 提供 Web 静态产物与同域 `/api/v1/` 反向代理，FastAPI 绑定内部端口。SSE 关闭代理缓冲和缓存，read timeout 大于心跳间隔。

```text
DATA_PROVIDER=fixture | okx
DATABASE_PATH=./data/trading-coach.sqlite3
INSTRUMENTS=BTC-USDT,ETH-USDT
TIMEFRAMES=1m,5m,15m,1h,4h,1d
ENGINE_VERSION=structure-breakout-v1
ANALYSIS_BOOTSTRAP_BARS=2000
SSE_RING_BATCHES=512
SSE_CLIENT_QUEUE_BATCHES=128
```

这些是建议配置名，尚未存在启动脚本。真实模式不允许找不到 Adapter 时隐式降级 fixture；错误配置启动失败。

单进程部署是设计约束：不能直接使用多个 Uvicorn worker，否则采集重复、内存快照和 seq 分裂。需要扩容时先拆独立 Collector/Engine，再引入共享存储或消息通道。MVP 不提前做微服务。

## 10. 错误、健康与性能验证

- 参数不支持返回 422；未知品种/形态返回 404；数据版本不匹配返回 409；限流 429；准备中或上游不可用且无缓存返回 503。
- 数据缺口与旧缓存通过 quality 呈现；源接口失败不返回合法空数组冒充没有行情。
- `/health/live` 仅验证进程；`/health/ready` 验证数据库、配置、后台任务初始化。真实源延迟单独放 provider/series health，短断线不制造进程重启循环。
- 结构化日志包含 instrumentId、timeframe、provider、openTime、epoch、seq、规则版本，不含 token 或完整请求认证信息。

待测目标：12 个采集序列、10 个浏览器连接；缓存 snapshot p95 < 300ms；收到上游行情到发布批次 p95 < 500ms（合并等待另记）。这是设计预算，须在指定机器与真实负载下测量。

必要验证：纯算法、Adapter payload fixture、REST/WS 接续、数据库事务失败、慢客户端、重启、历史修正、SSE 恢复和前后端契约。不需要以交易收益验收。
