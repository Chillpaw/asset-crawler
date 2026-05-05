from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any

import httpx


log = logging.getLogger(__name__)


class HardStop(RuntimeError):
    """Raised when the politeness policy says: stop, do not retry."""


@dataclass(frozen=True)
class PoliteClientConfig:
    user_agent: str
    delay_min_s: float = 3.0
    delay_max_s: float = 5.0
    retry_initial_s: float = 30.0
    retry_max_s: float = 300.0
    max_retries: int = 3
    request_timeout_s: float = 30.0


_RETRYABLE = {429, 503}


class PoliteClient:
    """Single-concurrency HTTP client with jittered delays, exponential backoff
    on 429/503, and hard-stop on 403/HTML/timeouts."""

    def __init__(
        self,
        config: PoliteClientConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._cfg = config
        self._client = httpx.Client(
            headers={"User-Agent": config.user_agent},
            timeout=config.request_timeout_s,
            transport=transport,
        )
        self._first_request = True

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PoliteClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> dict:
        self._inter_request_sleep()
        attempt = 0
        delay = self._cfg.retry_initial_s
        while True:
            try:
                resp = self._client.get(url, params=params)
            except httpx.TimeoutException as e:
                raise HardStop(f"timeout after {self._cfg.request_timeout_s}s: {e}") from e
            if resp.status_code == 200:
                return self._parse_json_or_hard_stop(resp)
            if resp.status_code == 403:
                raise HardStop(f"403 from {url} — refusing to retry")
            if resp.status_code in _RETRYABLE and attempt < self._cfg.max_retries:
                attempt += 1
                wait = min(delay, self._cfg.retry_max_s)
                log.warning(
                    "retryable %s on %s, attempt %d/%d, sleeping %.1fs",
                    resp.status_code, url, attempt, self._cfg.max_retries, wait,
                )
                time.sleep(wait + random.uniform(0, wait * 0.1))
                delay = delay * 2
                continue
            raise HardStop(f"{resp.status_code} from {url} (retries exhausted or non-retryable)")

    def _inter_request_sleep(self) -> None:
        if self._first_request:
            self._first_request = False
            return
        lo, hi = self._cfg.delay_min_s, self._cfg.delay_max_s
        if hi > 0:
            time.sleep(random.uniform(lo, hi))

    def _parse_json_or_hard_stop(self, resp: httpx.Response) -> dict:
        ctype = resp.headers.get("content-type", "")
        if "html" in ctype.lower() or resp.text.lstrip().startswith("<"):
            raise HardStop(f"HTML response when JSON expected from {resp.request.url}")
        try:
            return resp.json()
        except ValueError as e:
            raise HardStop(f"non-JSON 200 response from {resp.request.url}: {e}") from e
