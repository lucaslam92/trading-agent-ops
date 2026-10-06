# Trading Coach 前端技术架构

状态：设计提案。依赖：[统一契约](../shared/api-contracts.md)、[识别规则](../backend/technical-engine-spec.md)。

## 1. 职责与技术栈

前端负责选标的/周期、绘制 K 线与标注、展示算法证据、维护连接状态与偏好。后端提供权威行情和识别结果。

| 能力 | 选择 |
| --- | --- |
| 语言 / 构建 | TypeScript strict、React、Vite；依赖版本与 lockfile 在实施时锁定 |
| 路由 | React Router；Chart 的 instrumentId / timeframe 放 URL |
| REST 状态 | TanStack Query；历史分页和缓存 |
| UI 状态 | Zustand；选择、标注开关、详情和连接状态 |
| 图表 | Lightweight Charts；库调用集中于 ChartAdapter |
| 契约 | Pydantic 导出的 OpenAPI / JSON Schema 生成 TS 类型和运行时校验器 |
| 样式 | CSS Modules + CSS 自定义变量；UI Kit 可替换 |
| 验证 | Vitest、React Testing Library、Playwright |

采用最新兼容稳定版本前先验证图表 API；不使用 `latest` 作为提交的版本约束，不加载运行时 Babel 或外部 React CDN。

## 2. 目录与依赖边界

```text
trading-coach/frontend/
  src/
    app/                 # 入口、路由、providers、错误边界
    pages/               # WatchlistPage、ChartPage
    features/
      watchlist/         # 摘要、导航
      chart/             # ChartController、Toolbar、OHLC、连接提示
      pattern-detail/    # Evidence、条件、状态历史
    domain/              # Candle / Pattern 的前端只读视图类型、纯转换
    api/
      generated/         # 自动生成 DTO / 校验器，不手改
      http-client.ts
      chart-stream.ts
      stream-reducer.ts
    chart/
      chart-adapter.ts
      annotation-projector.ts
      renderers/         # Candle、Volume、Swing、Structure、Pattern
      primitives/        # 区域 / 点击命中等扩展
    state/               # ChartSessionStore、PreferencesStore
    ui/                  # 可替换展示组件，不依赖 provider DTO
    styles/              # tokens.css、基础样式
    test/fixtures/
```

依赖方向：页面 → feature → domain / api / chart；chart 可以使用 domain，不导入页面或业务 store。API 层不操纵图表实例。任何交易所字段转换留在后端。

## 3. 页面与交互

### Watchlist

- 首版固定 BTC/ETH 的现货 instrument，提供默认 `15m` 结构摘要。
- 趋势显示 `UPTREND / DOWNTREND / RANGE / UNKNOWN`；展示数据时间和来源。
- 点击进入 Chart URL；服务暂时不可用时保留最后摘要并标记状态。
- 只存本地展示偏好，首版无需账号和跨设备同步。

### Chart

- URL：`/chart?instrumentId=okx:spot:BTC-USDT&timeframe=15m`。
- 工具栏：标的、周期、Swing/结构/突破标注开关、数据状态。
- 主图 K 线、下方 Volume；共用时间轴和十字线。
- Crosshair OHLC 来自光标时间的 Candle，不误用最新报价。
- 左侧历史分页保留当前可视区；追加实时行情时，只有用户正在跟随最新价格才滚动。
- 加载、无数据、数据缺口、断线分别呈现，不用空白图替代错误状态。

### Pattern Detail

- 点击 marker / line / zone 通过 `annotationId → patternId` 解析。
- 展示方向、当前状态、关键位、判定时间、Swing 证据、确认/失效条件。
- 关闭成交量过滤时显示“未启用成交量确认”，不生成虚构倍数。
- `confidence` 首版省略；任何后续匹配分数需要明确含义。

## 4. 状态管理

| 状态 | 存放位置 | 规则 |
| --- | --- | --- |
| instrument / timeframe | URL | URL 为选择的唯一入口，store 派生 |
| 历史分页 | Query cache | key 包含 instrument、周期、cursor、数据版本 |
| 当前权威图表快照 | ChartSessionStore | epoch + seq + datasetRevision，整体替换或合法增量 |
| 实时最新 Candle | ChartSessionStore | 按 openTime upsert，不复制进多套 store |
| 详情选择 / 开关 | UI store | 不影响后端算法结果 |
| 主题 / 偏好 | PreferencesStore + localStorage | schema 版本化；不存权威 Pattern |
| 图表实例 | React ref | 不放入可序列化 store |

REST 缓存提供请求复用，实时图表只订阅 ChartSessionStore。合并后的实时 Candle 不在 Query 与 Zustand 中各维护一份权威版本。

## 5. 初始快照与切换

1. 用户选择产生新的 `selectionGeneration`。
2. 取消旧 REST 请求，关闭旧 EventSource，清理旧图表绑定。
3. 请求 Chart Snapshot 并检查响应属于当前选择；缓存仅作为加载预览。
4. 使用 snapshot 的 epoch / seq / revision 打开 SSE（详见契约）。
5. 按序消费增量；重复事件忽略，缺口或 reset 触发快照替换。
6. 新快照完成前不把新选择的增量应用到旧图。

即使浏览器取消请求失败，generation 检查仍阻止旧响应覆盖新图。新 epoch 的快照是完整替换，seq 不能跨 epoch 比较。

## 6. 图表适配层

```ts
interface ChartAdapter {
  mount(container: HTMLElement, theme: ChartTheme): void;
  setSnapshot(snapshot: ChartViewModel): void;
  updateCandle(candle: CandleViewModel): void;
  prependCandles(candles: readonly CandleViewModel[]): void;
  replaceAnnotations(items: readonly ChartAnnotation[]): void;
  setTheme(theme: ChartTheme): void;
  onAnnotationClick(handler: (annotationId: string) => void): () => void;
  dispose(): void;
}
```

接口是项目边界，不是某个 Lightweight Charts 版本的原生 API。Adapter 内部实现 candlestick、histogram、marker 和 primitive。

- API 时间全部 UTC 毫秒；Adapter 转为图表 Unix 秒，禁止其他模块自行混用单位。
- 价格 / 成交量十进制字符串在 domain 映射层校验为有限 number，保留原值用于详情格式化。
- 数据先按 openTime 升序去重再 `setData`；当前 bar 用增量 `update`。
- 同时间重复数据使用 revision 更新；旧历史修正触发有序重设，不能调用只支持最新 bar 的更新方式。
- Marker 适合点位；水平关键位用 price line；有起止范围的线、Zone、点击命中使用 primitive 或 overlay。
- `pivotTime` 定位 Swing，`confirmedAt` 显示何时确认；视觉标注不能让用户误以为峰值出现时已被识别。
- `ResizeObserver` 维护尺寸；组件卸载、StrictMode 重挂载时释放监听、observer、primitive 和图表。

## 7. 实时渲染与连接状态

- 连接状态：`CONNECTING / LIVE / RECONNECTING / STALE / OFFLINE / MOCK`。
- 服务端明确返回 `deliveryMode` 和 `lastMarketEventAt`；SSE 心跳成功不代表交易所行情正常。
- 单 stream 的增量批次原子进入 reducer；高频未收盘 Candle 可合并到下一动画帧。
- Pattern 确认、收盘、数据修正和 reset 不允许被丢弃。
- 已断线继续显示最后图表与时间，暂停标为实时；不切成随机 mock。
- 如果 seq 不连续，停止应用后续增量并重建 snapshot。

## 8. UI 样式未定时的设计

ChartTheme 规定语义 token：上涨/下跌、候选/形成/确认/失效、支撑/阻力、背景/文字/网格。ThemeAdapter 将 CSS 变量映射为图表选项。

状态还应以文字、符号、线型表示，不只依赖颜色。触摸和键盘都可以通过 Pattern 列表打开详情；图表命中不是唯一入口。

不在状态机中硬编码颜色，不让 Pattern 数据带 React 组件或 CSS class。是否采用 Tailwind、组件库或特定配色，在 UI 阶段选择。

## 9. 前端验证与交付

- 类型检查、lint、生产构建。
- reducer：重复、乱序、seq 缺口、epoch 改变、选择切换竞态。
- Adapter：时间转换、历史 prepend 后可视区、卸载释放。
- 集成：标的和六个周期切换、OHLC、Volume、详情证据、断线提示。
- E2E：历史 snapshot → SSE candle update → breakout confirmation → 点击详情。
- 性能小样目标：2,000 根 Candle、300 个可见标注，最新 bar 更新不触发整页重绘；以真实设备测量，记录环境。

前端单测验证数据和交互边界，技术形态正确性由后端 golden fixtures 验证。
