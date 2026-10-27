"""Read configuration once. Start all commands from the project root."""

import os
from pathlib import Path

from dotenv import load_dotenv


root = Path(os.getenv("PROJECT_ROOT", Path.cwd())).resolve()
load_dotenv(root / ".env", override=False)
runtime = root / "runtime"
runtime.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(runtime / "models"))
os.environ.setdefault("TORCH_HOME", str(runtime / "models" / "torch"))
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "4")

database_path = Path(os.getenv("DATABASE_PATH", runtime / "shop.db"))
search_url = os.getenv("OPENSEARCH_URL", "http://127.0.0.1:9200").rstrip("/")
search_index = os.getenv("OPENSEARCH_INDEX", "seek_products")
search_backend = os.getenv("SEARCH_BACKEND", "auto")
embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
rerank_model = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-base")
model_device = os.getenv("MODEL_DEVICE", "cpu")
embedding_enabled = os.getenv("EMBEDDING_ENABLED", "true").lower() == "true"
rerank_enabled = os.getenv("RERANK_ENABLED", "true").lower() == "true"
api_key = os.getenv("OPENAI_API_KEY", "")
base_url = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
chat_model = os.getenv("CHAT_MODEL", os.getenv("OPENAI_MODEL", ""))
model_timeout = float(os.getenv("MODEL_TIMEOUT", "45"))
api_host = os.getenv("API_HOST", "127.0.0.1")
api_port = int(os.getenv("API_PORT", "8000"))
