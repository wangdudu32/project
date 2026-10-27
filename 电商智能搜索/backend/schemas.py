"""Small request models keep validation visible near the API boundary."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str | None = Field(default=None, max_length=40)
    brand: str | None = Field(default=None, max_length=60)
    color: str | None = Field(default=None, max_length=20)
    min_price: float | None = Field(default=None, ge=0, le=100000)
    max_price: float | None = Field(default=None, ge=0, le=100000)
    in_stock: bool = True
    exclude_tags: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def check_price_range(self):
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("最低价格不能高于最高价格")
        if any(not tag.strip() or len(tag) > 30 for tag in self.exclude_tags):
            raise ValueError("排除条件需要是 1–30 字的有效词语")
        return self


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(default="", max_length=200)
    filters: ProductFilters = Field(default_factory=ProductFilters)
    sort: Literal["relevance", "price_asc", "price_desc", "newest"] = "relevance"
    page: int = Field(default=1, ge=1, le=1000)
    page_size: int = Field(default=12, ge=1, le=48)
    mode: Literal["keyword", "hybrid", "rerank", "diverse"] = "hybrid"


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, max_length=36)


class CompareRequest(BaseModel):
    product_ids: list[str] = Field(min_length=2, max_length=3)


class EventRequest(BaseModel):
    kind: Literal["view", "click", "favorite", "compare"]
    product_id: str = Field(min_length=1, max_length=40)
