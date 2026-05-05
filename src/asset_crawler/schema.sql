CREATE TABLE IF NOT EXISTS listings (
  source_site        TEXT NOT NULL,
  source_listing_id  TEXT NOT NULL,
  description        TEXT NOT NULL,
  source_categories  TEXT NOT NULL,
  source_url         TEXT,
  raw_payload        TEXT NOT NULL,
  first_seen_at      TEXT NOT NULL,
  last_seen_at       TEXT NOT NULL,
  PRIMARY KEY (source_site, source_listing_id)
);

CREATE INDEX IF NOT EXISTS idx_first_seen_at ON listings(first_seen_at);

CREATE TABLE IF NOT EXISTS crawl_runs (
  run_id          TEXT PRIMARY KEY,
  source_site     TEXT NOT NULL,
  filter_spec     TEXT,
  started_at      TEXT NOT NULL,
  finished_at     TEXT,
  status          TEXT NOT NULL,
  pages_fetched   INTEGER NOT NULL DEFAULT 0,
  items_seen      INTEGER NOT NULL DEFAULT 0,
  items_new       INTEGER NOT NULL DEFAULT 0,
  items_duplicate INTEGER NOT NULL DEFAULT 0,
  items_skipped   INTEGER NOT NULL DEFAULT 0,
  error_message   TEXT
);
