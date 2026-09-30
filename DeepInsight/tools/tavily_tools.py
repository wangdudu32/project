from typing import Literal
from dotenv import load_dotenv,find_dotenv
import os
from langchain_core.tools import tool
from tavily import TavilyClient
from api.monitor import monitor

load_dotenv(find_dotenv())

# 创建tavily客户端
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# 定义搜索工具
@tool
def internet_search(
        query:str,
        max_results:int=5,
        include_raw_content:bool=False,
        topic:Literal["general", "news", "finance" ] = "general"
):
    """
    进行联网查询工具！
    核心用途：
         当 AI Agent 需要获取外部互联网的公开信息、时效性数据（如新闻、金融动态）时调用，
         替代传统搜索引擎，返回更适配大模型的结构化结果。
    :param query: 查询的关键字
    :param max_results:查询返回的最大条数 默认5条
    :param topic: 查询的类别
    :param include_raw_content: 是否返回详细内容 False不返回  True返回
    :return: 查询的结果
    """
    monitor.report_tool("internet_search",{"query":query,"max_results":max_results,
                                           "include_raw_content":include_raw_content,"topic":topic})
    # 调用工具进行信息推送，前端进行工具调用显示
    print(f"网络搜索助手-网络搜索工具,本次查询关键字:{query},查询条数:{max_results},查询的类型:{topic}！")
    return tavily_client.search(
        query=query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic
    )