from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

import pytest

from asset_crawler.db import init_schema
from asset_crawler.listings_repo import upsert_listing
from asset_crawler.types import ListingRecord


@pytest.fixture()
def conn(memdb: sqlite3.Connection) -> sqlite3.Connection:
    init_schema(memdb)
    return memdb


def _record(**overrides) -> ListingRecord:
    base = {
        "source_site": "pickles",
        "source_listing_id": "uuid-1",
        "description": "first description",
        "source_categories": ["Salvage stock", "Trucks", "Truck"],
        "source_url": "https://x/y",
        "raw_payload": {"a": 1},
    }
    return ListingRecord(**(base | overrides))


def test_upsert_inserts_new(conn: sqlite3.Connection) -> None:
    now = datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC)
    is_new = upsert_listing(conn, _record(), now)
    assert is_new is True
    row = conn.execute("SELECT * FROM listings").fetchone()
    assert row["description"] == "first description"
    assert row["first_seen_at"] == "2026-05-04T12:00:00+00:00"
    assert row["last_seen_at"] == "2026-05-04T12:00:00+00:00"
    assert json.loads(row["source_categories"]) == ["Salvage stock", "Trucks", "Truck"]
    assert json.loads(row["raw_payload"]) == {"a": 1}


def test_upsert_existing_bumps_last_seen_only(conn: sqlite3.Connection) -> None:
    t0 = datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 5, 5, 12, 0, 0, tzinfo=UTC)
    upsert_listing(conn, _record(description="canonical"), t0)
    is_new = upsert_listing(conn, _record(description="EDITED LATER"), t1)
    assert is_new is False
    row = conn.execute("SELECT * FROM listings").fetchone()
    assert row["description"] == "canonical"
    assert row["first_seen_at"] == "2026-05-04T12:00:00+00:00"
    assert row["last_seen_at"] == "2026-05-05T12:00:00+00:00"


def test_upsert_different_pk_creates_two_rows(conn: sqlite3.Connection) -> None:
    now = datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC)
    upsert_listing(conn, _record(source_listing_id="a"), now)
    upsert_listing(conn, _record(source_listing_id="b"), now)
    count = conn.execute("SELECT COUNT(*) AS c FROM listings").fetchone()["c"]
    assert count == 2
