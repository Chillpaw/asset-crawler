from __future__ import annotations

import logging
from typing import Any

from asset_crawler.adapters.pickles.url import build_source_url
from asset_crawler.types import ListingRecord

log = logging.getLogger(__name__)

SITE = "pickles"


def api_record_to_listing(record: dict[str, Any]) -> ListingRecord | None:
    """Map a Pickles search-API record to a ListingRecord. Returns None for
    records the harness should skip (blank description). Validation other
    than blank-description is the harness's responsibility."""
    description = (record.get("description") or "").strip()
    if not description:
        return None

    asset_id = record["assetId"]
    lob_label = _resolve_lob_label(record)
    categories = _ordered_categories(lob_label, record)

    return ListingRecord(
        source_site=SITE,
        source_listing_id=str(asset_id),
        description=description,
        source_categories=categories,
        source_url=build_source_url(record),
        raw_payload=record,
    )


def _resolve_lob_label(record: dict[str, Any]) -> str:
    item_lob = record.get("itemLoB", "")
    urls = record.get("lineOfBusinessUrls") or []
    labels = record.get("lineOfBusinesses") or []
    for i, url in enumerate(urls):
        if url == item_lob and i < len(labels):
            return labels[i]
    log.warning(
        "lob_label fallback: itemLoB=%r not found in lineOfBusinessUrls=%r",
        item_lob, urls,
    )
    return item_lob


def _ordered_categories(lob_label: str, record: dict[str, Any]) -> list[str]:
    pt = ((record.get("productType") or {}).get("title") or "").strip()
    asset_type = (record.get("assetType") or "").strip()
    return [c for c in (lob_label, pt, asset_type) if c]
