"""餐厅咨询工具。文件名沿用原项目，这里没有运行独立 MCP 服务。"""
import os
import re
from decimal import Decimal

import config
from tools.db_tool import get_menu_item_list, menu_text
from tools.llm_tool import call_llm


def load_prompt(name):
    return (config.BASE_DIR / 'prompt' / f'{name}.txt').read_text(encoding='utf-8').strip()


def restaurant_info():
    return (f"餐厅：{os.getenv('RESTAURANT_NAME', '小满餐厅')}\n"
            f"营业时间：{os.getenv('RESTAURANT_HOURS', '每天 09:00-22:00')}\n"
            f"地址：{os.getenv('RESTAURANT_ADDRESS', '北京市海淀区中关村')}\n"
            f"联系方式：{os.getenv('RESTAURANT_PHONE', '请联系店内工作人员')}")


def general_inquiry(query, history=None, use_ai=True):
    info = restaurant_info()
    if use_ai and config.AI_ENABLED:
        response = call_llm(query, load_prompt('general_inquiry') + '\n' + info, history)
        return {'response': response, 'mode': 'ai'}
    return {'response': info + '\n可以告诉我想吃的菜系、口味或预算，我会从当前菜单中推荐。', 'mode': 'local'}


def local_candidates(query, items, preferences=''):
    """本地规则用于基础筛选，无法代替商家确认过敏原等特殊需求。"""
    candidates = list(items)
    constraints = query + ' ' + preferences
    if any(word in constraints for word in ['不辣', '清淡', '不要辣', '不吃辣']):
        candidates = [item for item in candidates if item['spice_level'] == 0]
    elif '微辣' in constraints:
        candidates = [item for item in candidates if item['spice_level'] <= 1]
    if any(word in constraints for word in ['素食', '素菜', '不吃肉']):
        candidates = [item for item in candidates if item['is_vegetarian']]
    budget = re.search(r'(\d+(?:\.\d{1,2})?)\s*元?\s*(?:以下|以内)', query)
    if budget is None:
        budget = re.search(r'(\d+(?:\.\d{1,2})?)\s*元?\s*(?:以下|以内)', preferences)
    if budget:
        candidates = [item for item in candidates if Decimal(item['price']) <= Decimal(budget.group(1))]
    categories = {item['category'] for item in items}
    known_cuisines = {'川菜', '鲁菜', '粤菜', '苏菜', '浙菜', '闽菜', '湘菜', '徽菜'}
    if any(cuisine in query and cuisine not in categories for cuisine in known_cuisines):
        return []
    requested = [category for category in categories if category in query]
    if requested:
        candidates = [item for item in candidates if item['category'] in requested]
    for allergen in ['花生', '大豆', '鱼', '牛奶', '鸡蛋', '虾', '海鲜', '麸质']:
        if any(word in constraints for word in [f'{allergen}过敏', f'不吃{allergen}', f'不要{allergen}', f'不含{allergen}']):
            candidates = [item for item in candidates if allergen not in item['allergens'] + item['main_ingredients']]
    def score(item):
        return (10 if item['dish_name'] in query else 0) + sum(
            word in query for word in [item['category'], item['flavor']] if word
        )
    return sorted(candidates, key=score, reverse=True)


def menu_inquiry(query, history=None, use_ai=True):
    items = get_menu_item_list()
    # 简单追问沿用上一轮需求；完整上下文同时传给模型。
    contextual_query = query
    if any(word in query for word in ['还有', '换一', '这些', '这道', '那道', '再推荐']):
        previous = next((item['content'] for item in reversed(history or []) if item['role'] == 'user'), '')
        contextual_query = previous + ' ' + query
    preferences = ' '.join(item['content'] for item in reversed(history or []) if item['role'] == 'user')
    candidates = local_candidates(contextual_query, items, preferences)
    notice = ''
    if config.PINECONE_ENABLED and use_ai:
        try:
            from tools.pine_cone_tool import search_menu_items_with_id
            ids = search_menu_items_with_id(contextual_query)['ids']
            ranks = {item_id: rank for rank, item_id in enumerate(ids)}
            candidates.sort(key=lambda item: ranks.get(str(item['id']), len(ranks)))
        except Exception:
            notice = '语义检索暂时不可用，已使用当前菜单进行推荐。'
    candidates = candidates[:2]
    if not candidates:
        return {'recommendation': '当前菜单中没有符合条件的菜品，可以换一种口味或联系商家。',
                'menu_ids': [], 'mode': 'local', 'notice': notice}
    context = '\n'.join(menu_text(item) for item in candidates)
    response = None
    if config.AI_ENABLED and use_ai:
        try:
            response = call_llm(query, load_prompt('menu_inquiry') + '\n当前可推荐菜品：\n' + context, history)
        except Exception:
            notice = 'AI 暂时不可用，已切换为本地菜单推荐。'
    result = response or '根据当前菜单，推荐：\n' + '\n'.join(
        f"{item['dish_name']} · ¥{item['price']}\n{item['description']}（{item['spice_text']}）" for item in candidates
    )
    if '过敏' in contextual_query + preferences:
        result += '\n如有食物过敏，请下单前联系商家确认食材及交叉接触情况。'
    return {'recommendation': result, 'menu_ids': [str(item['id']) for item in candidates],
            'mode': 'ai' if response else 'local', 'notice': notice}


def delivery_check_tool(address, travel_mode='2'):
    from tools.amap_tool import check_delivery_range
    result = check_delivery_range(address, travel_mode)
    response = result['message']
    if result['status'] == 'success':
        response += f"\n地址：{result['formatted_address']}\n距离：{result['distance']} 公里，预计 {round(result['duration'] / 60)} 分钟"
    return {'response': response, 'mode': 'map'}
