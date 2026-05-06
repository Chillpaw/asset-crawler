from __future__ import annotations

import os
import re

from asset_crawler import __version__

_DEFAULT_CONTACT = "https://github.com/Chillpaw/asset-crawler"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_RE = re.compile(r"^https?://[^\s]+$")


class ContactNotResolved(RuntimeError):
    pass


def resolve_contact() -> str:
    raw = os.environ.get("ASSET_CRAWLER_CONTACT")
    if raw is None:
        raw = _DEFAULT_CONTACT
    elif not raw.strip():
        raise ContactNotResolved(
            "ASSET_CRAWLER_CONTACT is set but empty. "
            "Provide a contact URL or email, or unset the variable."
        )
    if not _URL_RE.match(raw) and not _EMAIL_RE.match(raw):
        raise ContactNotResolved(
            f"ASSET_CRAWLER_CONTACT={raw!r} is not a URL or email. "
            "Set a contact URL or email so site operators can reach you."
        )
    return raw


def build_user_agent(contact: str) -> str:
    return f"asset-crawler/{__version__} (+{contact})"
