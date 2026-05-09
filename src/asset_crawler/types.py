from __future__ import annotations

from collections.abc import Iterator
from typing import Any, ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ListingRecord(BaseModel):
    """The uniform per-listing payload an adapter yields. Timestamps are
    added by the harness, not the adapter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_site: str = Field(min_length=1)
    source_listing_id: str = Field(min_length=1)
    description: str
    source_categories: list[str]
    source_url: str | None
    raw_payload: dict[str, Any]

    @field_validator("description")
    @classmethod
    def _description_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("description must not be blank")
        return v


@runtime_checkable
class SiteAdapter(Protocol):
    """Adapters are pure: no DB, no rate limiting, no timestamps. Yield
    `ListingRecord` objects until exhausted; the harness owns everything else."""

    site_name: ClassVar[str]

    def iter_listings(self) -> Iterator[ListingRecord]: ...
