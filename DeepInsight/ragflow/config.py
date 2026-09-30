import os
from dotenv import load_dotenv,find_dotenv
from typing import Tuple, Optional
from ragflow_sdk import RAGFlow

def _load_ragflow_env() -> Tuple[Optional[str], Optional[str]]:
    """
    加载 RAGFlow 环境变量（优先读取项目根目录 .env，兼容系统环境变量）
    返回值：(api_key, base_url) → 缺失则返回 None
    """
    # 优先加载项目根目录的 .env 文件
    load_dotenv(find_dotenv())

    api_key = os.getenv("RAGFLOW_API_KEY")
    base_url = os.getenv("RAGFLOW_API_URL")
    return api_key, base_url


# 创建一个知识库
def create_ragflow_ds():

    #1.登录和连接ragflow服务器
    api_key, base_url = _load_ragflow_env()
    rag = RAGFlow(api_key, base_url)
    #2.调用创建知识库的方法
    result = rag.create_dataset(name="代码创建的知识库",description="瞎整的没啥用！！哈哈哈！！")
    print(result)



def list_datasets():
    api_key, base_url = _load_ragflow_env()
    rag = RAGFlow(api_key, base_url)
    result = rag.list_datasets()
    print([ (ds.name,ds.description )for ds in result ])

if __name__ == "__main__":
    list_datasets()