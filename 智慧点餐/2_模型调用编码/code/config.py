"""统一读取配置，切换工作目录也能找到 .env。"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'aimenu.db'}")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
SESSION_HOURS = 24
AI_ENABLED = os.getenv("AI_ENABLED", "false").lower() == "true"
AMAP_ENABLED = os.getenv("AMAP_ENABLED", "false").lower() == "true"
PINECONE_ENABLED = os.getenv("PINECONE_ENABLED", "false").lower() == "true"
