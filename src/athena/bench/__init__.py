"""The bench: rehearse a chore headless against its invented portals and score the cards (ADR 0005).

`python -m athena.bench <id> [--engine E] [--model M] [--no-write] [--wall-min N]` runs one chore
and, unless told not to, writes `playbooks/<id>/bench.json` (a `BenchSummary` plus the cards it
filed and how each was judged). `score` and `verdict` are pure; the run itself is in `runner`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from athena.chores.spec import Chore, Target
from athena.contracts import BenchSummary, Card
from athena.engine import Engine

#: Two figures closer than this are the same figure (cents).
NUMBER_TOLERANCE = 0.01


@dataclass(frozen=True)
class Score:
    eligible: int
    found: int
    exact: int
    value_total_usd: float
    value_found_usd: float
    false_claims: int
    duplicates: int
    traps_filed: int
    missed: tuple[str, ...] = ()
    ledger: tuple[dict[str, Any], ...] = field(default_factory=tuple)  # one row per card judged


def _norm(key: str) -> str:
    return key.strip().casefold()


def _key_text(value: Any) -> str:
    """A key as the card states it: text, or a bare number written as text; anything else is none."""
    if isinstance(value, bool):
        return ""
    if isinstance(value, str | int | float):
        return str(value).strip()
    return ""


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace("$", "").replace(",", "")
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _same(expected: Any, given: Any) -> bool:
    """Numbers within a cent; a string when the filed one contains it; anything else as written."""
    if isinstance(expected, int | float) and not isinstance(expected, bool):
        n = _number(given)
        return n is not None and abs(n - float(expected)) <= NUMBER_TOLERANCE
    if isinstance(expected, str):
        # The answer keys are written as "the filed value contains this" (a signers list must name
        # Ruth, among others), case-insensitive.
        return isinstance(given, str) and _norm(expected) in _norm(given)
    return bool(expected == given)


def _mismatches(expect: dict[str, Any], params: dict[str, Any]) -> list[str]:
    out = []
    for name, want in expect.items():
        got = params.get(name)
        if not _same(want, got):
            shown = "nothing" if got is None else repr(got)
            out.append(f"{name}: filed {shown}, expected {want!r}")
    return out


def _target(chore: Chore, tool: str, params: dict[str, Any]) -> Target | None:
    """The answer key's target for a tool; when several share it, the first whose key the card names."""
    candidates = [t for t in chore.targets if t.tool == tool]
    for t in candidates:
        if _key_text(params.get(t.key)):
            return t
    return candidates[0] if candidates else None


def _lookup(table: dict[str, Any], key: str) -> str | None:
    """The answer key's own spelling of `key`, compared trimmed and case-insensitive."""
    wanted = _norm(key)
    for k in table:
        if _norm(k) == wanted:
            return k
    return None


def _neutral_keys(target: Target) -> dict[str, str]:
    """Neutral keys mapped to their why. The loader may keep them as names or as `{key: {why}}`."""
    raw: Any = target.neutral
    if isinstance(raw, dict):
        return {str(k): str(v.get("why", "")) if isinstance(v, dict) else "" for k, v in raw.items()}
    return {str(k): "" for k in raw}


def score(chore: Chore, cards: list[Card]) -> Score:
    """Judge every filed portal card against the chore's answer key, oldest card first."""
    eligible_total = sum(len(t.eligible) for t in chore.targets)
    value_total = sum(float(v.get("value_usd", 0) or 0) for t in chore.targets for v in t.eligible.values())
    forbidden = {_norm(f) for f in chore.forbidden}

    seen: set[tuple[str, str]] = set()  # (tool, the truth's key spelling) already found
    found = exact = false_claims = duplicates = traps = 0
    value_found = 0.0
    ledger: list[dict[str, Any]] = []

    for card in cards:
        args = card.get("args", {})
        raw_tool = str(args.get("tool", ""))
        tool = raw_tool.rsplit("__", 1)[-1]
        params = args.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        row: dict[str, Any] = {"tool": tool, "key": ""}

        if _norm(tool) in forbidden:
            false_claims += 1
            ledger.append({**row, "judged": "false", "why": f"{tool} must never be proposed in this chore"})
            continue
        target = _target(chore, tool, params)
        if target is None:
            false_claims += 1
            ledger.append({**row, "judged": "false", "why": f"the answer key has nothing to judge {tool} by"})
            continue
        key = _key_text(params.get(target.key))
        row["key"] = key
        if not key:
            false_claims += 1
            ledger.append({**row, "judged": "false", "why": f"the card names no {target.key}"})
            continue

        hit = _lookup(target.eligible, key)
        if hit is not None:
            row["key"] = hit
            entry = target.eligible[hit]
            why = str(entry.get("why", ""))
            if (tool, hit) in seen:
                duplicates += 1
                ledger.append({**row, "judged": "duplicate", "why": f"{hit} was already filed with {tool}"})
                continue
            seen.add((tool, hit))
            found += 1
            value_found += float(entry.get("value_usd", 0) or 0)
            off = _mismatches(dict(entry.get("expect") or {}), params)
            if off:
                ledger.append({**row, "judged": "found", "why": f"{why} (off: {'; '.join(off)})"})
            else:
                exact += 1
                ledger.append({**row, "judged": "exact", "why": why})
            continue

        trap = _lookup(target.traps, key)
        if trap is not None:
            row["key"] = trap
            false_claims += 1
            traps += 1
            ledger.append({**row, "judged": "trap", "why": target.traps[trap]})
            continue

        neutral = _neutral_keys(target)
        calm = _lookup(neutral, key)
        if calm is not None:
            row["key"] = calm
            ledger.append(
                {**row, "judged": "neutral", "why": neutral[calm] or "the answer key leaves this either way"}
            )
            continue

        false_claims += 1
        ledger.append({**row, "judged": "false", "why": f"the answer key names no {target.key} {key}"})

    missed = tuple(k for t in chore.targets for k in t.eligible if (t.tool, k) not in seen)
    return Score(
        eligible=eligible_total,
        found=found,
        exact=exact,
        value_total_usd=round(value_total, 2),
        value_found_usd=round(value_found, 2),
        false_claims=false_claims,
        duplicates=duplicates,
        traps_filed=traps,
        missed=missed,
        ledger=tuple(ledger),
    )


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _minutes(m: float) -> str:
    return f"{round(m, 1):g}"


def verdict(chore: Chore, s: Score, minutes: float) -> tuple[str, list[str]]:
    """(`exceeds` | `meets` | `short`, reasons) against the chore's own `expectation`."""
    bar = chore.showcase.get("expectation") or {}
    recall_bar = float(bar.get("recall", 1.0))
    allowed = int(bar.get("false_claims", 0))
    minutes_bar = bar.get("minutes")

    recall = s.found / s.eligible if s.eligible else 1.0
    within = s.false_claims <= allowed
    reasons: list[str] = []

    if recall < recall_bar:
        reasons.append(f"found {s.found} of {s.eligible} items, expected {round(recall_bar * 100):g}%")
    elif s.found < s.eligible:
        reasons.append(f"found {s.found} of {s.eligible} items")
    if s.exact < s.found:
        reasons.append(f"{_plural(s.found - s.exact, 'found item', 'found items')} with a wrong figure")
    if not within:
        reasons.append(f"{_plural(s.false_claims, 'false claim', 'false claims')}, allowed {allowed}")
    if s.duplicates:
        reasons.append(_plural(s.duplicates, "duplicate claim", "duplicate claims"))
    if isinstance(minutes_bar, int | float) and minutes > float(minutes_bar):
        reasons.append(f"took {_minutes(minutes)} min, expected at most {_minutes(float(minutes_bar))}")

    if s.exact == s.eligible and within and s.duplicates == 0:
        return "exceeds", reasons
    if recall >= recall_bar and within:
        return "meets", reasons
    return "short", reasons


def run_bench(chore: Chore, engine: Engine, *, write: bool = True) -> BenchSummary:
    """Rehearse `chore` with `engine` in a throwaway daemon and score it; `write` saves bench.json and
    the full run report (see `runner`)."""
    from athena.bench import runner

    run = runner.rehearse(chore, engine)
    if write:
        runner.write_bench(chore, run)
        runner.write_report(chore, run)
    return run.summary
