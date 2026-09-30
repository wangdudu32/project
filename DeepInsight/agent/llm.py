
from dotenv import load_dotenv,find_dotenv
import os

from langchain_classic.chat_models import init_chat_model

load_dotenv(find_dotenv())

llm = init_chat_model(
    model_provider="openai",
    model=os.getenv("LLM_QWEN_MAX")
)