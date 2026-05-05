from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from asset_crawler.http_client import (
    HardStop,
    PoliteClient,
    PoliteClientConfig,
)


def _client(handler: Callable[[httpx.Request], httpx.Response], **cfg) -> PoliteClient:
    config = PoliteClientConfig(
        user_agent="asset-crawler/test (+https://example.com)",
        delay_min_s=0.0,  # tests don't want to actually sleep
        delay_max_s=0.0,
        retry_initial_s=0.0,
        retry_max_s=0.0,
        max_retries=2,
        **cfg,
    )
    transport = httpx.MockTransport(handler)
    return PoliteClient(config=config, transport=transport)


def test_get_json_returns_parsed_body() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "n": 1})

    client = _client(handler)
    body = client.get_json("https://example.com/api")
    assert body == {"ok": True, "n": 1}


def test_user_agent_sent() -> None:
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.headers["user-agent"])
        return httpx.Response(200, json={})

    client = _client(handler)
    client.get_json("https://example.com/api")
    assert seen == ["asset-crawler/test (+https://example.com)"]


def test_403_hard_stops() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    client = _client(handler)
    with pytest.raises(HardStop, match="403"):
        client.get_json("https://example.com/api")


def test_429_retries_then_succeeds() -> None:
    state = {"calls": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        state["calls"] += 1
        if state["calls"] < 2:
            return httpx.Response(429, text="slow down")
        return httpx.Response(200, json={"ok": True})

    client = _client(handler)
    body = client.get_json("https://example.com/api")
    assert body == {"ok": True}
    assert state["calls"] == 2


def test_429_exhausts_retries_and_hard_stops() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="slow down")

    client = _client(handler)
    with pytest.raises(HardStop, match="retries exhausted"):
        client.get_json("https://example.com/api")


def test_html_when_json_expected_hard_stops() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html><body>cloudflare challenge</body></html>",
            headers={"content-type": "text/html"},
        )

    client = _client(handler)
    with pytest.raises(HardStop, match="HTML"):
        client.get_json("https://example.com/api")


def test_500_retries_but_408_hard_stops() -> None:
    # 503 retried; 408 (request timeout) is non-retryable in our policy
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(408, text="timeout")

    client = _client(handler)
    with pytest.raises(HardStop, match="408"):
        client.get_json("https://example.com/api")
