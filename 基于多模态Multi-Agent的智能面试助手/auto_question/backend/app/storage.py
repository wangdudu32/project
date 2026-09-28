"""SQLite 保存上传信息和面试记录，版本号防止并发提交互相覆盖。"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConflictError(RuntimeError):
    pass


class Storage:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "interviews.sqlite3"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, filename TEXT NOT NULL,
                    path TEXT NOT NULL, pages INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS interviews (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def add_document(self, document: dict):
        with self.connect() as db:
            db.execute("INSERT INTO documents VALUES (:id, :filename, :path, :pages)", document)

    def get_document(self, document_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
            return dict(row) if row else None

    def create(self, interview: dict):
        interview["version"] = 0
        with self.connect() as db:
            db.execute("INSERT INTO interviews VALUES (?, ?, ?, ?)", (
                interview["id"], json.dumps(interview, ensure_ascii=False), 0, interview["updated_at"],
            ))

    def get(self, interview_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM interviews WHERE id = ?", (interview_id,)).fetchone()
            return json.loads(row["payload"]) if row else None

    def list(self, limit: int = 100) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM interviews ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
            return [json.loads(row["payload"]) for row in rows]

    def update(self, interview: dict):
        version = interview["version"]
        updated = {**interview, "version": version + 1, "updated_at": now()}
        with self.connect() as db:
            result = db.execute("UPDATE interviews SET payload = ?, version = ?, updated_at = ? WHERE id = ? AND version = ?", (
                json.dumps(updated, ensure_ascii=False), updated["version"], updated["updated_at"], interview["id"], version,
            ))
            if result.rowcount != 1:
                raise ConflictError("面试记录已被另一个请求更新，请刷新后重试。")
        interview.update(updated)
