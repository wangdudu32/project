from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Credentials(InputModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)


class CartUpdate(InputModel):
    quantity: int = Field(ge=0, le=99, strict=True)


class OrderCreate(InputModel):
    request_id: UUID
    contact_name: str = Field(min_length=1, max_length=50)
    contact_phone: str = Field(pattern=r"^1[3-9]\d{9}$")
    delivery_address: str = Field(min_length=5, max_length=300)
    remark: str = Field(default="", max_length=300)


class OrderStatus(InputModel):
    status: Literal["preparing", "delivering", "completed"]


class MenuInput(InputModel):
    dish_name: str = Field(min_length=1, max_length=100)
    price: Decimal = Field(gt=0, le=99999, max_digits=7, decimal_places=2)
    category: str = Field(min_length=1, max_length=50)
    description: str = Field(default="", max_length=2000)
    spice_level: int = Field(default=0, ge=0, le=3)
    flavor: str = Field(default="", max_length=100)
    main_ingredients: str = Field(default="", max_length=1000)
    cooking_method: str = Field(default="", max_length=50)
    is_vegetarian: bool = False
    allergens: str = Field(default="", max_length=200)
    is_available: bool = True


class ChatMessage(InputModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(InputModel):
    query: str = Field(min_length=1, max_length=1000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=10)


class DeliveryRequest(InputModel):
    address: str = Field(min_length=2, max_length=300)
    travel_mode: Literal["1", "2", "3"] = "2"
