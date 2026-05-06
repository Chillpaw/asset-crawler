from __future__ import annotations

import pytest

from asset_crawler.config import (
    ContactNotResolved,
    build_user_agent,
    resolve_contact,
)


def test_resolve_contact_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASSET_CRAWLER_CONTACT", "https://example.com/me")
    assert resolve_contact() == "https://example.com/me"


def test_resolve_contact_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASSET_CRAWLER_CONTACT", "me@example.com")
    assert resolve_contact() == "me@example.com"


def test_resolve_contact_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASSET_CRAWLER_CONTACT", raising=False)
    contact = resolve_contact()
    assert contact.startswith("https://github.com/")


def test_resolve_contact_rejects_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASSET_CRAWLER_CONTACT", "not-a-url-or-email")
    with pytest.raises(ContactNotResolved):
        resolve_contact()


def test_build_user_agent() -> None:
    ua = build_user_agent("https://example.com/me")
    assert ua.startswith("asset-crawler/")
    assert "https://example.com/me" in ua
