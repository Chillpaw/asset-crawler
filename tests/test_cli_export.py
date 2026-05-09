from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from asset_crawler.cli import app
from asset_crawler.db import open_db
from asset_crawler.listings_repo import upsert_listing
from asset_crawler.types import ListingRecord


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def _seed(db: Path) -> None:
    conn = open_db(db)
    upsert_listing(
        conn,
        ListingRecord(
            source_site="pickles", source_listing_id="a",
            description="hello", source_categories=["Y"],
            source_url=None, raw_payload={"k": 1},
        ),
        datetime(2026, 5, 5, tzinfo=UTC),
    )
    conn.commit()
    conn.close()


def test_export_jsonl_writes_file(runner: CliRunner, tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    out = tmp_path / "out.jsonl"
    _seed(db)
    result = runner.invoke(
        app, ["export", "--format", "jsonl", "--db", str(db), "--out", str(out)]
    )
    assert result.exit_code == 0, result.stdout
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert rows[0]["source_listing_id"] == "a"


def test_export_csv_writes_file(runner: CliRunner, tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    out = tmp_path / "out.csv"
    _seed(db)
    result = runner.invoke(
        app, ["export", "--format", "csv", "--db", str(db), "--out", str(out)]
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    assert "hello" in out.read_text()


def test_export_missing_db_prints_clean_error(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["export", "--db", str(tmp_path / "nonexistent.db"), "--out", str(tmp_path / "out.jsonl")]
    )
    assert result.exit_code == 1
    # Should print an error message, not a traceback
    assert "database" in result.output.lower() or "database" in (result.stderr or "").lower()
