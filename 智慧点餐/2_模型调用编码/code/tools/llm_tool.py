import os

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()


def call_llm(user_query: str, system_instruction: str):
    """调用LLM"""

    try:
        # 1. 定义环境变量
        api_key = os.getenv("DASHSCOPE_API_KEY")
        base_url = os.getenv("DASHSCOPE_API_BASE")
        model_name = os.getenv("LLM_MODE")

        # 2. 定义提示词模版对象
        chat_prompt_template = ChatPromptTemplate.from_messages([
            ("system", "{system_instruction}"),
            ("human", "{user_query}")
        ])

        # 3. 定义LLM实例
        llm = ChatOpenAI(api_key=api_key, base_url=base_url, model=model_name)

        # 4. 定义链Chain
        chain = (
                {
                    "system_instruction": RunnablePassthrough(),
                    "user_query": RunnablePassthrough()
                }
                | chat_prompt_template
                | llm
        )

        # 5.调用Chain
        llm_response = chain.invoke({"system_instruction": system_instruction, "user_query": user_query})

        # 6.返回结果

        return llm_response.content  # 模型的输出内容在AIMessage对象的content中

    except Exception as e:
        return  f"LLM模型调用失败,原因{e}"
