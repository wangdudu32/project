import logging
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agent.tools import pdf_page_count
from app.config import Settings, get_settings
from app.interview import InterviewService, public_interview, summary
from app.llm import Model, ModelConfigError, ModelError, create_model
from app.models import AnswerRequest, QuestionRequest
from app.storage import ConflictError, Storage

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, model: Model | None = None) -> FastAPI:
    settings = settings or get_settings()
    storage = Storage(settings.storage_dir)
    service = InterviewService(storage, model or create_model(settings), settings)
    application = FastAPI(title="智能面试助手", version="1.0.0")
    application.state.service = service
    application.add_middleware(
        CORSMiddleware, allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
    )

    @application.exception_handler(ModelError)
    async def model_error_handler(_, exc):
        return JSONResponse(status_code=503 if isinstance(exc, ModelConfigError) else 502, content={"detail": str(exc)})

    @application.exception_handler(ConflictError)
    async def conflict_handler(_, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.exception_handler(KeyError)
    async def missing_handler(_, exc):
        return JSONResponse(status_code=404, content={"detail": exc.args[0]})

    @application.get("/health")
    def health():
        return {"status": "ok", "model_provider": settings.model_provider, "model_configured": settings.configured}

    @application.post("/upload", status_code=201)
    def upload_pdf(file: UploadFile = File(...)):
        filename = Path((file.filename or "").replace("\\", "/")).name
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(400, "只支持 PDF 文件。")
        document_id = uuid4().hex
        directory = settings.storage_dir / "uploads"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{document_id}.pdf"
        total = 0
        try:
            with path.open("wb") as target:
                while chunk := file.file.read(1024 * 1024):
                    if total == 0 and not chunk.startswith(b"%PDF-"):
                        raise HTTPException(400, "文件内容不是有效的 PDF。")
                    total += len(chunk)
                    if total > settings.max_upload_mb * 1024 * 1024:
                        raise HTTPException(413, f"文件不能超过 {settings.max_upload_mb} MB。")
                    target.write(chunk)
            if total == 0:
                raise HTTPException(400, "不能上传空文件。")
            try:
                pages = pdf_page_count(path, settings.max_pdf_pages)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            storage.add_document({"id": document_id, "filename": filename, "path": str(path), "pages": pages})
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            file.file.close()
        return {"document_id": document_id, "filename": filename, "page_count": pages}

    @application.post("/generate", status_code=201)
    def generate(request: QuestionRequest):
        return service.generate(request)

    @application.get("/interviews")
    def interviews(limit: int = Query(100, ge=1, le=500)):
        return [summary(item) for item in storage.list(limit)]

    @application.get("/interviews/{interview_id}")
    def get_interview(interview_id: str):
        return public_interview(service.get(interview_id))

    @application.post("/interviews/{interview_id}/questions/{question_id}/answer")
    def answer(interview_id: str, question_id: str, request: AnswerRequest):
        return service.answer(interview_id, question_id, request.answer)

    @application.post("/interviews/{interview_id}/questions/{question_id}/followup")
    def followup(interview_id: str, question_id: str):
        return service.followup(interview_id, question_id)

    @application.post("/interviews/{interview_id}/finish")
    def finish(interview_id: str):
        return service.finish(interview_id)

    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.getenv("BACKEND_HOST", "127.0.0.1"), port=int(os.getenv("BACKEND_PORT", "8000")))
