"""配置统一放在 auto_question/.env，也可通过环境变量覆盖。"""
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_DIR / ".env")


def project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else PROJECT_DIR / path).resolve()


@dataclass(frozen=True)
class Settings:
    storage_dir: Path
    model_provider: str = "remote"
    model_base_url: str = ""
    model_api_key: str = ""
    model_name: str = ""
    model_path: str = ""
    adapter_path: str = ""
    model_device: str = "auto"
    model_timeout: float = 120
    max_upload_mb: int = 20
    max_pdf_pages: int = 200
    max_source_pages: int = 10
    review_rounds: int = 3
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    @property
    def configured(self) -> bool:
        if self.model_provider == "remote":
            return bool(self.model_base_url and self.model_name and self.model_api_key)
        return self.model_provider == "local" and Path(self.model_path).is_dir()


@lru_cache
def get_settings() -> Settings:
    return Settings(
        storage_dir=project_path(os.getenv("STORAGE_DIR", "backend/storage")),
        model_provider=os.getenv("MODEL_PROVIDER", "remote"),
        model_base_url=os.getenv("MODEL_BASE_URL", "").rstrip("/"),
        model_api_key=os.getenv("MODEL_API_KEY", ""),
        model_name=os.getenv("MODEL_NAME", ""),
        model_path=str(project_path(os.getenv("MODEL_PATH", "models/qwen2.5vl"))),
        adapter_path=str(project_path(os.environ["ADAPTER_PATH"])) if os.getenv("ADAPTER_PATH") else "",
        model_device=os.getenv("MODEL_DEVICE", "auto"),
        model_timeout=float(os.getenv("MODEL_TIMEOUT", "120")),
        cors_origins=tuple(x.strip() for x in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",") if x.strip()),
    )
