# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`asset-crawler` is a polite, adapter-based Python CLI that pulls auction listings into SQLite under a uniform schema, with deduplication, run auditing, and JSONL/CSV export. v1 ships a Pickles reference adapter; new sites are one folder under `src/asset_crawler/adapters/`. See `docs/PRD-asset-crawler.md` for the canonical spec.

## Setup & Commands

```bash
uv sync                                    # install deps
uv run pytest                              # full test suite
uv run pytest tests/test_harness.py -v     # one file
uv run ruff check .                        # lint
uv run crawler --help                      # CLI surface
```

The CLI is also installable as `crawler` once `uv sync` has run.

## Architecture in one paragraph

`SiteAdapter` (Protocol, in `types.py`) yields `ListingRecord` objects. `CrawlerHarness` (`harness.py`) owns the DB, dedup, run audit, retry, and timestamping; adapters are pure. `PoliteClient` (`http_client.py`) enforces single-concurrency, jittered delays, exponential backoff on 429/503, and hard stops on 403/HTML. `robots.py` checks robots.txt; the CLI requires `--acknowledge-robots-disallowed` to override. The Pickles adapter (`adapters/pickles/`) talks to one OData JSON search API and maps records via `mapping.py`/`url.py`.

## Conventions

- Adapters: one folder under `adapters/<site>/` with `adapter.py`, `filters.py`, `api.py`, `mapping.py`, `url.py`. Adapters are pure (no DB, no rate-limit, no timestamps).
- Cross-site normalisation is deliberately deferred — categories are stored verbatim from each site.
- `ListingRecord` is frozen pydantic; blank descriptions are rejected at the model boundary.
- Tests use `httpx.MockTransport` for HTTP isolation; no real network in pytest.
- Database schema lives in `schema.sql`; idempotent `CREATE TABLE IF NOT EXISTS` style.
- Time is injected (`now: Callable[[], datetime]`) for testability.

## Spec & plan

- PRD: `docs/PRD-asset-crawler.md`
- Implementation plan: `docs/superpowers/plans/2026-05-04-asset-crawler-v1.md`
