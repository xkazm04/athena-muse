"""Authoring: the agreed sketch and the conversation become `playbook.json` and `world.json` under
`<data_dir>/drafts/<draft_id>/<chore_id>/`, checked by `load_chore`, with up to REPAIRS_MAX repairs.

One model call (surface `design`) is given the sketch, the person's conversation, the nearest library
chore as an example (never its answer key), the taxonomy and the exact rules the loader checks. Its
JSON is written beside an empty `truth.json` (the key step fills it) and loaded. When the loader finds
problems, the person sees them in plain words (`repair`) and the model gets the full list back.

The helpers the later steps share live here too: the draft's folder, the written chore, one ledgered
model call with no tools, and reading JSON out of a model's answer.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

from athena.app import Daemon
from athena.chores.spec import (
    PARAM_TYPES,
    TAXONOMY,
    Chore,
    ChoreError,
    chore_ids,
    library_dir,
    load_chore,
    load_library,
)
from athena.contracts import REPAIRS_MAX, Draft
from athena.drafts.rubric import SLOTS
from athena.drafts.shape import SLOT_MEANING
from athena.engine import Engine, EngineError, TextDelta, Usage
from athena.engine.prices import estimate
from athena.errors import ApiError

CHORE_ID_MAX = 80
EXEMPLAR_ROWS = 3  # rows per table shown from the example chore
CONVERSATION_TURNS = 40  # the newest turns of the draft's conversation given to the author
TOOL_NAME_MAX = 64  # `<app_id>__<tool>` is a function name, which engines cap at 64 characters
TRUTH_EMPTY: dict[str, Any] = {"targets": [], "forbidden": []}
WRITABLE: frozenset[str] = frozenset({"shape", "author"})
_NAME = re.compile(r"[A-Za-z0-9_-]+")
_FENCE = re.compile(r"```[a-zA-Z]*\s*\n(.*?)```", re.S)

#: Our own checks beyond the loader's, in the loader's voice so `plain` reads them alike.
NO_ANSWER = "the answer is not JSON with playbook and world"
NO_PHASES = "world.json has no phases"
NO_ACT_TOOL = "world.json has no act tool"
WRONG_KIND = "world.json has a value of the wrong kind"


# --- shared by the later steps --------------------------------------------------------------------


def data_folder(daemon: Daemon, draft: Draft) -> Path:
    """`<data_dir>/drafts/<draft_id>/`, or a plain 400 when the daemon keeps nothing on disk."""
    path = daemon.drafts.folder(draft["id"])
    if path is None:
        raise ApiError("bad_request", "drafts need a data folder; start Athena with one")
    return path


def chore_root(daemon: Daemon, draft: Draft) -> Path:
    if "chore_id" not in draft:
        raise ApiError("bad_request", "she has not written the chore yet")
    return data_folder(daemon, draft) / draft["chore_id"]


def load_written(daemon: Daemon, draft: Draft) -> Chore:
    """The draft's written chore, loaded; a 400 when it no longer loads."""
    try:
        return load_chore(chore_root(daemon, draft), origin="yours")
    except ChoreError as e:
        raise ApiError("bad_request", "the written chore no longer loads; write it again") from e


def not_busy(daemon: Daemon, draft: Draft) -> None:
    if daemon.busy.running(draft["space_id"]):
        raise ApiError("space_busy", "Athena is still working on this; try again when she is done")


def call_model(daemon: Daemon, engine: Engine, space_id: str, messages: list[dict[str, Any]]) -> str:
    """One model call with no tools, ledgered with surface `design`; answers the text. Raises EngineError
    (after ledgering it) when the call fails."""
    started = time.monotonic()
    parts: list[str] = []
    usage: Usage | None = None
    try:
        for chunk in engine.complete(messages, []):
            if isinstance(chunk, TextDelta):
                parts.append(chunk.text)
            elif isinstance(chunk, Usage):
                usage = chunk
    except EngineError as e:
        daemon.ledger.record(
            surface="design",
            space_id=space_id,
            engine=engine.id,
            model=engine.model,
            latency_ms=int((time.monotonic() - started) * 1000),
            ok=False,
            error=e.reason,
        )
        raise
    cost = None
    if usage is not None:
        cost = usage.cost_usd
        # A plan-billed engine is never priced from the list: no figure is not $0 (as a turn does).
        if cost is None and engine.cost_estimated:
            cost = estimate(engine.model, usage.input_tokens, usage.output_tokens)
    daemon.ledger.record(
        surface="design",
        space_id=space_id,
        engine=engine.id,
        model=engine.model,
        latency_ms=int((time.monotonic() - started) * 1000),
        ok=True,
        input_tokens=usage.input_tokens if usage else None,
        output_tokens=usage.output_tokens if usage else None,
        cost_usd=cost,
        cost_estimated=engine.cost_estimated,
    )
    return "".join(parts)


def json_values(text: str) -> list[Any]:
    """The JSON values in a model's answer: the whole answer, else each fenced block, else each value
    found by scanning from every `{` or `[`. An answer with none answers []."""
    text = text.strip()
    try:
        return [json.loads(text)]
    except ValueError:
        pass
    out: list[Any] = []
    for block in _FENCE.findall(text):
        try:
            out.append(json.loads(block))
        except ValueError:
            continue
    if out:
        return out
    decoder = json.JSONDecoder()
    i = 0
    while i < len(text):
        if text[i] in "{[":
            try:
                value, end = decoder.raw_decode(text, i)
            except ValueError:
                i += 1
                continue
            out.append(value)
            i = end
        else:
            i += 1
    return out


def first_object(text: str, key: str) -> dict[str, Any] | list[Any] | None:
    """The first object in the answer that has `key`, else the first bare list; None when neither."""
    values = json_values(text)
    for v in values:
        if isinstance(v, dict) and key in v:
            return cast("dict[str, Any]", v)
    for v in values:
        if isinstance(v, list):
            return v
    return None


def key_param(chore: Chore, app_id: str, tool: str) -> str:
    """An act tool's key param: the one marked `"key": true` in `world.json`, else its first."""
    t = next((t for t in chore.app(app_id).tools if t.name == tool), None)
    if t is None or not t.params:
        return ""
    marked = [p for p, spec in t.params.items() if spec.get("key") is True]
    return marked[0] if marked else next(iter(t.params))


def act_tools(chore: Chore) -> list[tuple[str, str]]:
    """(app_id, tool) for every act tool (any kind but READ), in the world's order."""
    return [(a.app_id, t.name) for a in chore.apps for t in a.tools if t.kind != "READ"]


def world_text(chore: Chore, *, rows: int | None = None) -> str:
    """The written world as the model reads it: apps, tools (with each act tool's key), tables, phases."""
    apps = []
    for a in chore.apps:
        tools = []
        for t in a.tools:
            tool: dict[str, Any] = {"name": t.name, "kind": t.kind, "description": t.description}
            tool["params"] = t.params
            if t.kind == "READ":
                tool["returns"] = t.returns
            else:
                tool["key"] = key_param(chore, a.app_id, t.name)
                tool["says"] = t.says
            tools.append(tool)
        apps.append({"app_id": a.app_id, "name": a.name, "origin": a.origin, "view": a.view, "tools": tools})
    tables = {k: v if rows is None else v[:rows] for k, v in chore.tables.items()}
    phases = [{"app": p.app, "message": p.message} for p in chore.phases]
    doc = {"today": chore.today, "apps": apps, "tables": tables, "phases": phases}
    return json.dumps(doc, ensure_ascii=False, indent=1)


def sketch_text(draft: Draft) -> str:
    """The sketch by slot, each node marked whose it is."""
    nodes = draft["sketch"]["nodes"]
    labels = {n["id"]: n["label"] for n in nodes}
    lines: list[str] = []
    for slot in SLOTS:
        here = [n for n in nodes if n["slot"] == slot]
        lines.append(f"- {slot} ({SLOT_MEANING[slot]}):")
        if not here:
            lines.append("  - left open: write a sensible default and say in the brief that it is one")
        for n in here:
            if n["origin"] == "you":
                whose = "the person's words"
            else:
                whose = "Athena's proposal, confirmed by the person" if n["confirmed"] else "Athena's guess"
            detail = f" - {n['detail']}" if n.get("detail") else ""
            lines.append(f'  - "{n["label"]}"{detail} ({whose})')
    edges = draft["sketch"]["edges"]
    if edges:
        lines.append("- the order, as linked:")
        for e in edges:
            lines.append(f'  - "{labels.get(e["from"], e["from"])}" -> "{labels.get(e["to"], e["to"])}"')
    return "\n".join(lines)


# --- plain words ----------------------------------------------------------------------------------

_FILES = {
    "playbook.json": "the chore's description",
    "world.json": "her practice apps",
    "truth.json": "what you expect",
    "sensed.json": "what her senses read",
    "taxonomy.json": "the kinds of chore Athena knows",
}

_RULES: tuple[tuple[str, str], ...] = (
    (r"(\S+\.json) is missing", "{file} is missing."),
    (r"(\S+\.json) cannot be read as JSON: .*", "{file} could not be read."),
    (r"(\S+\.json) must be an object", "{file} was not written as a whole."),
    (r"playbook\.json id .* is not the folder name .*", "The chore's name does not match where it is kept."),
    (r"playbook\.json has no title", "The chore has no title."),
    (r"playbook\.json has no promise", "The chore does not say what it promises."),
    (r"playbook\.json has no expectation", "The chore does not say what a good result is."),
    (r"category (.*) is not in taxonomy\.json", "The chore's kind of work, {0}, is not one Athena knows."),
    (r"job (.*) is not in taxonomy\.json", "The chore's goal, {0}, is not one Athena knows."),
    (r"featured.*", "The chore says it is featured, which only a proven chore can be."),
    (r"(?:world|sensed) table (\S+) must be a list of rows", "The table {0} is not a list of rows."),
    (r"sensed table (\S+) would shadow .*", "The table {0} is written twice."),
    (r"an app has no app_id", "One of her practice apps has no name to call it by."),
    (r"app (\S*) appears twice", "The practice app {0} appears twice."),
    (r"app (\S*) has two tools called (\S+)", "The practice app {0} has two tools called {1}."),
    (
        r"a phase opens app (.*), which the world does not have",
        "A step of the test run opens {0}, which is not one of her practice apps.",
    ),
    (r"truth target (.*) is a tool no app has", "What you expect names {0}, which no practice app has."),
    (r"forbidden tool (.*) is a tool no app has", "A never line names {0}, which no practice app has."),
    (re.escape(NO_PHASES), "The test run has no steps: it opens none of her practice apps."),
    (re.escape(NO_ACT_TOOL), "None of her practice apps has an action that waits for your signature."),
    (re.escape(NO_ANSWER), "Her answer could not be read as a chore."),
    (re.escape(WRONG_KIND) + r": .*", "Her practice apps hold a value of the wrong kind."),
)

_TOOL_RULES: tuple[tuple[str, str], ...] = (
    (r"a tool has no name", "A tool on {app} has no name."),
    (r"has no kind", "{who} does not say whether it reads or acts."),
    (r"param (\S+) has type (.*)", "{who} takes {0} as {1}, which is not text, a number or yes/no."),
    (r"a .* tool needs says", "{who} does not say what the app answers once it runs."),
    (r"a READ tool must return a table", "{who} reads, but does not say which table."),
    (
        r"reads table (.*), which no world or sensed table has",
        "{who} reads {0}, a table the apps do not have.",
    ),
    (
        r"(?:matches on|requires|defaults) (.*), which are not its params",
        "{who} looks rows up by {0}, which it does not take.",
    ),
    (
        r"matches columns (\S+) does not have: (.*)",
        "{who} looks for {1} in the table {0}, which has no such column.",
    ),
    (
        r"page_size must be a whole number above 0",
        "{who} pages its rows by a number that is not a whole number above 0.",
    ),
    (r"an act tool needs a param for the case it is about", "{who} does not say which case it acts on."),
    (r"marks more than one param as the key", "{who} names more than one thing as the case it acts on."),
    (r"a tool name may use only .*", "{who} has a name a model cannot call."),
)


def _words(name: str) -> str:
    return name.strip("'\"").replace("_", " ").strip() or "(no name)"


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def plain(problem: str) -> str:
    """One loader problem rewritten so a person who is not a developer can read it; same meaning."""
    p = problem.strip()
    for pattern, template in _RULES:
        m = re.fullmatch(pattern, p, re.S)
        if m:
            file = _cap(_FILES.get(m.group(1), m.group(1))) if "{file}" in template else ""
            return template.format(*(_words(g) for g in m.groups()), file=file)
    m = re.fullmatch(r"([^.:\s]*)\.([^:\s]*): (.+)", p, re.S)
    if m:
        app, tool = _words(m.group(1)), _words(m.group(2))
        for pattern, template in _TOOL_RULES:
            t = re.fullmatch(pattern, m.group(3), re.S)
            if t:
                said = template.format(*(_words(g) for g in t.groups()), who=f"{tool} on {app}", app=app)
                return _cap(said)
    for name, words in _FILES.items():
        p = p.replace(name, words)
    return _cap(p.rstrip(".")) + "."


# --- writing --------------------------------------------------------------------------------------


def slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")
    return s[:CHORE_ID_MAX].rstrip("-") or "my-chore"


def unique_id(base: str, taken: set[str]) -> str:
    """`base`, else `base-2`, `base-3`... each within CHORE_ID_MAX characters."""
    if base not in taken:
        return base
    n = 2
    while True:
        tail = f"-{n}"
        candidate = base[: CHORE_ID_MAX - len(tail)].rstrip("-") + tail
        if candidate not in taken:
            return candidate
        n += 1


def _usable(world: dict[str, Any]) -> list[str]:
    """What the later steps need beyond the loader, read from `world.json` as written so it is
    reported with the loader's problems: phases, act tools, each with one case to name."""
    problems: list[str] = []
    if not _items(world.get("phases")):
        problems.append(NO_PHASES)
    acts = 0
    for app in _items(world.get("apps")):
        app_id = str(app.get("app_id", ""))
        for tool in _items(app.get("tools")):
            name, kind = str(tool.get("name", "")), str(tool.get("kind", ""))
            params = tool.get("params") if isinstance(tool.get("params"), dict) else {}
            where = f"{app_id}.{name}"
            named = _NAME.fullmatch(app_id) and _NAME.fullmatch(name)
            if not named or len(app_id) + 2 + len(name) > TOOL_NAME_MAX:
                problems.append(f"{where}: a tool name may use only letters, digits, - and _")
            if kind == "READ" or not kind:
                continue
            acts += 1
            if not params:
                problems.append(f"{where}: an act tool needs a param for the case it is about")
            elif sum(1 for spec in params.values() if isinstance(spec, dict) and spec.get("key") is True) > 1:
                problems.append(f"{where}: marks more than one param as the key")
    if not acts:
        problems.append(NO_ACT_TOOL)
    return problems


def _items(value: Any) -> list[dict[str, Any]]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _taxonomy_ids() -> tuple[list[str], list[str]]:
    try:
        data = json.loads((library_dir() / TAXONOMY).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], []
    cats = [str(c.get("id")) for c in data.get("categories", []) if isinstance(c, dict)]
    jobs = [str(j.get("id")) for j in data.get("jobs", []) if isinstance(j, dict)]
    return cats, jobs


def _nearest(draft: Draft) -> Chore | None:
    """The library chore whose words share the most with the need and the sketch; the first on a tie."""
    words = set(re.findall(r"[a-z]{4,}", (draft["need"] + " " + sketch_text(draft)).casefold()))
    best: tuple[int, Chore] | None = None
    for chore in load_library():
        pb = chore.showcase
        theirs = " ".join(str(pb.get(k, "")) for k in ("title", "short_title", "promise", "category", "job"))
        score = len(words & set(re.findall(r"[a-z]{4,}", theirs.casefold())))
        if best is None or score > best[0]:
            best = (score, chore)
    return best[1] if best else None


def _exemplar(chore: Chore) -> str:
    pb = chore.showcase
    keep = ("title", "short_title", "category", "job", "promise", "brief", "persona", "expectation")
    playbook = {k: pb[k] for k in keep if k in pb}
    raw = json.loads((chore.root / "world.json").read_text(encoding="utf-8"))
    raw["tables"] = {k: v[:EXEMPLAR_ROWS] for k, v in chore.tables.items()}  # sensed tables merged in
    return (
        "playbook.json (cut to the parts you write):\n"
        + json.dumps(playbook, ensure_ascii=False, indent=1)
        + f"\n\nworld.json (each table cut to {EXEMPLAR_ROWS} rows):\n"
        + json.dumps(raw, ensure_ascii=False, indent=1)
    )


def _rules() -> str:
    cats, jobs = _taxonomy_ids()
    types = ", ".join(sorted(PARAM_TYPES))
    lines = [
        "playbook.json:",
        '- "title", "promise" and "expectation" are required. "expectation" is {"recall": the share, 0 to 1, '
        'of the right cards a careful person would file; "false_claims": how many wrong cards are allowed, '
        'a whole number, usually 0; "minutes": a whole number; "why": one sentence}.',
        f'- "category" is one of: {", ".join(cats)}. "job" is one of: {", ".join(jobs)}.',
        '- Also write "short_title", "brief" (a few plain lines: what she will do and what she leaves '
        'alone) and "persona" (who the person is).',
        '- Do not write "id" (Athena sets it), and never "featured".',
        "",
        "world.json:",
        '- "today": the date the practice apps live on, YYYY-MM-DD.',
        '- "apps": one invented practice app per place in the sketch, two or three in all. Each is '
        '{"app_id": a short lowercase id (letters, digits, _), unique; "name"; "origin": '
        '"https://<invented>.example"; "view": a small object of what the page shows at a glance; '
        '"tools": [...]}.',
        '- A tool is {"name": lowercase_with_underscores, unique within its app; "kind"; "description": '
        "plain sentences, the first clause is what the person reads on the card; "
        f'"params": {{"<param>": {{"type": one of {types}, "description": "..."}}}}}}. '
        f"An app id and a tool name together are at most {TOOL_NAME_MAX - 2} characters.",
        '- A READ tool has "kind": "READ" and "returns": {"table": a table in "tables" (required); '
        '"match": {"<its param>": "<a column of that table>"}; "require": [its params]; "default": '
        '{"<its param>": value}; "page_size": a whole number above 0; "fields": [columns to show]}. '
        'Only "table" is required; "match", "require" and "default" name only the tool\'s own params, '
        'and "match" only columns the table has.',
        '- An act tool files a card the person signs: "kind" is "REACHES_A_PERSON" (it reaches someone) '
        'or "PERMANENT" (it cannot be undone), and it needs "says": what the page answers once it runs, '
        'with {param} slots. It has at least one param, and exactly one param is marked "key": true: the '
        "case the card is about (a row id from a table, such as an invoice line or a day), so each case "
        "gets its own card.",
        '- "tables": {"<name>": [row objects]}: invented rows, 5 to 20 per table, holding both the cases '
        "she should act on and a few she should leave alone, so the person can tell them apart.",
        '- "phases": [{"app": an app_id, "message": what the person says to open that app, in their own '
        'voice, "nudges": a whole number 0 to 3}], in the order of the sketch. Every phase opens an app '
        "the world has.",
        "- No senses: every table is written in world.json.",
    ]
    return "\n".join(lines)


def _messages(daemon: Daemon, draft: Draft) -> list[dict[str, Any]]:
    system = [
        "You write one chore for Athena, a desktop companion, as two JSON documents: playbook.json (what "
        "the chore is) and world.json (her practice apps: invented websites she rehearses the chore on "
        "before she is trusted with the real ones). Everything in it is invented: names, addresses, "
        "people, rows. Never use a real company, person or address.",
        'Answer with one JSON object and nothing else: {"playbook": {...}, "world": {...}}.',
        "## The rules the files are checked by\n" + _rules(),
    ]
    example = _nearest(draft)
    if example is not None:
        system.append("## An example chore from Athena's library (its answer key is never shown)")
        system.append(_exemplar(example))
    turns = daemon.conversation.list(draft["space_id"], CONVERSATION_TURNS)
    said = "\n".join(f"{'Person' if t['role'] == 'person' else 'Athena'}: {t['text']}" for t in turns)
    user = [
        f"## The person's need, in their words\n{draft['need']}",
        "## The sketch agreed with the person (their picture of the process, not the files)\n"
        + sketch_text(draft),
        "## The conversation\n" + (said or "(none: the sketch is all there is)"),
    ]
    if draft.get("note"):
        user.append(f"## What the person asked to change last time\n{draft.get('note')}")
    user.append("Write the chore now.")
    return [
        {"role": "system", "content": "\n\n".join(system)},
        {"role": "user", "content": "\n\n".join(user)},
    ]


def _repair_message(problems: list[str]) -> str:
    lines = "\n".join(f"- {p}" for p in problems)
    return (
        f"The files were checked and these problems were found:\n{lines}\n"
        'Fix every one and answer with the whole corrected JSON object {"playbook": {...}, "world": {...}}.'
    )


def _clear(folder: Path) -> None:
    if folder.is_dir():
        shutil.rmtree(folder)
    folder.mkdir(parents=True, exist_ok=True)


def _attempt(
    answer: str, folder: Path, chore_id: str | None, draft: Draft, taken: set[str]
) -> tuple[list[str], str | None]:
    """(problems, chore id). Writes the answer into `folder/<chore id>/` and loads it."""
    doc = first_object(answer, "world")
    if not isinstance(doc, dict) or not all(isinstance(doc.get(k), dict) for k in ("playbook", "world")):
        return [NO_ANSWER], chore_id
    playbook = {k: v for k, v in doc["playbook"].items() if k not in ("id", "featured")}
    if chore_id is None:
        chore_id = unique_id(slug(str(playbook.get("title") or draft["need"])), taken)
    playbook = {"id": chore_id, **playbook}
    _clear(folder)
    root = folder / chore_id
    root.mkdir()
    for name, body in (
        ("playbook.json", playbook),
        ("world.json", doc["world"]),
        ("truth.json", TRUTH_EMPTY),
    ):
        (root / name).write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ours = _usable(doc["world"])
    try:
        load_chore(root, origin="yours")
    except ChoreError as e:
        return e.problems + ours, chore_id
    except (ValueError, TypeError) as e:  # a value the loader cannot even read, such as nudges in words
        return [f"{WRONG_KIND}: {e}", *ours], chore_id
    return ours, chore_id


def _back(daemon: Daemon, draft_id: str) -> None:
    daemon.drafts.put(cast("Draft", {**daemon.drafts.get(draft_id), "step": "shape"}))


def write(daemon: Daemon, engine: Engine, draft_id: str) -> Iterator[dict[str, Any]]:
    """AuthorEvents: `writing`, `repair`*, then `written` or `author_failed`. Validates first."""
    draft = daemon.drafts.get(draft_id)
    if draft["step"] not in WRITABLE:
        raise ApiError("bad_request", "she writes the chore from the sketch; go back to the sketch first")
    folder = data_folder(daemon, draft)
    not_busy(daemon, draft)
    return _write(daemon, engine, draft_id, folder)


def _write(daemon: Daemon, engine: Engine, draft_id: str, folder: Path) -> Iterator[dict[str, Any]]:
    space_id = daemon.drafts.get(draft_id)["space_id"]
    with daemon.busy.turn(space_id):
        daemon.drafts.skip_open(draft_id)  # "That's enough, write it": open slots read skipped
        draft = daemon.drafts.put(cast("Draft", {**daemon.drafts.get(draft_id), "step": "author"}))
        yield {"type": "writing"}
        messages = _messages(daemon, draft)
        taken = chore_ids(daemon.data_dir)
        chore_id: str | None = None
        problems: list[str] = []
        for attempt in range(REPAIRS_MAX + 1):
            try:
                answer = call_model(daemon, engine, space_id, messages)
            except EngineError as e:
                _clear(folder)
                _back(daemon, draft_id)
                yield {"type": "error", "error": "engine_unavailable", "reason": e.reason}
                return
            problems, chore_id = _attempt(answer, folder, chore_id, draft, taken)
            if not problems and chore_id is not None:
                done = cast("dict[str, Any]", dict(daemon.drafts.get(draft_id)))
                done.update(step="preview", chore_id=chore_id)
                for stale in ("expected", "key", "bench", "verdict", "note"):
                    done.pop(stale, None)
                daemon.drafts.put(cast("Draft", done))
                yield {"type": "written", "chore_id": chore_id}
                return
            if attempt < REPAIRS_MAX:
                yield {"type": "repair", "problems": [plain(p) for p in problems]}
                messages = [
                    *messages,
                    {"role": "assistant", "content": answer},
                    {"role": "user", "content": _repair_message(problems)},
                ]
        _clear(folder)
        _back(daemon, draft_id)
        yield {"type": "author_failed", "problems": [plain(p) for p in problems]}
