from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from asset_crawler.db import open_db
from asset_crawler.harness import CrawlerHarness, RunResult
from asset_crawler.types import ListingRecord


class FakeAdapter:
    site_name = "fake"

    def __init__(self, records: list[ListingRecord], raise_on: int | None = None) -> None:
        self._records = records
        self._raise_on = raise_on

    def iter_listings(self) -> Iterator[ListingRecord]:
        for i, rec in enumerate(self._records):
            if self._raise_on is not None and i == self._raise_on:
                raise RuntimeError("boom")
            yield rec


def _rec(n: int, description: str = "desc") -> ListingRecord:
    return ListingRecord(
        source_site="fake",
        source_listing_id=f"id-{n}",
        description=description,
        source_categories=["a", "b"],
        source_url=None,
        raw_payload={"n": n},
    )


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


def test_run_inserts_new_records_and_records_run(db_path: Path) -> None:
    adapter = FakeAdapter([_rec(1), _rec(2), _rec(3)])
    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    harness = CrawlerHarness(db_path=db_path, now=lambda: now)
    result = harness.run(adapter, filter_spec=None)

    assert result.status == "ok"
    assert result.counters.items_seen == 3
    assert result.counters.items_new == 3
    assert result.counters.items_duplicate == 0

    conn = open_db(db_path)
    try:
        n = conn.execute("SELECT COUNT(*) AS c FROM listings").fetchone()["c"]
        assert n == 3
        run = conn.execute("SELECT * FROM crawl_runs").fetchone()
        assert run["status"] == "ok"
        assert run["items_new"] == 3
    finally:
        conn.close()


def test_run_dedupes_and_counts_duplicates(db_path: Path) -> None:
    adapter1 = FakeAdapter([_rec(1), _rec(2)])
    adapter2 = FakeAdapter([_rec(2), _rec(3)])
    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    harness = CrawlerHarness(db_path=db_path, now=lambda: now)
    harness.run(adapter1, filter_spec=None)
    result = harness.run(adapter2, filter_spec=None)

    assert result.counters.items_seen == 2
    assert result.counters.items_new == 1
    assert result.counters.items_duplicate == 1


def test_blank_description_skipped_at_validation(db_path: Path) -> None:
    adapter = FakeAdapter([_rec(1)])
    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    harness = CrawlerHarness(db_path=db_path, now=lambda: now)
    result = harness.run(adapter, filter_spec=None)
    assert result.counters.items_skipped == 0  # nothing skipped by harness here
    # Empty categories accepted:
    rec = ListingRecord(
        source_site="fake", source_listing_id="empty",
        description="real", source_categories=[],
        source_url=None, raw_payload={},
    )
    adapter2 = FakeAdapter([rec])
    result2 = harness.run(adapter2, filter_spec=None)
    assert result2.counters.items_new == 1


def test_adapter_exception_marks_failed(db_path: Path) -> None:
    adapter = FakeAdapter([_rec(1), _rec(2)], raise_on=1)
    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    harness = CrawlerHarness(db_path=db_path, now=lambda: now)
    result = harness.run(adapter, filter_spec=None)
    assert result.status == "failed"
    assert "boom" in (result.error_message or "")

    conn = open_db(db_path)
    try:
        run = conn.execute("SELECT * FROM crawl_runs").fetchone()
        assert run["status"] == "failed"
        # First record should still have been persisted before the exception.
        assert conn.execute("SELECT COUNT(*) AS c FROM listings").fetchone()["c"] == 1
    finally:
        conn.close()


def test_filter_spec_persisted(db_path: Path) -> None:
    adapter = FakeAdapter([_rec(1)])
    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    harness = CrawlerHarness(db_path=db_path, now=lambda: now)
    harness.run(adapter, filter_spec={"line_of_business": ["industrial"]})
    conn = open_db(db_path)
    try:
        import json
        spec = conn.execute("SELECT filter_spec FROM crawl_runs").fetchone()["filter_spec"]
        assert json.loads(spec) == {"line_of_business": ["industrial"]}
    finally:
        conn.close()


def test_run_returns_result_object(db_path: Path) -> None:
    adapter = FakeAdapter([_rec(1)])
    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    harness = CrawlerHarness(db_path=db_path, now=lambda: now)
    result = harness.run(adapter, filter_spec=None)
    assert isinstance(result, RunResult)
    assert result.run_id  # uuid present


def test_stale_running_runs_marked_aborted_on_run(db_path: Path) -> None:

    from asset_crawler.runs_repo import start_run

    conn = open_db(db_path)
    stale_started = datetime(2026, 5, 4, 10, 0, tzinfo=UTC)
    stale_id = start_run(conn, "fake", None, stale_started)
    conn.commit()
    conn.close()

    # Now run the harness with "now" 2 hours later
    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    adapter = FakeAdapter([_rec(1)])
    harness = CrawlerHarness(db_path=db_path, now=lambda: now)
    harness.run(adapter, filter_spec=None)

    conn = open_db(db_path)
    try:
        stale = conn.execute(
            "SELECT status, error_message FROM crawl_runs WHERE run_id = ?", (stale_id,)
        ).fetchone()
        assert stale["status"] == "aborted"
        assert stale["error_message"] == "detected stale on startup"
    finally:
        conn.close()
