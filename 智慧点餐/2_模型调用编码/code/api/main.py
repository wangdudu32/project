"""智慧点餐 API。基础点餐不依赖模型和地图服务。"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

import config
from api import admin, auth, shop
from api.schemas import ChatRequest, DeliveryRequest
from database import SessionLocal, init_db
from seed import seed_menu

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    init_db()
    with SessionLocal() as db:
        seed_menu(db)
    yield


request_header = APIKeyHeader(name="X-Requested-With", auto_error=False, description="写接口填写 aimenu")
app = FastAPI(title="智慧点餐", version="2.0", lifespan=lifespan,
              dependencies=[Depends(request_header)])
app.include_router(auth.router)
app.include_router(shop.router)
app.include_router(admin.router)


@app.middleware("http")
async def protect_requests(request: Request, call_next):
    # Cookie 登录配合自定义请求头，拒绝第三方页面的普通表单提交。
    # 不开放跨域；前端开发时使用 Vite 的 /api 代理。
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.headers.get("X-Requested-With") != "aimenu":
        return JSONResponse(status_code=403, content={"detail": "请求缺少 X-Requested-With: aimenu"})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(status_code=422, content={"detail": "输入格式不正确，请检查必填项、长度和数值范围"})


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    logger.error("数据库操作失败：%s", type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "数据库暂时不可用，请稍后重试"})


@app.get("/")
def root():
    return {"message": "智慧点餐 API", "docs": "/docs"}


@app.get("/health")
@app.get("/healthy", include_in_schema=False)
def health():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/config")
def public_config():
    return {"restaurant_name": os.getenv("RESTAURANT_NAME", "小满餐厅"),
            "restaurant_address": os.getenv("RESTAURANT_ADDRESS", "北京市海淀区中关村"),
            "restaurant_hours": os.getenv("RESTAURANT_HOURS", "每天 09:00-22:00"),
            "ai_enabled": config.AI_ENABLED, "amap_enabled": config.AMAP_ENABLED,
            "payment_mode": "demo"}


@app.post("/chat")
def chat(data: ChatRequest):
    from LangChain.main import langchain_chat
    result = langchain_chat(data.query, [message.model_dump() for message in data.history])
    return {"success": True, "query": data.query, **result}


@app.post("/delivery")
def delivery(data: DeliveryRequest):
    from tools.amap_tool import check_delivery_range
    result = check_delivery_range(data.address, data.travel_mode)
    return {**result, "success": result["status"] == "success",
            "travel_mode": data.travel_mode, "input_address": data.address}
