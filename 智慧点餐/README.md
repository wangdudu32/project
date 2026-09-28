# 智慧点餐

一个单商家的点餐练习项目。前端用 Vue 3，后端用 FastAPI。可以选菜、下单、模拟支付，也可以让助手推荐菜品。

## 已有功能

- 用户注册、登录、退出。
- 菜单展示、分类筛选、购物车。
- 提交订单、查看详情、取消待付款订单、模拟支付。
- 商家管理菜品、上下架、处理订单。
- 菜品推荐、简单多轮问答、配送范围查询。

订单流程：待付款 → 已付款 → 制作中 → 配送中 → 已完成。管理员负责后面三个状态。

## 技术栈

Vue 3、Element Plus、FastAPI、SQLAlchemy。默认用 SQLite，也支持 MySQL。AI 部分使用 LangChain、通义千问和 Pinecone，地图使用高德。

## 目录

```text
智慧点餐/
├── 1_三个工具封装编码/       # 原始教学资料和旧 SQL
├── 2_模型调用编码/
│   ├── resource/           # 原始教学文档
│   └── code/
│       ├── api/            # 用户、点餐、商家接口
│       ├── serive/         # 业务逻辑，目录名沿用原项目
│       ├── LangChain/      # 意图识别和问答
│       ├── tools/          # 数据库、模型、向量、地图工具
│       ├── prompt/         # 提示词
│       ├── tests/          # 后端测试
│       ├── ui/             # 前端页面
│       ├── models.py       # 数据表
│       ├── manage.py       # 管理命令
│       └── run.py          # 后端启动入口
├── requirement.txt        # 完整 Python 依赖入口
└── README.md
```

## 本地启动

需要 Python 3.10+、Node.js 22.12+。第一次先启动后端，再启动前端。

根目录的 `requirement.txt` 汇总了基础、AI 和测试依赖。激活虚拟环境后，可在项目根目录运行 `pip install -r requirement.txt` 一次安装；下面的步骤先安装基础依赖。

### 1. 后端

```bash
cd 2_模型调用编码/code
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows 激活命令：`.venv\Scripts\activate`。

没有 `.env` 时，把 `.env.example` 复制为 `.env`；已有配置就按示例补充，不要覆盖自己的密钥。默认不开启外部服务，也能完成点餐。

```bash
python manage.py init-db
python run.py
```

首次启动会自动建表并添加 5 道示例菜，不会覆盖已有菜单。SQLite 文件为 `code/aimenu.db`。

后端地址：`http://127.0.0.1:8000`，接口文档：`http://127.0.0.1:8000/docs`。

### 2. 前端

另开一个终端：

```bash
cd 2_模型调用编码/code/ui
npm ci
npm run dev
```

打开 `http://127.0.0.1:3000`，点击“登录 / 注册”创建账号，然后选菜下单。

### 3. 商家账号

在 `code` 目录、已激活的 Python 环境中运行：

```bash
python manage.py create-admin --username admin
```

按提示设置密码。登录该账号后可以看到“商家后台”。没有默认管理员密码。

## 可选配置

配置修改后需要重启后端。

- **MySQL**：创建一个空数据库 `aimenu`，在 `.env` 设置 `DATABASE_URL=mysql+pymysql://用户名:密码@127.0.0.1:3306/aimenu?charset=utf8mb4`，然后运行 `python manage.py init-db`。连接密码有特殊字符时需要 URL 编码。
- **AI 问答**：安装 `pip install -r requirements-ai.txt`，设置 `AI_ENABLED=true`，填写 `DASHSCOPE_API_KEY`、`DASHSCOPE_API_BASE`、`LLM_MODE`。
- **向量检索**：安装 AI 依赖，设置 `PINECONE_ENABLED=true`，填写 Pinecone 和 DashScope 密钥，运行 `python manage.py sync-menu`。修改菜单后再次同步。默认索引是 `aimenu-items`，命名空间是 `aimenu`。
- **配送查询**：设置 `AMAP_ENABLED=true`，填写 `AMAP_API_KEY`、商家经纬度、`DELIVERY_RADIUS`（米）。地址解析使用 Web 服务 Key。
- **餐厅信息**：通过 `RESTAURANT_NAME`、`RESTAURANT_ADDRESS`、`RESTAURANT_HOURS`、`RESTAURANT_PHONE` 配置。

未开启 AI 或调用失败时，助手会使用本地菜单规则并提示。多轮上下文保留在当前页面，刷新或清空对话后重置。地图不可用时需要联系商家确认配送，不会伪造距离。

## 测试和构建

```bash
# code 目录
pip install -r requirements-dev.txt
python -m pytest -q

# ui 目录
npm run build
npm run preview
```

浏览器流程测试：保持 Python 虚拟环境已激活，在 `ui` 目录运行 `npx playwright install chromium`、`npm run test:e2e`。测试会自动启动临时数据库和测试服务，不修改自己的数据。

预览地址为 `http://127.0.0.1:4173`，仍需要运行后端。正式部署时，需要把 `/api` 反向代理到后端并去掉 `/api` 前缀；HTTPS 环境将 `COOKIE_SECURE=true`。

## 说明

- 支付是模拟流程，不会真实扣款；不包含真实支付、退款和骑手平台。
- 下单金额由后端计算，订单保存当时的菜名和价格；重复提交使用同一个请求编号，不会重复下单。
- 新表使用 `aimenu_` 前缀，保留旧表。无需导入旧 SQL，旧菜单和历史订单不会自动迁移。
- 写接口需要请求头 `X-Requested-With: aimenu`，前端已自动添加；接口文档中点击 Authorize 填写 `aimenu`。登录使用 HttpOnly Cookie，有效期 24 小时。
- `.env` 中的密钥不要上传仓库。此项目用于学习和本地演示。
