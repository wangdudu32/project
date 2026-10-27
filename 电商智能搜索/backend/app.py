"""FastAPI routes. Run from the root with: uvicorn app:app --app-dir backend."""

import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

import agent
import database
import ranking
import search
import search_engine
import settings
from import_data import import_products
from schemas import ChatRequest, CompareRequest, EventRequest, SearchRequest


logger = logging.getLogger("seek")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler(settings.runtime / "app.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)


def prepare_search():
    database.initialize_database()
    if database.product_count() == 0:
        import_products(settings.root / "data" / "products.jsonl", with_models=False)
    ranking.warm_models()
    if ranking.load_encoder() is not None and ranking.load_vectors() is None:
        ranking.build_vectors(database.select_products({"in_stock": False}))
    needs_index = not search_engine.index_ready() or (
        ranking.load_vectors() is not None and not search_engine.index_has_vectors()
    )
    if search_engine.is_available(force=True) and needs_index:
        search_engine.publish_index(
            database.select_products({"in_stock": False}), ranking.load_vectors()
        )


@asynccontextmanager
async def lifespan(application):
    await asyncio.to_thread(prepare_search)
    yield
    search_engine.get_client().close()


app = FastAPI(
    title="SEEK 寻物 · 电商智能搜索",
    version="1.0.0",
    description="关键词与向量检索、模型精排、多轮导购和商品对比。商品及参数均为模拟数据。",
    lifespan=lifespan,
)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "products": database.product_count(),
        "search_backend": "opensearch" if search_engine.index_ready() else "sqlite",
        "models": dict(ranking.model_state),
        "chat": {
            "configured": bool(settings.api_key and settings.base_url),
            **agent.model_status,
        },
        "is_demo": True,
    }


@app.get("/api/facets")
def facets():
    return database.get_facets()


@app.post("/api/search")
def search_catalog(request: SearchRequest):
    return search.search_products(request)


@app.get("/api/products/{product_id}")
def product_detail(product_id: str):
    product = database.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return search.public_product(product)


@app.post("/api/compare")
def compare(request: CompareRequest):
    try:
        return search.compare_products(request.product_ids)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        return await agent.answer_message(request.message, request.session_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/chat/{session_id}")
def conversation(session_id: UUID):
    try:
        identifier, state = database.load_session(str(session_id))
        return {
            "session_id": identifier,
            "state": state,
            "messages": database.get_messages(identifier),
        }
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.delete("/api/chat/{session_id}")
def clear_conversation(session_id: UUID):
    database.delete_session(str(session_id))
    return {"deleted": True}


@app.post("/api/events", status_code=201)
def event(request: EventRequest):
    if database.get_product(request.product_id) is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    database.record_event(request.kind, request.product_id)
    return {"recorded": True}


images = settings.root / "frontend" / "public" / "images"
if images.is_dir():
    app.mount("/images", StaticFiles(directory=images), name="images")
dist = settings.root / "frontend" / "dist"
if dist.is_dir():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
else:

    @app.get("/")
    def development_hint():
        return {
            "message": "后端已启动。开发界面请运行 cd frontend && npm run dev；构建后可直接访问此地址。",
            "docs": "/docs",
        }
