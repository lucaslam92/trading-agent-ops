# Trading Coach 前后端数据契约

状态：v1 设计提案；作为未来代码生成与契约测试依据，不代表接口已实现。

## 1. 通用约定

- API 前缀 `/api/v1`；JSON 字段 camelCase。
- 所有时间为 UTC Unix **毫秒**。仅图表 Adapter 转 Unix 秒。
- OHLC、volume、tickSize、level 等十进制量通过字符串传输，后端 Java `BigDecimal` 判定，前端校验后转换图表 number。后端领域值与 DTO 分离，DTO 的十进制字段使用 String，不能让默认 JSON 序列化输出浮点数字。
- `instrumentId` 唯一包含 provider、market、原生代码；`symbol` 仅为展示文字。
- timeframe 枚举：`1m / 5m / 15m / 1h / 4h / 1d`；MVP 不支持任意周期。
- `closeTime` 为排他结束时间，例如 15m bar 是 `[openTime, openTime + 900000)`。
- `confirmedAt` / `evaluatedAt` 表示收盘判定的逻辑时间；`receivedAt` / `firstSeenAt` 记录系统实际收到/发现的时间。历史回补不得把逻辑时间声称为实时发现时间。
- schemaVersion 与 API 主版本分别管理；破坏性字段变更升级 API，不手工分别修改两端类型。
- 当前 v1 尚未发布；本轮新增字段合入 v1 初始契约。上线后按上述兼容规则演进。

采用契约优先：未来应用目录 `trading-coach/contracts/schemas/` 中的 JSON Schema 2020-12 是 HTTP / SSE 公共数据模型的唯一来源，`contracts/openapi.yaml` 使用 OpenAPI 3.1 定义 HTTP 路径并引用这些 schema。SSE 的 snapshot / update / status / reset payload 也各自拥有 schema，不依赖 Spring 对 `SseEmitter` 返回类型的自动推断。当前这些机器可读文件尚未创建，P0 根据本页落地。

Java contracts 包用 record DTO 实现协议，Jackson 负责序列化，Jakarta Validation 和领域校验负责约束；Java 注解不是第二套协议来源。前端从同一 schema / OpenAPI 生成 TypeScript 类型和运行时校验器。CI 检查 schema 引用和生成产物无漂移，并验证 Java 实际 REST / SSE 输出、请求错误及固定 fixtures，防止 Java DTO 与协议脱节。

实施工具建议：HTTP 类型使用 openapi-typescript；SSE 类型使用 json-schema-to-typescript；运行时使用 Ajv 的 JSON Schema 2020-12 支持并预编译 validator。先对 schema 做引用打包，再生成产物；P0 验证这些工具对 OpenAPI 3.1、nullable 和外部引用的兼容性。前端允许兼容版本的新增非必需字段，但必需字段、十进制字符串格式、枚举和时间单位必须校验；不要以忽略全部解析错误实现所谓兼容。

## 2. Instrument

```json
{
  "instrumentId": "okx:spot:BTC-USDT",
  "symbol": "BTCUSDT",
  "provider": "okx",
  "market": "spot",
  "providerSymbol": "BTC-USDT",
  "baseAsset": "BTC",
  "quoteAsset": "USDT",
  "tickSize": "0.1",
  "instrumentMetadataVersion": "metadata-example-hash",
  "supportedTimeframes": ["1m", "5m", "15m", "1h", "4h", "1d"]
}
```

示例 tickSize 不作为交易所当前值，实现从 instrument metadata 获取。instrumentMetadataVersion 指向不可变的分析元数据；`/instruments` 可返回最新观测版本，ChartSnapshot 内的 instrument 必须属于当前分析代固定版本，不能用列表值覆盖。版本与采用流程见 [元数据版本](../backend/consistency-and-recovery.md#4-品种元数据版本)。

## 3. Candle

```json
{
  "instrumentId": "okx:spot:BTC-USDT",
  "timeframe": "15m",
  "openTime": 1791277200000,
  "closeTime": 1791278100000,
  "open": "62000.0",
  "high": "62150.0",
  "low": "61980.0",
  "close": "62120.0",
  "volume": "12.5",
  "quoteVolume": "776000.0",
  "isClosed": true,
  "confirmedAt": 1791278100000,
  "receivedAt": 1791278100100,
  "revision": 3
}
```

同一 datasetRevision 内业务唯一键为 instrumentId + timeframe + openTime；所属代由外层响应提供，物理存储键包含 datasetRevision。`volume` 为 base asset；`quoteVolume` 可为 null，不能用 base volume 冒充。未收盘 confirmedAt 为 null。revision 是服务端接受的该 Candle 版本，不是交易所原生序号，不能跨 datasetRevision 比较。

## 4. Swing、结构、关键位

```ts
interface SwingPoint {
  id: string;
  pivotTime: number;               // 峰/谷所在 bar 的 openTime
  price: string;
  type: 'HIGH' | 'LOW';
  leftBars: number;
  rightBars: number;
  confirmedAt: number;             // 第 rightBars 根右侧 bar 的 closeTime
  firstSeenAt: number;             // 服务端实际计算/恢复时刻
  structureLabel: 'HH' | 'HL' | 'LH' | 'LL' | null;
  relation: 'HIGHER' | 'LOWER' | 'EQUAL' | 'INITIAL';
}

interface StructureState {
  trend: 'UPTREND' | 'DOWNTREND' | 'RANGE' | 'UNKNOWN';
  asOf: number;                    // 最后处理的已收盘时间
  swingIds: string[];              // 判断依据，最近同类高/低点
  reasonCodes: string[];
}

interface KeyLevel {
  id: string;
  type: 'SUPPORT' | 'RESISTANCE';
  price: string;
  anchorSwingId: string;
  knownAt: number;
}
```

首版只输出确认 Swing，strength 使用明确的 leftBars/rightBars，不引入没有定义的评分。结构标签与关系在相应 Swing 确认时确定；更晚出现同类 Swing 不改写早期标签。结果因数据修正重建时通过 revision / reset 说明。

## 5. Pattern

```json
{
  "id": "breakout-example",
  "instrumentId": "okx:spot:BTC-USDT",
  "timeframe": "15m",
  "type": "BREAKOUT",
  "direction": "BULLISH",
  "status": "CONFIRMED",
  "isProvisional": false,
  "startTime": 1791277200000,
  "updatedAt": 1791278100000,
  "endTime": null,
  "firstSeenAt": 1791278100100,
  "level": "62000.0",
  "invalidateLevel": "61969.0",
  "anchorSwingId": "swing-high-example",
  "engineVersion": "structure-breakout-v1",
  "parametersHash": "example-hash",
  "instrumentMetadataVersion": "metadata-example-hash",
  "resultRevision": 1,
  "evidence": {
    "evaluatedCandleOpenTime": 1791277200000,
    "close": "62120.0",
    "breakoutBuffer": "31.0",
    "volumeFilterEnabled": false,
    "volumeRatio": null,
    "reasonCodes": ["CLOSE_ABOVE_BUFFERED_RESISTANCE"]
  },
  "confirmCondition": {
    "basis": "CLOSED_CANDLE",
    "operator": "GT",
    "threshold": "62031.0",
    "requiredCloses": 1
  },
  "invalidateCondition": {
    "basis": "CLOSED_CANDLE",
    "operator": "LT",
    "threshold": "61969.0",
    "observationBars": 10
  }
}
```

状态枚举：`CANDIDATE / FORMING / CONFIRMED / INVALIDATED / EXPIRED / COMPLETED`。type 首版仅 `BREAKOUT`。方向 `BULLISH / BEARISH`。

`isProvisional=true` 仅表示未收盘 preview，可能撤回，不能作为 canonical 已确认状态。Pattern ID 由序列、规则版本/参数、instrumentMetadataVersion、anchorSwingId、方向确定；不因重绘产生新 ID。

resultRevision 对应生成结果时的 datasetRevision。Canonical Transition：`patternId / resultRevision / transitionIndex / fromStatus / toStatus / evaluatedAt / firstSeenAt / reasonCodes`，其中新实例的 fromStatus 为 null。只存收盘规则确定的转换；同根收盘可产生有序的 FORMING、CONFIRMED 转换。详情接口按请求的当前有效版本返回权威 Pattern 和 canonical transition 列表，临时 preview 不混入历史；首版不提供 RETIRED 代查询。

首版不返回 confidence；条件是结构化数据，前端根据字段展示中文说明，不能自己另算阈值。

## 6. Chart Annotation

```ts
interface ChartAnnotation {
  id: string;
  kind: 'MARKER' | 'HORIZONTAL_LINE' | 'ZONE';
  semantic: 'SWING_HIGH' | 'SWING_LOW' | 'STRUCTURE'
    | 'SUPPORT' | 'RESISTANCE' | 'BREAKOUT';
  startTime: number;
  endTime: number | null;
  price: string | null;
  priceUpper: string | null;
  priceLower: string | null;
  label: string;
  status: Pattern['status'] | null;
  isProvisional: boolean;
  knownAt: number;
  patternId: string | null;
  swingId: string | null;
}
```

这是说明性 TypeScript 视图，正式类型由 schema 生成。Annotation 只包含语义和几何，不包含 CSS class、颜色、React 节点或图表实例。价格线、marker、zone 如何绘制由前端决定。

## 7. ChartSnapshot

Snapshot 必须在同一 session lock 下生成，避免 Candle 已更新而 Pattern 仍属于上一个 seq。

```ts
interface ChartSnapshot {
  schemaVersion: '1';
  instrument: Instrument;
  timeframe: Timeframe;
  epoch: string;
  seq: number;
  datasetRevision: number;
  generatedAt: number;
  engineVersion: string;
  parametersHash: string;
  instrumentMetadataVersion: string;
  analysisStartTime: number;
  lastProcessedCloseTime: number | null;
  liveWindow: { from: number; to: number }; // 最近最多 500 根的公共范围，[from,to)
  candles: Candle[];                  // 固定公共窗口内，升序；历史另行分页
  swings: SwingPoint[];
  structure: StructureState;
  levels: KeyLevel[];
  patterns: Pattern[];                // 活跃及与公共 liveWindow 相交的终止结果
  annotations: ChartAnnotation[];
  quality: SeriesQuality;
}

interface SeriesQuality {
  provider: string;
  deliveryMode: 'LIVE' | 'DELAYED' | 'HISTORICAL' | 'MOCK';
  connection: 'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'OFFLINE';
  isStale: boolean;
  isComplete: boolean;
  lastMarketEventAt: number | null;    // 本机接收最近上游行情的时间
  lastClosedOpenTime: number | null;
  missingRanges: Array<{ from: number; to: number }>;
  processing: ProcessingStatus;
}

interface ProcessingStatus {
  state: 'WARMING_UP' | 'READY' | 'REBUILDING' | 'DEGRADED';
  reasonCodes: ProcessingReason[];
  stateSince: number;
  lastProcessedCloseTime: number | null;
  lastSuccessfulProcessAt: number | null;
  pendingDatasetRevision: number | null;
}

type ProcessingReason = 'BOOTSTRAP' | 'HISTORY_CORRECTION' | 'CONFIG_CHANGED'
  | 'ANALYSIS_START_CHANGED' | 'METADATA_CHANGED' | 'DATA_GAP'
  | 'DATABASE_WRITE_FAILED' | 'STORAGE_LOW' | 'INPUT_OVERFLOW'
  | 'REBUILD_TIMEOUT' | 'CAPACITY_EXCEEDED' | 'PUBLISH_FAILED';
```

seq 是该 epoch 内事件批次序号；datasetRevision 只在历史修正、analysis 边界或配置重建等变化时推进，正常追加不推进。epoch 在服务重启或序列重建时变化，不能跨 epoch 应用增量。

processing 与上游 connection / isStale 正交：行情仍在到达时数据库或算法也可能 DEGRADED。lastClosedOpenTime 是最近接收到的上游已收盘 bar；processing.lastProcessedCloseTime 是算法已成功持久化的逻辑边界，与快照 / update 顶层同名字段一致。lastSuccessfulProcessAt 是本机成功提交时间，不能用它代替行情时间。READY 时 reasonCodes 为空；初始化无已提交结果时两个处理时间为 null。REBUILDING 带 pendingDatasetRevision；失败任务结束后它为 null。reasonCodes 仅描述处理状态，算法证据中的 reasonCodes 使用独立枚举。

| processing.state | 前端展示 | 数据响应 |
| --- | --- | --- |
| WARMING_UP | 历史准备中 | 尚无权威数据的接口 503 `SERIES_WARMING_UP` |
| READY | 识别已更新至指定收盘时间 | 返回当前代；仍单独标识行情 STALE / OFFLINE |
| REBUILDING | 正在重新计算，当前为旧版结果 | 已缓存旧代可读；需访问冻结代缺失历史时 503 `SERIES_REBUILDING` |
| DEGRADED | 识别暂停，显示原因与最后处理位置 | 可确定一致的旧结果继续提供；ACTIVE 指针与内存不一致时 503 `SERIES_UNAVAILABLE` |

## 8. REST

| 方法 / 路径 | 参数 | 响应 |
| --- | --- | --- |
| GET `/instruments` | 无 | `{ items: Instrument[] }`，仅开放 allowlist |
| GET `/candles` | instrumentId、timeframe、epoch、datasetRevision、before?、limit=500（1–1000） | `{ items, nextBefore, hasMore, epoch, seq, datasetRevision, quality }` |
| GET `/chart` | instrumentId、timeframe | ChartSnapshot，固定最近最多 500 根 |
| GET `/patterns/{id}` | instrumentId、timeframe、epoch、datasetRevision | `{ pattern, transitions, epoch, seq, datasetRevision }`，Pattern.resultRevision 必须匹配 |
| GET `/annotations` | instrumentId、timeframe、epoch、datasetRevision、from、to、cursor?、limit=1000（1–2000） | 当前代历史标注分页，不扩展分析起点 |
| GET `/watchlist` | timeframe=15m | `{ items: [{ instrumentId, epoch, seq, datasetRevision, structure, activePatternIds, quality }], generatedAt }` |
| GET `/health/live` | 无 | 进程状态 |
| GET `/health/ready` | 无 | 数据库 / 后台任务状态及 provider 摘要 |

表内路径均附加 `/api/v1` 前缀。`before` 是 openTime 排他边界，返回升序、不重复。items 为空且 hasMore=false 才表示该数据源历史已耗尽；请求失败是错误响应。

annotations 响应为 `{ items: ChartAnnotation[], nextCursor, hasMore, epoch, seq, datasetRevision, coverage: { analysisStartTime, requestedFrom, requestedTo, isFullyCovered } }`。`[from,to)` 必须对齐周期，最多跨 2,000 根；范围内按 `(knownAt,id)` 稳定排序，游标绑定序列、版本和范围。分页期间普通状态更新允许改变字段值，不改变排序键；最新公共窗口内由 SSE 覆盖更新。hasMore=false 表示本次范围已取完，coverage.isFullyCovered 表示范围是否都在分析覆盖内，两者不能混用。跨越 analysisStartTime 的范围只返回已有标注并说明 coverage，不扩展分析起点。

首次取 `/chart` 获得 epoch / datasetRevision，后续历史、标注和详情请求必须携带二者。缺失参数 422；epoch 不符返回 409 `SESSION_EPOCH_MISMATCH`，否则 datasetRevision 不符返回 409 `DATASET_REVISION_MISMATCH`，details 带当前版本。校验在 ReadContext 取得时执行，请求只读该上下文对应的代。切换前开始的旧请求可以完成，但前端按响应版本丢弃迟到数据，不混入新缓存。详情不能省略版本而自动跳到最新版；重建发布后先刷新 chart 再请求其他接口。

### 公共实时窗口与历史视口

- 服务端 liveWindow 固定为最近最多 500 根已存在 Candle（含未收盘 bar），from 为第一根 openTime，to 为最后一根 closeTime。窗口只随行情推进，不接受浏览器 viewport 参数。
- snapshot / SSE 携带窗口内 Swing、标注和终止 Pattern，以及所有活跃 Pattern、当前关键位和它们需要的 anchor Swing。客户端历史视口通过 `/candles`、`/annotations` 独立获取。
- 窗口移出的 candle / swing / canonical Pattern / annotation 只从客户端 live 集合移除，不是删除历史事实。历史页按版本和范围单独缓存，live 结果对相同 ID 优先；需要补查的历史窗口重新请求，不能由另一个客户端的滚动触发删除。
- epoch / datasetRevision 改变时保存用户视口时间范围，清空旧版数据和请求，安装公共新快照后按新版本重取原视口。已无数据时明确提示；不自动跳回最新行情。当前选择的 Pattern ID 在新代不存在时关闭详情并说明结果已更新。

## 9. SSE

订阅：`GET /api/v1/stream?instrumentId=...&timeframe=...&epoch=...&afterSeq=...`。

event 类型：`snapshot / update / status / reset`。快照 data 为完整 ChartSnapshot。其他事件都包含 `schemaVersion / instrumentId / timeframe / epoch / seq / datasetRevision / emittedAt`。

update payload：

```ts
interface ChartUpdatePayload {
  liveWindow: { from: number; to: number };
  candleUpserts: Candle[];
  candleRemovals: number[];            // 离开公共 liveWindow 的 openTime
  structure: StructureState;
  swingUpserts: SwingPoint[];
  swingRemovals: string[];             // 离开 live 集合且不再被活跃对象引用
  levels: KeyLevel[];                  // 全量替换当前关键位
  patternUpserts: Pattern[];
  patternRemovals: string[];           // 撤回 provisional 或移出公共 live 集合
  annotationUpserts: ChartAnnotation[];
  annotationRemovals: string[];
  lastProcessedCloseTime: number | null;
  quality: SeriesQuality;
}
```

status payload 仅包含 quality（含 processing）；同样占用 seq。reset 是发布新代时的控制帧，带 reason、新 epoch / datasetRevision、seq=0，不设置 SSE id，不推进恢复游标；客户端进入等待 snapshot 状态。紧随其后的完整 snapshot 设置新 epoch:0，前端必须安装它，不能因 reset 的 seq=0 把它当成重复。HTTP/SSE payload 全部进行 runtime schema 验证。

SSE `id` 格式为 `<epoch>:<seq>`，epoch 使用不含冒号的 UUID。浏览器自动重连带 `Last-Event-ID`，该 header 优先于 URL 的初始 epoch/afterSeq；token 始终绑定当前 instrument/timeframe，跨序列 token 无效。

恢复步骤：

1. REST snapshot 得到 token。
2. SSE endpoint 在 session lock 下完成客户端注册，记录当前高水位 S，检查 token。新注册客户端实时队列只接收 seq>S；网络发送在锁外执行。
3. 同 epoch、ring 完整且 `(token.seq,S]` 不超过 64 批 / 512 KiB：复制有界补发列表，先顺序发送该列表，再消费实时队列。补发列表独立于 128 批客户端实时队列并纳入全局内存预算。
4. token 过期、未来 seq、epoch 不同、ring 缺失或补发超过预算：在同一注册临界区准备 seq=S 的完整 snapshot，先发送它，再消费 seq>S 的实时队列，不拼接不完整增量。
5. 客户端忽略相同 epoch 下 seq ≤ 已应用值的重复 update/status；seq 缺口触发重同步。snapshot 在首次订阅、重同步、等待 reset 后快照时按版本安装，不套用普通增量的连续序号要求。
6. 补发期间实时队列仍溢出则关闭连接；客户端指数退避 1–30 秒加 jitter 重连，连续 3 次未取得进展则重新 GET chart。主动重建 EventSource 时 URL token 使用最后已应用值，不能继续使用最初的旧 token。

ring 512 批 / 8 MiB、每客户端实时队列 128 批 / 2 MiB，以先到上限为准；完整 snapshot 单独占一个发送槽，最大 2 MiB。总连接数、发送期限和全局字节预算见 [资源预算](../backend/operations.md#1-资源预算与超时)。注释心跳每 15 秒发送，不分配 seq，也不更新行情 freshness。

## 10. 错误契约

```json
{
  "error": {
    "code": "SERIES_WARMING_UP",
    "message": "Historical candles are being prepared",
    "retryable": true,
    "requestId": "request-example"
  }
}
```

包括 `UNSUPPORTED_TIMEFRAME / UNKNOWN_INSTRUMENT / PROVIDER_UNAVAILABLE / RATE_LIMITED / SERIES_WARMING_UP / SERIES_REBUILDING / SERIES_UNAVAILABLE / SESSION_EPOCH_MISMATCH / DATASET_REVISION_MISMATCH / PATTERN_NOT_FOUND / CAPACITY_EXCEEDED / QUERY_TIMEOUT / QUERY_RANGE_TOO_LARGE`。422 请求校验错误也统一此 envelope，details 可携带字段名。HTTP 状态按 [资源预算](../backend/operations.md#1-资源预算与超时) 与上述 REST 约定映射；有明确等待时间时返回 Retry-After。错误不能包含秘密或原始认证 header。

## 11. 契约验证

- JSON fixtures：Candle、Snapshot、每种 SSE event、错误响应、Pattern Detail。
- 时间单位、BigDecimal 到十进制字符串的映射、null、枚举、分页排他性和唯一键验证。
- TypeScript DTO 生成后运行 `tsc`；使用源 JSON Schema 校验 Java 服务实际输出的 REST / SSE payload，以及固定 fixtures。
- 契约测试确保 candle 与算法状态属于同一 seq、旧 revision 不混入当前图表。
- 前后端同时使用固定 fixtures；版本变更先修改 schema 和样例，再生成代码。
- 并行重建和历史分页不混代；重启 epoch 改变后旧响应被丢弃；元数据版本与阈值一致。
- processing 与 connection 独立变化；数据库失败后不得显示“识别正常”；snapshot 顶层与 processing 的处理边界一致。
- 两个客户端查看不同历史窗口互不影响；补发 64 / 65 / 512 批、字节上限和慢消费者覆盖恢复分支。
