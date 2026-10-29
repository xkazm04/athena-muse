"""The eight style dials and the style presets (personas' dials, as the prototype names them).

A dial's value runs DIAL_MIN..DIAL_MAX and says where it came from: `preset` (a style preset, the
first one until anything else is known), `learned` (from the person's own sent mail) or `you` (the
person set it). Applying a preset changes only the dials the person has not set.
"""

from __future__ import annotations

from athena.contracts import DIAL_MAX, DIAL_MIN, DialSource, StyleDial

# (id, label, the word at DIAL_MIN, the word at DIAL_MAX)
DIALS: tuple[tuple[str, str, str, str], ...] = (
    ("formality", "Formality", "casual", "formal"),
    ("warmth", "Warmth", "cool", "warm"),
    ("humor", "Humour", "none", "playful"),
    ("energy", "Energy", "calm", "lively"),
    ("length", "Length", "short", "long"),
    ("directness", "Directness", "gentle", "direct"),
    ("expressiveness", "Expressiveness", "plain", "vivid"),
    ("detail", "Detail", "light", "thorough"),
)
DIAL_IDS = tuple(d[0] for d in DIALS)

#: Each style preset's value per dial, in DIALS order. The first is where every twin starts.
PRESETS: dict[str, tuple[int, ...]] = {
    "Friendly pro": (3, 4, 2, 3, 3, 3, 3, 2),
    "Brief and direct": (3, 2, 1, 2, 1, 5, 2, 1),
    "Warm storyteller": (2, 5, 3, 4, 4, 2, 5, 4),
}
START = "Friendly pro"


def dials(chosen: dict[str, tuple[int, DialSource]]) -> list[StyleDial]:
    """All eight dials in order: the stored value and source where there is one, else the starting
    preset's."""
    out: list[StyleDial] = []
    for (dial_id, label, low, high), start in zip(DIALS, PRESETS[START], strict=True):
        value, source = chosen.get(dial_id, (start, "preset"))
        out.append(
            {"id": dial_id, "label": label, "low": low, "high": high, "value": value, "source": source}
        )
    return out


def preset_values(name: str) -> dict[str, int]:
    return dict(zip(DIAL_IDS, PRESETS[name], strict=True))


def valid(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and DIAL_MIN <= value <= DIAL_MAX
