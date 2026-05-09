from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from asset_crawler.db import init_schema
from asset_crawler.runs_repo import (
    RunCounters,
    finish_run,
    list_recent_runs,
    mark_stale_running,
    start_run,
)


@pytest.fixture()
def conn(memdb: sqlite3.Connection) -> sqlite3.Connection:
    init_schema(memdb)
    return memdb


def test_start_run_creates_running_row(conn: sqlite3.Connection) -> None:
    started = datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC)
    run_id = start_run(conn, "pickles", {"line_of_business": ["industrial"]}, started)
    row = conn.execute("SELECT * FROM crawl_runs WHERE run_id = ?", (run_id,)).fetchone()
    assert row["status"] == "running"
    assert row["source_site"] == "pickles"
    assert json.loads(row["filter_spec"]) == {"line_of_business": ["industrial"]}
    assert row["started_at"] == "2026-05-04T12:00:00+00:00"
    assert row["finished_at"] is None


def test_start_run_with_no_filter_stores_null(conn: sqlite3.Connection) -> None:
    run_id = start_run(conn, "pickles", None, datetime(2026, 5, 4, tzinfo=UTC))
    row = conn.execute("SELECT filter_spec FROM crawl_runs WHERE run_id = ?", (run_id,)).fetchone()
    assert row["filter_spec"] is None


def test_finish_run_records_counters_and_status(conn: sqlite3.Connection) -> None:
    started = datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC)
    finished = datetime(2026, 5, 4, 12, 13, 0, tzinfo=UTC)
    run_id = start_run(conn, "pickles", None, started)
    finish_run(
        conn,
        run_id,
        finished_at=finished,
        status="ok",
        counters=RunCounters(pages_fetched=200, items_seen=10000, items_new=9_500, items_duplicate=500, items_skipped=0),
        error_message=None,
    )
    row = conn.execute("SELECT * FROM crawl_runs WHERE run_id = ?", (run_id,)).fetchone()
    assert row["status"] == "ok"
    assert row["finished_at"] == "2026-05-04T12:13:00+00:00"
    assert row["pages_fetched"] == 200
    assert row["items_new"] == 9_500
    assert row["error_message"] is None


def test_mark_stale_marks_old_running_as_aborted(conn: sqlite3.Connection) -> None:
    now = datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC)
    fresh_id = start_run(conn, "pickles", None, now - timedelta(minutes=5))
    stale_id = start_run(conn, "pickles", None, now - timedelta(hours=2))
    n = mark_stale_running(conn, now=now, max_age=timedelta(hours=1))
    assert n == 1
    fresh = conn.execute("SELECT status FROM crawl_runs WHERE run_id = ?", (fresh_id,)).fetchone()
    stale = conn.execute("SELECT status, error_message FROM crawl_runs WHERE run_id = ?", (stale_id,)).fetchone()
    assert fresh["status"] == "running"
    assert stale["status"] == "aborted"
    assert stale["error_message"] == "detected stale on startup"


def test_list_recent_runs_orders_by_started_desc(conn: sqlite3.Connection) -> None:
    base = datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC)
    a = start_run(conn, "pickles", None, base - timedelta(hours=2))
    b = start_run(conn, "pickles", None, base - timedelta(hours=1))
    c = start_run(conn, "pickles", None, base)
    rows = list_recent_runs(conn, site=None, limit=10)
    assert [r["run_id"] for r in rows] == [c, b, a]


def test_list_recent_runs_filters_by_site(conn: sqlite3.Connection) -> None:
    now = datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC)
    start_run(conn, "pickles", None, now)
    start_run(conn, "grays", None, now)
    rows = list_recent_runs(conn, site="pickles", limit=10)
    assert len(rows) == 1
    assert rows[0]["source_site"] == "pickles"
