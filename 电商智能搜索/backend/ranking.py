"""Local CPU models and a small NumPy vector index for degraded search."""

import hashlib
import logging
from functools import lru_cache

import numpy as np

import database
import settings


logger = logging.getLogger("seek")
model_state = {"embedding": "not_loaded", "reranker": "not_loaded"}


@lru_cache(maxsize=1)
def load_encoder():
    if not settings.embedding_enabled:
        model_state["embedding"] = "disabled"
        return None
    try:
        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(4)
        model = SentenceTransformer(
            settings.embedding_model,
            device=settings.model_device,
            cache_folder=str(settings.runtime / "models"),
            local_files_only=True,
        )
        model_state["embedding"] = "ready"
        return model
    except (OSError, RuntimeError, ValueError, ImportError):
        model_state["embedding"] = "unavailable"
        logger.warning(
            "Embedding model is unavailable; keyword search remains available."
        )
        return None


@lru_cache(maxsize=1)
def load_reranker():
    if not settings.rerank_enabled:
        model_state["reranker"] = "disabled"
        return None
    try:
        from sentence_transformers import CrossEncoder

        model = CrossEncoder(
            settings.rerank_model,
            device=settings.model_device,
            max_length=256,
            local_files_only=True,
        )
        model_state["reranker"] = "ready"
        return model
    except (OSError, RuntimeError, ValueError, ImportError):
        model_state["reranker"] = "unavailable"
        logger.warning(
            "Reranking model is unavailable; retrieval order remains available."
        )
        return None


def encode_query(query):
    model = load_encoder()
    if model is None:
        return None
    instruction = "为这个句子生成表示以用于检索相关文章："
    return model.encode(instruction + query, normalize_embeddings=True).tolist()


def corpus_fingerprint(products):
    text = "\n".join(item["id"] + item["search_text"] for item in products)
    return hashlib.sha256((settings.embedding_model + text).encode()).hexdigest()


def build_vectors(products):
    model = load_encoder()
    if model is None:
        return False
    vectors = model.encode(
        [item["search_text"] for item in products],
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    target = settings.runtime / "vectors.npz"
    temporary = settings.runtime / "vectors-building.npz"
    np.savez_compressed(
        temporary,
        ids=np.array([item["id"] for item in products]),
        vectors=vectors,
        fingerprint=np.array(corpus_fingerprint(products)),
    )
    temporary.replace(target)
    load_vectors.cache_clear()
    return True


@lru_cache(maxsize=1)
def load_vectors():
    path = settings.runtime / "vectors.npz"
    if not path.exists():
        return None
    products = database.select_products({"in_stock": False})
    with np.load(path, allow_pickle=False) as saved:
        if str(saved["fingerprint"]) != corpus_fingerprint(products):
            logger.warning("Vector snapshot is stale; rebuild the product index.")
            return None
        return saved["ids"].tolist(), saved["vectors"].copy()


def local_vector_candidates(query_vector, allowed_ids, limit=120):
    saved = load_vectors()
    if saved is None or query_vector is None:
        return []
    product_ids, vectors = saved
    scores = vectors @ np.array(query_vector, dtype=np.float32)
    candidates = [
        (product_ids[index], float(scores[index]))
        for index in np.argsort(-scores)
        if product_ids[index] in allowed_ids and scores[index] >= 0.40
    ]
    return [product_id for product_id, score in candidates[:limit]]


def rerank_products(query, products, limit=32):
    model = load_reranker()
    if model is None or not products:
        return products, False
    try:
        head = products[:limit]
        scores = model.predict(
            [(query, item["search_text"]) for item in head],
            batch_size=8,
            show_progress_bar=False,
        )
        ranked = [
            item
            for score, item in sorted(
                zip(scores.tolist(), head),
                key=lambda pair: pair[0],
                reverse=True,
            )
        ]
        return ranked + products[limit:], True
    except (RuntimeError, ValueError):
        logger.warning("Reranking failed; falling back to retrieval order.")
        return products, False


def warm_models():
    load_encoder()
    load_reranker()
