from __future__ import annotations

from pathlib import Path

import httpx

from asset_crawler.robots import fetch_robots, is_allowed

FIXTURE = Path(__file__).parent / "fixtures" / "robots_pickles.txt"


def _transport(body: str, status: int = 200) -> httpx.MockTransport:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=body)

    return httpx.MockTransport(handler)


def test_fetch_robots_parses_disallow() -> None:
    body = FIXTURE.read_text()
    robots = fetch_robots("https://www.pickles.com.au", transport=_transport(body))
    assert is_allowed(robots, "/", user_agent="asset-crawler") is True
    assert is_allowed(
        robots, "/api-website/buyer/ms-web-asset-search/v2/api/product/public/search",
        user_agent="asset-crawler",
    ) is False
    assert is_allowed(robots, "/cars/vehicle/foo/itemid-x/lotid-y", user_agent="asset-crawler") is False


def test_fetch_robots_missing_returns_permissive() -> None:
    robots = fetch_robots("https://example.com", transport=_transport("", status=404))
    assert is_allowed(robots, "/anything", user_agent="asset-crawler") is True


def test_robots_check_records_source() -> None:
    body = FIXTURE.read_text()
    robots = fetch_robots("https://www.pickles.com.au", transport=_transport(body))
    assert robots.source_url == "https://www.pickles.com.au/robots.txt"
    assert robots.fetched_ok is True


def test_fetch_robots_5xx_returns_permissive_with_flag() -> None:
    robots = fetch_robots("https://example.com", transport=_transport("", status=500))
    assert robots.fetched_ok is False
    assert is_allowed(robots, "/anything", user_agent="asset-crawler") is True


def test_fetch_robots_connection_error_returns_permissive() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated dns/connect failure")

    robots = fetch_robots(
        "https://example.com",
        transport=httpx.MockTransport(handler),
    )
    assert robots.fetched_ok is False
    assert is_allowed(robots, "/anything", user_agent="asset-crawler") is True


def test_fetch_robots_strips_path_to_host_root() -> None:
    body = FIXTURE.read_text()
    seen_paths: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen_paths.append(req.url.path)
        return httpx.Response(200, text=body)

    robots = fetch_robots(
        "https://www.pickles.com.au/cars/vehicle/foo/",
        transport=httpx.MockTransport(handler),
    )
    assert seen_paths == ["/robots.txt"]
    assert robots.source_url == "https://www.pickles.com.au/robots.txt"
