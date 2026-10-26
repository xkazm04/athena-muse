"""Press prices (dev.meta.ai/docs/pricing-rate-limits, 2026-10-24), USD per 1M tokens. Estimates only."""

from __future__ import annotations

PRICES: dict[str, tuple[float, float]] = {
    "muse-spark-1.1": (1.25, 4.25),
    "muse-spark-1.2": (1.25, 4.25),
    "muse-spark-1.3": (1.25, 4.25),
    "muse-wonder-1.0": (4.00, 20.00),
}


def estimate(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """None when the model is unlisted: unpriced, never guessed."""
    row = PRICES.get(model)
    if row is None:
        return None
    return round((input_tokens * row[0] + output_tokens * row[1]) / 1_000_000, 8)
