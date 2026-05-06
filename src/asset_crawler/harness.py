from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from asset_crawler.db import open_db
from asset_crawler.listings_repo import upsert_listing
from asset_crawler.runs_repo import RunCounters, finish_run, mark_stale_running, start_run
from asset_crawler.types import SiteAdapter

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str  # 'ok' | 'failed' | 'aborted'
    counters: RunCounters
    error_message: str | None


class CrawlerHarness:
    def __init__(
        self,
        *,
        db_path: Path | str,
        now: Callable[[], datetime] | None = None,
        page_commit_interval: int = 50,
    ) -> None:
        self._db_path = db_path
        self._now = now or (lambda: datetime.now(UTC))
        self._commit_interval = page_commit_interval

    def run(
        self, adapter: SiteAdapter, *, filter_spec: dict[str, Any] | None
    ) -> RunResult:
        conn = open_db(self._db_path)
        n_stale = mark_stale_running(conn, now=self._now(), max_age=timedelta(hours=1))
        if n_stale:
            log.info("marked %d stale running rows as aborted", n_stale)

        started_at = self._now()
        run_id = start_run(conn, adapter.site_name, filter_spec, started_at)
        items_seen = items_new = items_duplicate = items_skipped = 0
        status = "ok"
        error_message: str | None = None

        try:
            batch = 0
            for record in adapter.iter_listings():
                items_seen += 1
                is_new = upsert_listing(conn, record, self._now())
                if is_new:
                    items_new += 1
                else:
                    items_duplicate += 1
                batch += 1
                if batch >= self._commit_interval:
                    conn.commit()
                    batch = 0
            conn.commit()
        except Exception as e:
            status = "failed"
            error_message = f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}"
            log.exception("crawl failed")
            conn.commit()  # persist partial progress

        counters = RunCounters(
            pages_fetched=0,
            items_seen=items_seen,
            items_new=items_new,
            items_duplicate=items_duplicate,
            items_skipped=items_skipped,
        )
        finish_run(
            conn,
            run_id,
            finished_at=self._now(),
            status=status,
            counters=counters,
            error_message=error_message,
        )
        conn.commit()
        conn.close()
        return RunResult(run_id=run_id, status=status, counters=counters, error_message=error_message)
