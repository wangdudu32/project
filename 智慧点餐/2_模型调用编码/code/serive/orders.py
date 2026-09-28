"""购物车与订单：金额由后端计算，订单保存下单时的菜品快照。"""
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from models import CartItem, MenuItem, Order, OrderItem, User, now

STATUS_TEXT = {"pending": "待付款", "paid": "已付款", "preparing": "制作中",
               "delivering": "配送中", "completed": "已完成", "cancelled": "已取消"}
NEXT_STATUS = {"paid": "preparing", "preparing": "delivering", "delivering": "completed"}


def menu_data(item: MenuItem):
    data = {column.name: getattr(item, column.name) for column in MenuItem.__table__.columns}
    data["price"] = str(item.price)
    data["formatted_price"] = f"¥{item.price:.2f}"
    data["spice_text"] = ["不辣", "微辣", "中辣", "重辣"][item.spice_level]
    return data


def lock_cart(db: Session, user_id: int):
    # 对同一用户的购物车写操作串行处理，兼容 MySQL 和 SQLite。
    db.execute(update(User).where(User.id == user_id).values(cart_revision=User.cart_revision + 1))


def cart_data(db: Session, user_id: int):
    rows = db.scalars(select(CartItem).where(CartItem.user_id == user_id).order_by(CartItem.id)).all()
    items = [{"dish": menu_data(row.dish), "quantity": row.quantity,
              "subtotal": str(row.dish.price * row.quantity)} for row in rows]
    total = sum((row.dish.price * row.quantity for row in rows), Decimal("0.00"))
    return {"items": items, "total_amount": str(total), "total_quantity": sum(row.quantity for row in rows)}


def update_cart(db: Session, user_id: int, dish_id: int, quantity: int):
    lock_cart(db, user_id)
    row = db.scalar(select(CartItem).where(CartItem.user_id == user_id, CartItem.dish_id == dish_id).with_for_update())
    if quantity == 0:
        if row:
            db.delete(row)
    else:
        dish = db.get(MenuItem, dish_id)
        if dish is None or not dish.is_available:
            raise HTTPException(409, "菜品不存在或已经下架")
        if row:
            row.quantity = quantity
        else:
            count = len(db.scalars(select(CartItem.id).where(CartItem.user_id == user_id).with_for_update()).all())
            if count >= 50:
                raise HTTPException(400, "购物车最多添加 50 种菜品")
            db.add(CartItem(user_id=user_id, dish_id=dish_id, quantity=quantity))
    db.flush()
    return cart_data(db, user_id)


def order_data(order: Order):
    return {"id": order.id, "order_no": order.order_no, "user_id": order.user_id,
            "contact_name": order.contact_name, "contact_phone": order.contact_phone,
            "delivery_address": order.delivery_address, "remark": order.remark,
            "total_amount": str(order.total_amount), "total_quantity": order.total_quantity,
            "status": order.status, "status_text": STATUS_TEXT[order.status],
            "created_at": order.created_at.isoformat() + "Z",
            "items": [{"dish_id": item.dish_id, "dish_name": item.dish_name,
                       "quantity": item.quantity, "unit_price": str(item.unit_price),
                       "subtotal": str(item.subtotal)} for item in order.items]}


def owned_order(db: Session, order_id: int, user_id: int):
    order = db.scalar(select(Order).where(Order.id == order_id, Order.user_id == user_id))
    if order is None:
        raise HTTPException(404, "订单不存在")
    return order


def create_order(db: Session, user_id: int, data):
    lock_cart(db, user_id)
    request_id = str(data.request_id)
    existing = db.scalar(select(Order).where(Order.user_id == user_id, Order.request_id == request_id).with_for_update())
    if existing:
        return order_data(existing)
    rows = db.scalars(select(CartItem).where(CartItem.user_id == user_id).order_by(CartItem.dish_id).with_for_update()).all()
    if not rows:
        raise HTTPException(400, "购物车为空，请先添加菜品")
    dishes = {dish.id: dish for dish in db.scalars(
        select(MenuItem).where(MenuItem.id.in_([row.dish_id for row in rows]))
        .order_by(MenuItem.id).with_for_update().execution_options(populate_existing=True)
    ).all()}
    total = Decimal("0.00")
    snapshots = []
    for row in rows:
        dish = dishes.get(row.dish_id)
        if dish is None or not dish.is_available:
            raise HTTPException(409, "购物车中有已下架的菜品，请移除后重新下单")
        subtotal = dish.price * row.quantity
        total += subtotal
        snapshots.append(OrderItem(dish_id=dish.id, dish_name=dish.dish_name,
                                   quantity=row.quantity, unit_price=dish.price, subtotal=subtotal))
    order = Order(order_no=uuid4().hex, user_id=user_id, request_id=request_id,
                  **data.model_dump(exclude={"request_id"}), total_amount=total,
                  total_quantity=sum(row.quantity for row in rows), items=snapshots)
    db.add(order)
    db.execute(delete(CartItem).where(CartItem.user_id == user_id))
    db.flush()
    return order_data(order)


def change_status(db: Session, order: Order, expected: str, target: str):
    # 条件更新避免并发付款、取消或商家重复操作覆盖订单状态。
    result = db.execute(update(Order).where(Order.id == order.id, Order.status == expected)
                        .values(status=target, updated_at=now()).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        raise HTTPException(409, "订单状态已变化，请刷新后重试")
    db.refresh(order)
    return order_data(order)
