from __future__ import annotations

import pytest
from pydantic import ValidationError

from asset_crawler.types import ListingRecord


def _valid_kwargs() -> dict:
    return {
        "source_site": "pickles",
        "source_listing_id": "abc-123",
        "description": "2018 Toyota Hilux SR 4x4 dual cab",
        "source_categories": ["Salvage stock", "Trucks", "Truck"],
        "source_url": "https://www.pickles.com.au/foo",
        "raw_payload": {"any": "thing"},
    }


def test_valid_record_constructs() -> None:
    rec = ListingRecord(**_valid_kwargs())
    assert rec.source_listing_id == "abc-123"
    assert rec.source_categories == ["Salvage stock", "Trucks", "Truck"]


def test_empty_description_rejected() -> None:
    kwargs = _valid_kwargs() | {"description": ""}
    with pytest.raises(ValidationError):
        ListingRecord(**kwargs)


def test_whitespace_description_rejected() -> None:
    kwargs = _valid_kwargs() | {"description": "   \n  "}
    with pytest.raises(ValidationError):
        ListingRecord(**kwargs)


def test_empty_categories_allowed() -> None:
    kwargs = _valid_kwargs() | {"source_categories": []}
    rec = ListingRecord(**kwargs)
    assert rec.source_categories == []


def test_source_url_optional() -> None:
    kwargs = _valid_kwargs() | {"source_url": None}
    rec = ListingRecord(**kwargs)
    assert rec.source_url is None
