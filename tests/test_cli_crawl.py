from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from typer.testing import CliRunner

from asset_crawler.cli import app

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "pickles_search_page.json").read_text())


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_crawl_pickles_aborts_when_robots_disallowed_without_flag(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ASSET_CRAWLER_CONTACT", "https://example.com/me")
    db = tmp_path / "out.db"

    def robots_handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /api-website/buyer/\n")
        return httpx.Response(200, json=FIXTURE)

    with patch(
        "asset_crawler.cli._build_transport",
        return_value=httpx.MockTransport(robots_handler),
    ):
        result = runner.invoke(
            app,
            ["crawl", "pickles", "--db", str(db)],
        )

    assert result.exit_code != 0
    assert "robots" in result.stdout.lower() or "robots" in (result.stderr or "").lower()


def test_crawl_pickles_runs_with_override(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ASSET_CRAWLER_CONTACT", "https://example.com/me")
    db = tmp_path / "out.db"

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /api-website/buyer/\n")
        # treat any other call as the search api — no nextLink to avoid infinite loop
        return httpx.Response(200, json={**FIXTURE, "@odata.nextLink": None})

    with patch(
        "asset_crawler.cli._build_transport",
        return_value=httpx.MockTransport(handler),
    ):
        result = runner.invoke(
            app,
            ["crawl", "pickles", "--db", str(db), "--acknowledge-robots-disallowed"],
        )

    assert result.exit_code == 0, result.stdout
    # Verify we wrote rows
    import sqlite3
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    assert n == 2


def test_crawl_pickles_passes_filters(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ASSET_CRAWLER_CONTACT", "https://example.com/me")
    db = tmp_path / "out.db"
    seen_filters: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="")
        seen_filters.append(req.url.params.get("$filter", ""))
        return httpx.Response(200, json={"value": [], "@odata.nextLink": None})

    with patch(
        "asset_crawler.cli._build_transport",
        return_value=httpx.MockTransport(handler),
    ):
        result = runner.invoke(
            app,
            ["crawl", "pickles", "--db", str(db), "--lob", "industrial", "--product-type", "Forklifts"],
        )

    assert result.exit_code == 0, result.stdout
    assert seen_filters == ["(itemLoB eq 'industrial') and (productType/title eq 'Forklifts')"]


def test_crawl_pickles_rejects_invalid_contact(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ASSET_CRAWLER_CONTACT", "not-a-url-or-email")
    db = tmp_path / "out.db"
    result = runner.invoke(app, ["crawl", "pickles", "--db", str(db)])
    assert result.exit_code == 2
