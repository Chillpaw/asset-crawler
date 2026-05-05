from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from asset_crawler.types import ListingRecord


def upsert_listing(
    conn: sqlite3.Connection, record: ListingRecord, now: datetime
) -> bool:
    """Insert a new listing, or bump last_seen_at on an existing PK match.

    Returns True if a row was inserted, False if an existing row was updated.
    Description and other fields are NEVER refreshed (first-write-wins).
    """
    iso = now.isoformat()
    cur = conn.execute(
        """
        INSERT INTO listings (
            source_site, source_listing_id, description, source_categories,
            source_url, raw_payload, first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_site, source_listing_id) DO UPDATE SET
            last_seen_at = excluded.last_seen_at
        """,
        (
            record.source_site,
            record.source_listing_id,
            record.description,
            json.dumps(record.source_categories, ensure_ascii=False),
            record.source_url,
            json.dumps(record.raw_payload, ensure_ascii=False, sort_keys=True),
            iso,
            iso,
        ),
    )
    return cur.rowcount == 1 and cur.lastrowid is not None and _was_inserted(conn, record)


def _was_inserted(conn: sqlite3.Connection, record: ListingRecord) -> bool:
    row = conn.execute(
        "SELECT first_seen_at = last_seen_at AS is_new FROM listings "
        "WHERE source_site = ? AND source_listing_id = ?",
        (record.source_site, record.source_listing_id),
    ).fetchone()
    return bool(row["is_new"])
