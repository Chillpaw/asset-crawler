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
        if page_size <= 0:
            raise ValueError(f"page_size must be > 0, got {page_size}")
        self._client = client
        self._filters = filters
        self._page_size = page_size

    def iter_listings(self) -> Iterator[ListingRecord]:
        skip = 0
        while True:
            page = search_page(
                self._client, filters=self._filters, skip=skip, top=self._page_size
            )
            log.info(
                "pickles page: skip=%d, returned=%d", skip, len(page.records),
            )

            if not page.records:
                return

            for raw in page.records:
                rec = api_record_to_listing(raw)
                if rec is not None:
                    yield rec

            # Pickles' search API never sets @odata.nextLink. A short page
            # signals end-of-data. (Cursor support probed and confirmed absent.)
            if len(page.records) < self._page_size:
                return
            skip += self._page_size
