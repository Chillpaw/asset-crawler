from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest


@pytest.fixture()
def memdb() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
