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

The CLI exposes four subcommands: `crawl`, `export`, `stats`, `runs`. Run `uv run crawler --help` or `uv run crawler <command> --help` for the authoritative option list.

### Global flags

These apply to every subcommand and must be placed **before** the subcommand:

| Flag | Description |
|---|---|
| `--verbose`, `-v` | Bump log level from INFO to DEBUG. Useful for inspecting page-by-page progress and HTTP details. |
| `--version` | Print the installed version and exit. |

```bash
uv run crawler --verbose crawl pickles --acknowledge-robots-disallowed
uv run crawler --version
```

### Crawl

```
crawler crawl <site> [--db PATH] [--lob TEXT]... [--product-type TEXT]...
                     [--acknowledge-robots-disallowed]
```

Fetches listings from the given site, deduplicates against the local DB, and records a row in `crawl_runs`. Site is positional and required; only `pickles` ships in v1.

| Option | Default | Description |
|---|---|---|
| `--db` | `./asset-crawler.db` | SQLite path. Created if it doesn't exist. |
| `--lob` | (none) | Filter by line of business. Repeat for multiple (OR-combined). Pickles uses URL slugs, e.g. `salvage`, `trucks-machinery-earthmoving`. |
| `--product-type` | (none) | Filter by product type label. Repeat for multiple (OR-combined). Pickles uses display titles, e.g. `Cars`, `Forklifts`. |
| `--acknowledge-robots-disallowed` | off | Required override; see note below. |

```bash
# Full Pickles crawl (~12k listings, ~12-20 min at the default polite delay)
uv run crawler crawl pickles --acknowledge-robots-disallowed

# Filter to one line of business and product type
uv run crawler crawl pickles --acknowledge-robots-disallowed \
  --lob salvage --product-type Cars

# Multiple filter values are OR'd together
uv run crawler crawl pickles --acknowledge-robots-disallowed \
  --lob salvage --lob trucks-machinery-earthmoving

# Use a custom database location
uv run crawler crawl pickles --acknowledge-robots-disallowed --db ~/data/pickles.db
```

On exit the command prints a one-line summary:

```
run <uuid> status=ok seen=11713 new=11713 dup=0 skipped=0
```

`status` is one of `ok` / `failed` / `aborted`. The exit code is `0` for `ok`, `1` for `failed`, `2` for usage errors (unknown site, missing contact), `3` if robots is disallowed and the override flag was not set.

**robots.txt note.** Pickles disallows the search API path in `robots.txt`. The crawler refuses to run unless `--acknowledge-robots-disallowed` is passed. This is your explicit acknowledgement that you accept responsibility for the crawl. The fact that the override was used is logged to stderr and recorded against the run.

**Politeness.** Single concurrency, 3–5 s jittered inter-request delay, identifiable `User-Agent`. Retries with exponential backoff on `429`/`503`; hard stop on `403` or HTML responses to JSON endpoints (typical Cloudflare challenge signature).

**Contact header.** The `User-Agent` includes a contact URL or email. Override via env var:

```bash
export ASSET_CRAWLER_CONTACT="https://example.com/contact"
uv run crawler crawl pickles --acknowledge-robots-disallowed
```

If `ASSET_CRAWLER_CONTACT` is set but empty, or doesn't look like a URL/email, the crawler exits before any HTTP traffic.

### Export

```
crawler export [--format jsonl|csv] [--out PATH] [--db PATH]
               [--site TEXT] [--since YYYY-MM-DD] [--no-raw]
```

Streams the contents of the `listings` table to a file. Read-only against the DB; safe to run while a crawl is in progress.

| Option | Default | Description |
|---|---|---|
| `--format` | `jsonl` | Output format: `jsonl` (one JSON object per line) or `csv`. |
| `--out` | `./export.<format>` | Output path. Default extension matches `--format` (`./export.jsonl` or `./export.csv`). |
| `--db` | `./asset-crawler.db` | SQLite path. |
| `--site` | (all sites) | Only export listings from this `source_site`. |
| `--since` | (no filter) | Only export listings with `first_seen_at >= <date>`. ISO date, e.g. `2026-01-01`. |
| `--no-raw` | off | Omit `raw_payload` from JSONL output. CSV never includes `raw_payload`. |

```bash
# Default: JSONL to ./export.jsonl
uv run crawler export

# CSV (lands at ./export.csv automatically)
uv run crawler export --format csv

# Custom path
uv run crawler export --out listings.jsonl

# Only Pickles listings first seen on or after 2026-01-01
uv run crawler export --site pickles --since 2026-01-01 --out recent.jsonl

# Smaller JSONL (drops raw_payload)
uv run crawler export --no-raw --out slim.jsonl
```

Output is deterministic: sorted by `source_site` then `source_listing_id`. JSONL keys are alphabetical within each object.

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

**CSV fields:** same set minus `raw_payload`. `source_categories` is rendered as the JSON-encoded array string. `source_url` is empty string when null.

The command prints `wrote <N> rows to <path>` on success. Exit code `1` if the database can't be opened or if a row's stored JSON is malformed; `2` for an unknown `--format`.

### Stats

```
crawler stats [--db PATH]
```

Prints four sections of coverage queries against the listings DB:

- **By site** — total listings per `source_site`.
- **By LoB (top 20)** — counts grouped by `source_categories[0]` (the line of business).
- **By product type (top 20)** — counts grouped by `source_categories[1]`.
- **Recent ingest (last 14 days)** — daily counts of `first_seen_at`, descending.

```bash
uv run crawler stats
uv run crawler stats --db ~/data/pickles.db
```

Read-only and fast (the underlying queries are `GROUP BY` over the indexed columns).

### Runs

```
crawler runs [--db PATH] [--site TEXT] [--limit N]
```

Lists recent rows from `crawl_runs`, most recent first.

| Option | Default | Description |
|---|---|---|
| `--db` | `./asset-crawler.db` | SQLite path. |
| `--site` | (all sites) | Filter to one `source_site`. |
| `--limit` | `20` | Max rows to display. |

```bash
uv run crawler runs
uv run crawler runs --site pickles --limit 50
```

Each line shows: `started_at  source_site  status  new=N dup=N skipped=N run_id=<uuid>`. `status` is one of:

| Status | Meaning |
|---|---|
| `running` | Currently in progress (or crashed mid-run before being marked stale). |
| `ok` | Completed without error. |
| `failed` | Hit a hard stop or exception; check stderr from the run. |
| `aborted` | Detected on the next startup as a stale `running` row older than 1 hour. |

## Development

```bash
uv run pytest           # full test suite (no network)
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
