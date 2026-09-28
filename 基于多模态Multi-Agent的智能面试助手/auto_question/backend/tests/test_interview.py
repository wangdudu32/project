import json
from dataclasses import replace
from pathlib import Path

import httpx
import pypdfium2 as pdfium
import pytest
from fastapi.testclient import TestClient

from app.agent.tools import parse_pdf_to_images
from app.config import Settings
from app.llm import ModelError, RemoteModel
from app.main import create_app
from app.storage import ConflictError, Storage


class FakeModel:
    """只用于测试接口和编排，不代表真实模型的评分质量。"""
    def __init__(self):
        self.prompts = []
        self.question_count = 0
        self.review_count = 0
        self.fail_reviews = 0
        self.fail_evaluation = False

    def complete(self, prompt, image_path=None):
        self.prompts.append(prompt)
        assert image_path and Path(image_path).is_file()
        if "You are the reviewer" in prompt:
            self.review_count += 1
            return json.dumps({"status": "FAIL" if self.review_count <= self.fail_reviews else "PASS", "feedback": "核对推导过程"})
        if "You are an interview evaluator" in prompt:
            if self.fail_evaluation:
                raise ModelError("模型暂时不可用")
            return json.dumps({"correctness": 80, "depth": 60, "clarity": 90,
                               "feedback": "思路正确，需要解释适用条件。", "strengths": ["概念清晰"], "improvements": ["补充适用条件"]})
        self.question_count += 1
        return json.dumps({"question": f"请解释概念 {self.question_count} 的适用条件。", "answer": "参考答案内容", "analysis": "考查理解能力"})


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "sample.pdf"
    with pdfium.PdfDocument.new() as document:
        for _ in range(4):
            page = document.new_page(500, 700)
            page.close()
        document.save(path)
    return path.read_bytes()


@pytest.fixture
def setup(tmp_path):
    settings = Settings(storage_dir=tmp_path / "storage", model_base_url="https://model.invalid/v1", model_name="test", model_api_key="test")
    model = FakeModel()
    with TestClient(create_app(settings, model)) as client:
        yield client, model, settings


def generate(client, pdf, **options):
    uploaded = client.post("/upload", files={"file": ("学习资料.PDF", pdf, "application/pdf")})
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["page_count"] == 4
    response = client.post("/generate", json={"document_id": uploaded.json()["document_id"], "num_questions": 2, **options})
    assert response.status_code == 201, response.text
    return response.json()


def answer(client, interview, question):
    return client.post(f"/interviews/{interview['id']}/questions/{question['id']}/answer", json={"answer": "我的解释和一个实际例子。"})


def test_full_interview_followup_report_and_restart(setup, pdf):
    client, model, settings = setup
    interview = generate(client, pdf, num_questions=2, difficulty="hard", language="en")
    assert len(interview["questions"]) == 2
    assert [q["page"] for q in interview["questions"]] == [1, 4]
    assert all(q["difficulty"] == "hard" and q["status"] == "verified" for q in interview["questions"])
    assert "Output language: English. Difficulty: hard" in model.prompts[0]
    for q in interview["questions"]:
        assert not {"answer", "analysis", "image_path", "feedback", "evaluation"} & q.keys()
    session_id = interview["id"]
    first = interview["questions"][0]
    assert client.post(f"/interviews/{session_id}/finish").status_code == 409
    assert client.post(f"/interviews/{session_id}/questions/{first['id']}/followup").status_code == 409
    answered = answer(client, interview, first)
    assert answered.status_code == 200
    q = answered.json()["questions"][0]
    assert q["answer"] == "参考答案内容"
    assert q["evaluation"]["score"] == 76
    assert "answer" not in answered.json()["questions"][1]
    assert answer(client, interview, first).status_code == 409
    followup = client.post(f"/interviews/{session_id}/questions/{first['id']}/followup")
    assert followup.status_code == 200, followup.text
    questions = followup.json()["questions"]
    assert questions[-1]["parent_id"] == first["id"]
    assert "answer" not in questions[-1]
    assert client.post(f"/interviews/{session_id}/questions/{first['id']}/followup").status_code == 409
    for q in questions[1:]:
        assert answer(client, interview, q).status_code == 200
    assert client.post(f"/interviews/{session_id}/questions/{questions[-1]['id']}/followup").status_code == 409
    finished = client.post(f"/interviews/{session_id}/finish")
    assert finished.status_code == 200
    assert finished.json()["report"]["score"] == 76
    assert finished.json()["report"]["question_count"] == 3
    assert finished.json()["status"] == "completed"
    assert client.post(f"/interviews/{session_id}/finish").json() == finished.json()
    assert answer(client, interview, first).status_code == 409
    with TestClient(create_app(settings, FakeModel())) as restarted:
        assert restarted.get(f"/interviews/{session_id}").json() == finished.json()
        item = restarted.get("/interviews").json()[0]
        assert item["answered_count"] == 3 and item["score"] == 76
        assert "questions" not in item


def test_review_failure_is_explicit_and_bounded(setup, pdf):
    client, model, _ = setup
    model.fail_reviews = 99
    interview = generate(client, pdf, num_questions=1)
    assert model.review_count == 3
    assert model.question_count == 3  # 生成一次，修订两次
    assert interview["questions"][0]["status"] == "needs_revision"
    assert "feedback" not in interview["questions"][0]
    assert answer(client, interview, interview["questions"][0]).status_code == 200
    report = client.post(f"/interviews/{interview['id']}/finish").json()["report"]
    assert report["unverified_count"] == 1


def test_revision_can_pass(setup, pdf):
    client, model, _ = setup
    model.fail_reviews = 1
    interview = generate(client, pdf, num_questions=1)
    assert model.review_count == 2
    assert interview["questions"][0]["status"] == "verified"


def test_grading_failure_keeps_answer_retryable(setup, pdf):
    client, model, _ = setup
    interview = generate(client, pdf, num_questions=1)
    model.fail_evaluation = True
    assert answer(client, interview, interview["questions"][0]).status_code == 502
    stored = client.get(f"/interviews/{interview['id']}").json()["questions"][0]
    assert "user_answer" not in stored and "answer" not in stored
    model.fail_evaluation = False
    assert answer(client, interview, interview["questions"][0]).status_code == 200


@pytest.mark.parametrize("options", [{"num_questions": 0}, {"num_questions": 11}, {"difficulty": "unknown"}, {"language": "other"}])
def test_invalid_generation_parameters(setup, options):
    client, model, _ = setup
    response = client.post("/generate", json={"document_id": "a" * 32, **options})
    assert response.status_code == 422
    assert not model.prompts


def test_upload_validation_and_no_arbitrary_paths(setup, pdf):
    client, _, settings = setup
    for name, content in [("bad.txt", pdf), ("fake.pdf", b"hello"), ("empty.pdf", b""), ("broken.pdf", b"%PDF-1.7\ninvalid")]:
        assert client.post("/upload", files={"file": (name, content)}).status_code == 400
    assert not list((settings.storage_dir / "uploads").glob("*"))
    uploaded = client.post("/upload", files={"file": ("../../escape.pdf", pdf)}).json()
    assert uploaded["filename"] == "escape.pdf"
    assert "path" not in uploaded
    assert len(list((settings.storage_dir / "uploads").glob("*.pdf"))) == 1
    assert client.post("/generate", json={"document_id": "../../escape.pdf"}).status_code == 422
    assert client.post("/generate", json={"document_id": "f" * 32}).status_code == 404
    assert client.get("/interviews/missing").status_code == 404


def test_upload_limits(setup, pdf):
    _, model, settings = setup
    with TestClient(create_app(replace(settings, max_pdf_pages=2), model)) as client:
        assert client.post("/upload", files={"file": ("large.pdf", pdf)}).status_code == 400
    with TestClient(create_app(replace(settings, max_upload_mb=1), model)) as client:
        assert client.post("/upload", files={"file": ("large.pdf", b"%PDF-" + b"0" * 1024 * 1024)}).status_code == 413


def test_empty_answers_are_rejected(setup, pdf):
    client, _, _ = setup
    interview = generate(client, pdf, num_questions=1)
    q = interview["questions"][0]
    response = client.post(f"/interviews/{interview['id']}/questions/{q['id']}/answer", json={"answer": "  \n "})
    assert response.status_code == 422


def test_optimistic_lock_prevents_overwriting_an_answer(setup, pdf):
    client, _, settings = setup
    interview = generate(client, pdf, num_questions=1)
    storage = Storage(settings.storage_dir)
    stale = storage.get(interview["id"])
    assert answer(client, interview, interview["questions"][0]).status_code == 200
    with pytest.raises(ConflictError):
        storage.update(stale)
    assert storage.get(interview["id"])["questions"][0]["evaluation"]


def test_pdf_sampling_uses_last_page_and_caps_render_size(tmp_path, pdf):
    path = tmp_path / "sample.pdf"
    path.write_bytes(pdf)
    pages = parse_pdf_to_images(str(path), str(tmp_path / "images"), max_pages=2)
    assert [p["page"] for p in pages] == [1, 4]
    from PIL import Image
    for page in pages:
        with Image.open(page["image_path"]) as image:
            assert max(image.size) <= 1600


def test_missing_model_configuration_is_reported(tmp_path, pdf):
    with TestClient(create_app(Settings(storage_dir=tmp_path / "storage"))) as client:
        assert client.get("/health").json()["model_configured"] is False
        uploaded = client.post("/upload", files={"file": ("test.pdf", pdf)}).json()
        response = client.post("/generate", json={"document_id": uploaded["document_id"]})
        assert response.status_code == 503
        assert not client.get("/interviews").json()
        assert not list((tmp_path / "storage" / "pages").iterdir())


def test_invalid_model_json_does_not_create_incomplete_interview(setup, pdf, monkeypatch):
    client, model, settings = setup
    calls = []
    def invalid(prompt, image_path=None):
        calls.append(prompt)
        return '{"question": "missing required answer"}'
    monkeypatch.setattr(model, "complete", invalid)
    uploaded = client.post("/upload", files={"file": ("test.pdf", pdf)}).json()
    response = client.post("/generate", json={"document_id": uploaded["document_id"]})
    assert response.status_code == 502
    assert len(calls) == 2
    assert client.get("/interviews").json() == []
    assert not list((settings.storage_dir / "pages").iterdir())


def test_remote_provider_sends_image_and_hides_upstream_errors(tmp_path, monkeypatch):
    settings = Settings(storage_dir=tmp_path, model_base_url="https://model.example/v1", model_name="vl-test", model_api_key="secret-key")
    original = httpx.Client
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok":true}'}}]})
    monkeypatch.setattr(httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    image = tmp_path / "page.png"
    image.write_bytes(b"test-image")
    assert RemoteModel(settings).complete("instruction", str(image)) == '{"ok":true}'
    payload = json.loads(requests[0].content)
    assert str(requests[0].url) == "https://model.example/v1/chat/completions"
    assert payload["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    monkeypatch.setattr(httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(lambda r: httpx.Response(401, text="secret-key")), **kw))
    with pytest.raises(ModelError, match="401") as error:
        RemoteModel(settings).complete("instruction")
    assert "secret-key" not in str(error.value)
