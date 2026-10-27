"""Compare retrieval modes on the bundled, explicitly synthetic regression set."""

import json
import math
import platform
from datetime import datetime, timezone

import numpy as np

import ranking
import search_engine
import settings
from schemas import SearchRequest
from search import search_products


def ndcg_at_10(product_ids, relevance):
    def gain(grades):
        return sum(
            (2**grade - 1) / math.log2(position + 2)
            for position, grade in enumerate(grades)
        )

    actual = gain([relevance.get(product_id, 0) for product_id in product_ids[:10]])
    ideal = gain(sorted(relevance.values(), reverse=True)[:10])
    return actual / ideal if ideal else 0.0


def run_evaluation(limit=None):
    queries = [
        json.loads(line)
        for line in (settings.root / "data" / "queries.jsonl").read_text().splitlines()
        if line.strip()
    ]
    if limit:
        queries = queries[:limit]
    ranking.warm_models()
    search_products(SearchRequest(query="通勤运动鞋", page_size=24))
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "30 rule-labeled synthetic demo queries; not a real-world relevance benchmark",
        "hardware": platform.platform(),
        "cpu_inference_threads": 4,
        "embedding_model": settings.embedding_model,
        "reranker": settings.rerank_model,
        "opensearch_available": search_engine.is_available(force=True),
        "queries": len(queries),
        "modes": {},
    }
    for mode in ("keyword", "hybrid", "rerank", "diverse"):
        rows = []
        for item in queries:
            result = search_products(
                SearchRequest(query=item["query"], mode=mode, page_size=24)
            )
            product_ids = [product["id"] for product in result["products"]]
            relevant_ids = set(item["relevance"])
            rows.append(
                {
                    "id": item["id"],
                    "query": item["query"],
                    "ndcg_at_10": ndcg_at_10(product_ids, item["relevance"]),
                    "recall_at_20": len(set(product_ids[:20]) & relevant_ids)
                    / len(relevant_ids)
                    if relevant_ids
                    else 0,
                    "latency_ms": result["meta"]["elapsed_ms"],
                    "backend": result["meta"]["backend"],
                    "semantic_used": result["meta"]["semantic"],
                    "reranked": result["meta"]["reranked"],
                }
            )
        latencies = [row["latency_ms"] for row in rows]
        summary = {
            "ndcg_at_10": round(float(np.mean([row["ndcg_at_10"] for row in rows])), 4),
            "recall_at_20": round(
                float(np.mean([row["recall_at_20"] for row in rows])), 4
            ),
            "latency_p50_ms": round(float(np.percentile(latencies, 50)), 2),
            "latency_p95_ms": round(float(np.percentile(latencies, 95)), 2),
            "degraded_queries": sum(row["backend"] == "sqlite" for row in rows),
        }
        report["modes"][mode] = {"summary": summary, "details": rows}
        print(mode, json.dumps(summary, ensure_ascii=False), flush=True)
    (settings.runtime / "evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    return report
