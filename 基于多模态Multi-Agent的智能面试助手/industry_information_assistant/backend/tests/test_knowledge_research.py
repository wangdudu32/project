"""使用临时数据库验证路由接线，外部模型、DocMind 和 Milvus 使用替身。"""
import asyncio
import importlib
import logging
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base, get_db
from models.chat import ChatSession
from models.knowledge import Document, KnowledgeBase
from models.research import ResearchCheckpoint
from models.user import User
from router.auth_router import get_current_user_required
from service.knowledge_collection import knowledge_collection

research = importlib.import_module("router.research_router")
knowledge = importlib.import_module("router.knowledge_router")


@compiles(JSONB, "sqlite")
def sqlite_json_type(_, compiler, **kw):
    return "JSON"


@pytest.fixture
def setup(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine, tables=[model.__table__ for model in (User, ChatSession, KnowledgeBase, Document, ResearchCheckpoint)])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        owner = User(username="owner", email="owner@example.com", hashed_password="unused")
        other = User(username="other", email="other@example.com", hashed_password="unused")
        db.add_all([owner, other])
        db.flush()
        kb = KnowledgeBase(name="中文知识库", user_id=owner.id)
        other_kb = KnowledgeBase(name="中文知识库", user_id=other.id)
        session = ChatSession(user_id=owner.id, title="test")
        other_session = ChatSession(user_id=other.id, title="other")
        db.add_all([kb, other_kb, session, other_session])
        db.commit()
    def database():
        with factory() as db:
            yield db
    app = FastAPI()
    app.include_router(research.router)
    app.include_router(knowledge.router)
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user_required] = lambda: owner
    monkeypatch.setattr("core.database.SessionLocal", factory)
    monkeypatch.setattr("service.checkpoint_service.SessionLocal", factory)
    monkeypatch.setattr(knowledge, "UPLOAD_DIR", str(tmp_path))
    calls = []
    class ResearchService:
        async def research(self, **kwargs):
            calls.append(kwargs)
            yield 'data: {"type":"research_complete"}\n\n'
    def make_service(max_iterations=None):
        calls.append({"max_iterations": max_iterations})
        return ResearchService()
    monkeypatch.setattr(research, "get_research_service_v2", make_service)
    with TestClient(app) as client:
        yield client, factory, owner, kb, other_kb, session, other_session, calls
    engine.dispose()


@pytest.mark.parametrize("method", ["post", "get"])
def test_research_passes_selection_modes_and_iterations(setup, method):
    client, _, owner, kb, _, session, _, calls = setup
    params = {"query": "分析资料", "kb_id": str(kb.id), "max_iterations": 2, "version": "v2"}
    if method == "post":
        params.update(session_id=str(session.id), search_modes=["local"])
        response = client.post("/research/stream", json=params)
    else:
        params.update(search_web=False, search_local=True)
        response = client.get("/research/stream", params=params)
    assert response.status_code == 200, response.text
    assert "research_complete" in response.text
    assert calls[0] == {"max_iterations": 2}
    assert calls[1]["kb_id"] == str(kb.id)
    assert calls[1]["user_id"] == str(owner.id)
    assert calls[1]["search_local"] is True and calls[1]["search_web"] is False


def test_invalid_and_foreign_knowledge_bases_are_rejected(setup):
    client, _, _, _, other_kb, _, other_session, calls = setup
    assert client.post("/research/stream", json={"query": "test", "search_modes": ["local"]}).status_code == 400
    assert client.post("/research/stream", json={"query": "test", "search_modes": ["local"], "kb_id": str(other_kb.id)}).status_code == 404
    assert client.post("/research/stream", json={"query": "test", "max_iterations": 0}).status_code == 422
    assert client.post("/research/stream", json={"query": "test", "session_id": str(other_session.id)}).status_code == 404
    assert not calls


def test_checkpoint_routes_do_not_expose_other_users(setup):
    client, factory, owner, _, _, session, other_session, calls = setup
    with factory() as db:
        db.add_all([
            ResearchCheckpoint(session_id=str(session.id), user_id=owner.id, query="mine", phase="writing", state_json={}),
            ResearchCheckpoint(session_id=str(other_session.id), user_id=other_session.user_id, query="private", phase="writing", state_json={}),
        ])
        db.commit()
    routes = [f"/research/checkpoint/{other_session.id}", f"/research/checkpoint/{other_session.id}/full"]
    for route in routes:
        assert client.get(route).status_code == 404
    assert client.post(f"/research/resume/{other_session.id}").status_code == 404
    assert client.post(f"/research/cancel/{other_session.id}").status_code == 404
    assert client.delete(f"/research/checkpoint/{other_session.id}").status_code == 404
    listing = client.get("/research/checkpoints")
    assert listing.status_code == 200
    assert [item["query"] for item in listing.json()["checkpoints"]] == ["mine"]
    assert not calls


def test_upload_and_scout_share_stable_collection_after_rename(setup, monkeypatch):
    client, _, _, kb, _, _, _, _ = setup
    parsed = []
    def parse_document(**kwargs):
        parsed.append(kwargs)
        return {"success": True, "document_count": 2}
    monkeypatch.setattr("service.docmind_service.process_document_with_docmind", parse_document)
    response = client.post(f"/knowledge-bases/{kb.id}/documents", files={"file": ("notes.txt", b"content")})
    assert response.status_code == 200, response.text
    assert parsed[0]["index_name"] == knowledge_collection(kb.id)
    assert parsed[0]["document_id"] == response.json()["id"]
    assert client.put(f"/knowledge-bases/{kb.id}", json={"name": "改名后"}).status_code == 200

    scout_module = importlib.import_module("service.deep_research_v2.agents.scout")
    scout = scout_module.DeepScout.__new__(scout_module.DeepScout)
    scout.logger = logging.getLogger("test-scout")
    searched = []
    class Milvus:
        def search(self, **kwargs):
            searched.append(kwargs)
            return [{"content": "content", "filename": "notes.txt", "score": .9, "doc_id": response.json()["id"]}]
    scout.milvus_service = Milvus()
    monkeypatch.setattr(scout_module, "MILVUS_AVAILABLE", True)
    monkeypatch.setattr(scout_module, "generate_embedding", lambda text: [0.1, 0.2])
    result = asyncio.run(scout._execute_local_search("query", kb_id=str(kb.id)))
    assert searched[0]["collection_name"] == parsed[0]["index_name"]
    assert result[0]["is_local"] is True
    assert result[0]["doc_id"] == response.json()["id"]


def test_graph_keeps_selected_kb_and_iteration_limit():
    from service.deep_research_v2.graph import DeepResearchGraph
    graph = DeepResearchGraph.__new__(DeepResearchGraph)
    graph.max_iterations = 2
    captured = []
    async def run(state):
        captured.append(state)
        yield {"type": "test"}
    graph._run_simplified = run
    kb_id = str(uuid4())
    async def consume():
        return [event async for event in graph.run("query", "session", search_web=False, search_local=True, kb_id=kb_id)]
    asyncio.run(consume())
    assert captured[0]["kb_id"] == kb_id
    assert captured[0]["max_iterations"] == 2
    assert captured[0]["search_web"] is False


def test_service_forwards_selected_kb(monkeypatch):
    module = importlib.import_module("service.deep_research_v2.service")
    calls = []
    class Graph:
        def __init__(self, **kwargs):
            calls.append(kwargs)
        async def run(self, *args, **kwargs):
            calls.append(kwargs)
            yield {"type": "test"}
    monkeypatch.setattr(module, "DeepResearchGraph", Graph)
    service = module.DeepResearchV2Service(max_iterations=2)
    kb_id = str(uuid4())
    async def consume():
        return [event async for event in service.research("query", kb_id=kb_id, search_local=True, search_web=False)]
    events = asyncio.run(consume())
    assert calls[0]["max_iterations"] == 2
    assert calls[1]["kb_id"] == kb_id
    assert calls[1]["search_local"] is True and calls[1]["search_web"] is False
    assert events[-1] == "data: [DONE]\n\n"


def test_same_names_have_different_collections():
    first, second = uuid4(), uuid4()
    assert knowledge_collection(first) != knowledge_collection(second)
    assert knowledge_collection(first) == knowledge_collection(str(first))
    assert knowledge_collection(first).isascii()
    with pytest.raises(ValueError):
        knowledge_collection("用户输入的名称")
