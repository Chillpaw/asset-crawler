from __future__ import annotations

import sqlite3
from pathlib import Path

from asset_crawler.db import init_schema, open_db


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r["name"] for r in rows}


def test_init_schema_creates_both_tables(memdb: sqlite3.Connection) -> None:
    init_schema(memdb)
    assert _table_names(memdb) == {"listings", "crawl_runs"}


def test_init_schema_is_idempotent(memdb: sqlite3.Connection) -> None:
    init_schema(memdb)
    init_schema(memdb)
    assert _table_names(memdb) == {"listings", "crawl_runs"}


def test_listings_pk_enforced(memdb: sqlite3.Connection) -> None:
    init_schema(memdb)
    insert = (
        "INSERT INTO listings (source_site, source_listing_id, description, "
        "source_categories, raw_payload, first_seen_at, last_seen_at) "
        "VALUES (?,?,?,?,?,?,?)"
    )
    args = ("pickles", "x", "d", "[]", "{}", "2026-05-04T00:00:00Z", "2026-05-04T00:00:00Z")
    memdb.execute(insert, args)
    try:
        memdb.execute(insert, args)
    except sqlite3.IntegrityError:
        return
    raise AssertionError("expected IntegrityError on duplicate PK")


def test_open_db_creates_file(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    conn = open_db(db_path)
    try:
        assert db_path.exists()
        assert _table_names(conn) == {"listings", "crawl_runs"}
    finally:
        conn.close()
