from __future__ import annotations

import json
from pathlib import Path

import httpx

from asset_crawler.adapters.pickles import PicklesAdapter
from asset_crawler.http_client import PoliteClient, PoliteClientConfig

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures"
PAGE = json.loads((FIXTURE_DIR / "pickles_search_page.json").read_text())


def _client(handler) -> PoliteClient:
    cfg = PoliteClientConfig(
        user_agent="asset-crawler/test (+https://example.com)",
        delay_min_s=0.0, delay_max_s=0.0, retry_initial_s=0.0, retry_max_s=0.0,
    )
    return PoliteClient(config=cfg, transport=httpx.MockTransport(handler))


def test_iter_listings_paginates_and_yields_records() -> None:
    # Page 1: 2 records (a full page at page_size=2). Page 2: 1 record (partial -> stop).
    page1 = dict(PAGE)
    page2 = {
        "@odata.nextLink": None,
        "value": [
            {
                "assetId": "00000000-0000-0000-0000-000000000003",
                "description": "1990 Mack Trident — runs",
                "itemLoB": "salvage",
                "lineOfBusinessUrls": ["salvage"],
                "lineOfBusinesses": ["Salvage stock"],
                "productType": {"title": "Trucks"},
                "assetType": "Truck",
                "eLotId": "EL-99", "lotNumber": "999",
            }
        ],
    }
    state = {"calls": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        state["calls"] += 1
        return httpx.Response(200, json=page1 if state["calls"] == 1 else page2)

    with _client(handler) as client:
        adapter = PicklesAdapter(client=client, filters=None, page_size=2)
        records = list(adapter.iter_listings())

    assert state["calls"] == 2
    assert [r.source_listing_id for r in records] == [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000003",
    ]


def test_iter_listings_skips_blank_descriptions() -> None:
    page = {
        "@odata.nextLink": None,
        "value": [
            {**PAGE["value"][0], "description": "   "},
            PAGE["value"][1],
        ],
    }

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=page)

    with _client(handler) as client:
        adapter = PicklesAdapter(client=client, filters=None)
        records = list(adapter.iter_listings())
    assert len(records) == 1
    assert records[0].source_listing_id == "00000000-0000-0000-0000-000000000002"


def test_site_name_constant() -> None:
    assert PicklesAdapter.site_name == "pickles"
