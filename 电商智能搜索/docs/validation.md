# 第一版验证记录

验证日期：2026-10-27。环境：Linux x64、Python 3.12.14、Node.js 24.21.0，模型使用 CPU 推理。

| 检查 | 结果 |
| --- | --- |
| Python 后端测试 | 20 项通过，使用临时数据库和模拟模型响应 |
| TypeScript 与 Vite 生产构建 | 通过 |
| 开发模式浏览器测试 | 桌面、手机共 8 项通过 |
| 构建产物浏览器测试 | 直接访问 8000 端口，桌面、手机共 8 项通过 |
| 中文字体、图片与响应式布局 | 通过；无浏览器脚本错误、无横向溢出 |
| 一条命令启动 | `scripts/start.py` 已启动本地 OpenSearch 与完整网站 |
| 搜索引擎 | OpenSearch 3.9.0 可用，256 条商品已建立带向量的索引 |
| 本地模型 | `bge-small-zh-v1.5` 与 `bge-reranker-base` 均成功加载 |
| 真实模型服务 | 自动发现可用模型，`search_products` 与 `compare_products` 工具调用成功 |
| 会话约束 | 真实三轮对话保留 500 元预算、白色与排除厚底条件 |
| 最终完整应用 | 真实模型调用成功；默认使用 hybrid；硬条件验证通过 |
| Git 忽略规则 | `.env`、`.venv`、缓存、数据库、下载服务、前端依赖与构建产物已被忽略 |
| 密钥检查 | 待纳入 Git 的项目文本文件没有真实密钥；`.env` 未被纳入 |
| 命名检查 | 项目 Python 业务、脚本与测试代码没有双下划线标识符 |

浏览器中的导购自动化测试使用响应拦截，避免重复消耗模型额度。另行执行的真实模型调用验证了服务连接和工具执行；这两类证据分开记录。

## 搜索取舍

完整结果见 [搜索回归评测](evaluation.md)。模拟回归集上，混合检索的 NDCG@10 为 0.9898，关键词检索为 0.9308；当前精排模型为 0.9781，多样性模式为 0.8368。

因此默认采用混合检索。保留精排和多样性模式用于学习和后续实验；当前多样性策略仍有明显相关性损失，不作为默认路径。上述数据来自规则标注的模拟数据，不能据此推断真实电商收益。

## 界面

- [桌面完整页面](screenshots/desktop.png)
- [手机完整页面](screenshots/mobile.png)
- [恢复真实导购会话的界面](screenshots/assistant.png)

## 参考资料

- [OpenSearch：本地发行包安装](https://docs.opensearch.org/latest/install-and-configure/install-opensearch/tar/)
- [OpenSearch：Python 客户端](https://docs.opensearch.org/latest/clients/python-low-level/)
- [Sentence Transformers：召回与精排](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html)
- [OpenAI Docs：function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [Vite](https://vite.dev/guide/)、[Tailwind CSS](https://tailwindcss.com/docs/installation/using-vite)、[shadcn/ui](https://ui.shadcn.com/docs/installation/vite)
