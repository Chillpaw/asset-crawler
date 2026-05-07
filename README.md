# asset-crawler

Polite, adapter-based CLI that pulls Australian auction listings into a local SQLite database with deduplication, run auditing, and JSONL/CSV export.

v1 ships a [Pickles](https://www.pickles.com.au) reference adapter. New sites are one folder under `src/asset_crawler/adapters/`.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)

## Setup

```bash
git clone https://github.com/Chillpaw/asset-crawler
cd asset-crawler
uv sync
```

After `uv sync`, the `crawler` command is available via `uv run crawler`.

## Where data is stored

By default everything is written to `asset-crawler.db` in the current working directory — a single SQLite file. Pass `--db <path>` to any command to use a different location.

The database has two tables:

| Table | Purpose |
|---|---|
| `listings` | One row per unique listing (deduped on `source_site` + `source_listing_id`). First-write-wins: re-crawling a listing only updates `last_seen_at`. |
| `crawl_runs` | One row per crawl invocation: start time, finish time, status, counters, and any error message. |

## Usage

### Crawl

```bash
# Crawl all Pickles listings (requires robots.txt override — see note below)
uv run crawler crawl pickles --acknowledge-robots-disallowed

# Filter to a specific line of business or product type
uv run crawler crawl pickles --acknowledge-robots-disallowed \
  --lob "Industrial & Construction" \
  --product-type "Excavators"

# Multiple values for the same filter (OR'd together)
uv run crawler crawl pickles --acknowledge-robots-disallowed \
  --lob "Industrial & Construction" --lob "Marine"

# Write to a custom database location
uv run crawler crawl pickles --acknowledge-robots-disallowed --db ~/data/pickles.db
```

**robots.txt note:** Pickles disallows the search API path in `robots.txt`. The crawler checks this by default and refuses to run unless you pass `--acknowledge-robots-disallowed`. This flag is your explicit acknowledgement that you accept responsibility for the crawl. The acknowledgement is logged to `crawl_runs.error_message` for auditing.

**Rate:** Single concurrency, 3–5 s jittered inter-request delay, identifiable `User-Agent`. Hard stops on HTTP 403/429/503.

**Contact header:** The crawler includes a contact URL or email in its `User-Agent` string. Set the `ASSET_CRAWLER_CONTACT` environment variable to override the default:

```bash
export ASSET_CRAWLER_CONTACT="https://example.com/contact"
uv run crawler crawl pickles --acknowledge-robots-disallowed
```

### Export

```bash
# JSONL (default) — one JSON object per line
uv run crawler export --out listings.jsonl

# CSV
uv run crawler export --format csv --out listings.csv

# Filter by site or date
uv run crawler export --site pickles --since 2026-01-01 --out recent.jsonl

# Omit the raw API payload (smaller output)
uv run crawler export --no-raw --out listings.jsonl
```

**JSONL fields:**

| Field | Type | Notes |
|---|---|---|
| `source_site` | string | e.g. `"pickles"` |
| `source_listing_id` | string | Site's own stable ID |
| `description` | string | Listing title / description |
| `source_categories` | array | Verbatim from source (no cross-site normalisation) |
| `source_url` | string or null | Direct URL to the listing page |
| `first_seen_at` | ISO 8601 | When first crawled |
| `last_seen_at` | ISO 8601 | When last seen on a re-crawl |
| `raw_payload` | object | Full API response object (omitted with `--no-raw`) |

Output is deterministic: sorted by `source_site` then `source_listing_id`, keys alphabetical.

### Stats

Print a breakdown of what's in the database:

```bash
uv run crawler stats
```

Shows total listings, counts by line of business, and counts by product type.

### Runs

Show the history of crawl runs:

```bash
uv run crawler runs

# Filter to one site, increase limit
uv run crawler runs --site pickles --limit 50
```

## Development

```bash
uv run pytest           # full test suite (93 tests, no network)
uv run pytest tests/test_harness.py -v   # single file
uv run ruff check .     # lint
uv run mypy src         # type check
```

Tests use `httpx.MockTransport` — no real network calls in the test suite.

## Architecture

```
src/asset_crawler/
  cli.py          — Typer CLI (crawl / export / stats / runs)
  harness.py      — CrawlerHarness: DB, dedup, run auditing, crash recovery
  listings_repo.py — upsert_listing (first-write-wins)
  http_client.py  — PoliteClient: jitter, backoff, hard stops
  robots.py       — robots.txt gate
  config.py       — User-Agent / contact resolution
  export.py       — JSONL + CSV writers
  stats.py        — coverage queries
  registry.py     — adapter registry
  types.py        — ListingRecord (Pydantic), SiteAdapter (Protocol)
  schema.sql      — idempotent CREATE TABLE IF NOT EXISTS

  adapters/pickles/
    adapter.py    — PicklesAdapter (SiteAdapter implementation)
    api.py        — OData pagination
    mapping.py    — API record → ListingRecord
    filters.py    — LoB / product-type → OData $filter
    url.py        — listing URL construction
```

**Adding a new site:** create `adapters/<site>/adapter.py` with a class that satisfies the `SiteAdapter` Protocol (implement `iter_listings() -> Iterator[ListingRecord]`, set `site_name: ClassVar[str]`), then register it in `registry.py`.

## Known limitations (v2)

- `items_skipped` is always 0 — blank-description filtering happens in the adapter mapping layer before records reach the harness counter.
- `pages_fetched` is always 0 — the harness iterates records, not pages.
- `--since` accepts any string; invalid values produce a silent empty export.
- Hard-stop conditions (3 consecutive non-retryable errors, degraded page size) are not yet implemented.
- Mid-stream resumable crawls (per-page checkpointing) are deferred.
