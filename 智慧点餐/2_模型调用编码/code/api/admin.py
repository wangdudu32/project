from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas import MenuInput, OrderStatus
from database import get_db
from models import MenuItem, Order
from security import admin_user
from serive.orders import NEXT_STATUS, change_status, menu_data, order_data

router = APIRouter(prefix="/admin", tags=["商家"], dependencies=[Depends(admin_user)])


@router.get("/menu")
def menu(db: Session = Depends(get_db)):
    return [menu_data(item) for item in db.scalars(select(MenuItem).order_by(MenuItem.id)).all()]


@router.post("/menu", status_code=201)
def add_menu(data: MenuInput, db: Session = Depends(get_db)):
    item = MenuItem(**data.model_dump())
    db.add(item)
    db.commit()
    return menu_data(item)


@router.put("/menu/{dish_id}")
def edit_menu(dish_id: int, data: MenuInput, db: Session = Depends(get_db)):
    item = db.scalar(select(MenuItem).where(MenuItem.id == dish_id).with_for_update())
    if item is None:
        raise HTTPException(404, "菜品不存在")
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    db.commit()
    return menu_data(item)


@router.get("/orders")
def orders(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    rows = db.scalars(select(Order).order_by(Order.id.desc()).offset(offset).limit(limit)).all()
    return [order_data(order) for order in rows]


@router.patch("/orders/{order_id}/status")
def update_status(order_id: int, data: OrderStatus, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "订单不存在")
    if NEXT_STATUS.get(order.status) != data.status:
        raise HTTPException(409, "请按已付款、制作中、配送中、已完成的顺序处理")
    result = change_status(db, order, order.status, data.status)
    db.commit()
    return result
