from __future__ import annotations

from typing import Any

_BASE = "https://www.pickles.com.au"

# Known LoB → URL slug. salvage/industrial confirmed against fixtures;
# trucks/cars/general are best-effort guesses to verify when those LoBs first
# appear in real responses. An unknown LoB returns None (non-load-bearing).
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
    # TODO: urllib.parse.quote(...) if Pickles ever emits IDs containing /, %, or spaces.
    return f"{_BASE}/{slug}/{kind}/itemid-{asset_id}/lotid-{lot_id}"
