from decimal import Decimal

from sqlalchemy import select

from models import MenuItem

SAMPLE_MENU = [
    dict(dish_name="宫保鸡丁", price=Decimal("28.00"), category="川菜", spice_level=1,
         description="鸡肉鲜嫩，花生香脆，酸甜微辣。", main_ingredients="鸡肉、花生、青椒", allergens="花生", flavor="酸甜微辣"),
    dict(dish_name="麻婆豆腐", price=Decimal("18.00"), category="川菜", spice_level=3,
         description="嫩豆腐配牛肉末，麻辣鲜香。", main_ingredients="豆腐、牛肉、豆瓣酱", allergens="大豆", flavor="麻辣"),
    dict(dish_name="清炒时蔬", price=Decimal("15.00"), category="素食", spice_level=0, is_vegetarian=True,
         description="时令蔬菜清炒，清淡爽口。", main_ingredients="时令蔬菜、蒜", flavor="清淡"),
    dict(dish_name="红烧鲈鱼", price=Decimal("45.00"), category="鲁菜", spice_level=0,
         description="鲈鱼慢烧入味，肉质细嫩。", main_ingredients="鲈鱼、葱姜、生抽", allergens="鱼类、大豆", flavor="咸鲜"),
    dict(dish_name="蒜蓉西兰花", price=Decimal("12.00"), category="素食", spice_level=0, is_vegetarian=True,
         description="西兰花搭配蒜蓉，清爽下饭。", main_ingredients="西兰花、大蒜", flavor="蒜香清淡"),
]


def seed_menu(db):
    if db.scalar(select(MenuItem.id).limit(1)) is not None:
        return False
    db.add_all([MenuItem(**item) for item in SAMPLE_MENU])
    db.commit()
    return True
