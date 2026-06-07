# 前端 React 构建改造任务清单

## 1. 执行模式

本任务采用“调度 Agent + subagent”的执行模式。

- 调度 Agent：负责拆解任务、分配 subagent、控制依赖顺序、汇总结果、触发验收、推动全部任务完成。
- subagent：负责执行具体改造任务，只处理自己被分配的范围，并向调度 Agent 汇报交付物、风险和验证结果。

调度 Agent 不直接长期沉入细节实现，除非出现阻塞、冲突或需要做最终集成判断。subagent 不自行扩大范围，不擅自跳过验收，不修改与本任务无关的文件。

## 2. 总体目标

将 `market-terminal` 从“单 HTML + CDN React + 浏览器 Babel”的原型页面，改造成 Vite + React 构建项目。

最终应满足：

- `market-terminal` 可以通过 `npm run dev` 本地启动。
- `market-terminal` 可以通过 `npm run build` 生成 `dist/`。
- 页面不再依赖 React CDN 和浏览器 Babel。
- 页面不再硬编码 `http://localhost:8000/api/stream`。
- 前端可以通过 `/api/stream` 连接 FastAPI SSE。
- 现有四个页面功能保持可用：
  - 行情监控
  - 工具箱
  - 今日清单
  - 每日日记
- 清单和日记第一阶段继续保留 IndexedDB 存储策略。
- 构建产物可以由 Nginx 静态托管，并通过 `/api/` 反向代理后端。

## 2.1 执行状态

执行日期：2026-06-07

当前状态：P0 主线任务已完成，P1 中与构建化直接相关的任务已完成，P2 后续增强任务未执行。

已完成：

- [x] Subagent A：工程初始化。
- [x] Subagent B：入口拆分。
- [x] Subagent C：文件迁移。
- [x] Subagent D：模块化改造。
- [x] Subagent E：数据层与 API 地址改造。
- [x] Subagent F：样式与静态资源检查。
- [x] Subagent G：本地开发验证。
- [x] Subagent H：生产构建验证。
- [x] Subagent I：部署路径与 Nginx 配置确认。
- [x] Subagent J：最终回归。

验证结果：

- [x] `npm install` 成功。
- [x] `npm run build` 成功。
- [x] 前端开发服务 `http://127.0.0.1:5173/` 可访问。
- [x] 后端 `/health` 返回正常。
- [x] 后端 `/api/stream` 可收到 SSE `snapshot`。
- [x] 页面不再依赖 React CDN。
- [x] 页面不再依赖浏览器 Babel。
- [x] 构建入口不再硬编码 `localhost:8000`。
- [x] 页面可通过 `/api/stream` 获取实时行情。
- [x] 四个页面均可切换并正常渲染。

剩余非阻塞项：

- [ ] npm audit 报告 2 个 moderate 级别提示，未执行 `npm audit fix --force`，避免引入破坏性依赖升级。
- [ ] 清单和日记仍使用 IndexedDB，尚未改为服务端 API。
- [ ] 字体仍通过 Google Fonts 引入，尚未本地化。
- [ ] Docker、systemd、一键部署脚本仍属于后续增强任务。

## 3. 调度 Agent 职责

### 3.1 任务拆解

- [ ] 读取 `docs/前端React构建改造方案.md`。
- [ ] 读取当前 `market-terminal` 源码。
- [ ] 识别当前文件依赖关系。
- [ ] 将改造工作拆分给各 subagent。
- [ ] 标记任务依赖和执行顺序。
- [ ] 明确每个 subagent 的交付物和验收标准。

### 3.2 任务调度

- [ ] 先分配基础工程任务。
- [ ] 再分配入口拆分任务。
- [ ] 再分配文件迁移和模块化任务。
- [ ] 再分配 API 地址和数据层任务。
- [ ] 再分配样式和资源任务。
- [ ] 再分配验证和部署任务。
- [ ] 对存在依赖的任务，等待上游任务完成后再启动下游任务。

### 3.3 集成控制

- [ ] 接收每个 subagent 的修改结果。
- [ ] 检查是否出现文件冲突。
- [ ] 检查是否有重复实现。
- [ ] 检查是否有遗漏的隐式全局依赖。
- [ ] 检查是否误改 `market-api` 后端非必要文件。
- [ ] 检查是否误删原型文件或业务内容。
- [ ] 统一处理跨模块 import/export 问题。

### 3.4 验收控制

- [ ] 触发本地开发验证。
- [ ] 触发生产构建验证。
- [ ] 触发页面功能验证。
- [ ] 触发 SSE 连接验证。
- [ ] 触发 IndexedDB 存储验证。
- [ ] 汇总所有 subagent 的验收结果。
- [ ] 对失败项重新分派修复任务。
- [ ] 全部验收通过后标记任务完成。

## 4. subagent 分工总览

| subagent | 任务范围 | 依赖 | 输出 |
| --- | --- | --- | --- |
| Subagent A | 工程初始化 | 无 | `package.json`、`vite.config.js` |
| Subagent B | 入口拆分 | A | `index.html`、`src/main.jsx`、`src/App.jsx` |
| Subagent C | 文件迁移 | A | `src/` 目录结构和迁移后的源码 |
| Subagent D | 模块化改造 | B、C | 显式 `export/import` |
| Subagent E | 数据层与 API 地址 | C、D | `/api/stream`、`VITE_API_BASE`、数据层导出 |
| Subagent F | 样式与静态资源 | B、C | 样式导入和资源检查 |
| Subagent G | 本地验证 | D、E、F | 开发环境验证结果 |
| Subagent H | 构建验证 | G | `npm run build` 和 preview 验证结果 |
| Subagent I | 部署说明与 Nginx 验证 | H | 部署检查项和 Nginx 配置确认 |
| Subagent J | 最终回归 | G、H、I | 总体验收报告 |

## 5. Subagent A：工程初始化

### 输入

- `docs/前端React构建改造方案.md`
- 当前 `market-terminal` 目录

### 执行任务

- [ ] 在 `market-terminal` 下新增 `package.json`。
- [ ] 添加 npm scripts：
  - [ ] `dev`
  - [ ] `build`
  - [ ] `preview`
- [ ] 添加运行依赖：
  - [ ] `react`
  - [ ] `react-dom`
- [ ] 添加构建依赖：
  - [ ] `vite`
  - [ ] `@vitejs/plugin-react`
- [ ] 新增 `vite.config.js`。
- [ ] 配置 Vite React 插件。
- [ ] 配置开发代理：
  - [ ] `/api -> http://127.0.0.1:8000`

### 交付物

- [ ] `market-terminal/package.json`
- [ ] `market-terminal/vite.config.js`
- [ ] npm 依赖锁文件

### 验收标准

- [ ] `npm install` 可以成功。
- [ ] `npm run dev` 命令存在。
- [ ] `npm run build` 命令存在。
- [ ] Vite 配置语法正确。

## 6. Subagent B：入口拆分

### 输入

- `market-terminal/金融市场监控终端.html`
- Subagent A 的工程初始化结果

### 执行任务

- [ ] 新增 `market-terminal/index.html`。
- [ ] 移除新入口中的 React CDN 引用。
- [ ] 移除新入口中的 ReactDOM CDN 引用。
- [ ] 移除新入口中的 Babel CDN 引用。
- [ ] 移除 `type="text/babel"` 脚本加载方式。
- [ ] 新增 `market-terminal/src/main.jsx`。
- [ ] 在 `src/main.jsx` 中挂载 React 应用。
- [ ] 新增 `market-terminal/src/App.jsx`。
- [ ] 将原 HTML 内联的 `App` 组件迁移到 `src/App.jsx`。
- [ ] 将原 HTML 中的基础样式迁移到可被 Vite 导入的 CSS 文件。

### 交付物

- [ ] `market-terminal/index.html`
- [ ] `market-terminal/src/main.jsx`
- [ ] `market-terminal/src/App.jsx`

### 验收标准

- [ ] `index.html` 只保留 Vite module 入口。
- [ ] `App.jsx` 可以被 `main.jsx` 正常导入。
- [ ] 页面根节点仍为 `#root`。
- [ ] 原有 App 逻辑没有丢失。

## 7. Subagent C：文件迁移

### 输入

- 当前 `market-terminal` 源码
- Subagent A 的工程初始化结果

### 执行任务

- [ ] 新建 `market-terminal/src/`。
- [ ] 新建 `market-terminal/src/styles/`。
- [ ] 新建 `market-terminal/src/lib/`。
- [ ] 新建 `market-terminal/src/components/`。
- [ ] 新建 `market-terminal/src/screens/`。
- [ ] 迁移 `lib/tokens.css` 到 `src/styles/tokens.css`。
- [ ] 迁移 `lib/data.js` 到 `src/lib/data.js`。
- [ ] 迁移 `lib/store.js` 到 `src/lib/store.js`。
- [ ] 迁移 `lib/components.jsx` 到 `src/components/components.jsx`。
- [ ] 迁移 `tweaks-panel.jsx` 到 `src/components/tweaks-panel.jsx`。
- [ ] 迁移 `app-screens.jsx` 到 `src/screens/app-screens.jsx`。
- [ ] 迁移 `review-screens.jsx` 到 `src/screens/review-screens.jsx`。

### 交付物

- [ ] `market-terminal/src/styles/tokens.css`
- [ ] `market-terminal/src/lib/data.js`
- [ ] `market-terminal/src/lib/store.js`
- [ ] `market-terminal/src/components/components.jsx`
- [ ] `market-terminal/src/components/tweaks-panel.jsx`
- [ ] `market-terminal/src/screens/app-screens.jsx`
- [ ] `market-terminal/src/screens/review-screens.jsx`

### 验收标准

- [ ] 原功能文件均有迁移目标。
- [ ] 迁移后文件内容没有业务缺失。
- [ ] 原型文件是否保留由调度 Agent 统一决定，不由 subagent 自行删除。

## 8. Subagent D：模块化改造

### 输入

- Subagent B 的入口文件
- Subagent C 的迁移文件

### 执行任务

- [ ] 将 `App.jsx` 改为默认导出。
- [ ] 将 `MarketScreen` 改为显式导出。
- [ ] 将 `ToolboxScreen` 改为显式导出。
- [ ] 将 `ChecklistScreen` 改为显式导出。
- [ ] 将 `JournalScreen` 改为显式导出。
- [ ] 将 `HeaderCountdown` 改为显式导出。
- [ ] 将 `TweaksPanel` 改为显式导出。
- [ ] 将 `TweakSection` 改为显式导出。
- [ ] 将 `TweakRadio` 改为显式导出。
- [ ] 将 `TweakSlider` 改为显式导出。
- [ ] 梳理并导出通用组件和工具函数：
  - [ ] `useMarket`
  - [ ] `IndexStrip`
  - [ ] `GlobalStrip`
  - [ ] `Clock`
  - [ ] `LiveChip`
  - [ ] `SectorFlowRanking`
  - [ ] `RotationMap`
  - [ ] `ThemeTape`
  - [ ] `BreadthBar`
  - [ ] `LeaderBoard`
  - [ ] `Spark`
  - [ ] `Pct`
  - [ ] `fmtPct`
  - [ ] `fmtFlow`
  - [ ] `cssVar`
- [ ] 将组件之间的隐式全局依赖改为显式 `import`。
- [ ] 移除不再需要的 `Object.assign(window, ...)`。

### 交付物

- [ ] 明确的 `export/import` 关系。
- [ ] 无浏览器 Babel 时代遗留的组件全局注册。
- [ ] 可被 Vite 编译的 JSX 模块。

### 验收标准

- [ ] Vite 开发服务不报模块解析错误。
- [ ] 浏览器控制台不出现组件未定义错误。
- [ ] 四个页面都能被 `App.jsx` 正常引用。

## 9. Subagent E：数据层与 API 地址

### 输入

- `src/lib/data.js`
- `src/lib/store.js`
- 依赖数据层的组件文件

### 执行任务

- [ ] 将 `window.MarketData` 改为模块导出。
- [ ] 保持 `connect`、`subscribe`、`themeAgg` 等接口稳定。
- [ ] 将组件中 `window.MarketData` 调用改为模块导入。
- [ ] 将 `window.MarketStore` 改为模块导出。
- [ ] 将组件中 `_store()` 对 `window.MarketStore` 的调用改为模块导入。
- [ ] 将 `http://localhost:8000/api/stream` 改为相对路径。
- [ ] 支持 `VITE_API_BASE` 环境变量。
- [ ] 拼接 SSE 地址：
  - [ ] 默认同域：`/api/stream`
  - [ ] 指定后端：`${VITE_API_BASE}/api/stream`
- [ ] 第一阶段继续保留 IndexedDB 存储策略。

### 交付物

- [ ] 模块化后的 `MarketData`。
- [ ] 模块化后的 `MarketStore`。
- [ ] 不再硬编码 `localhost:8000` 的 SSE 地址。

### 验收标准

- [ ] 本地开发下 Vite proxy 能代理 `/api/stream`。
- [ ] 生产同域部署下可以访问 `/api/stream`。
- [ ] 清单和日记仍使用 IndexedDB 正常读写。

## 10. Subagent F：样式与静态资源

### 输入

- `src/styles/tokens.css`
- `src/main.jsx`
- 当前页面样式

### 执行任务

- [ ] 在 `main.jsx` 中导入 `tokens.css`。
- [ ] 检查 CSS 中相对路径是否仍然有效。
- [ ] 检查原 HTML 内联样式是否已迁移。
- [ ] 检查 Google Fonts 是否继续使用。
- [ ] 评估是否需要将字体资源本地化。
- [ ] 检查构建后页面是否有样式丢失。
- [ ] 检查深色主题变量是否正常生效。

### 交付物

- [ ] 样式导入链路。
- [ ] 静态资源检查结果。
- [ ] 字体资源处理建议。

### 验收标准

- [ ] 页面主视觉与原型保持一致。
- [ ] 主题变量生效。
- [ ] 控制台没有 CSS 资源 404。

## 11. Subagent G：本地开发验证

### 输入

- Subagent D、E、F 的集成结果

### 执行任务

- [ ] 启动后端：
  - [ ] `cd market-api`
  - [ ] `uvicorn main:app --host 127.0.0.1 --port 8000`
- [ ] 启动前端：
  - [ ] `cd market-terminal`
  - [ ] `npm run dev`
- [ ] 打开 Vite 本地地址。
- [ ] 验证页面可以正常渲染。
- [ ] 验证顶部导航可以切换：
  - [ ] 行情监控
  - [ ] 工具箱
  - [ ] 今日清单
  - [ ] 每日日记
- [ ] 验证 SSE 行情数据能刷新。
- [ ] 验证断开后端时页面不会崩溃。
- [ ] 验证清单填写和保存。
- [ ] 验证日记填写、保存和历史读取。
- [ ] 验证刷新浏览器后 IndexedDB 数据仍在。

### 交付物

- [ ] 本地开发验证记录。
- [ ] 发现的问题列表。
- [ ] 需要回派给其他 subagent 的修复项。

### 验收标准

- [ ] `npm run dev` 可用。
- [ ] 四个页面可用。
- [ ] SSE 可用。
- [ ] IndexedDB 可用。

## 12. Subagent H：构建验证

### 输入

- Subagent G 通过后的前端工程

### 执行任务

- [ ] 执行 `npm run build`。
- [ ] 确认生成 `dist/`。
- [ ] 执行 `npm run preview`。
- [ ] 验证 preview 页面可访问。
- [ ] 检查构建产物中没有引用 `unpkg.com/react`。
- [ ] 检查构建产物中没有引用 `@babel/standalone`。
- [ ] 检查构建产物中没有硬编码 `localhost:8000`。
- [ ] 检查浏览器控制台无明显报错。

### 交付物

- [ ] 构建验证记录。
- [ ] preview 验证记录。
- [ ] 构建产物检查结果。

### 验收标准

- [ ] `npm run build` 成功。
- [ ] `dist/` 存在。
- [ ] 构建产物不依赖 React CDN。
- [ ] 构建产物不依赖浏览器 Babel。
- [ ] 构建产物不硬编码 `localhost:8000`。

## 13. Subagent I：部署说明与 Nginx 验证

### 输入

- Subagent H 的构建产物
- `market-api` 后端接口

### 执行任务

- [ ] 确认 `market-terminal/dist/` 可以上传到服务器。
- [ ] 确认 Nginx `root` 应指向 `dist/`。
- [ ] 确认 `location /` 配置：
  - [ ] `try_files $uri $uri/ /index.html`
- [ ] 确认 `location /api/` 反向代理到 FastAPI。
- [ ] 为 SSE 确认以下配置：
  - [ ] `proxy_buffering off`
  - [ ] `proxy_cache off`
  - [ ] `proxy_read_timeout 3600s`
  - [ ] `add_header X-Accel-Buffering no`
- [ ] 验证线上域名访问路径。
- [ ] 验证 `/api/stream` 持续推送。
- [ ] 验证 `/health` 可访问。

### 交付物

- [ ] Nginx 部署检查结果。
- [ ] SSE 代理配置确认。
- [ ] 部署风险说明。

### 验收标准

- [ ] 静态前端可以被 Nginx 托管。
- [ ] `/api/` 能正确反向代理到 FastAPI。
- [ ] SSE 不被 Nginx 缓冲阻塞。

## 14. Subagent J：最终回归

### 输入

- 所有 subagent 的交付物
- 所有验证记录

### 执行任务

- [ ] 汇总所有改造文件。
- [ ] 检查任务清单完成状态。
- [ ] 检查是否存在未处理的阻塞项。
- [ ] 检查是否存在未解释的失败验证。
- [ ] 检查 git diff，确认没有无关改动。
- [ ] 执行最终页面回归。
- [ ] 执行最终构建回归。
- [ ] 输出最终验收报告。

### 交付物

- [ ] 最终验收报告。
- [ ] 剩余风险列表。
- [ ] 后续增强建议。

### 验收标准

- [ ] 所有 P0 任务完成。
- [ ] 所有必须验证通过。
- [ ] 未完成项均有明确原因和后续归属。
- [ ] 调度 Agent 可以将整体任务标记为完成。

## 15. 调度 Agent 全局完成判定

只有同时满足以下条件，调度 Agent 才能将任务标记为完成：

- [ ] Subagent A 完成并通过验收。
- [ ] Subagent B 完成并通过验收。
- [ ] Subagent C 完成并通过验收。
- [ ] Subagent D 完成并通过验收。
- [ ] Subagent E 完成并通过验收。
- [ ] Subagent F 完成并通过验收。
- [ ] Subagent G 完成并通过验收。
- [ ] Subagent H 完成并通过验收。
- [ ] Subagent I 完成并通过验收。
- [ ] Subagent J 完成并通过验收。
- [ ] `npm run dev` 可用。
- [ ] `npm run build` 成功。
- [ ] 页面不依赖 React CDN。
- [ ] 页面不依赖浏览器 Babel。
- [ ] 页面不硬编码 `localhost:8000`。
- [ ] 四个页面均可访问。
- [ ] SSE 行情刷新正常。
- [ ] 清单和日记当前存储策略正常。
- [ ] Nginx 部署路径明确。

## 16. 失败回派规则

如果某个验证失败，调度 Agent 按下面规则回派：

- 工程命令失败：回派 Subagent A。
- 页面入口无法加载：回派 Subagent B。
- 文件缺失或路径错误：回派 Subagent C。
- 组件未定义或 import 错误：回派 Subagent D。
- SSE 或存储异常：回派 Subagent E。
- 样式丢失或资源 404：回派 Subagent F。
- 本地功能异常：回派 Subagent G，并由 G 判断是否继续回派。
- 构建失败：回派 Subagent H，并由 H 判断是否继续回派。
- Nginx 或部署问题：回派 Subagent I。
- 最终回归发现遗漏：回派 Subagent J，再由调度 Agent 分配给对应 subagent。

## 17. 优先级

### P0：必须完成

- [ ] Subagent A：工程初始化。
- [ ] Subagent B：入口拆分。
- [ ] Subagent C：文件迁移。
- [ ] Subagent D：模块化改造。
- [ ] Subagent E：SSE 地址和数据层改造。
- [ ] Subagent G：本地开发验证。
- [ ] Subagent H：生产构建验证。
- [ ] Subagent J：最终回归。

### P1：建议完成

- [ ] Subagent F：样式与静态资源完整检查。
- [ ] Subagent I：Nginx 部署验证。
- [ ] 清理主要 `window.*` 全局依赖。
- [ ] 完成显式 `export/import`。
- [ ] 增加环境变量配置。

### P2：后续增强

- [ ] 清单和日记接入后端数据库。
- [ ] 字体本地化。
- [ ] Docker 化部署。
- [ ] 自动化部署脚本。
- [ ] 增加 systemd service 示例。

## 18. 后续增强任务池

这些任务不阻塞 React 构建化，但可以由调度 Agent 在主线完成后继续分配：

- [ ] 将清单数据从 IndexedDB 改为 `/api/checklist`。
- [ ] 将日记数据从 IndexedDB 改为 `/api/journal`。
- [ ] 增加 `/api/journal/history` 前端接入。
- [ ] 增加删除日记功能。
- [ ] 增加 `.env.development`。
- [ ] 增加 `.env.production`。
- [ ] 增加 Dockerfile。
- [ ] 增加 Docker Compose。
- [ ] 增加 systemd service 示例。
- [ ] 增加一键构建脚本。
- [ ] 增加部署说明文档。
