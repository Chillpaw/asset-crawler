from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from asset_crawler.cli import app
from asset_crawler.db import open_db
from asset_crawler.runs_repo import RunCounters, finish_run, start_run


def _make_db(tmp_path: Path) -> Path:
    db = tmp_path / "t.db"
    conn = open_db(db)
    a = start_run(conn, "pickles", None, datetime(2026, 5, 4, 10, tzinfo=UTC))
    finish_run(
        conn, a,
        finished_at=datetime(2026, 5, 4, 10, 13, tzinfo=UTC),
        status="ok",
        counters=RunCounters(pages_fetched=1, items_seen=10, items_new=10, items_duplicate=0),
        error_message=None,
    )
    start_run(conn, "grays", None, datetime(2026, 5, 4, 11, tzinfo=UTC))
    conn.commit()
    conn.close()
    return db


def test_runs_lists_recent(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["runs", "--db", str(db)])
    assert result.exit_code == 0, result.stdout
    assert "pickles" in result.stdout
    assert "grays" in result.stdout


def test_runs_filters_site(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["runs", "--db", str(db), "--site", "pickles"])
    assert result.exit_code == 0
    assert "pickles" in result.stdout
    assert "grays" not in result.stdout
