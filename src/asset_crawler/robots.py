from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import httpx


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RobotsCheck:
    source_url: str
    fetched_ok: bool
    parser: RobotFileParser


def fetch_robots(
    base_url: str,
    *,
    transport: httpx.BaseTransport | None = None,
    timeout_s: float = 10.0,
) -> RobotsCheck:
    """Fetch and parse robots.txt. Missing or 5xx responses default to permissive
    (per-line industry convention) but the result records `fetched_ok=False`."""
    robots_url = urljoin(base_url.rstrip("/") + "/", "robots.txt")
    parser = RobotFileParser()
    try:
        with httpx.Client(transport=transport, timeout=timeout_s) as client:
            resp = client.get(robots_url)
    except httpx.HTTPError as e:
        log.warning("could not fetch %s: %s; treating as permissive", robots_url, e)
        parser.parse([])
        return RobotsCheck(source_url=robots_url, fetched_ok=False, parser=parser)

    if resp.status_code == 200:
        parser.parse(resp.text.splitlines())
        return RobotsCheck(source_url=robots_url, fetched_ok=True, parser=parser)
    if 400 <= resp.status_code < 500:
        # 4xx (incl. 404) → permissive per RFC 9309
        parser.parse([])
        return RobotsCheck(source_url=robots_url, fetched_ok=True, parser=parser)
    # 5xx → permissive but record failure
    parser.parse([])
    return RobotsCheck(source_url=robots_url, fetched_ok=False, parser=parser)


def is_allowed(robots: RobotsCheck, path: str, *, user_agent: str) -> bool:
    return robots.parser.can_fetch(user_agent, path)
