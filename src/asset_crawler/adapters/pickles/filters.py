from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PicklesFilters:
    line_of_business: list[str] | None = None
    product_types: list[str] | None = None

    def to_odata_filter(self) -> str | None:
        clauses: list[str] = []
        if self.line_of_business:
            clauses.append(_or_clause("itemLoB", self.line_of_business))
        if self.product_types:
            clauses.append(_or_clause("productType/title", self.product_types))
        if not clauses:
            return None
        return " and ".join(clauses)

    def to_dict(self) -> dict[str, Any] | None:
        if not self.line_of_business and not self.product_types:
            return None
        return {
            "line_of_business": list(self.line_of_business or []),
            "product_types": list(self.product_types or []),
        }


def _or_clause(field_name: str, values: list[str]) -> str:
    parts = [f"{field_name} eq '{_escape(v)}'" for v in values]
    return "(" + " or ".join(parts) + ")"


def _escape(v: str) -> str:
    # OData v4: single-quote escaped by doubling.
    return v.replace("'", "''")
