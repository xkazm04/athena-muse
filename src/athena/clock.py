"""Time and ids, in one place so tests can pin them."""

from __future__ import annotations

import secrets
import time
from datetime import UTC, datetime


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def monotonic_ms() -> int:
    """A steady clock in milliseconds, for how long something took (never a wall-clock time). Read it
    through this module (`clock.monotonic_ms()`) so a test can pin it."""
    return int(time.monotonic() * 1000)


def mint(prefix: str) -> str:
    """`<prefix>` + twelve hex digits."""
    return prefix + secrets.token_hex(6)
