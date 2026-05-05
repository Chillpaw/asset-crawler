from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from asset_crawler.adapters.pickles.api import SEARCH_URL, search_page
from asset_crawler.adapters.pickles.filters import PicklesFilters
from asset_crawler.http_client import PoliteClient, PoliteClientConfig


FIXTURE = json.loads((Path(__file__).parent.parent.parent / "fixtures" / "pickles_search_page.json").read_text())


def _client(handler) -> PoliteClient:
    cfg = PoliteClientConfig(
        user_agent="asset-crawler/test (+https://example.com)",
        delay_min_s=0.0, delay_max_s=0.0, retry_initial_s=0.0, retry_max_s=0.0,
    )
    return PoliteClient(config=cfg, transport=httpx.MockTransport(handler))


def test_search_page_returns_records_and_next_link() -> None:
    seen_params: list[dict] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen_params.append(dict(req.url.params))
        return httpx.Response(200, json=FIXTURE)

    with _client(handler) as client:
        page = search_page(client, filters=None, skip=0, top=50)

    assert len(page.records) == 2
    assert page.records[0]["assetId"] == "00000000-0000-0000-0000-000000000001"
    assert page.next_link is not None
    assert seen_params[0]["$top"] == "50"
    assert seen_params[0]["$skip"] == "0"
    assert seen_params[0]["$orderby"] == "assetId asc"
    assert "$filter" not in seen_params[0]


def test_search_page_includes_filter_when_present() -> None:
    seen_params: list[dict] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen_params.append(dict(req.url.params))
        return httpx.Response(200, json={"value": [], "@odata.nextLink": None})

    with _client(handler) as client:
        search_page(
            client,
            filters=PicklesFilters(line_of_business=["industrial"]),
            skip=0, top=50,
        )

    assert seen_params[0]["$filter"] == "(itemLoB eq 'industrial')"


def test_search_page_targets_correct_url() -> None:
    seen_urls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen_urls.append(str(req.url).split("?")[0])
        return httpx.Response(200, json={"value": [], "@odata.nextLink": None})

    with _client(handler) as client:
        search_page(client, filters=None, skip=0, top=50)

    assert seen_urls == [SEARCH_URL]
