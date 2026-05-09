from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from asset_crawler.db import open_db
from asset_crawler.export import export_csv, export_jsonl
from asset_crawler.listings_repo import upsert_listing
from asset_crawler.types import ListingRecord


def _seed(db_path: Path) -> None:
    conn = open_db(db_path)
    upsert_listing(
        conn,
        ListingRecord(
            source_site="pickles",
            source_listing_id="b",
            description="second by id",
            source_categories=["X"],
            source_url=None,
            raw_payload={"k": 2},
        ),
        datetime(2026, 5, 4, tzinfo=UTC),
    )
    upsert_listing(
        conn,
        ListingRecord(
            source_site="pickles",
            source_listing_id="a",
            description="first by id",
            source_categories=["Y"],
            source_url="https://x",
            raw_payload={"k": 1},
        ),
        datetime(2026, 5, 5, tzinfo=UTC),
    )
    conn.commit()
    conn.close()


def test_jsonl_deterministic_order_by_pk(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    out = tmp_path / "out.jsonl"
    _seed(db)
    export_jsonl(db_path=db, out=out, since=None, site=None, no_raw=False)

    lines = out.read_text().strip().splitlines()
    rows = [json.loads(line) for line in lines]
    assert [r["source_listing_id"] for r in rows] == ["a", "b"]
    assert "raw_payload" in rows[0]


def test_jsonl_no_raw_drops_payload(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    out = tmp_path / "out.jsonl"
    _seed(db)
    export_jsonl(db_path=db, out=out, since=None, site=None, no_raw=True)
    row = json.loads(out.read_text().splitlines()[0])
    assert "raw_payload" not in row


def test_jsonl_byte_identical_for_same_state(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    out1 = tmp_path / "out1.jsonl"
    out2 = tmp_path / "out2.jsonl"
    _seed(db)
    export_jsonl(db_path=db, out=out1, since=None, site=None, no_raw=False)
    export_jsonl(db_path=db, out=out2, since=None, site=None, no_raw=False)
    assert out1.read_bytes() == out2.read_bytes()


def test_jsonl_since_filter(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    out = tmp_path / "out.jsonl"
    _seed(db)
    export_jsonl(db_path=db, out=out, since="2026-05-05", site=None, no_raw=False)
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert [r["source_listing_id"] for r in rows] == ["a"]


def test_csv_drops_raw_payload_and_jsonifies_categories(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    out = tmp_path / "out.csv"
    _seed(db)
    export_csv(db_path=db, out=out, since=None, site=None)
    with out.open() as f:
        rows = list(csv.DictReader(f))
    assert "raw_payload" not in rows[0]
    assert json.loads(rows[0]["source_categories"]) == ["Y"]
