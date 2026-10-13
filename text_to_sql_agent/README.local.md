# 本地学习指南

项目来源：https://github.com/langchain-ai/text-to-sql-agent

导入版本：[39460e5e509ff36c9694bfe1cea8220be01a068a](https://github.com/langchain-ai/text-to-sql-agent/commit/39460e5e509ff36c9694bfe1cea8220be01a068a)。
本目录作为 `wangdudu32/project` 仓库的普通目录保存，便于一起提交源码和学习笔记。
保留上游 README 和来源信息；上游 README 标注 MIT，本次导入的快照未包含独立 LICENSE 文件。

代码位于 `~/project/text_to_sql_agent/text-to-sql-agent`，使用已有的
`~/project/text_to_sql_agent/.venv_text2sql`（Python 3.12）。
项目依赖使用上游 `uv.lock` 的版本，通过 `uv pip install` 安装；另装了
`notebook` 和 `ipykernel` 以运行教程。Chinook 示例数据库已下载到 `chinook.db`。

## 1. 激活环境

```bash
cd ~/project/text_to_sql_agent
source .venv_text2sql/bin/activate
cd text-to-sql-agent
python -c "import sys; print(sys.executable)"
```

解释器路径应以 `.venv_text2sql/bin/python` 结尾。

## 2. 配置模型

编辑本目录的 `.env`，填写 `ANTHROPIC_API_KEY`。
原项目在 `agent.py` 和 `tutorial.ipynb` 中使用
`claude-sonnet-4-5-20250929`；实际调用需要账号有权使用这个模型。
`.env` 已被 Git 忽略。

LangSmith 追踪默认关闭，不影响问答。如果需要查看追踪，填写
`LANGCHAIN_API_KEY`，并将 `LANGCHAIN_TRACING_V2` 和 `LANGSMITH_TRACING`
都设为 `true`。修改 `.env` 后重新运行命令；Notebook 中请重启内核。

## 3. 运行命令行示例

```bash
python agent.py --help
python agent.py "How many customers are from Canada?"
python agent.py "销售额最高的五位艺术家是谁？请用中文回答。"
```

第一个问答示例的数据库参考结果是 **8 位加拿大客户**。

## 4. 打开交互教程

```bash
python -m notebook tutorial.ipynb --no-browser
```

打开终端打印的本地链接，选择 `Python (text2sql)` 内核，并从上到下运行单元格。
如果使用 VS Code，选择 `.venv_text2sql/bin/python` 作为 Notebook 解释器。
从本项目目录启动教程，确保相对路径能找到 `chinook.db`。

## 5. 没有 API Key 时先熟悉数据库

下面的代码只在本地执行 SQL，不调用模型：

```bash
python - <<'PY'
from langchain_community.utilities import SQLDatabase

db = SQLDatabase.from_uri("sqlite:///file:chinook.db?mode=ro&uri=true")
print("表：", db.get_usable_table_names())
print(db.get_table_info(["Customer"]))
print("加拿大客户数：", db.run("SELECT COUNT(*) FROM Customer WHERE Country = 'Canada'"))
PY
```

建议先读 `tutorial.ipynb`：数据库连接 → 模型初始化 → SQL 工具 →
`create_agent` → 提问，再对照 `agent.py` 理解完整流程。

## 6. 用 uv 重新安装依赖

在本目录执行以下命令，显式指定已有环境，避免安装到其他 Python 环境：

```bash
uv export --frozen --no-dev --no-emit-project --no-hashes \
  --format requirements-txt --output-file /tmp/text2sql-upstream-requirements.txt
uv pip install --python ../.venv_text2sql/bin/python \
  -e . -r /tmp/text2sql-upstream-requirements.txt notebook ipykernel
../.venv_text2sql/bin/python -m ipykernel install --sys-prefix \
  --name text2sql --display-name "Python (text2sql)"
uv pip check --python ../.venv_text2sql/bin/python
```

未填写有效 API Key 前，可以验证依赖、数据库和命令行帮助；模型问答需要填好密钥后运行。

## 7. 在新机器上恢复环境

如果还没有父仓库，先执行 `git clone https://github.com/wangdudu32/project.git ~/project`。
已有父仓库时跳过克隆。以下步骤用于尚未配置过的新环境；安装前请确保 `uv` 可用：

```bash
cd ~/project/text_to_sql_agent
uv venv --python 3.12 .venv_text2sql
source .venv_text2sql/bin/activate
cd text-to-sql-agent

uv export --frozen --no-dev --no-emit-project --no-hashes \
  --format requirements-txt --output-file /tmp/text2sql-upstream-requirements.txt
uv pip install --python ../.venv_text2sql/bin/python \
  -e . -r /tmp/text2sql-upstream-requirements.txt notebook ipykernel
python -m ipykernel install --sys-prefix --name text2sql --display-name "Python (text2sql)"

curl --fail --location --retry 2 --output chinook.db \
  https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite
cp -n .env.example .env
chmod 600 .env
```

随后编辑 `.env` 填写密钥，按前面的命令运行。已有环境不要重复创建虚拟环境或覆盖数据库。
Git 保存依赖清单、锁文件和配置模板；`.venv_text2sql/`、`.env`、`chinook.db`
和 Python 缓存留在本机。

## 8. 后续提交学习修改

```bash
cd ~/project
git add -- text_to_sql_agent/text-to-sql-agent
git diff --cached --stat -- text_to_sql_agent/text-to-sql-agent
git diff --cached --name-only -- text_to_sql_agent/text-to-sql-agent
git commit --only -m "更新 Text2SQL 学习内容" -- text_to_sql_agent/text-to-sql-agent
git push origin main
```

检查文件列表，确认没有密钥或不应公开的 Notebook 输出。`--only` 将本次提交限制在此目录，
父仓库其他已暂存的修改仍留在暂存区。推送前也要确认当前分支上的其他未推送提交是否应上传。

本目录已由父仓库管理；在这里运行 `git pull` 也会更新父仓库。需要更新 LangChain 上游代码时，
另行克隆上游仓库，对照上面记录的导入版本合并需要的修改。
