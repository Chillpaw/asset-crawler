from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from asset_crawler.adapters.pickles.filters import PicklesFilters
from asset_crawler.http_client import PoliteClient

SEARCH_URL = (
    "https://www.pickles.com.au/api-website/buyer/ms-web-asset-search/v2/api/product/public/search"
)
DEFAULT_PAGE_SIZE = 50

# TODO(plan-task-9): probe whether this endpoint supports a true cursor
# (e.g. `nextPageToken` or skiptoken). If found, prefer it over offset
# to avoid the live-catalogue offset-shift problem.


@dataclass(frozen=True)
class PicklesPage:
    records: list[dict[str, Any]]
    next_link: str | None


def search_page(
    client: PoliteClient,
    *,
    filters: PicklesFilters | None,
    skip: int,
    top: int = DEFAULT_PAGE_SIZE,
) -> PicklesPage:
    params: dict[str, str | int] = {
        "$top": top,
        "$skip": skip,
        "$orderby": "assetId asc",
    }
    if filters is not None:
        expr = filters.to_odata_filter()
        if expr is not None:
            params["$filter"] = expr

    body = client.get_json(SEARCH_URL, params=params)
    value = body.get("value")
    if value is None:
        records: list[dict[str, Any]] = []
    elif not isinstance(value, list):
        raise ValueError(
            f"OData response field 'value' expected list, got {type(value).__name__!r}"
        )
    else:
        records = value
    return PicklesPage(
        records=records,
        next_link=body.get("@odata.nextLink"),
    )
