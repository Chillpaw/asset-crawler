from __future__ import annotations

from asset_crawler.adapters.pickles.url import build_source_url


def test_complete_salvage_record_yields_url() -> None:
    record = {
        "itemLoB": "salvage",
        "assetId": "abc",
        "eLotId": "EL-77",
        "lotNumber": "104",
        "productType": {"title": "Cars"},
    }
    url = build_source_url(record)
    assert url == "https://www.pickles.com.au/damaged-salvage/vehicle/itemid-abc/lotid-EL-77"


def test_falls_back_to_lotnumber_when_elotid_null() -> None:
    record = {
        "itemLoB": "salvage",
        "assetId": "abc",
        "eLotId": None,
        "lotNumber": "104",
        "productType": {"title": "Cars"},
    }
    url = build_source_url(record)
    assert url == "https://www.pickles.com.au/damaged-salvage/vehicle/itemid-abc/lotid-104"


def test_industrial_uses_item_kind() -> None:
    record = {
        "itemLoB": "industrial",
        "assetId": "x",
        "eLotId": "L1",
        "lotNumber": "1",
        "productType": {"title": "Forklifts"},
    }
    url = build_source_url(record)
    assert url == "https://www.pickles.com.au/industrial/item/itemid-x/lotid-L1"


def test_unknown_lob_returns_none() -> None:
    record = {"itemLoB": "mysterylob", "assetId": "x", "eLotId": "L1"}
    assert build_source_url(record) is None


def test_missing_lotid_returns_none() -> None:
    record = {
        "itemLoB": "salvage",
        "assetId": "abc",
        "eLotId": None,
        "lotNumber": None,
        "productType": {"title": "Cars"},
    }
    assert build_source_url(record) is None


def test_missing_assetid_returns_none() -> None:
    record = {"itemLoB": "salvage", "assetId": None, "eLotId": "L1"}
    assert build_source_url(record) is None
