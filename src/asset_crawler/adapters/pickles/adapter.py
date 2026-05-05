from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import ClassVar

from asset_crawler.adapters.pickles.api import DEFAULT_PAGE_SIZE, search_page
from asset_crawler.adapters.pickles.filters import PicklesFilters
from asset_crawler.adapters.pickles.mapping import api_record_to_listing
from asset_crawler.http_client import PoliteClient
from asset_crawler.types import ListingRecord

log = logging.getLogger(__name__)


class PicklesAdapter:
    site_name: ClassVar[str] = "pickles"

    def __init__(
        self,
        *,
        client: PoliteClient,
        filters: PicklesFilters | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> None:
        self._client = client
        self._filters = filters
        self._page_size = page_size

    def iter_listings(self) -> Iterator[ListingRecord]:
        skip = 0
        prev_max_asset_id: str | None = None
        empty_pages = 0

        while True:
            page = search_page(
                self._client, filters=self._filters, skip=skip, top=self._page_size
            )
            log.info(
                "pickles page: skip=%d, returned=%d, has_next=%s",
                skip, len(page.records), page.next_link is not None,
            )

            if not page.records:
                empty_pages += 1
                if empty_pages >= 1:
                    return
                continue
            empty_pages = 0

            page_asset_ids = [r.get("assetId", "") for r in page.records]
            min_id = min(page_asset_ids)
            max_id = max(page_asset_ids)
            if prev_max_asset_id is not None and min_id <= prev_max_asset_id:
                log.warning(
                    "pickles page overlap: prev_max=%s, this_min=%s — dedup will absorb",
                    prev_max_asset_id, min_id,
                )
            prev_max_asset_id = max_id

            for raw in page.records:
                rec = api_record_to_listing(raw)
                if rec is not None:
                    yield rec

            if not page.next_link:
                return
            skip += self._page_size
