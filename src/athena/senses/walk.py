"""The walk sense: a weekly walk of the room, filmed, to counts, promises and change checks.

A count is the number of DISTINCT tracks the segmenter followed for a prompt, never the frames that
show them, cited at the best frame of the best track. Promises come from the transcript by a plain
classifier a person can check by eye, and only from a walk whose consent notice was recorded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from athena.contracts import ProofRow, SenseName
from athena.senses.contract import SenseContext, SenseOutput, proof
from athena.senses.paper import best_segment, box_list

DAYS = "monday|tuesday|wednesday|thursday|friday|saturday|sunday"
MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
NUMBER_WORDS = "one|two|three|four|five|six|seven|eight|nine|ten|a|half a"

#: A price said out loud: a dollar amount, or work said to cost nothing.
PRICE = re.compile(r"\$\s?\d|\b\d[\d,.]*\s+dollars\b|\bno charge\b|\bfree of charge\b|\bat no cost\b", re.I)
#: A time said out loud: a weekday, a date, next week, or a number of days.
TIME = re.compile(
    rf"\b({DAYS})\b|\b(the\s+)?\d{{1,2}}(st|nd|rd|th)\b|\b({MONTHS})\s+\d{{1,2}}\b|\bnext week\b|\btomorrow\b"
    rf"|\b(\d+|{NUMBER_WORDS})\s+(more\s+)?days?\b",
    re.I,
)
#: Words that commit the speaker to something.
COMMIT = re.compile(
    r"\b(i'll|i will|we'll|we will|i'm going to|we're going to|should be here|will be)\b", re.I
)
#: Words that change the scope of the work.
CHANGE = re.compile(r"\b(upcharge|change order|swap|instead|upgrade|move|moving|relocate|extra|add)\b", re.I)


@dataclass(frozen=True)
class Promise:
    mentions_price: bool
    mentions_days: bool
    mentions_change: bool
    why: str


def classify(text: str) -> Promise | None:
    """A promise is a statement (not a question) that commits, names a price, or names a time.

    The reason is kept so a person can see why a line was taken for a promise.
    """
    if text.strip().endswith("?"):
        return None
    price, when, commit = bool(PRICE.search(text)), bool(TIME.search(text)), bool(COMMIT.search(text))
    if not (price or when or commit):
        return None
    why = ", ".join(
        w for w, on in (("commits", commit), ("names a price", price), ("names a time", when)) if on
    )
    return Promise(price, when, bool(CHANGE.search(text)), why)


def vague_change(change: dict[str, Any]) -> list[str]:
    """Why a change order cannot be signed as written: each missing or unusable term, in plain words."""
    reasons: list[str] = []
    price = change.get("price_usd")
    if price is None or price == "":
        reasons.append("no price")
    elif isinstance(price, bool) or not isinstance(price, int | float):
        reasons.append("price not a number")
    days = change.get("days")
    if days is None or days == "" or isinstance(days, bool) or not isinstance(days, int | float):
        reasons.append("no days")
    if not change.get("quote_line"):
        reasons.append("no quote line")
    return reasons


class WalkSense:
    name: SenseName = "walk"

    def build(self, ctx: SenseContext) -> SenseOutput:
        counts: list[dict[str, Any]] = []
        promises: list[dict[str, Any]] = []
        asked: list[str] = []
        for item in ctx.items("walk", "video"):
            p = item.params
            week = int(p.get("week") or 0)
            for prompt, quote_line in (p.get("count") or {}).items():
                segments, usage = ctx.segmenter.segment(item, str(prompt))
                ctx.record("walk", "segmenter", item.id, usage)
                by_track: dict[str, list[Any]] = {}
                for s in segments:
                    if s.track_id:
                        by_track.setdefault(s.track_id, []).append(s)
                row: dict[str, Any] = {"week": week, "media_id": item.id, "item": str(prompt)}
                row |= {"quote_line": str(quote_line), "count": len(by_track)}
                if by_track:
                    best = best_segment([best_segment(segs) for segs in by_track.values()])
                    row |= {"frame": best.frame, "box": box_list(best.box), "track_id": best.track_id}
                counts.append(row)
            if not p.get("consent_recorded"):
                asked.append(f"{item.id}.consent")  # its counts stand; its words are not used
                continue
            transcript, usage = ctx.transcriber.transcribe(item)
            ctx.record("walk", "transcriber", item.id, usage)
            roles = {str(k): str(v) for k, v in (p.get("speakers") or {}).items()}
            for t in transcript.turns:
                found = classify(t.text)
                if found is None:
                    continue
                promises.append(
                    {
                        "promise_id": f"{item.id}@{t.start_s:g}",
                        "week": week,
                        "media_id": item.id,
                        "second": t.start_s,
                        "end_s": t.end_s,
                        "speaker": roles.get(t.speaker, t.speaker),
                        "text": t.text,
                        "mentions_price": found.mentions_price,
                        "mentions_days": found.mentions_days,
                        "mentions_change": found.mentions_change,
                        "why": found.why,
                    }
                )
        checks = []
        for change in ctx.tables.get("change_orders", []):
            reasons = vague_change(change)
            check: dict[str, Any] = {"change_id": str(change["change_id"]), "signable": not reasons}
            if reasons:
                check["reasons"] = reasons
            checks.append(check)
        tables = {"walk_counts": counts, "walk_promises": promises, "change_checks": checks}
        return SenseOutput("walk", tables, tuple(asked))

    def prove(self, ctx: SenseContext, out: SenseOutput, key: dict[str, Any]) -> list[ProofRow]:
        k = key.get("walk") or {}
        rows: list[ProofRow] = []

        # F2 / F2d: each (walk, item) count against the key; extra objects over the key's total.
        truth = [
            (mid, item, int(n)) for mid, items in (k.get("counts") or {}).items() for item, n in items.items()
        ]
        got = {
            (str(r["media_id"]), str(r["item"])): int(r["count"]) for r in out.tables.get("walk_counts", [])
        }
        exact = sum(1 for mid, item, n in truth if got.get((mid, item)) == n)
        over = sum(max(0, got.get((mid, item), 0) - n) for mid, item, n in truth)
        total = sum(n for _, _, n in truth)
        rows.append(
            proof(
                "walk",
                "F2",
                "Is each item counted right on each walk?",
                0.90,
                ">=",
                len(truth),
                exact / len(truth) if truth else None,
                f"{exact} of {len(truth)} walk-item counts equal the key",
            )
        )
        rows.append(
            proof(
                "walk",
                "F2d",
                "How often is one object counted twice?",
                0.05,
                "<=",
                total,
                over / total if total else None,
                f"{over} objects over the key's {total} (distinct tracks, not frames)",
            )
        )

        # F3: each promise the key names found at its second, given to its speaker, with its price
        # and days flags right; a promise the key does not name counts against it.
        want = k.get("promises") or []
        mine = {(str(r["media_id"]), float(r["second"])): r for r in out.tables.get("walk_promises", [])}
        keyed = {(str(w["media_id"]), float(w["second"])) for w in want}
        right = 0
        for w in want:
            r = mine.get((str(w["media_id"]), float(w["second"])))
            if r is None:
                continue
            flags = (r["mentions_price"], r["mentions_days"]) == (w["mentions_price"], w["mentions_days"])
            right += int(r["speaker"] == w["speaker"] and flags)
        spurious = sum(1 for at in mine if at not in keyed)
        denom = len(want) + spurious
        rows.append(
            proof(
                "walk",
                "F3",
                "Is each promise found and given to who said it?",
                0.85,
                ">=",
                denom,
                right / denom if denom else None,
                f"{right} of {len(want)} key promises right (speaker, price and days); "
                f"{spurious} taken that the key does not name",
            )
        )

        # F4: the vague-change verdicts against the key.
        verdicts = {str(c["change_id"]): bool(c["signable"]) for c in out.tables.get("change_checks", [])}
        changes = k.get("changes") or {}
        agree = sum(1 for cid, ok in changes.items() if verdicts.get(cid) == bool(ok))
        rows.append(
            proof(
                "walk",
                "F4",
                "Is each change order judged signable or vague right?",
                1.0,
                ">=",
                len(changes),
                agree / len(changes) if changes else None,
                f"{agree} of {len(changes)} change orders judged as the key says",
            )
        )
        return rows
