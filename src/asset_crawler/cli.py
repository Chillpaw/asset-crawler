from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Annotated

import httpx
import typer

from asset_crawler import __version__
from asset_crawler.adapters.pickles.filters import parse_cli
from asset_crawler.config import ContactNotResolved, build_user_agent, resolve_contact
from asset_crawler.harness import CrawlerHarness
from asset_crawler.http_client import PoliteClient, PoliteClientConfig
from asset_crawler.robots import fetch_robots, is_allowed

log = logging.getLogger(__name__)
app = typer.Typer(help="asset-crawler — polite, adapter-based auction-listing crawler")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"asset-crawler {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: Annotated[bool, typer.Option("--version", callback=_version_callback)] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )


def _build_transport() -> httpx.BaseTransport | None:
    """Indirection point for tests to inject httpx.MockTransport."""
    return None


@app.command("crawl")
def crawl_cmd(
    site: Annotated[str, typer.Argument(help="Site name, e.g. 'pickles'")],
    db: Annotated[Path, typer.Option("--db", help="SQLite path")] = Path("./asset-crawler.db"),
    acknowledge_robots_disallowed: Annotated[
        bool, typer.Option("--acknowledge-robots-disallowed")
    ] = False,
    lob: Annotated[list[str] | None, typer.Option("--lob")] = None,
    product_type: Annotated[list[str] | None, typer.Option("--product-type")] = None,
) -> None:
    """Run a crawl for one site."""
    if site != "pickles":
        typer.echo(f"unknown site: {site}", err=True)
        raise typer.Exit(code=2)

    try:
        contact = resolve_contact()
    except ContactNotResolved as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2) from e
    user_agent = build_user_agent(contact)

    transport = _build_transport()
    base_url = "https://www.pickles.com.au"
    api_path = "/api-website/buyer/ms-web-asset-search/v2/api/product/public/search"
    robots = fetch_robots(base_url, transport=transport)
    allowed = is_allowed(robots, api_path, user_agent=user_agent)
    if not allowed and not acknowledge_robots_disallowed:
        typer.echo(
            "robots.txt disallows the target API path. Pass "
            "--acknowledge-robots-disallowed to override (operator responsibility).",
            err=True,
        )
        raise typer.Exit(code=3)

    filters = parse_cli(lob, product_type)

    cfg = PoliteClientConfig(user_agent=user_agent)
    if transport is not None:
        cfg = PoliteClientConfig(
            user_agent=user_agent,
            delay_min_s=0.0,
            delay_max_s=0.0,
            retry_initial_s=0.0,
            retry_max_s=0.0,
        )

    from asset_crawler.adapters.pickles import PicklesAdapter

    with PoliteClient(config=cfg, transport=transport) as client:
        adapter = PicklesAdapter(client=client, filters=filters)
        harness = CrawlerHarness(db_path=db)
        result = harness.run(adapter, filter_spec=filters.to_dict())

    typer.echo(
        f"run {result.run_id} status={result.status} "
        f"seen={result.counters.items_seen} new={result.counters.items_new} "
        f"dup={result.counters.items_duplicate} skipped={result.counters.items_skipped}"
    )
    if not allowed:
        log.warning("ran with --acknowledge-robots-disallowed")
    if result.status != "ok":
        raise typer.Exit(code=1)


@app.command("export")
def export_cmd(
    format: Annotated[str, typer.Option("--format", help="jsonl|csv")] = "jsonl",
    out: Annotated[Path, typer.Option("--out")] = Path("./export.jsonl"),
    db: Annotated[Path, typer.Option("--db")] = Path("./asset-crawler.db"),
    since: Annotated[str | None, typer.Option("--since", help="YYYY-MM-DD")] = None,
    site: Annotated[str | None, typer.Option("--site")] = None,
    no_raw: Annotated[bool, typer.Option("--no-raw")] = False,
) -> None:
    """Export listings to JSONL or CSV."""
    format = format.lower()
    from asset_crawler.export import export_csv, export_jsonl

    if format == "jsonl":
        n = export_jsonl(db_path=db, out=out, since=since, site=site, no_raw=no_raw)
    elif format == "csv":
        n = export_csv(db_path=db, out=out, since=since, site=site)
    else:
        typer.echo(f"unknown format: {format}", err=True)
        raise typer.Exit(code=2)
    typer.echo(f"wrote {n} rows to {out}")


@app.command("stats")
def stats_cmd(
    db: Annotated[Path, typer.Option("--db")] = Path("./asset-crawler.db"),
) -> None:
    """Print canonical coverage queries from the listings DB."""
    from asset_crawler.db import open_db
    from asset_crawler.stats import (
        counts_by_lob,
        counts_by_product_type,
        counts_by_site,
        recent_ingest_by_day,
    )

    conn = open_db(db)
    try:
        typer.echo("# By site")
        for site, n in counts_by_site(conn):
            typer.echo(f"  {site}: {n}")
        typer.echo("\n# By LoB (top 20)")
        for lob, n in counts_by_lob(conn):
            typer.echo(f"  {lob}: {n}")
        typer.echo("\n# By product type (top 20)")
        for pt, n in counts_by_product_type(conn):
            typer.echo(f"  {pt}: {n}")
        typer.echo("\n# Recent ingest (last 14 days)")
        for d, n in recent_ingest_by_day(conn):
            typer.echo(f"  {d}: {n}")
    finally:
        conn.close()


@app.command("runs")
def runs_cmd(
    db: Annotated[Path, typer.Option("--db")] = Path("./asset-crawler.db"),
    site: Annotated[str | None, typer.Option("--site")] = None,
    limit: Annotated[int, typer.Option("--limit")] = 20,
) -> None:
    """Show recent crawl runs."""
    from asset_crawler.db import open_db
    from asset_crawler.runs_repo import list_recent_runs

    conn = open_db(db)
    try:
        rows = list_recent_runs(conn, site=site, limit=limit)
        for r in rows:
            typer.echo(
                f"{r['started_at']}  {r['source_site']:10}  {r['status']:8}  "
                f"new={r['items_new']:<6} dup={r['items_duplicate']:<6} "
                f"skipped={r['items_skipped']:<4} run_id={r['run_id']}"
            )
    finally:
        conn.close()
