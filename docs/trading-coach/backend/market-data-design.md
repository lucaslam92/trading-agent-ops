# Trading Coach 数据源设计与旧分支参考

状态：设计提案；已阅读远程分支的设计与源码，尚未验证交易所在线接口。检查日期：2026-10-06。数据源属于后端职责；统一 DTO 见 [shared 契约](../shared/api-contracts.md)。

## 1. 找到的参考分支

### 市场监控终端

分支：`claude/market-structure-trading-manual-11y7C`，检查提交：`9e38e7fb6f8128c06da90585e7987cbf7a659abc`。

- [后端设计](https://github.com/lucaslam92/trading-agent-ops/blob/9e38e7fb6f8128c06da90585e7987cbf7a659abc/docs/market-backend-design.md)：FastAPI、DataAdapter、Scheduler、SSE、SQLite。
- [适配器接口](https://github.com/lucaslam92/trading-agent-ops/blob/9e38e7fb6f8128c06da90585e7987cbf7a659abc/market-api/adapters/base.py)：`fetch() → RawSnapshot`。
- [东方财富实现](https://github.com/lucaslam92/trading-agent-ops/blob/9e38e7fb6f8128c06da90585e7987cbf7a659abc/market-api/adapters/eastmoney.py)：HTTP 快照、Yahoo 全球参考补充。
- [Tushare 实现](https://github.com/lucaslam92/trading-agent-ops/blob/9e38e7fb6f8128c06da90585e7987cbf7a659abc/market-api/adapters/tushare_adapter.py)：日频 / 盘后数据。
- [SSE 实现](https://github.com/lucaslam92/trading-agent-ops/blob/9e38e7fb6f8128c06da90585e7987cbf7a659abc/market-api/sse_manager.py)：每客户端 asyncio.Queue 广播。

可以参考数据源与前端解耦、公共 API 契约、生命周期管理、SSE 心跳、同域部署。以上 FastAPI / asyncio 是旧分支实现；Trading Coach 已选定 Java + Spring Boot，使用 Spring 生命周期管理和受控任务队列重新实现。当前接口提供指数、板块资金流、市场宽度等“快照”，不能作为 Trading Coach 的历史 / 实时 OHLCV 接口直接复用。

代码与文档存在差异：东方财富代码使用 `push2delay.eastmoney.com`，设计写 `push2.eastmoney.com`；前端代码断线标为 disconnected，旧设计有回退 mock 描述。Trading Coach 使用独立 freshness / deliveryMode，不根据 provider 名称就显示“实时”，不采用静默 mock 回退。

### BTC 量化系统

分支：`claude/btc-ai-vnpy-system-vAQ2B`，检查提交：`b41440069e269cf5093f47fc37716f40c955b843`。

- [历史下载代码](https://github.com/lucaslam92/trading-agent-ops/blob/b41440069e269cf5093f47fc37716f40c955b843/scripts/download_data.py)：实际调用 OKX `market/history-candles`，倒序分页、转换 UTC 时间、写入 vn.py 数据库。
- [行情服务](https://github.com/lucaslam92/trading-agent-ops/blob/b41440069e269cf5093f47fc37716f40c955b843/services/market_data_service.py)：读取 vn.py bar，计算指标。

旧使用指南仍写 Binance，接入参考以源码为准。这里可复用的是分页、时间和成交量字段映射思路，不引入 vn.py、交易网关或回测依赖。

已有代码需要改进后才能用于 Coach：

- `_to_bar_data()` 未保留 OKX `confirm`，Coach 必须保留收盘状态。
- 日线映射为 `1D`，Coach 统一 UTC 日线应核验 `1Dutc`，不能混用日线边界。
- 请求失败返回 `[]`，会把失败与数据耗尽混淆；新接口区分错误、空结果和 end-of-history。
- 成交量读取 `volCcy`，新适配器要按 SPOT / SWAP 官方定义验证单位；不硬编码合约张数对应 BTC 数量。
- 下载脚本的固定 sleep、内存累积和周期 enum 依赖需要替换为共享限流器、受控 I/O 任务、分块写入和明确的周期映射。

## 2. 数据源选择

| 来源 | 已有内容 | Coach 用途 | MVP 结论 |
| --- | --- | --- | --- |
| Fixture / Mock | 旧分支有随机快照 | 固定 OHLCV 数据、无网络测试 | 首先实现，固定 seed / 数据文件 |
| OKX | 已有历史 OHLCV 下载 | Crypto 现货历史 + 实时 Candle | 首个真实适配器 |
| Binance Spot | 旧指南和交易相关设计 | 同类替代交易所 | 后续独立适配器，不自动混合数据 |
| 东方财富 | A 股快照、板块数据 | 后续 A 股源参考 | 现有快照不能替代 K 线；延迟须识别 |
| Tushare | 日频、盘后补充 | 后续 A 股历史 / 核验 | 不作为六周期实时 Crypto 源 |
| Yahoo | 全球参考报价 | 后续多市场研究参考 | 现有使用方式非完整 K 线供应链，首版不接 |

选择 OKX 基于现有代码和 MVP 市场，不声称已经完成地区可用性、许可或实时频道验证。Binance 是替代 provider；真实源暂不可用时允许使用明确标识的 fixture 模式继续开发。

## 3. 品种、周期和来源隔离

- instrumentId：`okx:spot:BTC-USDT`，包含 provider / market / provider symbol。
- 首版市场：现货；默认 BTC-USDT 和 ETH-USDT，不混入永续合约。
- 数据序列键：`instrumentId + timeframe`；不同 venue 的 BTC 不共用 series。
- Binance 将使用如 `binance:spot:BTCUSDT` 的独立 instrumentId。
- 统一 UTC；`openTime` 为 Unix 毫秒，日线边界是 UTC 00:00。

| 产品周期 | OKX REST bar / WS candle channel 映射候选 |
| --- | --- |
| 1m | 1m / candle1m |
| 5m | 5m / candle5m |
| 15m | 15m / candle15m |
| 1h | 1H / candle1H |
| 4h | 4H / candle4H |
| 1d | 1Dutc / candle1Dutc |

频道名称和适用 endpoint 必须在接入时对照官方当前文档。上表是待核验的映射，不是联调结果。六个周期优先取交易所原生 bar，首版不在前端用不同历史长度临时聚合；fixture 预先提供六周期数据或由测试工具按 UTC 完整聚合。

## 4. Adapter 契约

```java
public interface MarketDataAdapter extends AutoCloseable {
    List<Instrument> listInstruments();

    CandlePage fetchCandles(
        String instrumentId, Timeframe timeframe,
        OptionalLong before, int limit
    );

    MarketDataSubscription subscribe(
        List<SeriesKey> subscriptions, MarketDataListener listener
    );

    ProviderHealth health();
    @Override void close();
}

public interface MarketDataListener {
    void onUpdate(NormalizedCandleUpdate update);
    void onFailure(MarketDataException failure);
    void onClosed();
}

public interface MarketDataSubscription extends AutoCloseable {
    @Override void close();
}
```

以上为分文件的 Java 接口示意，领域类型详见统一契约。REST 方法在受限 I/O executor 中调用，具有超时和取消边界；网络 / 上游错误抛出带错误分类与可重试标记的 `MarketDataException`。JDK HttpClient 负责 REST，JDK WebSocket 负责实时连接。Listener 只投递有界队列，不执行算法或数据库写入；队列拒绝时通知 Collector 标记 incomplete、关闭订阅并启动 REST 对账，不能静默丢弃。`close()` 幂等，释放连接并等待回调结束，回调线程不调用会等待自身结束的清理操作。重连由 Collector 统一管理，避免 Adapter 和 Collector 双重重试。

`before` 统一为 openTime 排他边界；返回升序 Candle、next cursor、hasMore。Adapter 负责把 provider 原生分页转换成统一语义。`NormalizedCandleUpdate` 带 provider 收盘标记、可用的上游时间/序号和接收时间，交给 Reconciler 判定 revision。

接口不涉及数据库、图表、趋势或 Pattern；无数据用空页，超时 / HTTP 错误 / 业务错误用 typed error。Provider 仅接受配置的 host、instrument 和周期，浏览器不能指定任意上游 URL。

## 5. Candle 归一化

OKX 原始数组为 `[ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]`，按交易所当前 SPOT 字段定义映射：

- OHLC 保留十进制字符串，后端规则使用从字符串构造的 `BigDecimal`；不经 double 中转。
- Instrument 的 tickSize、base/quote、成交量单位保存为不可变 instrumentMetadataVersion；启动 / 重连及每 6 小时刷新最新观测值，分析代继续引用其固定版本。变化进入 METADATA_CHANGED，采用新版本按 [元数据流程](consistency-and-recovery.md#4-品种元数据版本) 显式重建。
- 统一 `volume` 为 base asset 数量，`quoteVolume` 为 quote asset 成交额，Instrument 中记录 base/quote。
- 对 SPOT 先核验 `vol` / `volCcy` 的实际币种；对未来 SWAP 使用合约元数据，不能把张数当 BTC。
- `confirm` 决定 isClosed；provider 时间毫秒原样归一化。
- `closeTime = openTime + intervalMs` 为排他的周期结束边界，和 provider 的 inclusive close timestamp 区分。
- `confirmedAt` 是市场收盘逻辑时间；`receivedAt` 是本系统收到更新的时间。

校验：有限非负 volume、正价格、high ≥ max(open, close)、low ≤ min(open, close)、时间与周期对齐、来源正确。校验不通过隔离记录并设置 quality，不以 0 替代缺失字段。

## 6. 缓存、分页和补齐

历史 REST：读取请求所绑定的 ACTIVE 代，本地 SQLite 优先；缺失范围由共享请求协调器拉取并分块 upsert。重建时源代冻结，缓存缺失返回 SERIES_REBUILDING，不向旧代写入；常规缺失插入不改变分析起点，同键已收盘冲突只能写入新 BUILDING 代并走统一发布流程。向左分页必须验证 cursor 严格变小；provider 重复返回同页时退出并记录错误，避免无限请求。

实时 WS：共享订阅、连接重试、事件去重；重连后用 REST 带重叠补齐。晚到收盘消息可以完成对应旧 bar，不能因已经收到新 bar 而丢弃。

发现缺口时暂停跨缺口推进确认算法，quality 标为 incomplete。未补齐之前不凭空插入零成交量 Candle。历史数据耗尽、新上市品种、源故障分别处理。

Provider 不提供可靠 revision 时，由 Reconciler 对同键规范化 payload 比较：重复忽略；未收盘更新接受当前连接的有效更新；重连后 REST 对账；已收盘冲突触发修正流程。不能把系统接收时间视为交易所版本时间来“证明”数据更准确。

## 7. 失败、限流与切源

- REST 超时、429、业务错误采用有限重试、指数退避与 jitter；若上游有 Retry-After 则遵守。次数、期限和共享并发预算见 [运行维护](operations.md#1-资源预算与超时)，不得在多个层次叠加重试。
- WS 使用 provider 要求的 ping/pong、重连和订阅速率限制；限流器按 provider 共享。
- 参数、地区拒绝和明确权限错误不无限重试。
- 数据 freshness 与网络 connected 分开：SSE 心跳正常也可能 market data stale。
- 每个 Adapter 声明预期推送间隔与 staleAfterMs，依据当前官方频道行为核验；OKX 活跃品种的初始 stale 阈值建议 30 秒，联调后调整。独立健康定时器即使没有行情消息也更新 stale 状态并发布 status；不用 Candle closeTime 判断日线推送连接是否健康。
- 真实行情失败继续显示最后真实快照，状态为 stale/offline；fixture 仅显式启用。
- 切换 OKX → Binance 是选择新 instrument、新数据缓存和新算法实例，不自动继承旧关键位或 Pattern。

服务和 UI 都显示 `provider / market / deliveryMode / lastMarketEventAt / quality`，避免延迟报价被误认作实时。

## 8. 接入验证清单

实现 Adapter 前读取官方当前文档；保存非敏感示例 payload 和文档版本/核验日期。需验证：

1. 部署网络能访问官方 REST 和 WS；本次未发起交易所网络请求。
2. BTC/ETH 现货 instrument、tickSize、volume 单位与六周期支持。
3. UTC 日线边界、收盘标记和 WS 频道。
4. 分页边界、最大条数、历史覆盖和速率限制。
5. 从 REST 到实时的 overlap、收盘切换、断线补齐。
6. 重复 / 乱序 / 错误响应不能生成重复确认或虚假 Candle。
7. 对照相同交易所、相同市场、相同 UTC 周期的官方图表检查 OHLCV。

后续股票市场另行设计交易日历、休市、时区、复权和数据权限；不把 Crypto 的 24 小时规则直接推广过去。
