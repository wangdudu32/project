"""按真实菜品 ID 同步向量，失败时保留原索引数据。"""
import os
import time
from functools import lru_cache

import config
from tools.db_tool import get_menu_item_list, menu_text

DIMENSION = 1536
NAMESPACE = "aimenu"


def embedding(text):
    import dashscope
    key = os.getenv("DASHSCOPE_API_KEY")
    if not key:
        raise RuntimeError("请配置 DASHSCOPE_API_KEY")
    response = dashscope.TextEmbedding.call(api_key=key, model="text-embedding-v4", input=[text], dimension=DIMENSION)
    if response.status_code != 200:
        raise RuntimeError("菜品向量生成失败，请检查模型服务配置")
    vector = response['output']['embeddings'][0]['embedding']
    if len(vector) != DIMENSION:
        raise RuntimeError("向量维度不匹配")
    return vector


def client():
    from pinecone import Pinecone
    if not config.PINECONE_ENABLED or not os.getenv("PINECONE_API_KEY"):
        raise RuntimeError("请启用并配置 Pinecone")
    return Pinecone(api_key=os.environ["PINECONE_API_KEY"])


@lru_cache(maxsize=1)
def index():
    pc = client()
    name = os.getenv("PINECONE_INDEX", "aimenu-items")
    if not pc.has_index(name):
        raise RuntimeError("菜单向量索引不存在，请先执行 python manage.py sync-menu")
    return pc.Index(name)


def sync_menu():
    from pinecone import ServerlessSpec
    pc = client()
    items = get_menu_item_list()
    # 先生成全部向量，任何一步失败都不会清空线上索引。
    vectors = [{"id": str(item['id']), "values": embedding(menu_text(item)),
                "metadata": {"dish_id": str(item['id']), "content": menu_text(item)}} for item in items]
    name = os.getenv("PINECONE_INDEX", "aimenu-items")
    if not pc.has_index(name):
        pc.create_index(name=name, dimension=DIMENSION, metric="cosine",
                        spec=ServerlessSpec(cloud="aws", region=os.getenv("PINECONE_ENV", "us-east-1")))
    for _ in range(30):
        if pc.describe_index(name).status['ready']:
            break
        time.sleep(1)
    else:
        raise RuntimeError("索引仍在初始化，请稍后重新同步")
    target = pc.Index(name)
    for start in range(0, len(vectors), 100):
        target.upsert(vectors=vectors[start:start + 100], namespace=NAMESPACE)
    # 只清理本项目 namespace 中已下架或删除的菜品，保留其他业务数据。
    active = {str(item['id']) for item in items}
    for batch in target.list(namespace=NAMESPACE):
        stale = [item_id for item_id in batch if item_id not in active]
        if stale:
            target.delete(ids=stale, namespace=NAMESPACE)
    index.cache_clear()
    return len(items)


def search_menu_items_with_id(query, top_k=5):
    matches = index().query(vector=embedding(query), namespace=NAMESPACE, top_k=top_k, include_metadata=True).matches
    # 每次从业务数据库取最新价格和上下架状态，避免旧向量推荐已下架菜品。
    available = {str(item['id']): item for item in get_menu_item_list()}
    ids = [match.id for match in matches if match.id in available and match.score >= 0.25]
    return {"ids": ids, "contents": [menu_text(available[item_id]) for item_id in ids]}


def search_menu_items(query, top_k=2):
    return search_menu_items_with_id(query, top_k)['contents']
