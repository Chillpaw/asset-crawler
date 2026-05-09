from __future__ import annotations

from asset_crawler.adapters.pickles.mapping import api_record_to_listing


def _base() -> dict:
    return {
        "assetId": "00000000-0000-0000-0000-000000000001",
        "description": "2018 Toyota Hilux SR 4x4 dual cab — engine no compression",
        "itemLoB": "salvage",
        "lineOfBusinessUrls": ["salvage", "industrial"],
        "lineOfBusinesses": ["Salvage stock", "Industrial"],
        "productType": {"title": "Trucks"},
        "assetType": "Truck",
        "eLotId": "ABC-77",
        "lotNumber": "104",
    }


def test_full_record_maps_correctly() -> None:
    rec = api_record_to_listing(_base())
    assert rec.source_site == "pickles"
    assert rec.source_listing_id == "00000000-0000-0000-0000-000000000001"
    assert rec.description.startswith("2018 Toyota Hilux")
    assert rec.source_categories == ["Salvage stock", "Trucks", "Truck"]


def test_lob_label_falls_back_to_raw_when_unmatched() -> None:
    raw = _base() | {
        "itemLoB": "weirdlob",
        "lineOfBusinessUrls": ["salvage"],
        "lineOfBusinesses": ["Salvage stock"],
    }
    rec = api_record_to_listing(raw)
    assert rec.source_categories[0] == "weirdlob"


def test_empty_intermediate_fields_dropped() -> None:
    raw = _base() | {"productType": {"title": ""}}
    rec = api_record_to_listing(raw)
    assert rec.source_categories == ["Salvage stock", "Truck"]


def test_missing_producttype_dropped() -> None:
    raw = _base()
    raw.pop("productType")
    rec = api_record_to_listing(raw)
    assert rec.source_categories == ["Salvage stock", "Truck"]


def test_raw_payload_preserved_verbatim() -> None:
    raw = _base() | {"someExtraField": [1, 2, 3]}
    rec = api_record_to_listing(raw)
    assert rec.raw_payload == raw


def test_blank_description_returns_none() -> None:
    raw = _base() | {"description": "   "}
    assert api_record_to_listing(raw) is None
