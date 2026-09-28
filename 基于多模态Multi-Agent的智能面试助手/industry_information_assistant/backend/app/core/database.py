# Copyright © 2026 深圳市深维智见教育科技有限公司 版权所有
# 未经授权，禁止转售或仿制。

"""数据库连接和会话管理"""
import os
from sqlalchemy import create_engine, URL
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# 从环境变量获取数据库配置
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres123")
POSTGRES_DB = os.getenv("POSTGRES_DB", "industry_assistant")

DATABASE_URL = URL.create(
    "postgresql+psycopg2", username=POSTGRES_USER, password=POSTGRES_PASSWORD,
    host=POSTGRES_HOST, port=int(POSTGRES_PORT), database=POSTGRES_DB,
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """获取数据库会话的依赖函数"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
