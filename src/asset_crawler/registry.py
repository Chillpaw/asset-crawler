from __future__ import annotations

from collections.abc import Callable
from typing import Any


class UnknownAdapterError(KeyError):
    pass


_REGISTRY: dict[str, Callable[..., Any]] = {}


def register_adapter(site_name: str, factory: Callable[..., Any]) -> None:
    _REGISTRY[site_name] = factory


def get_adapter_factory(site_name: str) -> Callable[..., Any]:
    if site_name not in _REGISTRY:
        raise UnknownAdapterError(f"adapter not registered: {site_name}")
    return _REGISTRY[site_name]


def available_sites() -> list[str]:
    return sorted(_REGISTRY)


# Side-effect registration of built-in adapters.
def _register_builtin() -> None:
    from asset_crawler.adapters.pickles import PicklesAdapter
    register_adapter(PicklesAdapter.site_name, PicklesAdapter)


_register_builtin()
