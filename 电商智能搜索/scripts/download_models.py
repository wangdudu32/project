"""Download the configured models once; request handlers use local files only."""

import sys
from pathlib import Path


sys.path.insert(0, str(Path.cwd() / "backend"))
import settings

import torch
from sentence_transformers import CrossEncoder, SentenceTransformer

torch.set_num_threads(4)
print(f"Downloading embedding model: {settings.embedding_model}", flush=True)
SentenceTransformer(
    settings.embedding_model,
    device=settings.model_device,
    cache_folder=str(settings.runtime / "models"),
)
print(f"Downloading reranking model: {settings.rerank_model}", flush=True)
CrossEncoder(settings.rerank_model, device=settings.model_device, max_length=256)
print("Both models are available locally.", flush=True)
