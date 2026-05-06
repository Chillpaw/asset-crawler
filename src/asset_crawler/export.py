from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path


def _query(since: str | None, site: str | None) -> tuple[str, list]:
    where: list[str] = []
    args: list = []
    if since:
        where.append("first_seen_at >= ?")
        args.append(since)
    if site:
        where.append("source_site = ?")
        args.append(site)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    sql = (
        "SELECT source_site, source_listing_id, description, source_categories, "
        "source_url, raw_payload, first_seen_at, last_seen_at "
        "FROM listings" + where_sql + " ORDER BY source_site ASC, source_listing_id ASC"
    )
    return sql, args


def export_jsonl(
    *, db_path: Path, out: Path, since: str | None, site: str | None, no_raw: bool
) -> int:
    sql, args = _query(since, site)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    n = 0
    try:
        with out.open("w", encoding="utf-8") as f:
            for row in conn.execute(sql, args):
                try:
                    source_categories = json.loads(row["source_categories"])
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"malformed source_categories for listing "
                        f"{row['source_site']}/{row['source_listing_id']}: {exc}"
                    ) from exc
                obj = {
                    "source_site": row["source_site"],
                    "source_listing_id": row["source_listing_id"],
                    "description": row["description"],
                    "source_categories": source_categories,
                    "source_url": row["source_url"],
                    "first_seen_at": row["first_seen_at"],
                    "last_seen_at": row["last_seen_at"],
                }
                if not no_raw:
                    try:
                        raw_payload = json.loads(row["raw_payload"])
                    except json.JSONDecodeError as exc:
                        raise ValueError(
                            f"malformed raw_payload for listing "
                            f"{row['source_site']}/{row['source_listing_id']}: {exc}"
                        ) from exc
                    obj["raw_payload"] = raw_payload
                f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")
                n += 1
    finally:
        conn.close()
    return n


def export_csv(
    *, db_path: Path, out: Path, since: str | None, site: str | None
) -> int:
    sql, args = _query(since, site)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    n = 0
    try:
        with out.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "source_site",
                    "source_listing_id",
                    "description",
                    "source_categories",
                    "source_url",
                    "first_seen_at",
                    "last_seen_at",
                ],
            )
            writer.writeheader()
            for row in conn.execute(sql, args):
                writer.writerow({
                    "source_site": row["source_site"],
                    "source_listing_id": row["source_listing_id"],
                    "description": row["description"],
                    "source_categories": row["source_categories"],  # already JSON-encoded
                    "source_url": row["source_url"] or "",
                    "first_seen_at": row["first_seen_at"],
                    "last_seen_at": row["last_seen_at"],
                })
                n += 1
    finally:
        conn.close()
    return n
