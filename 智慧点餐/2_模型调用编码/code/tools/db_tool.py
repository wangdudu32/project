"""菜单查询共用一份数据库配置，兼容 SQLite 和 MySQL。"""
from sqlalchemy import select

from database import SessionLocal
from models import MenuItem
from serive.orders import menu_data


def get_menu_item_list():
    with SessionLocal() as db:
        return [menu_data(item) for item in db.scalars(
            select(MenuItem).where(MenuItem.is_available.is_(True)).order_by(MenuItem.id)
        ).all()]


def get_menu_item_by_id(item_id):
    with SessionLocal() as db:
        item = db.get(MenuItem, int(item_id))
        return menu_data(item) if item and item.is_available else {}


def menu_text(item):
    return (f"菜品ID:{item['id']}|菜品名称:{item['dish_name']}|价格:¥{item['price']}|"
            f"菜品描述:{item['description']}|分类:{item['category']}|辣度:{item['spice_text']}|"
            f"口味:{item['flavor']}|主要食材:{item['main_ingredients']}|"
            f"素食:{'是' if item['is_vegetarian'] else '否'}|过敏原:{item['allergens'] or '未标注'}")


def get_all_menu_items():
    return "\n".join(menu_text(item) for item in get_menu_item_list())


def get_menu_items_by_category():
    result = {}
    for item in get_menu_item_list():
        result.setdefault(item['category'], []).append(item)
    return result
