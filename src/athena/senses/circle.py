"""The circle sense: a parent's care shared by a family.

Counter photos become the bottles on hand, each label read twice and kept only where both reads
agree (as paper does). A family call becomes the tasks people claimed, by a plain-rules spotter
that skips negated, hedged and question sentences. `senses/signers.json` becomes the signer rules,
and `whose_yes` says whose yes an action needs. Nothing here gives dosing advice: a label is copied
as printed, and a mismatch is a question for the pharmacist.
"""

from __future__ import annotations

import json
import re
from typing import Any

from athena.contracts import ProofRow, SenseName
from athena.senses.contract import SenseContext, SenseOutput, proof
from athena.senses.normalise import comparable, stored
from athena.senses.paper import box_list, merge_reads, read_twice, tracks

LABEL_FIELDS = ("name", "strength", "directions")
REFUSE = "refuse"

SENTENCE = re.compile(r"(?<=[.!?])\s+")
CLAIM = re.compile(r"\b(i'll|i will|i'm going to|i am going to|i can)\s+(\w+)", re.I)
#: "I can" about hearing or seeing is not a task.
NOT_TASKS = {"hear", "see", "tell", "understand", "imagine"}
NEGATED = re.compile(r"\b(can't|cannot|won't|will not|don't|do not|not|never|couldn't)\b", re.I)
HEDGED = re.compile(r"\b(maybe|might|perhaps|possibly|probably|i guess|if i have time)\b", re.I)


# --- whose yes ------------------------------------------------------------------------------------


def whose_yes(action: str, subject: str, table: list[dict[str, Any]]) -> dict[str, Any]:
    """The rule an action on a subject falls under: `{needs, parent_veto}`, or `{needs: "refuse"}`.

    The rule naming the exact subject beats the `*` rule for the action; no rule at all is refuse.
    """
    exact = next((r for r in table if r.get("action") == action and r.get("subject") == subject), None)
    rule = exact or next((r for r in table if r.get("action") == action and r.get("subject") == "*"), None)
    if rule is None or rule.get("needs") == REFUSE:
        return {"needs": REFUSE}
    return {"needs": str(rule["needs"]), "parent_veto": bool(rule.get("parent_veto"))}


def runs(
    rule: dict[str, Any], proposer: str, yes: list[str], no: list[str], members: list[dict[str, Any]]
) -> bool:
    """Whether the yeses on record meet the rule. Only members' exact ids count; a member who said
    both yes and no counts as no; the parent's no beats any quorum when the rule gives her a veto;
    the proposer's own yes never counts toward a quorum."""
    needs = str(rule.get("needs") or REFUSE)
    if needs == REFUSE:
        return False
    role_of = {str(m["id"]): str(m["role"]) for m in members}
    noes = {n for n in no if n in role_of}
    yeses = {y for y in yes if y in role_of and y not in noes}
    if rule.get("parent_veto") and any(role_of[n] == "parent" for n in noes):
        return False
    if needs == "parent":
        return any(role_of[y] == "parent" for y in yeses)
    if needs.startswith("role:"):
        return any(role_of[y] == needs[len("role:") :] for y in yeses)
    if needs.startswith("quorum:"):
        return len(yeses - {proposer}) >= int(needs[len("quorum:") :])
    return False


def signer_rows(signers: dict[str, Any]) -> list[dict[str, Any]]:
    members = signers.get("members") or []
    name_of_role = {str(m["role"]): f"{m['name']} ({m['role']})" for m in members}
    parent = name_of_role.get("parent", "the parent")
    rows = []
    for i, r in enumerate(signers.get("rules") or [], start=1):
        needs = str(r["needs"])
        if needs == "parent":
            who, count = parent, 1
        elif needs.startswith("role:"):
            who, count = name_of_role.get(needs[5:], needs[5:]), 1
        elif needs.startswith("quorum:"):
            count = int(needs[7:])
            who = f"any {count} members other than the one who asks"
        else:
            who, count = "no one", 0
        veto = bool(r.get("parent_veto"))
        rows.append(
            {
                "rule_id": f"R{i}",
                "action": str(r["action"]),
                "subject": str(r["subject"]),
                "needs": needs,
                "parent_veto": veto,
                "signers": who,
                "yeses_needed": count,
                "decided_by": f"{who}; a no from {parent} stops it" if veto else who,
            }
        )
    return rows


# --- tasks ----------------------------------------------------------------------------------------


def claims(text: str) -> list[str]:
    """The sentences of a turn in which the speaker takes a task on."""
    out = []
    for sentence in SENTENCE.split(text.strip()):
        s = sentence.strip()
        if not s or s.endswith("?") or HEDGED.search(s):
            continue
        m = CLAIM.search(s)
        if m is None or m.group(2).casefold() in NOT_TASKS:
            continue
        if NEGATED.search(s[m.start() :]):
            continue
        out.append(s)
    return out


def member_id(role_line: str) -> str:
    """`maya (primary carer)` -> `maya`."""
    return role_line.split("(")[0].strip().split(" ")[0].casefold()


class CircleSense:
    name: SenseName = "circle"

    def build(self, ctx: SenseContext) -> SenseOutput:
        meds: list[dict[str, Any]] = []
        tasks: list[dict[str, Any]] = []
        asked: list[str] = []
        for photo in ctx.items("circle", "photo"):
            segments, usage = ctx.segmenter.segment(photo, str(photo.params.get("prompt") or ""))
            ctx.record("circle", "segmenter", photo.id, usage)
            bottles = tracks(photo.id, segments)
            names = [f"{b.track_id}.{f}" for b in bottles for f in LABEL_FIELDS]
            if not names:
                continue
            reads = read_twice(ctx, "circle", photo, names)
            for b in bottles:
                row: dict[str, Any] = {"med_id": b.track_id, "media_id": photo.id, "frame": b.best.frame}
                row["box"] = box_list(b.best.box)
                if photo.params.get("where"):
                    row["where"] = str(photo.params["where"])
                missing = []
                for f in LABEL_FIELDS:
                    _, cited, _ = merge_reads(f"{b.track_id}.{f}", reads[0], reads[1])
                    if cited is None:
                        missing.append(f)
                        asked.append(f"{b.track_id}.{f}")
                    else:
                        row[f] = stored(f, cited.value)
                row["status"] = "asked" if missing else "read"
                if missing:
                    row["asked"] = missing
                meds.append(row)
        for call in ctx.items("circle", "audio"):
            transcript, usage = ctx.transcriber.transcribe(call)
            ctx.record("circle", "transcriber", call.id, usage)
            members = {str(k): member_id(str(v)) for k, v in (call.params.get("members") or {}).items()}
            n = 0
            for t in transcript.turns:
                for sentence in claims(t.text):
                    n += 1
                    row = {"task_id": f"{call.id}#{n}", "media_id": call.id}
                    if t.speaker in members:
                        row["member"] = members[t.speaker]
                    row |= {"speaker": t.speaker, "second": t.start_s, "end_s": t.end_s, "text": sentence}
                    tasks.append(row)
        signers_path = ctx.senses_dir / "signers.json"
        signers = json.loads(signers_path.read_text(encoding="utf-8")) if signers_path.is_file() else {}
        tables = {"counter_meds": meds, "circle_tasks": tasks, "signer_rules": signer_rows(signers)}
        return SenseOutput("circle", tables, tuple(asked))

    def prove(self, ctx: SenseContext, out: SenseOutput, key: dict[str, Any]) -> list[ProofRow]:
        k = key.get("circle") or {}
        signers_path = ctx.senses_dir / "signers.json"
        signers = json.loads(signers_path.read_text(encoding="utf-8")) if signers_path.is_file() else {}
        table, members = signers.get("rules") or [], signers.get("members") or []
        rows: list[ProofRow] = []

        # F1 / F1x: whose yes each action needs, and whether each recorded decision may run.
        rules_k = k.get("whose_yes") or []
        decisions = k.get("decisions") or []
        rule_ok = 0
        for w in rules_k:
            expect = {"needs": w["needs"]} | ({"parent_veto": w["parent_veto"]} if "parent_veto" in w else {})
            rule_ok += int(whose_yes(w["action"], w["subject"], table) == expect)
        dec_ok = breaches = 0
        for d in decisions:
            verdict = runs(
                whose_yes(d["action"], d["subject"], table), d["proposer"], d["yes"], d["no"], members
            )
            dec_ok += int(verdict == d["runs"])
            breaches += int(verdict and not d["runs"])
        n = len(rules_k) + len(decisions)
        rows.append(
            proof(
                "circle",
                "F1",
                "Does each action need the right yeses?",
                1.0,
                ">=",
                n,
                (rule_ok + dec_ok) / n if n else None,
                f"{rule_ok} of {len(rules_k)} rules resolved and {dec_ok} of {len(decisions)} "
                "decisions judged as the key says",
            )
        )
        rows.append(
            proof(
                "circle",
                "F1x",
                "Would any action run without the yeses it needs?",
                0.0,
                "<=",
                len(decisions),
                breaches if decisions else None,
                f"{breaches} of {len(decisions)} decisions would run where the key says not",
            )
        )

        # F3 / F3a / F3x: the bottles found, and their labels as read against the key.
        photos = k.get("photos") or {}
        truth = {(mid, bid): b for mid, p in photos.items() for bid, b in (p.get("bottles") or {}).items()}
        meds = out.tables.get("counter_meds", [])
        seen = {(str(m["media_id"]), str(m["med_id"])) for m in meds}
        both = len(seen & set(truth))
        union = len(seen | set(truth))
        rows.append(
            proof(
                "circle",
                "F3",
                "Is every bottle on the counter found, once?",
                0.95,
                ">=",
                len(truth),
                both / union if union else None,
                f"{both} bottles found of {len(truth)} in the key, {len(seen)} found in all",
            )
        )
        read = [
            (m, f)
            for m in meds
            for f in LABEL_FIELDS
            if f in m and (str(m["media_id"]), str(m["med_id"])) in truth
        ]
        right = sum(
            1
            for m, f in read
            if comparable(f, m[f]) == comparable(f, truth[(str(m["media_id"]), str(m["med_id"]))][f])
        )
        wrong = len(read) - right
        rows.append(
            proof(
                "circle",
                "F3a",
                "Are the label fields marked read right?",
                0.95,
                ">=",
                len(read),
                right / len(read) if read else None,
                f"{right} of {len(read)} label fields read equal the key",
            )
        )
        rows.append(
            proof(
                "circle",
                "F3x",
                "Is any label cleared with a wrong value?",
                0.0,
                "<=",
                len(read),
                wrong / len(read) if read else None,
                f"{wrong} of {len(read)} label fields read but wrong",
            )
        )

        # F4: how many of the spotted tasks a person would have to correct (missed, extra, wrong member).
        want = [(mid, t) for mid, ts in (k.get("tasks") or {}).items() for t in ts]
        got = list(out.tables.get("circle_tasks", []))
        used: set[int] = set()
        fixes = 0
        for mid, t in want:
            hit = next(
                (
                    i
                    for i, g in enumerate(got)
                    if i not in used
                    and g["media_id"] == mid
                    and float(g["second"]) == float(t["second"])
                    and str(t["says"]).casefold() in str(g["text"]).casefold()
                ),
                None,
            )
            if hit is None:
                fixes += 1
                continue
            used.add(hit)
            fixes += int(got[hit].get("member") != t.get("member"))
        extra = len(got) - len(used)
        fixes += extra
        rows.append(
            proof(
                "circle",
                "F4",
                "How many spotted tasks would a person correct?",
                0.25,
                "<=",
                len(want),
                fixes / len(want) if want else None,
                f"{fixes} corrections over {len(want)} key tasks ({extra} spotted that the key "
                "does not name)",
            )
        )
        return rows
