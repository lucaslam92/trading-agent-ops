# Trading Coach 后端技术架构

状态：设计提案，后端语言已确定为 Java，应用尚未实现。依据：[数据源参考](market-data-design.md)、[API 契约](../shared/api-contracts.md)、[算法规则](technical-engine-spec.md)。

跨接口版本发布以 [一致性与恢复设计](consistency-and-recovery.md) 为准；容量、备份、恢复和升级以 [运行维护设计](operations.md) 为准。

## 1. 技术选择与运行边界

采用 Java 21 LTS、Spring Boot 4.1.x、Spring MVC、Jackson、Jakarta Validation、JDK HttpClient / WebSocket、Spring JDBC + Xerial SQLite JDBC。SSE 使用 Spring MVC `SseEmitter`。构建采用 Gradle Wrapper 和 Java toolchain 21；实施时锁定兼容的补丁版本、Wrapper 和依赖，不使用动态版本。

MVP 部署一个 Spring Boot JVM 实例、一个 SQLite WAL 数据库。单实例内部运行 HTTP 请求、采集、序列处理、数据库写入和 SSE 发送任务；“单实例”不等于单线程。首版采用 Spring MVC + JDBC 的命令式模型，线程职责和队列边界见第 4 节。

后端负责上游数据接入、归一化、收盘确认、技术计算、快照一致性和实时推送。应用只读公共行情，不需要交易账户、不接订单执行。Java 选型基于用户的 Android / Java 背景和长期维护需求。旧 Python 实现仅供数据源行为参考。

## 2. 模块结构

```text
trading-coach/backend/
  build.gradle / settings.gradle / gradlew / gradle/wrapper/
  src/main/java/com/tradingcoach/
    TradingCoachApplication.java
    config/               # 配置、线程执行器、Spring 依赖装配
    api/                  # instruments、candles、chart、stream、patterns、watchlist、health
    contracts/            # Java record DTO、请求校验、domain 映射；JSON 字段 camelCase
    domain/               # Candle、Swing、Structure、Pattern、规则配置
    marketdata/
      adapters/           # MarketDataAdapter interface、OKX、Fixture；Binance 后续
      CandleNormalizer.java / CandleValidator.java
      Reconciler.java      # 历史 / 实时接续、断线补齐
      Collector.java       # 上游连接与限流
    technical/
      SwingDetector.java / StructureDetector.java / LevelDetector.java
      BreakoutDetector.java / PatternStateMachine.java / TechnicalEngine.java
    sessions/
      ChartSession.java   # 顺序处理、原子快照、seq / epoch
      StreamHub.java      # ring buffer、有界客户端队列
    repositories/         # Candle、Pattern、转换事件、规则版本
    storage/              # JDBC 实现、schema migration、事务、单写入任务队列
    observability/        # 结构化日志、健康状态、指标
  src/main/resources/
    application.yml
    db/migration/         # 编号 SQL 与 migration 版本 / 校验和
  src/test/java/com/tradingcoach/   # JUnit：unit、contract、integration
  src/test/resources/fixtures/
```

domain / technical 不导入 Spring、api、storage、marketdata 或图表代码。DTO 转换集中在 contracts；Provider payload 不能直接进入算法。领域层价格采用 `BigDecimal`，HTTP / SSE DTO 使用十进制字符串；JSON Schema 是跨端协议来源，Java 序列化结果必须通过契约验证。

## 3. 服务职责

| 模块 | 输入 / 输出 | 关键约束 |
| --- | --- | --- |
| MarketDataAdapter | REST / WS → NormalizedCandleUpdate | 交易所字段、周期、成交量单位映射；无业务形态判断 |
| Reconciler | 历史与实时 → 有序数据变更 | 去重、缺口补齐、closed 不退回 open、识别修正 |
| CandleRepository | 校验 Candle → 缓存 / SQLite | 物理键为 instrument + timeframe + datasetRevision + openTime；查询绑定当前代 |
| TechnicalEngine | 顺序收盘 Candle → 确认结果 | 纯逻辑；规则版本、参数固定；无未来数据 |
| ChartSession | Candle / 技术结果 → ChartSnapshot | 每序列串行处理；同一事务逻辑生成原子视图 |
| StreamHub | 快照 / 增量 → SSE | seq、epoch、ring buffer、有界队列、重同步 |
| PatternRepository | 生命周期 → 查询结果 | 稳定 ID；相同转换幂等；保存证据 |

## 4. 运行模型与启动

- 固定 instrument allowlist：OKX Spot BTC-USDT / ETH-USDT，六个周期，共 12 个序列。
- Collector 共享上游连接与 REST 限流器；不为每个浏览器建立交易所连接。
- 每个序列有独立 ChartSession、有界输入队列和串行处理器；同一序列的收盘、修正、状态变更严格按序处理，不同序列可并发。
- Watchlist 首版固定查询 `15m` 摘要，每 5 秒 REST 刷新，不另建大量订阅。
- UI 订阅只控制下游推送；固定序列持续采集，保证没有用户连接时形态仍连续。

线程与任务职责：

| 执行位置 | 职责 / 约束 |
| --- | --- |
| MVC 请求线程 | 参数校验、读取不可变快照、提交受限查询；不直接运行历史回放 |
| Collector / I/O executor | REST、重连、限流、历史下载；阻塞 I/O 可用 Java 21 虚拟线程，但仍限制并发请求数、队列和超时 |
| ChartSession 串行处理器 | 首版每序列一个受控处理任务；拥有 canonical state，快照读取和订阅登记由 session lock 协调 |
| 重建 executor | 固定并发上限和有界队列；从冻结的数据版本及收盘边界计算独立状态，完成后由 session 校验重建任务标识并安装；不并发修改运行中的状态 |
| SQLite writer | 一个有界队列、一个写线程，负责整个事务；不等待 session lock，不跨线程传播 JDBC 事务 |
| SSE sender | 每客户端串行发送、独立于采集和算法；可用虚拟线程，限制总连接数并保留每客户端有界队列 |

虚拟线程用于等待 I/O，不能增加 CPU 计算能力。所有 executor、定时器和连接由 Spring 管理并有明确 owner。WebSocket 回调只解析并投递；输入队列满时不静默丢弃收盘消息，标记 incomplete 并暂停该序列确认计算，通过断线重连和 REST 对账恢复；重建期间的暂存也必须有界。

启动顺序：配置验证 → 数据库 migration → 加载已收盘历史与规则版本 → 建立实时连接并暂存 → 历史回补 → 重建引擎 → 合并暂存与对账 → 标记可用。第一次历史准备允许各序列独立完成；未准备好的序列返回 `SERIES_WARMING_UP`。

停止顺序：拒绝新订阅 → 停止采集和重试定时器 → 关闭上游连接 → 在限定时间内排空已接收序列任务和数据库写队列 → 关闭 SSE、executor 和数据库。使用 Spring `SmartLifecycle` 协调资源顺序及 graceful shutdown；停止超时时不伪报完成，重启从最后已提交收盘位置回补。

## 5. 历史与实时一致性

1. 先启动实时连接并暂存更新，后拉历史，避免两者之间的空窗。
2. 历史数据校验后升序 upsert；缓存末尾允许一根未收盘 Candle。
3. 合并暂存数据、补齐 overlap，按 provider finality 与 revision 决定更新。
4. 对每个新收盘 Candle：以该 bar 开始前已知关键位计算突破 → 在独立 nextState 上推进 Swing / Structure → 事务写入数据与结果 → 安装 nextState、快照和新 seq → 发布批次。
5. 未收盘更新用于 Candle 与 provisional Pattern 展示，不推进确认 Swing，也不提前持久化确认事件。
6. 确认 Candle 的重复到达不重复计算或生成转换。

实时断线时保留最后图表，进入 `STALE`；从最后确认位置进行带重叠的 REST 回补，补齐后按顺序推进。新周期消息本身不足以证明前一根已收盘，优先取上游收盘标识，否则补请求确认。

历史已收盘数据修正先创建独立 BUILDING 代，旧 ACTIVE 代停止写入并继续提供标明 REBUILDING 状态的缓存结果。新代完整计算并追赶后，事务切换 ACTIVE 指针，再在发布锁内安装内存状态、更新 datasetRevision / epoch 并发送 reset / snapshot。BUILDING 数据不可被任何公开接口读到。请求通过统一 ReadContext 取得版本；所有历史和详情请求必须携带 epoch / datasetRevision。完整发布、失败与崩溃恢复步骤见 [一致性设计](consistency-and-recovery.md#2-重建与原子发布)。

## 6. 算法状态与重建

- 从数据库的完整已保留历史顺序重建，首版不保存 Java 对象序列化快照。后续 checkpoint 使用显式版本化的数据格式，包含规则、数据版本及最后处理位置，并验证与完整回放等价。
- 初次 bootstrap 获取最近 2,000 根/序列作为 analysis 起点；至少要满足 Swing 和可选成交量窗口。
- `analysisStartTime` 记录实际起点。滚动图表展示 500 根不改变引擎历史；历史分页也不改变 analysis 起点。
- 增加更早的 analysis 历史是显式重建操作：revision / epoch 更新，重新生成当前算法版本的结果。
- 首版保留已采集闭合 Candle；未来清理历史时必须先设计可恢复 checkpoint，不按图表缓存窗口删除引擎依赖数据。
- 重建按批读取，在独立 executor 中执行；记录耗时、处理条数和暂存深度。以持续增长的历史量验证恢复时间，超出约定恢复预算后再引入 checkpoint，不能在请求线程全量回放。
- 重建开始时暂停该序列的确认推进，冻结规则配置、数据版本和收盘边界，后续行情进入有界暂存；旧快照保留并标明质量状态。后台结果携带重建任务标识，过期任务结果丢弃；由 session 顺序对账暂存、完成对应持久化后安装新状态。暂存溢出则重新 REST 补齐，不把旧任务结果覆盖到更新的状态上。
- `engineVersion + parametersHash + instrumentMetadataVersion + datasetRevision + analysisStartTime` 共同界定结果；UI 能查看规则与分析元数据版本。重启从持久化的 ACTIVE 代读取固定配置，不以启动时最新元数据覆盖。

技术识别的完整默认参数及双向规则见算法文档。新增形态通过 detector 接口和状态规则注册，不新增 Agent。

## 7. 存储设计

| 表 | 唯一键 / 主要字段 | 用途 |
| --- | --- | --- |
| instruments | instrument_id；provider、market、provider_symbol、latest_metadata_version | 品种目录及最新观测元数据指针 |
| instrument_metadata_versions | instrument_id + metadata_version；base、quote、tick_size、volume_unit、observed_at、规范化内容 | 不可变元数据，分析代显式引用 |
| candles | instrument_id + timeframe + dataset_revision + open_time；OHLC、base_volume、quote_volume、revision、confirmed_at | 分代已收盘行情；十进制文本保存 |
| swings | instrument_id + timeframe + dataset_revision + swing_id；pivot_time、confirmed_at、price、relation、label | 可分页查询的历史识别结果，避免全部常驻内存 |
| pattern_instances | pattern_id + result_revision；type、anchor、状态、证据 JSON、规则版本 | 生命周期当前结果与修正后的结果版本 |
| pattern_transitions | pattern_id + result_revision + transition_index | 按顺序记录 canonical 状态转换，幂等写入 |
| series_metadata | instrument_id + timeframe；active_dataset_revision、next_dataset_revision | 当前公开代指针和单调分配器 |
| series_versions | instrument_id + timeframe + dataset_revision；BUILDING / ACTIVE / RETIRED / FAILED、engine_version、parameters_hash、instrument_metadata_version、analysis_start_time、last_processed_close_time、last_successful_process_at、build_task_id | 固定分析上下文及收盘恢复边界 |
| engine_configs | engine_version + parameters_hash；规范化配置 JSON | 固定判定配置 |

P0 的 DDL 必须落地复合主键、外键、每序列最多一个 ACTIVE 代的约束，以及 Candle 的序列 / 版本 / 时间索引、Swing 的序列 / 版本 / pivot_time 索引、Pattern 的序列 / 版本 / 状态 / 时间索引。ACTIVE 指针与代状态在同一事务更新；所有代内查询显式绑定 dataset_revision，不能通过全表 MAX(revision) 选结果。DDL 和 migration SQL 是 P0 交付物，目前仍为设计。

未收盘数据存内存，闭合后落库；重启重新从交易所获取未收盘 bar。Pattern provisional 只在内存，不进入 canonical 转换表。

单序列收盘写入在一个 SQLite 事务中完成：Candle + Pattern + transition + metadata。成功后才更新权威快照并发布事件；失败时保留上一版，进入 degraded 状态，不能先广播后声称已持久化。

算法计算产生独立的 nextState 和待写结果，不提前修改 canonical state。由 writer 在线程内执行 `TransactionTemplate`，提交成功后 session 在锁内安装新状态 / 快照并推进 seq；回滚则丢弃 nextState，暂停后续确认推进并从最后提交位置重试。若提交结果不明或数据库已提交但内存安装失败，先读取已提交 metadata 并重建，再接受新事件，避免重复转换。进程重启重建并更换 epoch。

SQLite 通过 Spring JDBC + Xerial 驱动访问；所有写入口（包括历史回补）共用 writer，整个事务使用同一连接。读连接不与写事务共用正在使用的 Connection，显式设置 WAL、foreign_keys、busy_timeout；WAL 启用结果须校验。历史导入分块并给实时写入留出调度机会，限制 SQLITE_BUSY 重试次数；监测 WAL 大小和 checkpoint 耗时，避免长读事务阻止回收。图表摘要缓存内存，API 查询不每次扫描全部 Candle。

migration 在采集启动前独占执行，记录版本和校验和，失败时 readiness 不通过。已确认 Candle 的冲突更新必须由 Reconciler 触发 revision / 重建流程，Repository 不得绕过它直接覆盖数据。SQLite 使用本机持久化目录；未来需要多实例或更高写入吞吐时再迁移 PostgreSQL，并重新验证事务和数值语义。

## 8. REST 与 SSE

REST 提供 instruments、历史分页、ChartSnapshot、Pattern Detail、Watchlist 和健康检查。SSE 推送一个序列的 Candle 与算法变化，协议见契约文档。

- ChartSession 维护 boot/session epoch、递增 seq 和最近 512 个事件批次。
- 从 snapshot 到订阅之间通过 resume token 消除竞态；无法补齐时直接发完整快照。
- 每客户端队列最多 128 个批次；队列溢出时断开该客户端，由重连 + snapshot 恢复，不无限堆积，也不阻塞 collector。
- ring 同时限制 8 MiB，客户端实时队列同时限制 2 MiB。一次恢复最多补发 64 批 / 512 KiB，超过直接发完整快照；补发副本和实时队列独立计费，注册时划定 seq 高水位。细节见 [SSE 契约](../shared/api-contracts.md#9-sse)。
- 未收盘行情在进入 session 发布前可以合并到每秒最多 4 批；收盘、转换、quality/reset 不被合并丢弃。
- SSE 每 15 秒发注释心跳；客户端断开释放队列。
- `SseEmitter.send()` 在客户端专属发送任务中执行，不持有 session lock；发送异常、超时、完成回调均幂等清理订阅。Servlet 异步超时与代理超时分别配置，并通过慢客户端测试验证写阻塞不会拖住采集任务。
- 日志记录 stream key / epoch / seq，客户端数、队列深度、重建次数与拒绝数。

推送统一覆盖服务器最近最多 500 根的 liveWindow，浏览器视口不改变共享事件流。历史标注由 REST 分页提供，离开 liveWindow 的移除事件只影响客户端 live 集合；不会删除历史事实或其他浏览器数据。REST 和 SSE 都携带 processing 状态，使行情正常但识别暂停的情况可以被 UI 正确显示。

SSE 满足首版单向更新。以后若需要双向实时命令，可增加客户端 WebSocket Adapter，保持事件载荷语义。

## 9. 部署与配置

生产：Nginx / Caddy 提供 Web 静态产物与同域 `/api/v1/` 反向代理，Spring Boot 可执行 JAR / 容器绑定内部端口，运行于 Java 21。SSE 关闭代理缓冲和缓存，read timeout 大于心跳间隔；数据库目录使用持久卷。

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

这些是建议环境变量名，由 `application.yml` 显式映射到 `@ConfigurationProperties` 并校验，尚未存在启动脚本。真实模式不允许找不到 Adapter 时隐式降级 fixture；错误配置启动失败。

单 JVM 应用实例是设计约束：不能直接把副本数调到 2 或同时启动两套应用，否则采集重复、内存快照和 seq 分裂。HTTP 线程、虚拟线程和后台 executor 均属于同一实例。需要扩容时先明确 Collector/Engine 的序列所有权，再引入共享存储或消息通道。MVP 保持模块化单体。

启动时对本地数据目录取得进程独占锁；升级采用维护窗口，数据库备份和 schema 兼容检查通过后再启动新构建。完整预算和操作顺序见 [运行维护](operations.md)，包括小时备份、恢复演练、磁盘告警和不兼容 schema 的回滚。

## 10. 错误、健康与性能验证

- 参数不支持返回 422；未知品种/形态返回 404；数据版本不匹配返回 409；限流 429；准备中或上游不可用且无缓存返回 503。
- 用 `@RestControllerAdvice` 将 Bean Validation、参数绑定和业务异常映射到统一错误 envelope，显式保留契约要求的 422，不能依赖框架默认错误页面 / 状态码。
- 数据缺口与旧缓存通过 quality 呈现；源接口失败不返回合法空数组冒充没有行情。
- `/health/live` 仅验证进程；`/health/ready` 验证数据库、配置、后台任务初始化。真实源延迟单独放 provider/series health，短断线不制造进程重启循环。
- SeriesQuality.processing 用 WARMING_UP / READY / REBUILDING / DEGRADED 描述识别处理状态，独立于连接状态；标明最后已提交收盘边界、最后成功处理时间和 reasonCodes。状态变化也发布 SSE status，即使没有新行情。
- 结构化日志包含 instrumentId、timeframe、provider、openTime、epoch、seq、规则版本，不含 token 或完整请求认证信息。

待测目标：12 个采集序列、10 个浏览器连接；缓存 snapshot p95 < 300ms；收到上游行情到发布批次 p95 < 500ms（合并等待另记）。这是设计预算，须在指定机器与真实负载下测量。

必要验证：JUnit 纯算法、Adapter payload fixture、REST/WS 接续、真实 SQLite 临时库的事务失败 / 重试、慢客户端、输入队列溢出、重启、历史修正、SSE 恢复和前后端契约。事务失败测试同时检查数据库、canonical state、seq 和快照；重建测试与实时订阅并行运行。不需要以交易收益验收。

## 11. Java 技术依据

核验日期：2026-10-06。版本兼容性依据 [Spring Boot 系统要求](https://docs.spring.io/spring-boot/system-requirements.html)；SSE 依据 [Spring MVC 异步请求](https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-ann-async.html)；虚拟线程边界依据 [Java 21 文档](https://docs.oracle.com/en/java/javase/21/core/virtual-threads.html)。数据库采用 [Xerial SQLite JDBC](https://github.com/xerial/sqlite-jdbc)，事务边界依据 [Spring 编程式事务](https://docs.spring.io/spring-framework/reference/data-access/transaction/programmatic.html)。这些是技术设计依据，不代表依赖组合已构建或通过联调。
