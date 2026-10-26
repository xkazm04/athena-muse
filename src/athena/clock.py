"""Time and ids, in one place so tests can pin them."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def mint(prefix: str) -> str:
    """`<prefix>` + twelve hex digits."""
    return prefix + secrets.token_hex(6)
