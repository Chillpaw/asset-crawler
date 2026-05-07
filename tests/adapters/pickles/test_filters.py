from __future__ import annotations

from asset_crawler.adapters.pickles.filters import PicklesFilters


def test_empty_filters_emit_none() -> None:
    f = PicklesFilters()
    assert f.to_odata_filter() is None


def test_single_lob() -> None:
    f = PicklesFilters(line_of_business=["industrial"])
    expr = f.to_odata_filter()
    assert expr == "(itemLoB eq 'industrial')"


def test_multi_lob_uses_or() -> None:
    f = PicklesFilters(line_of_business=["industrial", "salvage"])
    expr = f.to_odata_filter()
    assert expr == "(itemLoB eq 'industrial' or itemLoB eq 'salvage')"


def test_combined_lob_and_product_type() -> None:
    f = PicklesFilters(line_of_business=["industrial"], product_types=["Forklifts"])
    expr = f.to_odata_filter()
    assert expr == "(itemLoB eq 'industrial') and (productType/title eq 'Forklifts')"


def test_to_dict_for_audit() -> None:
    f = PicklesFilters(line_of_business=["industrial"], product_types=["Forklifts"])
    assert f.to_dict() == {
        "line_of_business": ["industrial"],
        "product_types": ["Forklifts"],
    }
    empty = PicklesFilters()
    assert empty.to_dict() is None  # empty filter audited as NULL


def test_single_quote_escaped_in_filter() -> None:
    f = PicklesFilters(line_of_business=["O'Reilly"])
    assert f.to_odata_filter() == "(itemLoB eq 'O''Reilly')"


def test_parse_cli_maps_args() -> None:
    from asset_crawler.adapters.pickles.filters import parse_cli
    assert parse_cli(lob=["salvage"], product_type=["Trucks"]) == PicklesFilters(
        line_of_business=["salvage"], product_types=["Trucks"]
    )
    assert parse_cli(lob=None, product_type=None) == PicklesFilters()
