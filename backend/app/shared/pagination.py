"""List envelope per NAMING_CONVENTIONS.md: {items, page, page_size, total}."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

ItemT = TypeVar("ItemT")


class ListEnvelope(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    page: int
    page_size: int
    total: int


def paginate(items: list[ItemT], page: int, page_size: int) -> ListEnvelope[ItemT]:
    """One-based pagination over a materialized list.

    Repositories should prefer SQL LIMIT/OFFSET; this helper keeps the
    envelope shape in one place for small in-memory sets.
    """
    start = (page - 1) * page_size
    return ListEnvelope[ItemT](
        items=items[start : start + page_size],
        page=page,
        page_size=page_size,
        total=len(items),
    )
