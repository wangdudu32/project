# DeepInsight

面向医药业务的多智能体查询与报告生成后端，基于 DeepAgents、LangChain 和 FastAPI。

主智能体根据任务调度 MySQL 数据库助手、Tavily 网络搜索助手和 RAGFlow 知识库助手，汇总答案，并按需生成 Markdown 或 PDF。执行进度通过 WebSocket 推送。

## 目录结构

```text
agent/      主智能体、子智能体及模型配置
api/        HTTP 接口、WebSocket、会话上下文与日志
tools/      数据查询、搜索及文档生成工具
prompt/     智能体提示词
utils/      文件路径处理与 PDF 转换
ragflow/    RAGFlow 知识库管理示例
output/     按会话保存的生成文件
log/        按会话保存的执行日志
updated/    上传文件目录，运行时创建
```

## 配置与启动

建议使用独立的 Python 虚拟环境，以下命令均在项目根目录执行。

### 1. 安装依赖

```bash
python -m pip install -r requirements.txt
python -m pip install langchain-classic markdown
```

第二条命令补充当前依赖清单未显式列出的依赖。PDF 转换还需要 Windows、已安装的 Microsoft Word，以及 `python -m pip install pywin32`。

### 2. 配置环境变量

在项目根目录创建或补全 `.env`，将以下占位符替换为实际配置：

```dotenv
OPENAI_BASE_URL=https://your-model-service.example/v1
OPENAI_API_KEY=your-model-api-key
LLM_QWEN_MAX=your-model-name

TAVILY_API_KEY=your-tavily-api-key

RAGFLOW_API_URL=http://your-ragflow-host:port
RAGFLOW_API_KEY=your-ragflow-api-key

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=your-db-user
MYSQL_PASSWORD=your-db-password
MYSQL_DATABASE=your-database
```

模型服务需兼容 OpenAI 接口并支持工具调用。使用数据库或知识库功能前，需准备 MySQL 业务表，以及关联知识库的 RAGFlow 聊天助手；仓库不包含这些服务的初始化数据。

### 3. 启动开发服务

```bash
python -m api.server
```

默认端口为 `8000`，接口文档：http://127.0.0.1:8000/docs 。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/task` | 提交 JSON：`query`、可选的 `thread_id` |
| POST | `/api/upload` | 上传表单：`files`、`thread_id`，仅保存文件 |
| GET | `/api/files` | 列出文件，`path` 为 output 内目录的绝对路径 |
| GET | `/api/download` | 下载文件，`path` 为 output 内文件的绝对路径 |
| GET | `/outputs/{path}` | 访问相对于 output 目录的生成文件 |
| WebSocket | `/ws/{thread_id}` | 接收会话目录、助手调用、工具执行、回答及错误事件 |

提交任务示例：

```bash
curl -X POST http://127.0.0.1:8000/api/task \
  -H 'Content-Type: application/json' \
  -d '{"query":"查询数据库中的药品信息，生成 Markdown 报告","thread_id":"demo-001"}'
```

接口立即返回 `{"status":"started","thread_id":"demo-001"}`，表示任务已启动。需要接收完整执行事件时，先连接 `ws://127.0.0.1:8000/ws/demo-001`，再提交任务；新任务建议使用新的 ID。

生成文件保存到 `output/session_{thread_id}/`，日志保存到 `log/agent_trace_{thread_id}.log`。

