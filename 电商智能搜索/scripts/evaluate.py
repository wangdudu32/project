import argparse
import sys
from pathlib import Path


sys.path.insert(0, str(Path.cwd() / "backend"))
from evaluate import run_evaluation

parser = argparse.ArgumentParser(description="Evaluate synthetic regression queries")
parser.add_argument("--limit", type=int)
arguments = parser.parse_args()
report = run_evaluation(arguments.limit)
folder = Path("docs")
folder.mkdir(exist_ok=True)
lines = [
    "# 搜索回归评测",
    "",
    f"生成时间：{report['created_at']}。共 {report['queries']} 条查询。",
    "",
    "数据为模拟商品与规则生成的相关性标注，用于回归验证。结果不能代表真实电商搜索效果，也不用于声称线上收益。",
    "",
    "耗时为模型预热后的单进程串行调用，包含过滤、检索、融合与排序，不是并发压测或生产 SLA。",
    "",
    "| 模式 | NDCG@10 | Recall@20 | P50（ms） | P95（ms） | 引擎降级查询数 |",
    "| --- | ---: | ---: | ---: | ---: | ---: |",
]
for mode, result in report["modes"].items():
    values = result["summary"]
    lines.append(
        f"| {mode} | {values['ndcg_at_10']} | {values['recall_at_20']} | {values['latency_p50_ms']} | {values['latency_p95_ms']} | {values['degraded_queries']} |"
    )
lines.extend(
    [
        "",
        f"向量模型：`{report['embedding_model']}`；精排模型：`{report['reranker']}`；CPU 推理线程数：4。",
        "",
        "NDCG 使用分级相关性；Recall 的正例为标注等级大于零的商品。rerank 为模型精排；diverse 在精排后的前 12 个候选内调整商品系列顺序，不从低相关性的尾部强行补入其他系列。",
        "",
        "完整逐查询结果保存于被 Git 忽略的 `runtime/evaluation.json`。",
        "",
        "复现命令：从项目根目录运行 `.venv/bin/python scripts/evaluate.py`。",
        "",
    ]
)
(folder / "evaluation.md").write_text("\n".join(lines))
print("Report saved to docs/evaluation.md")
