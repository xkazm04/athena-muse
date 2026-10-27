"""The call sense: a recorded phone call to cited turns, kept only when its consent line was heard.

If no turn in the first 60 seconds says the call's consent line (case and punctuation aside), the
call keeps no turns at all and `<media_id>.consent` is asked. A packet of sentences is bound to its
sources by `packet_sha256`; a sentence is supported only when it cites at least one source and
every cite is a field read off paper or a turn of a call that was kept.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from athena.contracts import ProofRow, SenseName
from athena.senses.contract import SenseContext, SenseOutput, proof

CONSENT_WINDOW_S = 60.0
WORDS = re.compile(r"[^\w\s]")


def plain(text: str) -> str:
    """Lower case, punctuation off, whitespace collapsed: how a spoken line is matched."""
    return " ".join(WORDS.sub(" ", text.casefold()).split())


def packet_sha256(sentences: list[dict[str, Any]]) -> str:
    """The hash an approval binds to: sentences in order with their exact text, cites sorted and
    de-duplicated, every other key dropped; canonical JSON (sorted keys, no spaces)."""
    canon = [
        {"cites": sorted({str(c) for c in s.get("cites") or []}), "text": str(s["text"])} for s in sentences
    ]
    blob = json.dumps(canon, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def sources(tables: dict[str, list[dict[str, Any]]]) -> set[str]:
    """Every cite a sentence may lean on: `<sheet>.<field>` read off paper, `<call>#<n>` kept turns."""
    cites = {
        f"{f['sheet_id']}.{f['field']}" for f in tables.get("sheet_fields", []) if f.get("status") == "read"
    }
    return cites | {str(t["turn_id"]) for t in tables.get("call_turns", [])}


def unsupported(sentences: list[dict[str, Any]], known: set[str]) -> list[int]:
    """Indexes of sentences with no cite, or a cite to nothing that was read or kept."""
    return [
        i
        for i, s in enumerate(sentences)
        if not s.get("cites") or any(str(c) not in known for c in s["cites"])
    ]


class CallSense:
    name: SenseName = "call"

    def build(self, ctx: SenseContext) -> SenseOutput:
        turns: list[dict[str, Any]] = []
        log: list[dict[str, Any]] = []
        asked: list[str] = []
        for item in ctx.items("call", "audio"):
            transcript, usage = ctx.transcriber.transcribe(item)
            ctx.record("call", "transcriber", item.id, usage)
            p = item.params
            line = plain(str(p.get("consent_line") or ""))
            heard = next(
                (
                    t
                    for t in transcript.turns
                    if t.start_s < CONSENT_WINDOW_S and line and line in plain(t.text)
                ),
                None,
            )
            roles = {str(k): str(v) for k, v in (p.get("speakers") or {}).items()}
            row: dict[str, Any] = {"media_id": item.id}
            if p.get("title"):
                row["title"] = str(p["title"])
            if heard is None:
                row |= {"consent": "missing", "turns": 0}
                asked.append(f"{item.id}.consent")
            else:
                kept = [
                    {
                        "turn_id": f"{item.id}#{n}",
                        "media_id": item.id,
                        "speaker": roles.get(t.speaker, t.speaker),
                        "second": t.start_s,
                        "end_s": t.end_s,
                        "text": t.text,
                    }
                    for n, t in enumerate(transcript.turns, start=1)
                ]
                turns += kept
                row |= {"consent": "heard", "turns": len(kept), "consent_second": heard.start_s}
            log.append(row)
        return SenseOutput("call", {"call_turns": turns, "call_log": log}, tuple(asked))

    def prove(self, ctx: SenseContext, out: SenseOutput, key: dict[str, Any]) -> list[ProofRow]:
        k = key.get("call") or {}
        calls: dict[str, dict[str, Any]] = k.get("calls") or {}
        turns = out.tables.get("call_turns", [])
        log = {str(r["media_id"]): r for r in out.tables.get("call_log", [])}
        rows: list[ProofRow] = []

        # F1: speaker attribution, turn by turn, against the key's roles.
        by_second = {(str(t["media_id"]), float(t["second"])): t for t in turns}
        want = [(mid, t) for mid, c in calls.items() for t in c.get("turns") or []]
        right = sum(
            1
            for mid, t in want
            if (by_second.get((mid, float(t["second"]))) or {}).get("speaker") == t["speaker"]
        )
        rows.append(
            proof(
                "call",
                "F1",
                "Is each turn given to the right speaker?",
                0.90,
                ">=",
                len(want),
                right / len(want) if want else None,
                f"{right} of {len(want)} key turns kept with the key's speaker",
            )
        )

        # F1k: the ids, dates and numbers said on the call, captured exactly in the turn that said them.
        exact = [(mid, e) for mid, c in calls.items() for e in c.get("exact") or []]
        caught = sum(
            1
            for mid, e in exact
            if str(e["text"]) in str((by_second.get((mid, float(e["second"]))) or {}).get("text", ""))
        )
        rows.append(
            proof(
                "call",
                "F1k",
                "Are the ids, dates and numbers said captured exactly?",
                0.95,
                ">=",
                len(exact),
                caught / len(exact) if exact else None,
                f"{caught} of {len(exact)} key keywords and numbers in the turn that said them",
            )
        )

        # F3 / F3x / F4: the drafted packets, checked sentence by sentence and bound by hash.
        packets = k.get("packets") or {}
        drafts = ctx.tables.get(str(packets.get("table") or ""), [])
        if drafts:
            known = sources(ctx.tables)
            by_id = {str(d["packet_id"]): d for d in drafts}
            fileable = [by_id[p] for p in packets.get("fileable") or [] if p in by_id]
            bad_sentences = sum(len(unsupported(d["sentences"], known)) for d in fileable)
            total = sum(len(d["sentences"]) for d in fileable)
            rows.append(
                proof(
                    "call",
                    "F3",
                    "Does a fileable packet hold an unsupported sentence?",
                    0.0,
                    "<=",
                    total,
                    bad_sentences if total else None,
                    f"{bad_sentences} unsupported of {total} sentences in {len(fileable)} fileable packet(s)",
                )
            )
            seeded = [by_id[p] for p in packets.get("unsupported") or [] if p in by_id]
            caught_bad = sum(1 for d in seeded if unsupported(d["sentences"], known))
            rows.append(
                proof(
                    "call",
                    "F3x",
                    "Is every seeded bad draft caught?",
                    1.0,
                    ">=",
                    len(seeded),
                    caught_bad / len(seeded) if seeded else None,
                    f"{caught_bad} of {len(seeded)} seeded drafts flagged with an unsupported sentence",
                )
            )
            bound = sum(1 for d in drafts if packet_sha256(d["sentences"]) == d.get("packet_sha256"))
            rows.append(
                proof(
                    "call",
                    "F4",
                    "Does each packet's hash bind its exact sentences?",
                    1.0,
                    ">=",
                    len(drafts),
                    bound / len(drafts),
                    f"{bound} of {len(drafts)} drafts recompute to their stored sha256",
                )
            )

        # R4: the consent gate. A call without its line keeps nothing; one with it keeps its turns.
        kept_ids = {str(t["media_id"]) for t in turns}
        gated = 0
        for mid, c in calls.items():
            heard = (log.get(mid) or {}).get("consent") == "heard"
            if bool(c.get("consent")) == heard and (mid in kept_ids) == heard:
                gated += 1
        rows.append(
            proof(
                "call",
                "R4",
                "Does a call without its consent line keep no turns?",
                1.0,
                ">=",
                len(calls),
                gated / len(calls) if calls else None,
                f"{gated} of {len(calls)} calls gated as the key says",
            )
        )
        return rows
