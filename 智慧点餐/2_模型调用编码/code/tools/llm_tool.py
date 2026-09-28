import os

import config  # 先加载 .env


def call_llm(user_query: str, system_instruction: str, history=None):
    """明确区分系统消息、历史消息和当前问题。异常交给上层处理。"""
    if not config.AI_ENABLED or not os.getenv("DASHSCOPE_API_KEY"):
        raise RuntimeError("AI 服务未启用或未配置密钥")
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_openai import ChatOpenAI

    prompt = ChatPromptTemplate.from_messages([
        ("system", "{instruction}"), MessagesPlaceholder("history"), ("human", "{query}")
    ])
    llm = ChatOpenAI(api_key=os.environ["DASHSCOPE_API_KEY"],
                     base_url=os.getenv("DASHSCOPE_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
                     model=os.getenv("LLM_MODE", "qwen2.5-14b-instruct"), timeout=20, max_retries=0)
    messages = [("human" if item["role"] == "user" else "ai", item["content"]) for item in (history or [])[-10:]]
    result = (prompt | llm).invoke({"instruction": system_instruction, "query": user_query, "history": messages})
    if not isinstance(result.content, str) or not result.content.strip():
        raise RuntimeError("模型没有返回有效文字")
    return result.content.strip()[:4000]
