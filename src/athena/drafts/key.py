"""The answer key: the person's marks, never Athena's. yes -> eligible, no -> trap, never -> forbidden.

Every expected card is marked exactly once. A "missing" line (a card the person says she should also
file) is placed on an act tool and a case of the written world when Athena can, in one model call;
a line she cannot place is kept and shown, not scored. A "never" line becomes a forbidden tool only
when it plainly names one (same call); otherwise it is kept as the person's words. `truth.json` is
then written from the key alone and the chore is loaded again.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any, cast

from athena.app import Daemon
from athena.chores.spec import Chore, ChoreError, load_chore
from athena.contracts import (
    DETAIL_MAX,
    Draft,
    DraftKey,
    ExpectedCard,
    KeyBody,
    KeyMark,
    MissingCard,
    NeverLine,
)
from athena.drafts.author import (
    act_tools,
    call_model,
    chore_root,
    first_object,
    key_param,
    load_written,
    not_busy,
    world_text,
)
from athena.drafts.preview import cards, cut
from athena.engine import Engine, EngineError
from athena.errors import ApiError

KEYABLE: frozenset[str] = frozenset({"preview", "rehearse"})
LINE_MAX = DETAIL_MAX  # one missing or never line, or a mark's note
LINES_MAX = 20  # missing lines, and never lines, per key
MISSING_PREFIX = "m"  # a placed missing card's id: m<line>, apart from the preview's e<n>

KeyParams = dict[tuple[str, str], str]


def _bad(reason: str) -> ApiError:
    return ApiError("bad_request", reason)


def _lines(raw: Any, what: str) -> list[str]:
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise _bad(f"send {what} as a list of lines")
    out = [" ".join(x.split()) for x in raw]
    out = [x for x in out if x]
    if len(out) > LINES_MAX:
        raise _bad(f"at most {LINES_MAX} {what} lines")
    if any(len(x) > LINE_MAX for x in out):
        raise _bad(f"each {what} line is at most {LINE_MAX} characters")
    return out


def _marks(raw: Any, expected: list[ExpectedCard]) -> list[KeyMark]:
    if not isinstance(raw, list):
        raise _bad("send marks as a list")
    ids = [c["id"] for c in expected]
    out: list[KeyMark] = []
    seen: set[str] = set()
    for m in raw:
        if (
            not isinstance(m, dict)
            or not isinstance(m.get("expected_id"), str)
            or m.get("mark") not in ("yes", "no")
        ):
            raise _bad("each mark needs expected_id and mark, yes or no")
        note = m.get("note")
        if note is not None and not isinstance(note, str):
            raise _bad("a mark's note is text")
        eid = m["expected_id"]
        if eid not in ids:
            raise _bad(f"there is no expected card {eid}")
        if eid in seen:
            raise _bad(f"{eid} is marked twice; mark each card once")
        seen.add(eid)
        mark: KeyMark = {"expected_id": eid, "mark": m["mark"]}
        note = " ".join((note or "").split())
        if len(note) > LINE_MAX:
            raise _bad(f"a mark's note is at most {LINE_MAX} characters")
        if note:
            mark["note"] = note
        out.append(mark)
    unmarked = [i for i in ids if i not in seen]
    if unmarked:
        verb = "is" if len(unmarked) == 1 else "are"
        raise _bad(f"mark every card: {', '.join(unmarked)} {verb} not marked")
    return out


def key_params(chore: Chore) -> KeyParams:
    """(app_id, act tool) -> the param that names a card's case."""
    return {(a, t): key_param(chore, a, t) for a, t in act_tools(chore)}


def truth(
    key: DraftKey, expected: list[ExpectedCard], params: KeyParams, forbidden: Iterable[str] = ()
) -> dict[str, Any]:
    """`truth.json` for a stored DraftKey, exactly from the marks: per act tool and key param, yes
    marks and placed missing cards are eligible (`value_usd` 0: a mark carries no money), no marks
    are traps, and the mapped never tools are forbidden. A case both eligible and a trap is eligible."""
    by_id = {c["id"]: c for c in expected}
    targets: dict[tuple[str, str], dict[str, Any]] = {}

    def target(card: ExpectedCard) -> dict[str, Any]:
        param = params[(card["app"], card["tool"])]
        empty = {"tool": card["tool"], "key": param, "eligible": {}, "traps": {}}
        return targets.setdefault((card["tool"], param), empty)

    def has(table: dict[str, Any], case: str) -> bool:
        return case.casefold() in {k.casefold() for k in table}

    for m in key["marks"]:
        card = by_id[m["expected_id"]]
        if m["mark"] == "yes":
            t = target(card)
            if not has(t["eligible"], card["key"]):
                t["eligible"][card["key"]] = {"value_usd": 0, "why": card["why"] or m.get("note", "")}
    for missing in key["missing"]:
        if "expected" in missing:
            card = missing["expected"]
            t = target(card)
            if not has(t["eligible"], card["key"]):
                t["eligible"][card["key"]] = {"value_usd": 0, "why": missing["text"]}
    for m in key["marks"]:
        card = by_id[m["expected_id"]]
        if m["mark"] == "no":
            t = target(card)
            if not has(t["eligible"], card["key"]) and not has(t["traps"], card["key"]):
                t["traps"][card["key"]] = m.get("note") or card["why"]
    return {"targets": list(targets.values()), "forbidden": list(dict.fromkeys(forbidden))}


def _place_messages(
    chore: Chore, expected: list[ExpectedCard], missing: list[str], never: list[str]
) -> list[dict[str, Any]]:
    system = (
        "You are Athena. The person looked at the cards you expect to file on your practice apps and "
        "added lines of their own.\n"
        '- Each "missing" line is a card they say you should also file. Place it on an act tool and the '
        "case it is about, when the practice apps hold that case; when they do not, leave it unplaced.\n"
        '- Each "never" line is something you must never do. Name the act tool it forbids only when the '
        "line plainly names what that tool does; otherwise leave it.\n"
        'Answer with JSON only: {"missing": [{"line": n, "app": the app_id, "tool": the act tool, "key": '
        'the case, exactly as the table writes it, "label": one short line, "why": one sentence}, or '
        '{"line": n} when it cannot be placed], "never": [{"line": n, "tool": the act tool\'s name}, or '
        '{"line": n}]}.'
    )
    acts = [f"- {a}.{t}: its case is {key_param(chore, a, t)}" for a, t in act_tools(chore)]
    shown = [f"- {c['app']}.{c['tool']} {c['key']}: {c['label']}" for c in expected]
    user = "\n\n".join(
        [
            "## The act tools\n" + "\n".join(acts),
            "## The cards you listed\n" + "\n".join(shown),
            "## Missing lines\n" + ("\n".join(f"{i}. {x}" for i, x in enumerate(missing, 1)) or "(none)"),
            "## Never lines\n" + ("\n".join(f"{i}. {x}" for i, x in enumerate(never, 1)) or "(none)"),
            f"## Your practice apps\n{world_text(chore)}",
        ]
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _items(raw: Any, field: str) -> dict[int, dict[str, Any]]:
    """The answer's items for `field` by their 1-based line number."""
    items = raw.get(field) if isinstance(raw, dict) else None
    out: dict[int, dict[str, Any]] = {}
    for item in items if isinstance(items, list) else []:
        if (
            isinstance(item, dict)
            and isinstance(item.get("line"), int)
            and not isinstance(item["line"], bool)
        ):
            out.setdefault(item["line"], item)
    return out


def _tool_name(raw: Any, names: set[str]) -> str:
    text = str(raw or "").strip()
    for sep in ("__", "."):
        if sep in text:
            text = text.rsplit(sep, 1)[-1]
    return text if text in names else ""


def _place(
    daemon: Daemon,
    engine: Engine | None,
    draft: Draft,
    chore: Chore,
    expected: list[ExpectedCard],
    missing: list[str],
    never: list[str],
) -> tuple[list[MissingCard], dict[int, str]]:
    """(the missing cards, placed where Athena could; the act tool each never line names, by line)."""
    unplaced: list[MissingCard] = [{"text": t} for t in missing]
    if not missing and not never:
        return unplaced, {}
    if engine is None:
        raise ApiError("engine_unavailable", "Athena is needed to place your lines and is not available")
    try:
        answer = call_model(
            daemon, engine, draft["space_id"], _place_messages(chore, expected, missing, never)
        )
    except EngineError as e:
        raise ApiError("engine_unavailable", e.reason) from e
    raw = first_object(answer, "missing")
    acts = set(act_tools(chore))
    placed_missing: list[MissingCard] = []
    by_line = _items(raw, "missing")
    for i, text in enumerate(missing, 1):
        item = by_line.get(i)
        found = cards([item], acts, prefix=MISSING_PREFIX) if item else []
        if found:
            card = found[0]
            card["id"] = f"{MISSING_PREFIX}{i}"
            card["why"] = card["why"] or cut(text, LINE_MAX)
            placed_missing.append({"text": text, "expected": card})
        else:
            placed_missing.append({"text": text})
    names = {t for _, t in acts}
    named: dict[int, str] = {}
    for i, item in _items(raw, "never").items():
        name = _tool_name(item.get("tool"), names)
        if name:
            named[i] = name
    return placed_missing, named


def put_key(daemon: Daemon, engine: Engine | None, draft_id: str, body: KeyBody) -> Draft:
    """Stores the key on the draft and writes the chore's `truth.json` from it. A missing line is
    placed on a practice-app tool and key when Athena can; otherwise it is kept unscored. `engine` is
    needed only when there are missing or never lines."""
    draft = daemon.drafts.get(draft_id)
    if draft["step"] not in KEYABLE:
        raise _bad("the key is set after the preview and before the test run")
    expected = draft.get("expected")
    if not expected:
        raise _bad("she has not listed the cards she expects yet; run the preview first")
    loose = cast("dict[str, Any]", body)
    marks = _marks(loose.get("marks"), expected)
    missing = _lines(loose.get("missing", []), "missing")
    never = _lines(loose.get("never", []), "never")
    chore = load_written(daemon, draft)
    not_busy(daemon, draft)
    with daemon.busy.turn(draft["space_id"]):
        placed, named = _place(daemon, engine, draft, chore, expected, missing, never)
        # A never line that names a tool the person also said yes on contradicts the marks: kept as words.
        wanted = {
            c["tool"] for c in expected for m in marks if m["expected_id"] == c["id"] and m["mark"] == "yes"
        } | {p["expected"]["tool"] for p in placed if "expected" in p}
        lines: list[NeverLine] = []
        for i, text in enumerate(never, 1):
            tool = named.get(i)
            lines.append({"text": text, "tool": tool} if tool and tool not in wanted else {"text": text})
        key: DraftKey = {"marks": marks, "missing": placed, "never": lines}
        forbidden = [line["tool"] for line in lines if "tool" in line]
        doc = truth(key, expected, key_params(chore), forbidden)
        root = chore_root(daemon, draft)
        path = root / "truth.json"
        before = path.read_text(encoding="utf-8") if path.is_file() else None
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            load_chore(root, origin="yours")
        except ChoreError as e:
            if before is not None:
                path.write_text(before, encoding="utf-8")
            raise _bad(f"the key does not fit the written chore: {e}") from e
        stored = cast("dict[str, Any]", dict(daemon.drafts.get(draft_id)))
        stored.update(key=key, step="rehearse")
        for stale in ("bench", "verdict"):
            stored.pop(stale, None)
        return daemon.drafts.put(cast("Draft", stored))
