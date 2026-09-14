from tools.amap_tool import check_delivery_range,PathModeInput
from  tools.db_tool import get_menu_item_list
from  LangChain.main import langchain_chat
from typing import  List,Dict

def   delivery_check(address:str,travel_mode:PathModeInput):
     """配送范围的查询"""

     return check_delivery_range(address, travel_mode)


def   menu_lists()->List[Dict]:
    """菜品列表查询"""
    return  get_menu_item_list()


def  smart_chat(user_query:str):
    """对话聊天的入口"""

    return  langchain_chat(user_query)





