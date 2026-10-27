"""Filter first, retrieve candidates, fuse ranks, and rerank a bounded shortlist."""

import time
from collections import defaultdict

import database
import ranking
import search_engine
import settings
from schemas import ProductFilters, SearchRequest
from text import extract_constraints, retrieval_text, tokenize


def merge_results(keyword_ids, vector_ids):
    scores = {}
    for candidates in (keyword_ids, vector_ids):
        for position, product_id in enumerate(candidates, start=1):
            scores[product_id] = scores.get(product_id, 0) + 1 / (60 + position)
    return sorted(scores, key=scores.get, reverse=True)


def public_product(product):
    return {key: value for key, value in product.items() if key != "search_text"}


def diversify_products(products, window=12):
    """Alternate product families so near-identical editions do not fill the first screen."""
    families = defaultdict(list)
    for product in products[:window]:
        families[product.get("family_id", product["id"])].append(product)
    result = []
    for position in range(max((len(items) for items in families.values()), default=0)):
        result.extend(
            items[position] for items in families.values() if position < len(items)
        )
    return result + products[window:]


def search_products(request):
    started = time.perf_counter()
    typed = (
        request
        if isinstance(request, SearchRequest)
        else SearchRequest.model_validate(request)
    )
    filters = extract_constraints(
        typed.query, typed.filters.model_dump(exclude_none=True)
    )
    filters = ProductFilters.model_validate(filters).model_dump(exclude_none=True)
    eligible = database.select_products(filters)
    products = {item["id"]: item for item in eligible}
    query = retrieval_text(typed.query)
    notices = []
    backend = "catalog"
    reranked = False
    semantic_used = False
    if not query or not products:
        results = sorted(eligible, key=lambda item: item["popularity"], reverse=True)
    else:
        query_vector = ranking.encode_query(query) if typed.mode != "keyword" else None
        native = search_engine.retrieve(query, set(products), query_vector)
        if native is not None:
            keyword_ids, vector_ids = native
            backend = "opensearch"
        else:
            keyword_ids = database.keyword_candidates(tokenize(query), set(products))
            vector_ids = ranking.local_vector_candidates(query_vector, set(products))
            backend = "sqlite"
            if settings.search_backend != "sqlite":
                notices.append("搜索引擎暂不可用，当前使用本地检索")
        semantic_used = bool(vector_ids)
        if typed.mode == "keyword":
            ordered_ids = keyword_ids
        else:
            ordered_ids = merge_results(keyword_ids, vector_ids)
        # Always re-read authoritative, already-filtered product records.
        results = [
            products[product_id] for product_id in ordered_ids if product_id in products
        ]
        if (
            typed.mode in ("rerank", "diverse")
            and typed.sort == "relevance"
            and results
        ):
            results, reranked = ranking.rerank_products(query, results)
            if typed.mode == "diverse":
                results = diversify_products(results)
        if typed.mode != "keyword" and query_vector is None:
            notices.append("向量模型未就绪，当前使用关键词检索")
        if typed.mode in ("rerank", "diverse") and results and not reranked:
            notices.append("精排模型未就绪，当前保留召回顺序")
    if typed.sort == "price_asc":
        results.sort(key=lambda item: (item["price"], item["id"]))
    elif typed.sort == "price_desc":
        results.sort(key=lambda item: (-item["price"], item["id"]))
    elif typed.sort == "newest":
        results.sort(key=lambda item: item["created_at"], reverse=True)
    start = (typed.page - 1) * typed.page_size
    return {
        "products": [
            public_product(item) for item in results[start : start + typed.page_size]
        ],
        "total": len(results),
        "page": typed.page,
        "page_size": typed.page_size,
        "filters": filters,
        "meta": {
            "backend": backend,
            "semantic": semantic_used,
            "reranked": reranked,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "notices": notices,
        },
    }


def compare_products(product_ids):
    unique = list(dict.fromkeys(product_ids))
    if not 2 <= len(unique) <= 3:
        raise ValueError("请选择两至三件不同的商品进行比较")
    products = [database.get_product(product_id) for product_id in unique]
    if any(product is None for product in products):
        raise LookupError("比较列表中包含不存在的商品")
    rows = []
    for label, field in (
        ("价格", "price"),
        ("品牌", "brand"),
        ("颜色", "color_label"),
        ("材质", "material"),
        ("重量", "weight"),
        ("适用场景", "tags"),
        ("库存", "stock"),
    ):
        rows.append({"label": label, "values": [item[field] for item in products]})
    return {
        "products": [public_product(item) for item in products],
        "rows": rows,
        "is_demo": True,
    }
