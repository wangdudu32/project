# 行业助手前端

React + TypeScript + Ant Design，使用 Node.js 22。

```bash
cp .env.example .env
npm ci
npm run dev
```

默认访问 http://localhost:5183，后端默认在 8001 端口。
可以在 `.env` 中修改代理地址和面试助手入口。
依赖中有旧版 React peer 声明，项目的 `.npmrc` 已配置兼容安装方式。

```bash
npm run build
```

完整启动步骤见 [项目 README](../../README.md)。
