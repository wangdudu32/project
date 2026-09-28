"""统一远程视觉接口和本地 Qwen 推理，重依赖按需加载。"""
import base64
import json
import logging
import threading
from pathlib import Path
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings

logger = logging.getLogger(__name__)


class ModelError(RuntimeError):
    pass


class ModelConfigError(ModelError):
    pass


class Model(Protocol):
    def complete(self, prompt: str, image_path: str | None = None) -> str: ...


class RemoteModel:
    def __init__(self, settings: Settings):
        self.settings = settings

    def complete(self, prompt: str, image_path: str | None = None) -> str:
        s = self.settings
        if not s.configured:
            raise ModelConfigError("请在 auto_question/.env 配置 MODEL_BASE_URL、MODEL_API_KEY 和 MODEL_NAME。")
        content = [{"type": "text", "text": prompt}]
        if image_path:
            encoded = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}})
        try:
            with httpx.Client(timeout=s.model_timeout) as client:
                response = client.post(
                    f"{s.model_base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {s.model_api_key}"},
                    json={"model": s.model_name, "messages": [{"role": "user", "content": content}],
                          "temperature": 0.3, "max_tokens": 3000},
                )
                response.raise_for_status()
                result = response.json()["choices"][0]["message"]["content"]
                if not isinstance(result, str) or not result.strip():
                    raise ValueError("empty content")
                return result
        except httpx.TimeoutException as exc:
            raise ModelError("模型请求超时，请稍后重试或增大 MODEL_TIMEOUT。") from exc
        except httpx.HTTPStatusError as exc:
            raise ModelError(f"模型服务返回 HTTP {exc.response.status_code}，请检查模型名称、密钥及额度。") from exc
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise ModelError("模型服务连接失败或响应格式不正确，请检查模型配置。") from exc


class LocalModel:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = None
        self.processor = None
        self.lock = threading.Lock()

    def complete(self, prompt: str, image_path: str | None = None) -> str:
        with self.lock:
            try:
                import torch
                from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
                from qwen_vl_utils import process_vision_info
            except ImportError as exc:
                raise ModelConfigError("本地模式请先安装 backend/requirements-local.txt。") from exc
            if not self.settings.configured:
                raise ModelConfigError("MODEL_PATH 目录不存在，请下载模型并配置路径。")
            try:
                if self.model is None:
                    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                        self.settings.model_path,
                        torch_dtype="auto",
                        device_map=self.settings.model_device,
                    )
                    if self.settings.adapter_path:
                        from peft import PeftModel
                        model = PeftModel.from_pretrained(model, self.settings.adapter_path)
                    processor = AutoProcessor.from_pretrained(self.settings.model_path)
                    self.model, self.processor = model.eval(), processor
                content = [{"type": "text", "text": prompt}]
                if image_path:
                    content.insert(0, {"type": "image", "image": image_path})
                messages = [{"role": "user", "content": content}]
                text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                images, _ = process_vision_info(messages)
                inputs = self.processor(text=[text], images=images, padding=True, return_tensors="pt").to(self.model.device)
                with torch.inference_mode():
                    ids = self.model.generate(**inputs, max_new_tokens=3000)
                trimmed = [out[len(src):] for src, out in zip(inputs.input_ids, ids)]
                return self.processor.batch_decode(trimmed, skip_special_tokens=True)[0]
            except Exception as exc:
                logger.exception("Local model inference failed")
                raise ModelError("本地模型加载或推理失败，请检查模型文件、适配器及显存。") from exc


def create_model(settings: Settings) -> Model:
    if settings.model_provider == "remote":
        return RemoteModel(settings)
    if settings.model_provider == "local":
        return LocalModel(settings)
    raise ModelConfigError("MODEL_PROVIDER 只支持 remote 或 local。")


T = TypeVar("T", bound=BaseModel)


def model_json(model: Model, prompt: str, schema: type[T], image_path: str | None = None) -> T:
    instruction = prompt + "\nReturn ONLY one JSON object matching this schema:\n" + json.dumps(schema.model_json_schema())
    for attempt in range(2):
        raw = model.complete(instruction, image_path).strip()
        if raw.startswith("```") and raw.endswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            return schema.model_validate_json(raw)
        except ValidationError:
            if attempt == 0:
                instruction += "\nYour last response was invalid. Follow the schema strictly; include every required field."
    raise ModelError("模型连续返回了格式不正确的结果，请重试。")
