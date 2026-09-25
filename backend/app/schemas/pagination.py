from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel, Field


ItemT = TypeVar("ItemT")


class PaginatedResponse(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    pages: int = Field(ge=0)

    @classmethod
    def build(cls, items: list[ItemT], page: int, page_size: int, total: int):
        return cls(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            pages=ceil(total / page_size) if total else 0,
        )
