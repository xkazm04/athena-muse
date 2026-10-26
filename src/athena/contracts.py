"""The wire contract between the daemon and the desktop.

Every identifier that crosses the loopback lives here and in `apps/desktop/src/lib/contract.ts`,
key for key. JSON keys are snake_case. Absent values: the key is omitted (never null); core is the
empty string `""`; `cost_usd` omitted means unpriced.

Vocabulary: the person's word is Project, the wire's is space (`spc_` ids), so a later Chores port
keeps athena-portable's `proj_` meaning for a chore's case.
"""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

VERSION = "0.1.0"

# --- ids and caps ---------------------------------------------------------------------------------

SPACE_PREFIX = "spc_"
CORE = ""  # the space of everything outside every project
CORE_ITEM = "core"  # path segment standing in for CORE where an empty segment cannot be written

NAME_MAX = 60
BRIEF_MAX = 1600
APPS_MAX = 24
SPACES_MAX = 100
HUE_MAX = 359
TEXT_MAX = 8000  # one person message
MEMORY_LIMIT_DEFAULT = 50
MEMORY_LIMIT_MAX = 200
LEDGER_LIMIT_DEFAULT = 100
TOOL_ROUNDS_MAX = 6  # model calls per turn

# --- enums ----------------------------------------------------------------------------------------

ErrorWord = Literal["bad_request", "unknown_ref", "space_busy", "unauthorized", "engine_unavailable"]
EngineId = Literal["muse", "scripted"]
KeySource = Literal["env", "file", "absent"]
MemoryKind = Literal["episode", "fact"]
Role = Literal["person", "athena"]
ActionClass = Literal["auto", "gated"]
CardState = Literal["waiting", "approved", "declined"]
Verdict = Literal["approve", "decline"]
Surface = Literal["turn", "probe"]
ActionName = Literal["recall", "remember", "propose_brief", "add_app", "forget"]
AppEventType = Literal["card_filed", "card_resolved", "space_changed", "active_space", "engine", "turn_done"]

# The closed action catalog. The daemon is its only author; the class decides whether it runs or
# files a card. A project never changes a class.
CATALOG: dict[ActionName, ActionClass] = {
    "recall": "auto",
    "remember": "auto",
    "propose_brief": "gated",
    "add_app": "gated",
    "forget": "gated",
}


# --- shapes ---------------------------------------------------------------------------------------


class ErrorBody(TypedDict):
    error: ErrorWord
    reason: str


class Health(TypedDict):
    ok: bool
    version: str


class EngineStatus(TypedDict):
    engine: EngineId
    model: str
    key: KeySource
    simulated: bool


class Probe(TypedDict):
    ok: bool
    model: NotRequired[str]
    latency_ms: NotRequired[int]
    error: NotRequired[str]


class SpaceCounts(TypedDict):
    episodes: int
    facts: int


class SpaceSummary(TypedDict):
    id: str
    name: str
    brief: str
    apps: list[str]
    hue: int
    created: str  # ISO 8601 UTC
    updated: str
    counts: SpaceCounts


class SpaceErased(TypedDict):
    id: str
    episodes: int
    facts: int
    turns: int


class MemoryRow(TypedDict):
    id: str
    kind: MemoryKind
    line: str  # <= 240 characters
    created: str
    space_id: str


class MemoryPage(TypedDict):
    rows: list[MemoryRow]
    showing: int
    total: int


class ActiveSpace(TypedDict):
    space_id: str


class Card(TypedDict):
    id: str
    space_id: str
    action: ActionName
    label: str  # plain words: what will happen if signed
    args: dict[str, Any]
    state: CardState
    created: str
    resolved: NotRequired[str]


class Turn(TypedDict):
    id: str
    space_id: str
    role: Role
    text: str
    created: str
    cost_usd: NotRequired[float]
    card_id: NotRequired[str]


class LedgerRow(TypedDict):
    id: int
    ts: str
    surface: Surface
    space_id: str
    engine: EngineId
    model: str
    input_tokens: NotRequired[int]
    output_tokens: NotRequired[int]
    cost_usd: NotRequired[float]
    cost_estimated: bool
    latency_ms: int
    ok: bool
    error: NotRequired[str]


class LedgerTotals(TypedDict):
    calls: int
    cost_usd: float
    cost_estimated: bool


class LedgerPage(TypedDict):
    rows: list[LedgerRow]
    totals: LedgerTotals


# --- the turn stream (NDJSON, one object per line) ------------------------------------------------


class StartEvent(TypedDict):
    type: Literal["start"]
    turn_id: str
    engine: EngineId
    simulated: bool


class TextEvent(TypedDict):
    type: Literal["text"]
    delta: str


class ToolEvent(TypedDict):
    type: Literal["tool"]
    name: ActionName
    label: str
    # `class` is a Python keyword; the wire key is "class" (see tool_event()).


class CardEvent(TypedDict):
    type: Literal["card"]
    card: Card


class DoneEvent(TypedDict):
    type: Literal["done"]
    turn_id: str
    waiting: bool
    cost_usd: NotRequired[float]


class ErrorEvent(TypedDict):
    type: Literal["error"]
    error: ErrorWord
    reason: str


def tool_event(name: ActionName, label: str) -> dict[str, Any]:
    """The tool line of a turn stream: `{type, name, label, class}`."""
    return {"type": "tool", "name": name, "label": label, "class": CATALOG[name]}


class AppEvent(TypedDict):
    """One SSE message on `/events`. Payload keys by type:
    card_filed / card_resolved: `card`; space_changed: `space_id` (and `erased: true` on erase);
    active_space: `space_id`; engine: `status`; turn_done: `space_id`, `turn_id`.
    """

    type: AppEventType
    card: NotRequired[Card]
    space_id: NotRequired[str]
    erased: NotRequired[bool]
    status: NotRequired[EngineStatus]
    turn_id: NotRequired[str]


# --- routes ---------------------------------------------------------------------------------------

ROUTES = {
    "health": "/health",
    "engine": "/engine",
    "engine_key": "/engine/key",
    "engine_probe": "/engine/probe",
    "spaces": "/spaces",
    "space": "/spaces/{id}",
    "space_memory": "/spaces/{id}/memory",
    "memory_core": "/spaces/{id}/memory/{mem_id}/core",
    "active_space": "/settings/active-space",
    "conversation": "/conversation",
    "run": "/run",
    "cards": "/cards",
    "decision": "/decisions/{card_id}",
    "ledger": "/ledger",
    "events": "/events",
}
