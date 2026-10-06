# Trading Coach 前后端数据契约

状态：v1 设计提案；作为未来代码生成与契约测试依据，不代表接口已实现。

## 1. 通用约定

- API 前缀 `/api/v1`；JSON 字段 camelCase。
- 所有时间为 UTC Unix **毫秒**。仅图表 Adapter 转 Unix 秒。
- OHLC、volume、tickSize、level 等十进制量通过字符串传输，后端 Decimal 判定，前端校验后转换图表 number。
- `instrumentId` 唯一包含 provider、market、原生代码；`symbol` 仅为展示文字。
- timeframe 枚举：`1m / 5m / 15m / 1h / 4h / 1d`；MVP 不支持任意周期。
- `closeTime` 为排他结束时间，例如 15m bar 是 `[openTime, openTime + 900000)`。
- `confirmedAt` / `evaluatedAt` 表示收盘判定的逻辑时间；`receivedAt` / `firstSeenAt` 记录系统实际收到/发现的时间。历史回补不得把逻辑时间声称为实时发现时间。
- schemaVersion 与 API 主版本分别管理；破坏性字段变更升级 API，不手工分别修改两端类型。

Pydantic v2 model 是 HTTP 与 SSE DTO 的唯一 schema 来源。HTTP 导出 OpenAPI；所有 SSE payload 额外导出 JSON Schema，因为 OpenAPI 不会自动描述 StreamingResponse 内的事件。生成 TypeScript 类型和运行时校验器，CI 验证生成产物无漂移。

实施工具建议：HTTP 类型使用 openapi-typescript；SSE 类型使用 json-schema-to-typescript；运行时使用 Ajv 的 JSON Schema 2020-12 支持并预编译 validator。先对 schema 做引用打包，再生成产物。前端允许兼容版本的新增非必需字段，但必需字段、Decimal 格式、枚举和时间单位必须校验；不要以忽略全部解析错误实现所谓兼容。

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
  "supportedTimeframes": ["1m", "5m", "15m", "1h", "4h", "1d"]
}
```

示例 tickSize 不作为交易所当前值，实现从 instrument metadata 获取。

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

唯一键为 instrumentId + timeframe + openTime。`volume` 为 base asset；`quoteVolume` 可为 null，不能用 base volume 冒充。未收盘 confirmedAt 为 null。revision 是服务端接受的该 Candle 版本，不是交易所原生序号。

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

`isProvisional=true` 仅表示未收盘 preview，可能撤回，不能作为 canonical 已确认状态。Pattern ID 由序列、规则版本/参数、anchorSwingId、方向确定；不因重绘产生新 ID。

resultRevision 对应生成结果时的 datasetRevision。Canonical Transition：`patternId / resultRevision / transitionIndex / fromStatus / toStatus / evaluatedAt / firstSeenAt / reasonCodes`，其中新实例的 fromStatus 为 null。只存收盘规则确定的转换；同根收盘可产生有序的 FORMING、CONFIRMED 转换。详情接口返回当前权威 Pattern 和 canonical transition 列表，临时 preview 不混入历史。

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
  analysisStartTime: number;
  lastProcessedCloseTime: number | null;
  candles: Candle[];                  // 默认最近 500，升序
  swings: SwingPoint[];
  structure: StructureState;
  levels: KeyLevel[];
  patterns: Pattern[];                // 活跃和可见范围内的终止结果
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
}
```

seq 是该 epoch 内事件批次序号；datasetRevision 只在历史修正、analysis 边界或配置重建等变化时推进，正常追加不推进。epoch 在服务重启或序列重建时变化，不能跨 epoch 应用增量。

## 8. REST

| 方法 / 路径 | 参数 | 响应 |
| --- | --- | --- |
| GET `/instruments` | 无 | `{ items: Instrument[] }`，仅开放 allowlist |
| GET `/candles` | instrumentId、timeframe、before?、limit=500（1–1000） | `{ items, nextBefore, hasMore, datasetRevision, quality }` |
| GET `/chart` | instrumentId、timeframe、limit=500（1–1000） | ChartSnapshot |
| GET `/patterns/{id}` | resultRevision? | 当前结果及 transitions；默认当前有效数据版本 |
| GET `/annotations` | instrumentId、timeframe、from、to、datasetRevision | 对历史可视区生成标注，不扩展分析起点 |
| GET `/watchlist` | timeframe=15m | `{ items: [{ instrumentId, structure, activePatternIds, quality }], generatedAt }` |
| GET `/health/live` | 无 | 进程状态 |
| GET `/health/ready` | 无 | 数据库 / 后台任务状态及 provider 摘要 |

表内路径均附加 `/api/v1` 前缀。`before` 是 openTime 排他边界，返回升序、不重复。items 为空且 hasMore=false 才表示该数据源历史已耗尽；请求失败是错误响应。

annotations 响应为 `{ items: ChartAnnotation[], datasetRevision, coverage: { analysisStartTime, requestedFrom, requestedTo, isFullyCovered } }`，`[from,to)` 范围与 candles 时间边界一致。较早数据可能仅显示 K 线；如果在 analysisStartTime 之前，没有算法结果，返回 coverage 说明，不临时改变全局引擎。过期版本请求返回 HTTP 409、`DATASET_REVISION_MISMATCH`，前端重新取 snapshot。

## 9. SSE

订阅：`GET /api/v1/stream?instrumentId=...&timeframe=...&epoch=...&afterSeq=...`。

event 类型：`snapshot / update / status / reset`。快照 data 为完整 ChartSnapshot。其他事件都包含 `schemaVersion / instrumentId / timeframe / epoch / seq / datasetRevision / emittedAt`。

update payload：

```ts
interface ChartUpdatePayload {
  candleUpserts: Candle[];
  structure: StructureState;
  swingUpserts: SwingPoint[];
  levels: KeyLevel[];                  // 全量替换当前关键位
  patternUpserts: Pattern[];
  patternRemovals: string[];           // 删除撤回的 provisional / 不再可见结果
  annotationUpserts: ChartAnnotation[];
  annotationRemovals: string[];
  lastProcessedCloseTime: number | null;
  quality: SeriesQuality;
}
```

status payload 仅包含 quality；同样占用 seq。reset 包含 reason 和新 epoch，客户端停止增量并接受紧随其后的完整 snapshot。HTTP/SSE payload 全部进行 runtime schema 验证。

SSE `id` 格式为 `<epoch>:<seq>`，epoch 使用不含冒号的 UUID。浏览器自动重连带 `Last-Event-ID`，该 header 优先于 URL 的初始 epoch/afterSeq；token 始终绑定当前 instrument/timeframe，跨序列 token 无效。

恢复步骤：

1. REST snapshot 得到 token。
2. SSE endpoint 在 session lock 下完成客户端注册、检查 token 和准备补发序列，消除订阅窗口竞态。
3. 同 epoch 且 ring 完整：补发所有 seq > token.seq，再消费实时队列。
4. token 过期、未来 seq、revision 改变或 epoch 不同：发送最新完整 snapshot，不拼接不完整增量。
5. 客户端忽略相同 epoch 下 seq ≤ 已应用值的重复；seq 缺口触发重同步。

ring 512 批次、每客户端队列 128 批次是初始可配置值。慢消费者队列溢出关闭连接；重连不能恢复时用 snapshot。注释心跳每 15 秒发送，不分配 seq，也不更新行情 freshness。

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

包括 `UNSUPPORTED_TIMEFRAME / UNKNOWN_INSTRUMENT / PROVIDER_UNAVAILABLE / RATE_LIMITED / SERIES_WARMING_UP / DATASET_REVISION_MISMATCH / PATTERN_NOT_FOUND`。422 请求校验错误也统一此 envelope，details 可携带字段名。错误不能包含秘密或原始认证 header。

## 11. 契约验证

- JSON fixtures：Candle、Snapshot、每种 SSE event、错误响应、Pattern Detail。
- 时间单位、Decimal、null、枚举、分页排他性和唯一键验证。
- DTO 生成后运行 `tsc`，生成的 JSON Schema 校验真实 REST/SSE payload。
- 契约测试确保 candle 与算法状态属于同一 seq、旧 revision 不混入当前图表。
- 前后端同时使用固定 fixtures；版本变更先修改 schema 和样例，再生成代码。
