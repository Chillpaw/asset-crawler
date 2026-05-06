from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from asset_crawler.cli import app
from asset_crawler.db import open_db
from asset_crawler.listings_repo import upsert_listing
from asset_crawler.stats import (
    counts_by_lob,
    counts_by_product_type,
    counts_by_site,
    recent_ingest_by_day,
)
from asset_crawler.types import ListingRecord


def _seed(db: Path) -> None:
    conn = open_db(db)
    for i, (site, lob, pt) in enumerate([
        ("pickles", "Salvage stock", "Trucks"),
        ("pickles", "Salvage stock", "Cars"),
        ("pickles", "Industrial", "Forklifts"),
    ]):
        upsert_listing(
            conn,
            ListingRecord(
                source_site=site, source_listing_id=f"x{i}",
                description="d", source_categories=[lob, pt, "X"],
                source_url=None, raw_payload={},
            ),
            datetime(2026, 5, 4, tzinfo=UTC),
        )
    conn.commit()
    conn.close()


def test_counts_by_site(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    _seed(db)
    conn = open_db(db)
    rows = list(counts_by_site(conn))
    assert rows == [("pickles", 3)]


def test_counts_by_lob(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    _seed(db)
    conn = open_db(db)
    rows = list(counts_by_lob(conn))
    assert ("Salvage stock", 2) in rows
    assert ("Industrial", 1) in rows


def test_counts_by_product_type(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    _seed(db)
    conn = open_db(db)
    rows = list(counts_by_product_type(conn))
    assert ("Trucks", 1) in rows


def test_recent_ingest(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    _seed(db)
    conn = open_db(db)
    rows = list(recent_ingest_by_day(conn, days=7))
    assert rows[0][0] == "2026-05-04"
    assert rows[0][1] == 3


def test_stats_cli(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    _seed(db)
    runner = CliRunner()
    result = runner.invoke(app, ["stats", "--db", str(db)])
    assert result.exit_code == 0, result.stdout
    assert "pickles" in result.stdout
    assert "Salvage stock" in result.stdout
