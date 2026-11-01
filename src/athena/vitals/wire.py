"""A peer's vitals as they arrive on the wire (ADR 0017, vitals)."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from athena.vitals import TASKS_RUNNING_CAP, VitalsView

__all__ = ["clean_view"]

_NUMBER_KEYS = ("cpu_pct", "ram_pct")
_INT_KEYS = ("cores", "ram_total_mb", "ram_free_mb", "battery_pct", "disk_free_mb")
_ROOMS = ("ok", "tight", "full")
#: The longest ``held`` sentence or GPU name a peer's view may carry here.
_TEXT_CAP = 300


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return None
    return float(value)


def _int(value: Any) -> int | None:
    number = _num(value)
    return None if number is None else int(number)


def _text(value: Any) -> str | None:
    return value[:_TEXT_CAP] if isinstance(value, str) else None


def clean_view(raw: Any) -> VitalsView | None:
    """A peer's ``vitals`` off its hello, rebuilt key by key into :data:`VitalsView`.

    The peer holds a token this PC minted, but its answer is still data: every key is re-typed, an
    unknown key is dropped, a missing one is ``None``, text is cut, and anything that is not an
    object is ``None``. ``runs`` and ``sleep`` are always ``None`` here.
    """
    if not isinstance(raw, Mapping):
        return None
    gpus_raw = raw.get("gpus")
    gpus: list[Any] | None = None
    if isinstance(gpus_raw, list):
        gpus = [
            {
                "name": _text(gpu.get("name")) or "GPU",
                "util_pct": _num(gpu.get("util_pct")),
                "vram_total_mb": _int(gpu.get("vram_total_mb")),
                "vram_used_mb": _int(gpu.get("vram_used_mb")),
            }
            for gpu in gpus_raw[:8]
            if isinstance(gpu, Mapping)
        ]
    power = raw.get("power")
    room = raw.get("room")
    slots = _int(raw.get("slots"))
    view: dict[str, Any] = {
        "at": _text(raw.get("at")) or "",
        **{key: _num(raw.get(key)) for key in _NUMBER_KEYS},
        **{key: _int(raw.get(key)) for key in _INT_KEYS},
        "gpus": gpus,
        "power": power if power in ("mains", "battery") else None,
        "room": room if room in _ROOMS else None,
        "slots": 0 if slots is None else max(0, min(TASKS_RUNNING_CAP, slots)),
        "held": _text(raw.get("held")),
        "runs": None,
        "sleep": None,
    }
    ordered = {key: view[key] for key in VitalsView.__annotations__}
    return ordered  # type: ignore[return-value]
