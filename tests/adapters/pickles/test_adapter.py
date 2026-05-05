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
    # Page 1: 2 records, has next_link. Page 2: 1 new record, no next_link.
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
        adapter = PicklesAdapter(client=client, filters=None)
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


def test_iter_listings_logs_overlap_but_continues(caplog) -> None:
    # Page 2's lowest assetId equals page 1's highest -> overlap warning.
    overlap_page = {
        "@odata.nextLink": None,
        "value": [PAGE["value"][1]],  # same assetId as page1's max
    }
    state = {"calls": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        state["calls"] += 1
        return httpx.Response(200, json=PAGE if state["calls"] == 1 else overlap_page)

    with _client(handler) as client:
        adapter = PicklesAdapter(client=client, filters=None)
        with caplog.at_level("WARNING"):
            records = list(adapter.iter_listings())

    assert any("overlap" in m.lower() for m in caplog.messages)
    assert len(records) == 3  # 2 from page1, 1 from overlap page (dedup at harness)


def test_site_name_constant() -> None:
    assert PicklesAdapter.site_name == "pickles"
