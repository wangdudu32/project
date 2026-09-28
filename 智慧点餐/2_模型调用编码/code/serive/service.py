"""保留原项目的业务入口，供脚本调用。"""
from LangChain.main import langchain_chat
from tools.amap_tool import check_delivery_range
from tools.db_tool import get_menu_item_list


def delivery_check(address, travel_mode='2'):
    return check_delivery_range(address, travel_mode)


def menu_lists():
    return get_menu_item_list()


def smart_chat(user_query, history=None):
    return langchain_chat(user_query, history)
