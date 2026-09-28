# 基于多模态 Multi-Agent 的智能面试助手

上传 PDF 学习资料，生成面试题，再通过作答、评分和追问检查自己的理解。

项目包含两个可以独立启动的模块：

- **面试助手**：资料出题、自动审核、文字作答、评分反馈、追问、面试总结和历史记录。
- **行业助手**：行业搜索、知识库问答、多 Agent 研究报告。可以从面试助手侧栏进入。

目前的多模态输入是 PDF 中的文字和图片，面试使用文字作答，暂不支持音视频面试。面试模块适合个人本地使用，记录保存在 SQLite 中；行业模块使用单独的账号登录。

## 技术和目录

前端使用 React、TypeScript、Vite，后端使用 Python、FastAPI。出题流程由 LangGraph 编排，支持在线视觉模型和本地 Qwen2.5-VL。

```text
auto_question/
  backend/app/        面试接口、Agent、评分和记录存储
  frontend/           面试页面
  train/              LoRA 训练脚本
  deployment/         Docker 和 Nginx 配置
industry_information_assistant/
  backend/app/        行业检索、知识库和研究 Agent
  frontend/           行业助手页面
```

根目录的 `requirements.txt` 汇总两个后端的运行依赖，`requirement.txt` 也指向同一份清单。若需要在同一个 Python 3.12 虚拟环境中运行两个后端，可激活环境后在项目根目录执行：

```bash
python -m pip install -r requirements.txt
```

仅运行一个模块时，按下方步骤安装该模块的依赖即可。本地模型、训练和测试依赖按需单独安装；前端依赖仍需在各自的 `frontend` 目录执行 `npm ci`。

## 启动面试助手

准备 Python 3.12 和 Node.js 22。下面的命令适用于 Linux/macOS，从项目根目录执行。

```bash
cd auto_question
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

编辑 `.env`，填写在线模型配置：

| 配置项 | 填什么 |
| --- | --- |
| `MODEL_PROVIDER` | 在线模式填 `remote` |
| `MODEL_BASE_URL` | 服务商的兼容接口地址，包含 `/v1` 等前缀 |
| `MODEL_API_KEY` | 自己的 API Key |
| `MODEL_NAME` | 支持图片输入的模型名称 |

在线接口需要支持 `POST /chat/completions` 和图片 Data URL。使用在线模式时，抽取的 PDF 页面和作答内容会发送给配置的模型服务。

安装前端依赖并启动：

```bash
cd frontend
npm ci
cd ..
bash run.sh
```

打开 **http://localhost:5173**，接口文档是 **http://localhost:8000/docs**。按 `Ctrl+C` 停止。配置修改后需要重启服务。

使用步骤：选择 PDF → 设置题量、难度和语言 → 生成题目 → 提交回答 → 查看反馈或继续追问 → 完成面试。

- 每次生成 1～10 道题；PDF 最大 20 MB、200 页，均匀抽取最多 10 页作为材料。
- 参考答案在提交作答后显示。每道原题最多追问一次。
- 总分按准确性 50%、技术深度 30%、表达清晰度 20% 计算，所有题目（含追问）取平均。AI 评分仅供练习参考。
- 未通过自动审核的题目会明确标注，需要结合原文核对。
- 文件和面试记录保存在 `auto_question/backend/storage/`。备份这个目录即可保留记录。

也可以使用命令行生成题目，再到网页历史记录中作答：

```bash
bash run.sh cli /你的路径/资料.pdf --num 3 --difficulty medium --language zh
```

## 使用本地模型（可选）

在 `auto_question` 目录安装额外依赖，将 Qwen2.5-VL 模型下载到 `models/qwen2.5vl/`：

```bash
pip install -r backend/requirements-local.txt
```

然后在 `.env` 设置 `MODEL_PROVIDER=local` 和 `MODEL_PATH=models/qwen2.5vl`。本地模型需要相应的内存和显存，建议使用 NVIDIA GPU。

已有 LoRA 训练结果时，设置 `ADAPTER_PATH=results/qgen-sft` 即可加载。训练相关依赖在 `auto_question/requirements.txt`，入口是 `generate_sft_data.py` 和 `train/train_qgen.py`；训练需要自行准备模型、数据和 GPU。

## 启动行业助手（可选）

行业模块还需要 Docker、PostgreSQL、Redis、Milvus，以及百炼、搜索服务等配置。从项目根目录另开终端：

```bash
cd industry_information_assistant
docker compose up -d
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 后再启动
python app/app_main.py
```

网络研究需要 `DASHSCOPE_API_KEY` 和 `BOCHA_API_KEY`；普通联网问答使用 `SERPER_API_KEY`；知识库文档解析需要 `DOCMIND_ACCESS_KEY_ID` 和 `DOCMIND_ACCESS_KEY_SECRET`。按实际使用的功能填写。

另开终端启动前端：

```bash
cd industry_information_assistant/frontend
cp .env.example .env
npm ci
npm run dev
```

访问 **http://localhost:5183** 注册并登录，后端地址为 **http://localhost:8001**。使用本地检索时，先在知识库页面上传资料，等待处理完成，再在聊天输入区选择知识库。

知识库集合现在使用固定 ID。旧版本按名称保存的向量数据需要重新上传原始文件，原来的集合不会自动迁移。

## Docker 启动面试助手

先完成 `auto_question/.env` 的在线模型配置，再执行：

```bash
cd auto_question
docker compose up --build -d
```

访问 **http://localhost:3000**。该 Compose 使用在线模型，记录仍保存在宿主机的 `backend/storage/`。本地模型请使用前面的 Python 启动方式。

## 测试

从项目根目录执行面试模块测试：

```bash
auto_question/.venv/bin/pip install -r auto_question/backend/requirements-dev.txt
auto_question/.venv/bin/python -m pytest auto_question/backend/tests -q
```

行业模块测试对应 `industry_information_assistant/backend/requirements-dev.txt` 和 `industry_information_assistant/backend/tests/`，使用它自己的虚拟环境执行即可。两个前端都可以运行 `npm run build` 检查构建。

自动测试使用模型和外部服务替身，不消耗真实 API 额度。真实模型效果、GPU 训练及外部服务连通性需要在配置好环境后另行验证。
