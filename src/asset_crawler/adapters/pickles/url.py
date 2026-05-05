from __future__ import annotations

from typing import Any

_BASE = "https://www.pickles.com.au"

# Known LoB → URL slug. Add entries here as new LoBs appear in the wild.
# An unknown LoB returns None for source_url, which is non-load-bearing.
_LOB_URL_SLUG: dict[str, str] = {
    "salvage": "damaged-salvage",
    "industrial": "industrial",
    "trucks": "trucks",
    "cars": "used-cars",
    "general": "general-goods",
}

# Asset kind segment of the path. Vehicles use /vehicle/, everything else /item/.
_VEHICLE_LOBS = {"salvage", "cars"}


def build_source_url(record: dict[str, Any]) -> str | None:
    asset_id = record.get("assetId")
    item_lob = record.get("itemLoB")
    lot_id = record.get("eLotId") or record.get("lotNumber")

    if not asset_id or not item_lob or not lot_id:
        return None

    slug = _LOB_URL_SLUG.get(item_lob)
    if slug is None:
        return None

    kind = "vehicle" if item_lob in _VEHICLE_LOBS else "item"
    return f"{_BASE}/{slug}/{kind}/itemid-{asset_id}/lotid-{lot_id}"
