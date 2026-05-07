from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from typer.testing import CliRunner

from asset_crawler.cli import app

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "pickles_search_page.json").read_text())


def test_full_flow_crawl_export_stats_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ASSET_CRAWLER_CONTACT", "https://example.com/me")
    db = tmp_path / "ac.db"
    out = tmp_path / "out.jsonl"
    runner = CliRunner()

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="")
        return httpx.Response(200, json={**FIXTURE, "@odata.nextLink": None})

    with patch(
        "asset_crawler.cli._build_transport",
        return_value=httpx.MockTransport(handler),
    ):
        r1 = runner.invoke(app, ["crawl", "pickles", "--db", str(db)])
        assert r1.exit_code == 0, r1.stdout

    r2 = runner.invoke(app, ["export", "--db", str(db), "--out", str(out)])
    assert r2.exit_code == 0, r2.stdout
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(rows) == 2

    r3 = runner.invoke(app, ["stats", "--db", str(db)])
    assert r3.exit_code == 0
    assert "pickles" in r3.stdout

    r4 = runner.invoke(app, ["runs", "--db", str(db)])
    assert r4.exit_code == 0
    assert "ok" in r4.stdout

    # And the underlying DB has the right shape
    conn = sqlite3.connect(db)
    n_listings = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    n_runs = conn.execute("SELECT COUNT(*) FROM crawl_runs").fetchone()[0]
    assert n_listings == 2
    assert n_runs == 1
