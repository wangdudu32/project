from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "aimenu_users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    cart_revision: Mapped[int] = mapped_column(Integer, default=0)


class LoginSession(Base):
    __tablename__ = "aimenu_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("aimenu_users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class MenuItem(Base):
    __tablename__ = "aimenu_menu_items"
    __table_args__ = (CheckConstraint("price > 0", name="positive_price"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    dish_name: Mapped[str] = mapped_column(String(100))
    price: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(50))
    spice_level: Mapped[int] = mapped_column(Integer, default=0)
    flavor: Mapped[str] = mapped_column(String(100), default="")
    main_ingredients: Mapped[str] = mapped_column(Text, default="")
    cooking_method: Mapped[str] = mapped_column(String(50), default="")
    is_vegetarian: Mapped[bool] = mapped_column(Boolean, default=False)
    allergens: Mapped[str] = mapped_column(String(200), default="")
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)


class CartItem(Base):
    __tablename__ = "aimenu_cart_items"
    __table_args__ = (
        UniqueConstraint("user_id", "dish_id"),
        CheckConstraint("quantity >= 1 AND quantity <= 99", name="cart_quantity"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("aimenu_users.id"), index=True)
    dish_id: Mapped[int] = mapped_column(ForeignKey("aimenu_menu_items.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    dish: Mapped[MenuItem] = relationship(lazy="joined")


class Order(Base):
    __tablename__ = "aimenu_orders"
    __table_args__ = (UniqueConstraint("user_id", "request_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("aimenu_users.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    contact_name: Mapped[str] = mapped_column(String(50))
    contact_phone: Mapped[str] = mapped_column(String(20))
    delivery_address: Mapped[str] = mapped_column(String(300))
    remark: Mapped[str] = mapped_column(String(300), default="")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total_quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    items: Mapped[list["OrderItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class OrderItem(Base):
    __tablename__ = "aimenu_order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("aimenu_orders.id", ondelete="CASCADE"), index=True)
    dish_id: Mapped[int] = mapped_column(ForeignKey("aimenu_menu_items.id"))
    dish_name: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
