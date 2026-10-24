"""分页参数与分页响应。"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = Field(1, ge=1, description="页码，从 1 开始")
    size: int = Field(20, ge=1, le=100, description="每页条数")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def build(cls, items: list[T], total: int, params: PageParams) -> Page[T]:
        pages = (total + params.size - 1) // params.size if total else 0
        return cls(items=items, total=total, page=params.page, size=params.size, pages=pages)
