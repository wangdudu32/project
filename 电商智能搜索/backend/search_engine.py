"""OpenSearch operations stay in one module, with SQLite as the source of truth."""

import logging
import time
from functools import lru_cache
from uuid import uuid4

from opensearchpy import OpenSearch, helpers
from opensearchpy.exceptions import OpenSearchException

import settings


logger = logging.getLogger("seek")
engine_state = {"available": False, "checked_at": 0.0, "error": None}


@lru_cache(maxsize=1)
def get_client():
    return OpenSearch(
        hosts=[settings.search_url], timeout=3, max_retries=0, retry_on_timeout=False
    )


def is_available(force=False):
    if settings.search_backend == "sqlite":
        return False
    if not force and time.monotonic() - engine_state["checked_at"] < 10:
        return engine_state["available"]
    try:
        info = get_client().info()
        engine_state["available"] = (
            info.get("version", {}).get("distribution") == "opensearch"
        )
        engine_state["error"] = None
    except OpenSearchException:
        engine_state["available"] = False
        engine_state["error"] = "OpenSearch 暂不可用，已启用本地检索"
    engine_state["checked_at"] = time.monotonic()
    return engine_state["available"]


def index_ready():
    try:
        return is_available() and get_client().indices.exists(
            index=settings.search_index
        )
    except OpenSearchException:
        return False


def index_has_vectors():
    if not index_ready():
        return False
    try:
        mapping = get_client().indices.get_mapping(index=settings.search_index)
        return all(
            "embedding" in value["mappings"]["properties"] for value in mapping.values()
        )
    except OpenSearchException:
        return False


def publish_index(products, vectors=None):
    """Build a new index, then switch its alias atomically."""
    if not is_available(force=True):
        return False
    client = get_client()
    name = settings.search_index + "_" + uuid4().hex[:12]
    properties = {
        "id": {"type": "keyword"},
        "name": {"type": "text", "analyzer": "cjk"},
        "search_text": {"type": "text", "analyzer": "cjk"},
        "brand": {"type": "keyword"},
        "category": {"type": "keyword"},
        "color": {"type": "keyword"},
        "tags": {"type": "keyword"},
        "price": {"type": "float"},
        "stock": {"type": "integer"},
    }
    index_settings = {"number_of_shards": 1, "number_of_replicas": 0}
    vector_map = {}
    if vectors is not None:
        product_ids, matrix = vectors
        vector_map = dict(zip(product_ids, matrix.tolist()))
        index_settings["index.knn"] = True
        properties["embedding"] = {
            "type": "knn_vector",
            "dimension": int(matrix.shape[1]),
            "method": {"name": "hnsw", "engine": "lucene", "space_type": "cosinesimil"},
        }
    client.indices.create(
        index=name,
        body={"settings": index_settings, "mappings": {"properties": properties}},
    )
    actions = []
    for product in products:
        document = {
            field: product[field] for field in properties if field != "embedding"
        }
        if product["id"] in vector_map:
            document["embedding"] = vector_map[product["id"]]
        actions.append({"_index": name, "_id": product["id"], "_source": document})
    helpers.bulk(client, actions, refresh=True)
    previous = (
        list(client.indices.get_alias(name=settings.search_index))
        if client.indices.exists_alias(name=settings.search_index)
        else []
    )
    alias_actions = [
        {"remove": {"index": old, "alias": settings.search_index}} for old in previous
    ]
    alias_actions.append({"add": {"index": name, "alias": settings.search_index}})
    client.indices.update_aliases(body={"actions": alias_actions})
    for old in previous:
        if old.startswith(settings.search_index + "_"):
            client.indices.delete(index=old)
    return True


def retrieve(query, allowed_ids, query_vector=None, limit=120):
    if not index_ready():
        return None
    client = get_client()
    filters = {"terms": {"id": list(allowed_ids)}}
    try:
        keywords = client.search(
            index=settings.search_index,
            body={
                "size": limit,
                "_source": False,
                "query": {
                    "bool": {
                        "must": {
                            "multi_match": {
                                "query": query,
                                "fields": ["name^3", "search_text"],
                            }
                        },
                        "filter": filters,
                    }
                },
            },
        )
        keyword_ids = [item["_id"] for item in keywords["hits"]["hits"]]
        vector_ids = []
        if query_vector is not None:
            mapping = client.indices.get_mapping(index=settings.search_index)
            has_vectors = all(
                "embedding" in value["mappings"]["properties"]
                for value in mapping.values()
            )
            if has_vectors:
                semantic = client.search(
                    index=settings.search_index,
                    body={
                        "size": limit,
                        "_source": False,
                        "query": {
                            "knn": {
                                "embedding": {
                                    "vector": query_vector,
                                    "k": limit,
                                    "filter": filters,
                                }
                            }
                        },
                    },
                )
                # Lucene cosine score is (1 + cosine_similarity) / 2.
                vector_ids = [
                    item["_id"]
                    for item in semantic["hits"]["hits"]
                    if item["_score"] >= 0.70
                ]
        return keyword_ids, vector_ids
    except OpenSearchException:
        engine_state.update(
            available=False,
            checked_at=time.monotonic(),
            error="搜索引擎请求失败，已切换到本地检索",
        )
        logger.warning("OpenSearch retrieval failed; using local retrieval.")
        return None
