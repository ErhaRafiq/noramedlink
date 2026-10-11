"""Limit/offset pagination (pagination.py), on an in-memory SQLite table."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Integer, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from pagination import MAX_PAGE_SIZE, Page, PageParams, page_params, paginate


class Base(DeclarativeBase):
    pass


class Row(Base):
    __tablename__ = "rows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(Row(id=i) for i in range(1, 26))
        db.commit()
        yield db


def ids(page: dict) -> list[int]:
    return page["items"]


def test_first_page(session):
    page = paginate(session.query(Row).order_by(Row.id), PageParams(limit=10, offset=0), lambda r: r.id)
    assert ids(page) == list(range(1, 11))
    assert (page["total"], page["limit"], page["offset"]) == (25, 10, 0)


def test_last_partial_page_and_past_the_end(session):
    query = session.query(Row).order_by(Row.id)
    assert ids(paginate(query, PageParams(limit=10, offset=20), lambda r: r.id)) == [21, 22, 23, 24, 25]
    past = paginate(query, PageParams(limit=10, offset=40), lambda r: r.id)
    assert past["items"] == [] and past["total"] == 25


def test_total_counts_the_filtered_rows(session):
    page = paginate(session.query(Row).filter(Row.id > 20).order_by(Row.id.desc()), PageParams(5, 0), lambda r: r.id)
    assert ids(page) == [25, 24, 23, 22, 21]
    assert page["total"] == 5


def test_page_model_validates_the_envelope():
    page = Page[int](items=[1, 2], total=2, limit=20, offset=0)
    assert page.model_dump() == {"items": [1, 2], "total": 2, "limit": 20, "offset": 0}


app = FastAPI()


@app.get("/items")
def items(params: PageParams = Depends(page_params)):
    return {"limit": params.limit, "offset": params.offset}


client = TestClient(app)


def test_query_defaults():
    assert client.get("/items").json() == {"limit": 20, "offset": 0}


@pytest.mark.parametrize("query", ["limit=1", f"limit={MAX_PAGE_SIZE}", "offset=500"])
def test_valid_query_values(query):
    assert client.get(f"/items?{query}").status_code == 200


@pytest.mark.parametrize("query", ["limit=0", f"limit={MAX_PAGE_SIZE + 1}", "offset=-1", "limit=abc"])
def test_invalid_query_values_are_422(query):
    assert client.get(f"/items?{query}").status_code == 422
