"""The preview: one call in which Athena reads her practice apps and lists the cards she would file.

The call is given the written world (every table and tool) and the sketch, and answers JSON cards
`{app, tool, key, label, why}`. A card whose app or tool is not an act tool of the written chore is
dropped, as is a second card for the same case; the rest are numbered `e1..en` and kept on the draft
as `expected`. The person's marks on them become the answer key (see `key`).
"""

from __future__ import annotations

from typing import Any, cast

from athena.app import Daemon
from athena.contracts import DETAIL_MAX, LABEL_MAX, Draft, ExpectedCard
from athena.drafts.author import (
    act_tools,
    call_model,
    first_object,
    key_param,
    load_written,
    not_busy,
    sketch_text,
    world_text,
)
from athena.engine import Engine, EngineError
from athena.errors import ApiError

#: A card's label is one line on screen and its why one sentence; longer text is cut at a word.
CARD_LABEL_MAX = 2 * LABEL_MAX
CARD_WHY_MAX = DETAIL_MAX
CARDS_MAX = 40


def cut(text: str, n: int) -> str:
    text = " ".join(text.split())
    if len(text) <= n:
        return text
    head = text[: n - 1]
    if " " in head:
        head = head.rsplit(" ", 1)[0]
    return head.rstrip(" ,;:.-") + "…"


def _text(value: Any) -> str:
    """A model's value as one line of text: text or a bare number; anything else is none."""
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        return ""
    return " ".join(str(value).split())


def cards(raw: Any, acts: set[tuple[str, str]], prefix: str = "e") -> list[ExpectedCard]:
    """The model's cards, each checked: an act tool of the chore, a case named, one card per case."""
    items = raw.get("expected") if isinstance(raw, dict) else raw
    out: list[ExpectedCard] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        app, tool, key = _text(item.get("app")), _text(item.get("tool")), _text(item.get("key"))
        if "__" in tool and not app:  # the model-facing name `<app>__<tool>`
            app, tool = tool.split("__", 1)
        if (app, tool) not in acts or not key:
            continue
        case = (app, tool, key.casefold())
        if case in seen:
            continue
        seen.add(case)
        label = _text(item.get("label")) or f"{tool.replace('_', ' ')} {key}"
        card: ExpectedCard = {
            "id": f"{prefix}{len(out) + 1}",
            "app": app,
            "tool": tool,
            "key": key,
            "label": cut(label, CARD_LABEL_MAX),
            "why": cut(_text(item.get("why")), CARD_WHY_MAX),
        }
        out.append(card)
        if len(out) >= CARDS_MAX:
            break
    return out


def _messages(draft: Draft, world: str, keys: list[str]) -> list[dict[str, Any]]:
    system = (
        "You are Athena. Before a test run on your practice apps, you tell the person which cards you "
        "expect to file, so they can say whether that is what they want. Read the practice apps below "
        "(every table and tool) and list each card you would file with an act tool: one card per case.\n"
        'Answer with JSON only: {"expected": [{"app": the app_id, "tool": the act tool\'s name, "key": the '
        'value you would give the tool\'s key param, exactly as the table writes it, "label": one short '
        'line the person reads, "why": one plain sentence naming what in the tables makes it right}]}.\n'
        "List only cards you would file; leave out what you would leave alone. Never invent a case the "
        "tables do not hold."
    )
    user = "\n\n".join(
        [
            f"## The person's need\n{draft['need']}",
            f"## The sketch agreed with the person\n{sketch_text(draft)}",
            "## The act tools and the param that names each card's case\n" + "\n".join(keys),
            f"## Your practice apps\n{world}",
        ]
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def preview(daemon: Daemon, engine: Engine, draft_id: str) -> list[ExpectedCard]:
    """Every card names a real act tool of the written chore; one that does not is dropped."""
    draft = daemon.drafts.get(draft_id)
    if draft["step"] != "preview":
        raise ApiError("bad_request", "she previews the cards once the chore is written and before the key")
    chore = load_written(daemon, draft)
    not_busy(daemon, draft)
    acts = act_tools(chore)
    keys = [f"- {a}.{t}: {key_param(chore, a, t)}" for a, t in acts]
    with daemon.busy.turn(draft["space_id"]):
        try:
            answer = call_model(daemon, engine, draft["space_id"], _messages(draft, world_text(chore), keys))
        except EngineError as e:
            raise ApiError("engine_unavailable", e.reason) from e
        listed = cards(first_object(answer, "expected"), set(acts))
        if not listed:
            raise ApiError(
                "engine_unavailable", "She could not name a card on her practice apps; try the preview again."
            )
        stored = cast("dict[str, Any]", dict(daemon.drafts.get(draft_id)))
        stored["expected"] = listed
        daemon.drafts.put(cast("Draft", stored))
    return listed
