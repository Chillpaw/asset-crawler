from __future__ import annotations

import sqlite3
from collections.abc import Iterator


def counts_by_site(conn: sqlite3.Connection) -> Iterator[tuple[str, int]]:
    for row in conn.execute(
        "SELECT source_site, COUNT(*) AS n FROM listings GROUP BY 1 ORDER BY 2 DESC"
    ):
        yield row["source_site"], row["n"]


def counts_by_lob(conn: sqlite3.Connection, limit: int = 20) -> Iterator[tuple[str, int]]:
    for row in conn.execute(
        "SELECT json_extract(source_categories, '$[0]') AS lob, COUNT(*) AS n "
        "FROM listings GROUP BY 1 ORDER BY 2 DESC LIMIT ?", (limit,),
    ):
        yield row["lob"], row["n"]


def counts_by_product_type(conn: sqlite3.Connection, limit: int = 20) -> Iterator[tuple[str, int]]:
    for row in conn.execute(
        "SELECT json_extract(source_categories, '$[1]') AS pt, COUNT(*) AS n "
        "FROM listings GROUP BY 1 ORDER BY 2 DESC LIMIT ?", (limit,),
    ):
        yield row["pt"], row["n"]


def recent_ingest_by_day(conn: sqlite3.Connection, days: int = 14) -> Iterator[tuple[str, int]]:
    for row in conn.execute(
        "SELECT DATE(first_seen_at) AS d, COUNT(*) AS n FROM listings "
        "GROUP BY 1 ORDER BY 1 DESC LIMIT ?", (days,),
    ):
        yield row["d"], row["n"]
