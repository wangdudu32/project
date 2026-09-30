# 导入系统核心模块
import os
import logging
# 导入自定义监控模块（用于上报工具调用日志）
from api.monitor import monitor
# 导入HTTP请求库（用于健康检查）
import requests
# 导入RAGFlow SDK核心类（用于操作RAGFlow助手/知识库）
from ragflow_sdk import RAGFlow
# 导入环境变量加载工具（用于读取.env文件中的配置）
from dotenv import load_dotenv
# 导入LangChain工具装饰器（用于将函数注册为Agent可调用的工具）
from langchain_core.tools import tool
from typing_extensions import Annotated

# 初始化日志器（用于记录工具运行日志）
logger = logging.getLogger(__name__)

# 导入类型注解（用于函数返回值/参数类型约束）
from typing import Tuple, Optional


def _load_ragflow_env() -> Tuple[Optional[str], Optional[str]]:
    """
    加载RAGFlow的环境变量（API密钥和服务地址）
    优先加载当前脚本目录下的.env文件，若不存在则加载系统环境变量

    Returns:
        Tuple[Optional[str], Optional[str]]:
            - 第一个值：RAGFlow API密钥（RAGFLOW_API_KEY）
            - 第二个值：RAGFlow服务地址（RAGFLOW_API_URL）
            - 若未配置则返回None
    """
    load_dotenv()

    # 从环境变量中读取配置
    api_key = os.getenv("RAGFLOW_API_KEY")
    base_url = os.getenv("RAGFLOW_API_URL")
    return api_key, base_url


# 第一个工具 查询所有的聊天助手（名称 描述 以及对应的知识库） -》 给大模型作为参考，用于下次具体的提问！
@tool
def ragflow_chat_list()->str:
    """
    查询ragflow中的所有聊天助手信息，返回 名称 描述 以及关联的知识库
    作用： 用于判断哪个助手可以给与详细的内部信息支持！用于后续的查询
    :return: 查询到的助手信息 有： 聊天助手名称: xx 描述：xx 关联的知识库：xxx,xxx,xxx \n 聊天助手名称: xx 描述：xx 关联的知识库：xxx,xxx,xxx
    """

    api_key, base_url = _load_ragflow_env()
    monitor.report_tool("ragflow_chat_list",{"ragflow_chat_list":"查询ragflow所有的聊天助手信息！用于后续的具体提问准备！"})
    try:
        # 1. 链接客户端信息
        ragflow = RAGFlow(api_key, base_url)
        # 2. 直接查询所有的助手集合
        chats_list = ragflow.list_chats()
        result = '' # 最终数据拼接
        # 3. 单独处理每一个助手信息（name,description,datasets）
        for chat in chats_list:
            # 一个chat  一个name 一个 description n个知识库
            chat_datasets = chat.datasets
            datasets_name = [ dataset['name'] for dataset in chat_datasets ]
            # 4. 拼接字符串返回即可
            result += f"聊天助手名称：{chat.name},描述：{chat.description} ，关联的知识库:{'、'.join(datasets_name)}\n"
        return result
    except Exception as e:
        return f"链接ragflow服务器失败，没有查询到任何助手信息，错误原因：{str(e)}"


@tool
def create_ask_delete(
        chat_name:str,
        question:str
) -> str:
    """
    向指定的助手进行会话和提问，获取查询的结果并返回！
    注意：chat_name 助手名称需要调用ragflow_chat_list工具查询和确认，确保名称和功能对应！！
    :param chat_name: 助手名称
    :param question:  提问的问题
    :return: 查询返回的结果
    """

    # 获取url和api_key
    api_key, base_url = _load_ragflow_env()
    monitor.report_tool("create_ask_delete",
                        {"create_ask_delete": "向具体的ragflow的聊天助手进行提问！","chat_name":chat_name,"question":question})
    try:
        # 创建ragflow客户端
        ragflow = RAGFlow(api_key, base_url)
        # 查询指定名称的助手对象
        chat_list =  ragflow.list_chats(name=chat_name)
        if not chat_list:
            return f"没有合适的助手可以查询数据，本次没有有效数据返回！"
        chat = chat_list[0]
        # 有，助手，创建session会话（会话有个name）
        session = chat.create_session(name="temp_session")
        # 向会话流式提问 ，并收集最终结果（content属性）
        stream = session.ask(question = question,stream=True)
        final_result = ''
        for part in stream:
            # print(part.content)
            final_result = part.content
        # 关闭会话
        chat.delete_sessions(ids=[session.id])
        # 返回结果即可！！
        return final_result
    except Exception as e:
        return f"链接或者提问报错，没有查询有效信息！ 错误原因为：{str(e)}"
