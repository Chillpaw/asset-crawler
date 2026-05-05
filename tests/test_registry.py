from __future__ import annotations

import pytest

from asset_crawler.registry import (
    UnknownAdapterError,
    available_sites,
    get_adapter_factory,
    register_adapter,
)


def test_register_and_get() -> None:
    sentinel = object()
    register_adapter("test-site", lambda **kw: sentinel)
    factory = get_adapter_factory("test-site")
    assert factory() is sentinel


def test_unknown_site_raises() -> None:
    with pytest.raises(UnknownAdapterError, match="not-real"):
        get_adapter_factory("not-real")


def test_pickles_is_registered_on_import() -> None:
    # Importing the package side-effect-registers pickles.
    import asset_crawler.registry  # noqa: F401
    assert "pickles" in available_sites()
