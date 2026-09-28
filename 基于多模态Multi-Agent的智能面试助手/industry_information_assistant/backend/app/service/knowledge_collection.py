"""知识库使用固定 ID 命名集合，避免中文名称、改名和用户重名造成冲突。"""
from uuid import UUID


def knowledge_collection(kb_id: str) -> str:
    return "kb_" + UUID(str(kb_id)).hex
