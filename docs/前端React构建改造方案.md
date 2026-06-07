# 前端 React 构建改造方案

## 1. 背景

当前 `market-terminal` 前端是一个单 HTML 原型页面：

- 入口文件：`market-terminal/金融市场监控终端.html`
- 样式文件：`market-terminal/lib/tokens.css`
- 数据层：`market-terminal/lib/data.js`
- 本地存储：`market-terminal/lib/store.js`
- 页面组件：`market-terminal/app-screens.jsx`
- 复盘组件：`market-terminal/review-screens.jsx`
- 调参面板：`market-terminal/tweaks-panel.jsx`
- 通用组件：`market-terminal/lib/components.jsx`

页面通过浏览器直接加载 React、ReactDOM 和 Babel：

```html
<script src="https://unpkg.com/react@18.3.1/umd/react.development.js"></script>
<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js"></script>
<script src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js"></script>
```

这种方式适合原型演示，但不适合长期部署到服务器，主要问题包括：

- 依赖外部 CDN，网络不可用时页面可能白屏。
- JSX 在浏览器中实时编译，性能和稳定性较弱。
- 缺少标准构建产物，不利于 Nginx 静态托管、缓存控制和版本发布。
- API 地址当前写死为 `http://localhost:8000/api/stream`，上线后浏览器会访问用户本机的 `localhost`。
- 多个模块通过 `window.*` 暴露全局变量，后续维护成本较高。

## 2. 改造目标

将 `market-terminal` 改造成 Vite + React 构建项目，实现：

- 本地开发通过 `npm run dev` 启动。
- 生产环境通过 `npm run build` 生成 `dist/`。
- React、ReactDOM 等依赖由 npm 管理，不再依赖运行时 CDN。
- JSX 由构建工具编译，不再在浏览器中实时编译。
- 前端 API 地址支持相对路径和环境变量配置。
- 生产产物可以直接由 Nginx、Caddy 或对象存储静态托管。
- 与现有 FastAPI 后端通过 `/api/` 反向代理集成。

## 3. 目标目录结构

建议将 `market-terminal` 调整为如下结构：

```text
market-terminal/
  package.json
  vite.config.js
  index.html
  src/
    main.jsx
    App.jsx
    styles/
      tokens.css
    lib/
      data.js
      store.js
    components/
      components.jsx
      tweaks-panel.jsx
    screens/
      app-screens.jsx
      review-screens.jsx
  dist/
```

其中：

- `index.html`：Vite 入口 HTML。
- `src/main.jsx`：React 挂载入口。
- `src/App.jsx`：从原 HTML 内联脚本中拆出的主应用组件。
- `src/styles/tokens.css`：全局设计变量和基础样式。
- `src/lib/data.js`：行情数据层和 SSE 连接逻辑。
- `src/lib/store.js`：清单和日记存储逻辑。
- `src/components/components.jsx`：通用展示组件。
- `src/components/tweaks-panel.jsx`：调参面板组件。
- `src/screens/app-screens.jsx`：行情监控和工具箱页面。
- `src/screens/review-screens.jsx`：今日清单和每日日记页面。
- `dist/`：构建后的生产静态产物。

## 4. 文件迁移关系

```text
market-terminal/金融市场监控终端.html
  -> market-terminal/index.html
  -> market-terminal/src/App.jsx
  -> market-terminal/src/main.jsx

market-terminal/lib/tokens.css
  -> market-terminal/src/styles/tokens.css

market-terminal/lib/data.js
  -> market-terminal/src/lib/data.js

market-terminal/lib/store.js
  -> market-terminal/src/lib/store.js

market-terminal/lib/components.jsx
  -> market-terminal/src/components/components.jsx

market-terminal/tweaks-panel.jsx
  -> market-terminal/src/components/tweaks-panel.jsx

market-terminal/app-screens.jsx
  -> market-terminal/src/screens/app-screens.jsx

market-terminal/review-screens.jsx
  -> market-terminal/src/screens/review-screens.jsx
```

## 5. 核心改造内容

### 5.1 引入 Vite + React

新增 `package.json`：

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^latest",
    "vite": "^latest",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {}
}
```

实际版本建议在执行时锁定为当前 npm 可用的稳定版本。

新增 `vite.config.js`：

```js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
});
```

### 5.2 拆分入口文件

原 HTML 中的内联 `App` 组件迁移到 `src/App.jsx`。

原 HTML 中的：

```js
ReactDOM.createRoot(document.getElementById('root')).render(<App />);
```

迁移到 `src/main.jsx`：

```jsx
import React from 'react';
import { createRoot } from 'react-dom/client';
import './styles/tokens.css';
import App from './App.jsx';

createRoot(document.getElementById('root')).render(<App />);
```

新的 `index.html` 保留最小结构：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>市场监控终端</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

### 5.3 去除浏览器 Babel

当前页面通过：

```html
<script type="text/babel" src="app-screens.jsx"></script>
```

让浏览器实时编译 JSX。

改造后应全部改为 ES Module 的 `import/export`，由 Vite 在构建阶段完成 JSX 编译。

### 5.4 去除全局 `window.*`

当前代码中存在较多全局挂载方式：

```js
window.MarketData = { ... };
window.MarketStore = { ... };
Object.assign(window, { ChecklistScreen, JournalScreen, HeaderCountdown });
```

建议逐步改为模块导出：

```js
export const MarketData = { ... };
export const MarketStore = { ... };
export function ChecklistScreen() { ... }
export function JournalScreen() { ... }
export function HeaderCountdown() { ... }
```

调用方使用：

```js
import { MarketData } from '../lib/data.js';
import { ChecklistScreen, JournalScreen } from './screens/review-screens.jsx';
```

为了降低一次性改造风险，可以先保留部分 `window.*`，完成构建后再分阶段清理。

### 5.5 API 地址改造

当前 `market-terminal/lib/data.js` 中写死了：

```js
const SSE_URL = 'http://localhost:8000/api/stream';
```

上线后必须改为相对路径或环境变量：

```js
const API_BASE = import.meta.env.VITE_API_BASE || '';
const SSE_URL = `${API_BASE}/api/stream`;
```

部署为前后端同域时：

```text
https://your-domain.com/
https://your-domain.com/api/stream
```

前端默认访问 `/api/stream`，Nginx 将 `/api/` 反向代理到 FastAPI。

### 5.6 存储策略

当前清单和日记使用浏览器 IndexedDB：

```js
window.MarketStore = { open, save, get, getAll, del, today };
```

这意味着数据只保存在当前浏览器中：

- 换浏览器不可见。
- 换设备不可见。
- 清理浏览器数据可能丢失。
- 多人访问无法共享。

FastAPI 后端已经存在对应接口：

- `GET /api/checklist`
- `POST /api/checklist`
- `GET /api/journal`
- `POST /api/journal`
- `GET /api/journal/history`
- `DELETE /api/journal`

因此可以分两步处理：

1. 第一阶段继续保留 IndexedDB，先完成前端构建化。
2. 第二阶段将 `store.js` 改造成后端 API 适配层，实现多设备同步和服务器持久化。

## 6. 部署方式

### 6.1 前端构建

```bash
cd market-terminal
npm install
npm run build
```

生成：

```text
market-terminal/dist/
```

### 6.2 后端启动

```bash
cd market-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

### 6.3 Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    root /opt/market-terminal/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header Connection "";

        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        add_header X-Accel-Buffering no;
    }
}
```

其中 `proxy_buffering off` 和 `X-Accel-Buffering no` 对 SSE 长连接比较重要。

## 7. 推荐实施阶段

### 阶段一：最小构建化

目标：页面能通过 Vite 启动和构建，功能保持当前行为不变。

- 引入 Vite + React。
- 拆分 HTML、App 和 main 入口。
- 保留现有页面组件结构。
- 暂时允许少量 `window.*` 兼容。
- 将 SSE 地址改为 `/api/stream`。

### 阶段二：模块化整理

目标：消除全局变量，建立清晰的模块边界。

- `MarketData` 改为模块导出。
- `MarketStore` 改为模块导出。
- 页面组件改为显式 `export/import`。
- 通用函数和 Hook 从全局调用改为模块导入。

### 阶段三：服务端数据持久化

目标：清单和日记可以跨设备、跨浏览器保存。

- 将 `store.js` 改为 API 客户端。
- 接入 `/api/checklist`。
- 接入 `/api/journal`。
- 保留 IndexedDB 作为可选离线缓存时再单独设计同步策略。

### 阶段四：生产增强

目标：提升生产环境稳定性和运维体验。

- 将字体资源本地化或调整为系统字体栈。
- 增加 `.env.development`、`.env.production`。
- 增加 Dockerfile 或 Docker Compose。
- 增加 systemd 服务配置。
- 增加构建检查和部署脚本。

## 8. 风险与注意事项

- 一次性移除所有 `window.*` 容易造成组件依赖断裂，建议先构建化，再模块化。
- 当前组件文件之间存在隐式全局依赖，迁移时需要逐个确认函数来源。
- SSE 在 Nginx 下需要关闭代理缓冲，否则实时推送可能延迟。
- 如果继续使用 IndexedDB，服务器部署并不等于数据服务端持久化。
- 如果使用外部行情源，服务器网络、限流和 token 配置需要单独验证。

## 9. 结论

前端建议改为 Vite + React 构建项目。

最小可行路径是：

1. 先完成 Vite 构建化。
2. 将 SSE 地址改成 `/api/stream`。
3. 使用 Nginx 托管 `dist/` 并反向代理 `/api/`。
4. 后续再逐步清理 `window.*` 和接入服务端日记/清单存储。

这样可以在不大规模重写页面的前提下，让当前原型具备标准前端项目的部署能力。
