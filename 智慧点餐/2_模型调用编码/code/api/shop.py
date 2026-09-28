from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from api.schemas import CartUpdate, OrderCreate
from database import get_db
from models import CartItem, MenuItem, Order, User
from security import current_user
from serive.orders import cart_data, change_status, create_order, lock_cart, menu_data, order_data, owned_order, update_cart

router = APIRouter(tags=["点餐"])


@router.get("/menu/list")
def menu_list(db: Session = Depends(get_db)):
    items = db.scalars(select(MenuItem).where(MenuItem.is_available.is_(True)).order_by(MenuItem.id)).all()
    return {"success": True, "menu_items": [menu_data(item) for item in items], "count": len(items)}


@router.get("/cart")
def get_cart(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return cart_data(db, user.id)


@router.put("/cart/{dish_id}")
def put_cart(dish_id: int, data: CartUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    result = update_cart(db, user.id, dish_id, data.quantity)
    db.commit()
    return result


@router.delete("/cart")
def clear_cart(user: User = Depends(current_user), db: Session = Depends(get_db)):
    lock_cart(db, user.id)
    db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    db.commit()
    return cart_data(db, user.id)


@router.post("/orders", status_code=201)
def checkout(data: OrderCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    result = create_order(db, user.id, data)
    db.commit()
    return result


@router.get("/orders")
def orders(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Order).where(Order.user_id == user.id).order_by(Order.id.desc()).offset(offset).limit(limit)).all()
    return [order_data(order) for order in rows]


@router.get("/orders/{order_id}")
def order_detail(order_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return order_data(owned_order(db, order_id, user.id))


@router.post("/orders/{order_id}/pay")
def pay(order_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    order = owned_order(db, order_id, user.id)
    if order.status in ("paid", "preparing", "delivering", "completed"):
        return order_data(order)
    if order.status != "pending":
        raise HTTPException(409, "只有待付款订单可以模拟支付")
    result = change_status(db, order, "pending", "paid")
    db.commit()
    return result


@router.post("/orders/{order_id}/cancel")
def cancel(order_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    order = owned_order(db, order_id, user.id)
    if order.status == "cancelled":
        return order_data(order)
    if order.status != "pending":
        raise HTTPException(409, "仅待付款订单可取消，已付款请联系商家")
    result = change_status(db, order, "pending", "cancelled")
    db.commit()
    return result
