from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class RunCounters:
    pages_fetched: int = 0
    items_seen: int = 0
    items_new: int = 0
    items_duplicate: int = 0
    items_skipped: int = 0


def start_run(
    conn: sqlite3.Connection,
    source_site: str,
    filter_spec: dict[str, Any] | None,
    started_at: datetime,
) -> str:
    run_id = str(uuid.uuid4())
    spec_json = json.dumps(filter_spec, sort_keys=True) if filter_spec is not None else None
    conn.execute(
        "INSERT INTO crawl_runs (run_id, source_site, filter_spec, started_at, status) "
        "VALUES (?, ?, ?, ?, 'running')",
        (run_id, source_site, spec_json, started_at.isoformat()),
    )
    return run_id


def finish_run(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    finished_at: datetime,
    status: str,
    counters: RunCounters,
    error_message: str | None,
) -> None:
    if status not in {"ok", "failed", "aborted"}:
        raise ValueError(f"invalid terminal status: {status}")
    conn.execute(
        """
        UPDATE crawl_runs SET
          finished_at = ?,
          status = ?,
          pages_fetched = ?,
          items_seen = ?,
          items_new = ?,
          items_duplicate = ?,
          items_skipped = ?,
          error_message = ?
        WHERE run_id = ?
        """,
        (
            finished_at.isoformat(),
            status,
            counters.pages_fetched,
            counters.items_seen,
            counters.items_new,
            counters.items_duplicate,
            counters.items_skipped,
            error_message,
            run_id,
        ),
    )


def mark_stale_running(
    conn: sqlite3.Connection, *, now: datetime, max_age: timedelta
) -> int:
    cutoff = (now - max_age).isoformat()
    cur = conn.execute(
        "UPDATE crawl_runs SET status = 'aborted', error_message = 'detected stale on startup' "
        "WHERE status = 'running' AND started_at < ?",
        (cutoff,),
    )
    return cur.rowcount


def list_recent_runs(
    conn: sqlite3.Connection, *, site: str | None, limit: int
) -> Sequence[sqlite3.Row]:
    if site is None:
        return conn.execute(
            "SELECT * FROM crawl_runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return conn.execute(
        "SELECT * FROM crawl_runs WHERE source_site = ? ORDER BY started_at DESC LIMIT ?",
        (site, limit),
    ).fetchall()
