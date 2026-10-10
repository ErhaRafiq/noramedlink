"""Limit/offset pagination shared by list endpoints.

Every paginated endpoint takes `?limit=&offset=` and returns
    {"items": [...], "total": <rows matching the filters>, "limit": n, "offset": n}
so the frontend can render "Load more" or page controls without guessing.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy.orm import Query as SqlQuery

T = TypeVar("T")

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class PageParams:
    limit: int
    offset: int


def page_params(
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Items to skip"),
) -> PageParams:
    """FastAPI dependency: `params: PageParams = Depends(page_params)`."""
    return PageParams(limit=limit, offset=offset)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


def paginate(query: SqlQuery, params: PageParams, serialize: Callable[[Any], T]) -> dict[str, Any]:
    """Counts the filtered query, then returns one ordered page of serialized rows."""
    total = query.order_by(None).count()
    rows = query.limit(params.limit).offset(params.offset).all()
    return {"items": [serialize(row) for row in rows], "total": total, "limit": params.limit, "offset": params.offset}
