# PRD: asset-crawler

## Problem

There is no maintained, open-source tool for extracting structured asset data from Australian auction sites. Researchers, ML practitioners, market analysts, and journalists who need this data either build one-off scrapers or scrape manually. The fragmentation produces brittle code, inconsistent schemas, and repeated work.

`asset-crawler` is a polite, adapter-based crawler that pulls listing data from Australian auction sites into a uniform schema, with deduplication, run auditing, and filterable exports. v1 ships a single reference adapter for pickles.com.au; the architecture is designed so additional sites are one file each.

Downstream use is out of scope. The tool produces a clean dataset; what consumers do with it (training corpora, market analysis, dashboards, etc.) is their problem.

## Success criteria (v1)

- Reference adapter (Pickles) crawls end-to-end without manual intervention.
- Records carry full free-text `description`, ordered `source_categories`, and a stable site-native identifier.
- Filtered crawls supported via adapter-native filter vocabulary (no cross-site normalisation).
- Crashes mid-crawl are recoverable: re-running picks up cleanly with no data loss and bounded re-fetch cost.
- Export to JSONL is byte-identical for the same DB state.
- A new site adapter is implementable in a single file with no harness changes.

## Scope

**v1:** pickles.com.au reference adapter, SQLite persistence, JSONL/CSV export, filter spec, run audit.

**v2+:** additional site adapters (Grays, Manheim, Gumtree, etc.). Interface is stable; implementation deferred until a contributor or use case justifies each one.

## Architecture

```
SiteAdapter ──iter_listings()──▶ CrawlerHarness ──▶ asset-crawler.db
                                                          │
                                                   export ▼
                                                   handoff.jsonl
```

### Adapter interface

```python
class SiteAdapter(Protocol):
    site_name: str
    def iter_listings(self) -> Iterator[ListingRecord]: ...

@dataclass(frozen=True)
class ListingRecord:
    source_site:        str
    source_listing_id:  str
    description:        str
    source_categories:  list[str]
    source_url:         str | None
    raw_payload:        dict
```

Adapters are pure: no DB access, no rate-limit logic, no timestamp logic. The harness owns retry, throttling, dedup, persistence, and timestamping. Consistent harness ownership is what lets a new adapter be one file.

A new adapter is registered via a class-level `site_name` and resolved by the harness from a registry at startup.

### Filtering

Filters are adapter-local and adapter-native. The harness does not know or care what filters mean. A user runs:

```
crawler crawl pickles --lob industrial --product-type Forklifts
```

The Pickles adapter accepts a `PicklesFilters` dataclass:

```python
@dataclass(frozen=True)
class PicklesFilters:
    line_of_business: list[str] | None = None   # API slug values
    product_types:    list[str] | None = None   # API title values
```

Other adapters define their own filter dataclass with their own field names. There is deliberately no cross-site filter abstraction — each site's facet vocabulary is incompatible.

The active filter spec for a crawl is logged on `crawl_runs.filter_spec` as JSON. Listings themselves are filter-agnostic: the same listing discovered via a filtered crawl and an unfiltered crawl is the same row, dedup-keyed on `(source_site, source_listing_id)`. Filters affect *what gets discovered*, never *what gets stored differently*.

## Functional requirements

1. **Discovery** — adapter enumerates currently-listed assets via paginated API calls, optionally narrowed by adapter-native filters.
2. **Extraction** — adapter yields one `ListingRecord` per asset.
3. **Deduplication** — harness uses `(source_site, source_listing_id)` as PK. Re-encountered listings get `last_seen_at` updated only; description and other fields are NOT refreshed.
4. **Validation** — records with empty `description` are skipped and counted in `items_skipped`; records with empty `source_categories` are stored with `[]` (legitimate state, not error).
5. **Persistence** — atomic insert-or-update per record; transaction-bounded by page.
6. **Audit** — every run records start/finish, counts, and filter spec in `crawl_runs`.
7. **Recovery** — on startup, any `crawl_runs` row in `running` state older than 1 hour is marked `aborted`. Re-running a crawl starts a new run from page 1; dedup absorbs already-captured records.
8. **Export** — separate subcommand produces deterministic JSONL or CSV, filterable by site and date.

### Re-crawl policy

Never re-fetch an already-seen listing's description. First successful capture is canonical.

Rationale: snapshot consistency over per-listing freshness. A listing's description may be edited by the seller mid-auction; we capture the version present when first crawled and treat it as immutable. Consumers needing re-listing variance (e.g. same physical asset listed in successive auctions with different descriptions) should either relax dedup at the consumer side or extend the schema to capture description history (deliberately deferred).

## Data model

### `listings` table

```sql
CREATE TABLE listings (
  source_site        TEXT NOT NULL,
  source_listing_id  TEXT NOT NULL,
  description        TEXT NOT NULL,
  source_categories  TEXT NOT NULL,    -- JSON array, may be '[]'
  source_url         TEXT,             -- nullable
  raw_payload        TEXT NOT NULL,    -- JSON
  first_seen_at      TEXT NOT NULL,    -- ISO 8601 UTC
  last_seen_at       TEXT NOT NULL,    -- ISO 8601 UTC
  PRIMARY KEY (source_site, source_listing_id)
);
CREATE INDEX idx_first_seen_at ON listings(first_seen_at);
```

The leftmost prefix of the PK covers `WHERE source_site = ?` queries.

### `crawl_runs` table

```sql
CREATE TABLE crawl_runs (
  run_id          TEXT PRIMARY KEY,    -- UUID
  source_site     TEXT NOT NULL,
  filter_spec     TEXT,                -- nullable JSON; NULL = unfiltered crawl
  started_at      TEXT NOT NULL,
  finished_at     TEXT,
  status          TEXT NOT NULL,       -- 'running' | 'ok' | 'failed' | 'aborted'
  pages_fetched   INTEGER NOT NULL DEFAULT 0,
  items_seen      INTEGER NOT NULL DEFAULT 0,
  items_new       INTEGER NOT NULL DEFAULT 0,
  items_duplicate INTEGER NOT NULL DEFAULT 0,
  items_skipped   INTEGER NOT NULL DEFAULT 0,
  error_message   TEXT
);
```

### Why SQLite, not Parquet/JSONL

- Tens of thousands of records is trivially small for SQLite; query ergonomics matter more than IO efficiency at this scale.
- Decoupled-export means consumers choose the final format.
- Ad-hoc filtering (`source_categories[0] = 'Trucks'`) is clumsy on raw JSONL.
- Parquet is correct at 1M+ rows; not now.

### Pickles field mapping

| `ListingRecord` field | Pickles API field | Note |
|---|---|---|
| `source_site` | constant `"pickles"` | adapter constant |
| `source_listing_id` | `assetId` (UUID) | stable across re-listings of the same physical asset |
| `description` | `description` | full free-text |
| `source_categories` | `[lob_label, productType.title, assetType]` | broad → narrow; empty intermediate fields dropped |
| `source_url` | constructed; see below | best-effort; nullable |
| `raw_payload` | the entire API record | preserves the ~120 fields not extracted |

`lob_label` derivation: find index `i` where `lineOfBusinessUrls[i] == itemLoB`, take `lineOfBusinesses[i]` (e.g. `itemLoB="salvage"` → `"Salvage stock"`). **Fallback:** if no match, use raw `itemLoB` and emit a warning log. Field is never null.

`source_categories` example for a salvage trailer: `["Salvage stock", "Trailers", "Trailer"]`. Redundancy between `productType.title` and `assetType` is preserved verbatim — no normalisation across or within sites.

Multi-LoB assets get their primary `itemLoB` only; alternates remain in `raw_payload`.

### `source_url` construction

Pickles listing URLs follow the pattern:

```
/{lob_url_slug}/{asset_kind}/itemid-{id}/lotid-{lot_id}
```

With small lookups for `lob_url_slug` (e.g. `salvage` → `damaged-salvage`) and `asset_kind` (`vehicle` for cars/salvage, `item` for trucks/general). When all required IDs are present, construct and store; otherwise `NULL`. Not load-bearing for corpus integrity.

**Open decision:** which API field provides the `lotid`. The sample record had `eLotId: None` and `lotNumber: '104'`. Implementation should probe a second sample; if unresolvable the field stays `NULL` and the adapter documents why.

### Category capture rationale (no normalisation)

Cross-site category normalisation is deliberately deferred:

- Each site's taxonomy is internally inconsistent (Pickles' `productType.title` and `assetType` already disagree on plurality).
- Consumers apply their own classification scheme; site categories are hints, not labels.
- Normalising now would force a schema decision before a second site's data exists to validate against.

## Pagination

Pickles' search API uses OData `$skip`/`$top`. Offset pagination is brittle on a live catalogue: insertions during a crawl shift offsets and silently drop records; dedup catches duplicates but not misses.

**Mitigation v1:** sort by a stable field (`assetId` ascending via `$orderby`). Track the highest `assetId` seen per page; assert next page's lowest exceeds it. If overlap detected, log warning and continue (dedup absorbs cost).

**Open decision:** probe whether the API supports a true cursor before committing to ordered offset. If a cursor exists, prefer it.

## Crash recovery

- On startup, mark any `crawl_runs` row with `status='running'` and `started_at` older than 1 hour as `status='aborted'` with `error_message='detected stale on startup'`.
- Crashed crawls are NOT auto-resumed mid-stream. Re-running starts a new run from page 1.
- Cost of restart: API calls duplicated, dedup ensures no data corruption. Acceptable for ~13-min full crawl.
- Resumable mid-stream crawls (per-page checkpointing) deferred until restart cost becomes painful.

## Tech stack

**Python 3.12+**, with:

- `httpx` — HTTP client with retry primitives.
- `sqlite3` (stdlib) — direct SQL, no ORM.
- `typer` — CLI.
- `pydantic` — `ListingRecord` validation at the adapter boundary.
- `uv` — project / dependency management.

### Why Python over Rust

- ~200 API calls per crawl: performance is irrelevant.
- Adapter changes are schema-driven (fields renamed, added) — Python's iteration speed wins.
- No production-deployment requirement that would favour a static binary.
- Open-source contribution barrier: Python is broadly accessible.

### Why no Playwright / scraper / lxml

Investigation showed all required Pickles data is in JSON. HTML parsing is not on the critical path. Future adapters that need HTML parsing can add `lxml` as an optional dep.

## Politeness

Defaults are conservative; operators tune for their use case.

- **Concurrency:** 1 in-flight request per adapter.
- **Inter-request delay:** 3–5 seconds with uniform jitter (configurable).
- **User-Agent:** `asset-crawler/<version> (+<contact URL>)`. Identifiable, not browser-impersonating. Operators set the contact URL via env var `ASSET_CRAWLER_CONTACT`; default falls back to the repo URL. The tool refuses to start without a contact value resolvable to a URL or email.
- **Retry policy:** exponential backoff on 429/503 starting at 30 s, max 3 retries, max delay 5 minutes; jitter on each retry.
- **Hard stop conditions:**
  - any 403
  - HTML response where JSON expected (e.g. Cloudflare challenge)
  - three consecutive non-retryable errors
  - degraded page size (received < 50% of requested for 3 consecutive pages)
  - page overlap (3 consecutive pages share > 10% of IDs with prior — silent throttling indicator)

  Crawler exits non-zero, no auto-recovery.
- **Excluded mitigations (deliberate):** no proxy rotation, no UA rotation, no header spoofing, no IP cycling. Out of scope for a polite, identifiable crawler.

### robots.txt

Some target endpoints (including Pickles' search API) are disallowed by `robots.txt`. Operators are responsible for understanding the legal and ethical implications in their jurisdiction and use case. Behaviour:

- By default, the harness fetches and respects `robots.txt`. If an adapter targets a disallowed path, the crawl aborts with an explanatory error.
- Passing `--acknowledge-robots-disallowed` overrides the check. The flag is per-invocation and explicit. Logs and `crawl_runs.error_message` (when applicable) record that the override was used.

This is an operator-responsibility choice, not a tool-policy one.

Full crawl wall-clock at default config: ~13 minutes per ~10k Pickles records.

## Observability

- **Per-request structured logs** to stderr: timestamp, page, HTTP status, latency, items returned.
- **Run summary** on exit, persisted to `crawl_runs`: pages fetched, items seen / new / duplicate / skipped, errors, wall-clock, filter spec.
- **Coverage SQL** — canonical queries:

```sql
-- Total by site
SELECT source_site, COUNT(*) FROM listings GROUP BY 1;

-- Top broad categories
SELECT json_extract(source_categories, '$[0]') AS lob, COUNT(*)
FROM listings GROUP BY 1 ORDER BY 2 DESC LIMIT 20;

-- Top productType categories
SELECT json_extract(source_categories, '$[1]') AS pt, COUNT(*)
FROM listings GROUP BY 1 ORDER BY 2 DESC LIMIT 20;

-- Recent ingest
SELECT DATE(first_seen_at) AS d, COUNT(*) FROM listings
GROUP BY 1 ORDER BY 1 DESC LIMIT 14;

-- Recent runs
SELECT run_id, source_site, filter_spec, status, items_new, started_at
FROM crawl_runs ORDER BY started_at DESC LIMIT 20;
```

No metrics infrastructure (Prometheus, Grafana, log shipping). Overkill at this scale.

## Export

```
crawler export --format jsonl --out FILE [--since YYYY-MM-DD] [--site NAME] [--no-raw]
```

- Default: JSONL, one `ListingRecord` per line plus `first_seen_at` / `last_seen_at` and `raw_payload`.
- `--format csv`: drops `raw_payload`; JSON-encodes `source_categories`.
- `--since` filters by `first_seen_at`.
- Output ordered by `(source_site, source_listing_id)` ascending. Byte-identical for a given DB state.

The crawler does not write to any consumer's data store directly. Decoupling preserves repo independence and lets consumers evolve their ingestion shape without crawler churn.

## CLI surface (v1)

```
crawler crawl <site> [adapter-specific filter flags]   # run a crawl
crawler export --format jsonl --out OUT                # produce export
crawler stats                                          # print canonical coverage SQL output
crawler runs [--site NAME] [--limit N]                 # show recent crawl runs
```

Filter flags are defined per-adapter and surfaced through an adapter-supplied `register_cli` hook. The harness does not enumerate filters.

## Out of scope

- Classification, labelling, or downstream taxonomy mapping.
- Any UI: CLI sort, web UI, autocomplete.
- Re-fetching already-seen listings (description history).
- Image/photo capture, price, seller, bid, condition fields beyond `raw_payload`.
- Authentication, login state, watchlist, bidding.
- Headless browser / Playwright (until a target site requires it).
- Cross-site category normalisation.
- Cross-site filter abstraction.
- v2+ site adapters: `SiteAdapter` Protocol is ready, implementations are deferred.
- Distributed / parallel crawling.
- Mid-stream resumable crawls.
- Schema migrations / Alembic until DDL changes require it.

## Open decisions

- `source_url` `lotid` field source — flagged in §Pickles field mapping.
- Pagination stability — flagged in §Pagination. Probe before committing to ordered offset.