"""The wire contract between the daemon and the desktop.

Every identifier that crosses the loopback lives here and in `apps/desktop/src/lib/contract.ts`,
key for key. JSON keys are snake_case. Absent values: the key is omitted (never null); core is the
empty string `""`; `cost_usd` omitted means unpriced.

Vocabulary: the person's word is Project, the wire's is space (`spc_` ids); `proj_` stays free for
a chore's case.
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
EngineId = Literal["muse", "muse_code", "claude_code", "scripted"]
KeySource = Literal["env", "file", "absent"]
MemoryKind = Literal["episode", "fact"]
Role = Literal["person", "athena"]
ActionClass = Literal["auto", "gated"]
CardState = Literal["waiting", "approved", "declined"]
Verdict = Literal["approve", "decline"]
Surface = Literal["turn", "probe", "design", "rehearsal", "twin"]
ActionName = Literal[
    "recall",
    "remember",
    "propose_brief",
    "add_app",
    "forget",
    "portal_read",
    "portal_act",
    "sketch",
    "ask",
    "twin_send",
    "twin_note",
]
AppEventType = Literal["card_filed", "card_resolved", "space_changed", "active_space", "engine", "turn_done"]

# The closed action catalog. The daemon is its only author; the class decides whether it runs or
# files a card. A project never changes a class.
CATALOG: dict[ActionName, ActionClass] = {
    "recall": "auto",
    "remember": "auto",
    "propose_brief": "gated",
    "add_app": "gated",
    "forget": "gated",
    # A chore's invented portals (ADR 0005): a READ tool answers at once, any other files a card.
    "portal_read": "auto",
    "portal_act": "gated",
    # The stage (ADR 0007): offered only on a draft's design turn; they change the sketch, nothing else.
    "sketch": "auto",
    "ask": "auto",
    # Twins (ADR 0009): one Gmail message (in-thread when replying), one Notion append or create. A
    # draft the send rule lets go alone runs without a card; every other one waits on this class.
    "twin_send": "gated",
    "twin_note": "gated",
}

# --- chores (ADR 0005) ---------------------------------------------------------------------------

SenseName = Literal["paper", "call", "walk", "circle"]
FeaturedStatus = Literal["proven", "rehearsed", "failing", "unproven"]
BenchWord = Literal["exceeds", "meets", "short"]
ProofOp = Literal[">=", "<="]
ChoreOrigin = Literal["library", "yours"]  # the app's playbooks/ or the person's <data_dir>/chores/

# --- drafts: a chore written in conversation (ADR 0007) ------------------------------------------

DraftStep = Literal["describe", "shape", "author", "preview", "rehearse", "verdict", "saved"]
Slot = Literal["need", "apps", "inputs", "steps", "hand", "output", "never"]
SketchKind = Literal["source", "app", "step", "gate", "output", "never"]
NodeOrigin = Literal["you", "athena"]
SketchOpName = Literal["add", "change", "remove", "link"]
Mark = Literal["yes", "no"]
DraftVerdict = Literal["keep", "revise"]
StageView = Literal["drawing", "orbit"]  # the two views of the stage, switched by a tab

FOLLOW_UPS_MAX = 2  # questions per slot after the first
REPAIRS_MAX = 2  # silent authoring repairs before author_failed
SKETCH_NODES_MAX = 60
LABEL_MAX = 80  # a node's label and a suggested answer
DETAIL_MAX = 240  # a node's optional second line
ASK_TEXT_MAX = 240  # one question, shown whole on the stage
SUGGESTIONS_MIN = 2
SUGGESTIONS_MAX = 4
NEED_MAX = 2000

# --- twins: a clone that speaks for you (ADR 0008-0010) -------------------------------------------
# A name the wire already uses (`Mark`, `Decision` on a card) is prefixed for twins.

Place = Literal["who", "channels", "voice", "knowledge", "chores", "never", "autonomy", "memory", "mission"]
ChannelKind = Literal["gmail", "notion"]
Autonomy = Literal["review", "assist", "auto"]
TwinState = Literal["setting_up", "live", "paused"]
ChannelStatus = Literal["connected", "needs_sign_in", "disconnected"]
ChannelHealth = Literal["active", "quiet", "stale"]  # omitted on a channel that has never spoken
MissionState = Literal["open", "resolved", "handed_back"]
SendDecision = Literal["sent_alone", "waits"]
WaitReason = Literal["review", "assist", "first_message", "below_bar", "risk", "paused"]
TwinMark = Literal["me", "edited", "not_me"]
ChoreKind = Literal["outcome", "inbox", "test", "channel"]
DialSource = Literal["learned", "preset", "you"]
TwinTurnSide = Literal["twin", "other"]
TwinMessageKind = Literal["first_message", "reply"]
PieceOpName = Literal["add", "change", "remove", "dial"]
SetupPanel = Literal["connect", "samples", "style", "pages", "chores", "autonomy", "memory", "rehearsal"]
FactSuggest = Literal["keep", "drop"]
ConnectState = Literal["idle", "waiting", "exchanging", "done", "failed"]

TWINS_MAX = 20
SAMPLES_MAX = 12  # sent mail the voice is learned from
BAR_MIN = 50  # how sure a draft must be, in whole percent, to send alone on Auto
BAR_MAX = 99
BAR_DEFAULT = 80
RISKS_MAX = 5  # lines on one draft's risk list
POLL_SECONDS_DEFAULT = 300  # Gmail threads with an open mission, while the daemon runs
DIAL_MIN = 1  # a style dial's value
DIAL_MAX = 5


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


class SpaceList(TypedDict):
    spaces: list[SpaceSummary]


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


class TurnList(TypedDict):
    turns: list[Turn]


class CardList(TypedDict):
    cards: list[Card]


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


class ChoreApp(TypedDict):
    app_id: str
    name: str


class BenchSummary(TypedDict):
    """The latest bench run of a chore (`playbooks/<id>/bench.json`)."""

    verdict: BenchWord
    reasons: list[str]
    found: int
    eligible: int
    value_found_usd: float
    value_total_usd: float
    false_claims: int
    duplicates: int
    traps_filed: int
    turns: int
    minutes: float
    engine: EngineId
    model: str
    run_at: str  # ISO 8601 UTC
    cost_usd: NotRequired[float]  # omitted = unpriced (a plan-billed CLI engine)


class ProofRow(TypedDict):
    """One row of `senses/proofs.json`: a spike proof measured on one build."""

    sense: SenseName
    id: str  # the proof id, unique per sense (F1, R2...)
    question: str
    bar: float
    op: ProofOp
    passed: bool
    n: int
    measured: NotRequired[float]
    note: NotRequired[str]


class ChoreSummary(TypedDict):
    id: str
    title: str
    short_title: str
    promise: str
    category: str
    job: str
    senses: list[SenseName]  # empty for a chore that is not featured
    featured: FeaturedStatus  # computed from proofs.json, never authored
    origin: ChoreOrigin
    bench: NotRequired[BenchSummary]


class ChoreList(TypedDict):
    chores: list[ChoreSummary]


class ChoreDetail(TypedDict):
    chore: ChoreSummary
    brief: str
    persona: str
    apps: list[ChoreApp]
    proofs: list[ProofRow]
    backends: dict[str, str]  # the sense roles the proofs ran on: segmenter / transcriber / reader


# --- drafts (ADR 0007) ----------------------------------------------------------------------------
# The sketch is the person's picture of the process, not the chore's source: Athena writes the chore
# files in one step once it is agreed. Coverage is computed from the sketch, never claimed by a model.

CoverageValue = float | Literal["skipped"]  # 0, 0.5 or 1; "skipped" = left open with a stated default


class SketchNode(TypedDict):
    id: str
    kind: SketchKind
    slot: Slot
    label: str  # <= LABEL_MAX
    origin: NodeOrigin  # "you": the person's own words, confirmed when added; "athena": a proposal
    confirmed: bool
    detail: NotRequired[str]
    quote: NotRequired[str]  # on the person's nodes: their own words it was drawn from, verbatim


# `from` is a Python keyword, so this one is spelled the functional way.
SketchEdge = TypedDict("SketchEdge", {"from": str, "to": str})


class Sketch(TypedDict):
    nodes: list[SketchNode]
    edges: list[SketchEdge]


class SketchOp(TypedDict):
    """One change to the sketch, as applied. `add` and `change` carry the whole node after the change;
    `remove` carries the node or the edge removed; `link` carries the edge."""

    op: SketchOpName
    node: NotRequired[SketchNode]
    edge: NotRequired[SketchEdge]


class Ask(TypedDict):
    slot: Slot
    text: str
    suggestions: list[str]
    follow_up: int  # 0 for the first question on a slot, up to FOLLOW_UPS_MAX


class Coverage(TypedDict):
    need: CoverageValue
    apps: CoverageValue
    inputs: CoverageValue
    steps: CoverageValue
    hand: CoverageValue
    output: CoverageValue
    never: CoverageValue


class PracticeApp(TypedDict):
    """One invented app of a written chore, as the person sees it on the stage."""

    app_id: str
    name: str
    reads: list[str]  # what she can look at there, in plain words
    acts: list[str]  # what she can do there (each waits for a signature)
    rows: int  # invented rows across the tables she reads there


class ExpectedCard(TypedDict):
    """A card Athena expects to file on her practice apps; the person's marks turn it into the key."""

    id: str
    app: str  # the practice app's id
    tool: str  # its act tool
    key: str  # the case the card is about, as truth.json names it
    label: str
    why: str


class ExpectedList(TypedDict):
    expected: list[ExpectedCard]


class KeyMark(TypedDict):
    expected_id: str
    mark: Mark  # yes = eligible, no = a trap
    note: NotRequired[str]


class MissingCard(TypedDict):
    """A card the person says she should have listed. `expected` is filled when Athena could place it
    on her practice apps (a tool and a key); a line she could not place is kept and not scored."""

    text: str
    expected: NotRequired[ExpectedCard]


class NeverLine(TypedDict):
    """A "she must never..." line. `tool` is the act tool it forbids, when Athena could name one and
    the person did not also say yes to that tool; a line without one is kept as words."""

    text: str
    tool: NotRequired[str]


class DraftKey(TypedDict):
    marks: list[KeyMark]
    missing: list[MissingCard]
    never: list[NeverLine]


class Draft(TypedDict):
    id: str  # drf_ + 12 hex
    space_id: str  # the draft's Project, made active when the draft starts
    step: DraftStep
    need: str
    sketch: Sketch
    coverage: Coverage
    agreed: bool  # computed: need, apps, hand, output at 1; the rest at 0.5, 1 or skipped
    created: str
    updated: str
    chore_id: NotRequired[str]  # once written
    practice: NotRequired[list[PracticeApp]]  # once written: her practice apps
    ask: NotRequired[Ask]  # while shaping: the question still open, so a reopened stage shows it
    expected: NotRequired[list[ExpectedCard]]  # once previewed
    key: NotRequired[DraftKey]  # once marked
    bench: NotRequired[BenchSummary]  # once a test run has finished
    verdict: NotRequired[DraftVerdict]
    note: NotRequired[str]  # the person's words with a "revise" verdict
    views: NotRequired[dict[StageView, int]]  # stage turns that counted, per view the person answered in


class DraftAbandoned(TypedDict):
    id: str  # DELETE /drafts/{id}: the draft is gone, its Project stays


class NewDraftBody(TypedDict):
    need: str  # 1..NEED_MAX


class SayBody(TypedDict):
    text: str  # "" when the person picked a suggestion
    choice: NotRequired[str]
    view: NotRequired[StageView]  # the view the person answered in; counted on the draft


class ConfirmBody(TypedDict):
    node_ids: list[str]


class DropBody(TypedDict):
    node_ids: list[str]  # Athena's unconfirmed guesses the person rubs out, with their links


class KeyBody(TypedDict):
    marks: list[KeyMark]
    missing: list[str]
    never: list[str]


class VerdictBody(TypedDict):
    verdict: DraftVerdict
    note: NotRequired[str]


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


class SketchEvent(TypedDict):
    """Stage turns only: the sketch changes this reply made, in order."""

    type: Literal["sketch"]
    ops: list[SketchOp]


class AskEvent(TypedDict):
    type: Literal["ask"]
    ask: Ask


class CoverageEvent(TypedDict):
    type: Literal["coverage"]
    coverage: Coverage
    agreed: bool


# --- authoring and the test run (NDJSON streams of POST /drafts/{id}/write and /rehearse) ---------


class AuthorWriting(TypedDict):
    type: Literal["writing"]


class AuthorRepair(TypedDict):
    type: Literal["repair"]
    problems: list[str]  # plain words


class AuthorWritten(TypedDict):
    type: Literal["written"]
    chore_id: str
    practice: list[PracticeApp]


class AuthorFailed(TypedDict):
    type: Literal["author_failed"]
    problems: list[str]


class RehearsalPhase(TypedDict):
    type: Literal["phase"]
    index: int  # from 1
    app: str
    message: str


class RehearsalCard(TypedDict):
    type: Literal["card"]
    card: Card


class RehearsalScored(TypedDict):
    type: Literal["scored"]
    bench: BenchSummary


# A failed write or run streams the turn's ErrorEvent shape: {type: "error", error, reason}.


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


# --- twins (ADR 0008-0010) ------------------------------------------------------------------------
# Field names follow docs/concepts/twin-module/prototypes/shared/SCHEMA.md. The daemon computes every
# derived number (`readiness`, `coverage`, `ready`, `open_missions`, `waiting_count`, the stats); an
# unmeasured figure is an omitted key and reads "-", never 0. Percent values are whole numbers 0-100.


class Piece(TypedDict):
    """One part of a twin, on its place in the document. Origin is computed as a sketch node's is."""

    id: str
    place: Place
    label: str  # <= LABEL_MAX
    origin: NodeOrigin  # "you": the person's words, confirmed when added; "athena": her proposal
    confirmed: bool
    detail: NotRequired[str]
    quote: NotRequired[str]  # on the person's pieces: their own words it was drawn from, verbatim
    evidence: NotRequired[list[str]]  # the sample ids it was learned from


class PlaceCoverage(TypedDict):
    who: CoverageValue
    channels: CoverageValue
    voice: CoverageValue
    knowledge: CoverageValue
    chores: CoverageValue
    never: CoverageValue
    autonomy: CoverageValue
    memory: CoverageValue
    mission: CoverageValue


class StyleDial(TypedDict):
    id: str
    label: str
    low: str  # the word at DIAL_MIN
    high: str  # the word at DIAL_MAX
    value: int  # DIAL_MIN..DIAL_MAX
    source: DialSource


class Sample(TypedDict):
    """A sent mail of the person's that the voice may be learned from."""

    id: str
    to: str
    subject: str
    date: str  # ISO 8601 date
    words: int
    excerpt: str
    suggest: bool  # Athena suggests learning from it
    picked: bool  # the person's choice
    why_not: NotRequired[str]  # when she does not suggest it


class NotionPage(TypedDict):
    id: str
    title: str
    kind: str  # Notion's word: "page" or "database"
    suggest: bool
    picked: bool
    why_not: NotRequired[str]


class ChorePreset(TypedDict):
    """A ready-made chore the twin may run (ADR 0005); the catalogue grows with the tools."""

    id: str
    tool: str  # the tool it runs on: "notion" today, others listed as `coming`
    name: str
    does: str
    kind: ChoreKind
    suggest: bool
    picked: bool
    later: NotRequired[bool]  # can be picked once the twin is live
    coming: NotRequired[bool]  # a tool this app cannot reach yet: shown, never picked


# `from` is a Python keyword, so this one is spelled the functional way.
MemoryFact = TypedDict(
    "MemoryFact",
    {
        "id": str,
        "fact": str,
        "from": str,  # where she noticed it, in plain words
        "suggest": FactSuggest,
        "reason": NotRequired[str],  # why she suggests it
        "keep": NotRequired[bool],  # the person's call; omitted until they make it
    },
)


class AutonomySplit(TypedDict):
    """A channel with two levels: one for first messages, one for replies."""

    first_message: Autonomy
    reply: Autonomy


class TwinChannel(TypedDict):
    kind: ChannelKind
    account: str
    status: ChannelStatus
    autonomy: Autonomy
    bar: int  # BAR_MIN..BAR_MAX; kept on every level, it only matters where a level is Auto
    split: NotRequired[AutonomySplit]  # when set, it decides the level per kind of message
    scope: NotRequired[str]  # what it may touch there, in plain words ("practice page only")
    health: NotRequired[ChannelHealth]  # computed from last_at
    last_at: NotRequired[str]


class MissionBeat(TypedDict):
    label: str
    done: bool


class MissionTurn(TypedDict):
    """One message of a mission or the dress rehearsal. The twin's turns carry its draft facts."""

    id: str
    side: TwinTurnSide
    text: str  # what was sent, or the draft as it waits
    at: str  # ISO 8601 UTC
    kind: NotRequired[TwinMessageKind]  # the twin's turns from here down
    confidence: NotRequired[int]  # how sure it was, whole percent
    risks: NotRequired[list[str]]  # its risk list, plain words, <= RISKS_MAX
    decision: NotRequired[SendDecision]
    reason: NotRequired[WaitReason]  # when it waits
    bar: NotRequired[int]  # the bar it was held against, when its level was Auto
    elapsed_s: NotRequired[float]  # how long it took to write
    draft: NotRequired[str]  # the waiting draft's id
    mark: NotRequired[TwinMark]  # the person's mark (rehearsal)
    edited_text: NotRequired[str]  # with mark "edited": the person's words
    learned: NotRequired[str]  # what an edit taught it, in plain words


class TwinFiled(TypedDict):
    """What a preset chore wrote when a mission ended."""

    chore: str  # the ChorePreset id
    where: str  # plain words: "Notion: Partnerships"
    row: dict[str, str]


# `with` is a Python keyword, so this one is spelled the functional way.
Mission = TypedDict(
    "Mission",
    {
        "id": str,
        "twin_id": str,
        "title": str,
        "with": str,  # who the conversation is with
        "channel": ChannelKind,
        "goal": str,
        "state": MissionState,
        "beats": list[MissionBeat],
        "turns": list[MissionTurn],
        "created": str,
        "last_at": NotRequired[str],
        "note": NotRequired[str],  # the latest, in plain words ("They said 'by Friday'.")
        "thread": NotRequired[str],  # the Gmail thread it lives on
        "practice": NotRequired[bool],  # the dress rehearsal on a Notion practice page
        "filed": NotRequired[TwinFiled],
    },
)


class TwinDraft(TypedDict):
    """A message the twin wrote. A waiting one is a signature card the person may edit."""

    id: str
    twin_id: str
    channel: ChannelKind
    to: str
    subject: str
    text: str
    confidence: int
    risks: list[str]
    decision: SendDecision
    created: str
    mission: NotRequired[str]
    reason: NotRequired[WaitReason]  # when it waits
    bar: NotRequired[int]  # the bar it was held against, when its level was Auto
    card_id: NotRequired[str]  # when it waits
    answers: NotRequired[str]  # the message it replies to; omitted on a first message


class TwinWeek(TypedDict):
    """The last seven days; each figure is omitted until measured."""

    sent: NotRequired[int]
    sent_alone: NotRequired[int]
    held_by_risk: NotRequired[int]
    median_reply_min: NotRequired[float]
    cost_usd: NotRequired[float]  # an estimate; the screen says "est."


class TwinSummary(TypedDict):
    """One twin: a document in the wallet and a row of the ledger."""

    id: str  # tw_ + 12 hex
    space_id: str
    name: str
    purpose: str
    state: TwinState
    channels: list[TwinChannel]
    week: TwinWeek
    readiness: int  # whole percent: the mean coverage over the places setup requires
    open_missions: int  # open or handed back
    waiting_count: int  # drafts waiting for a signature
    missions: list[Mission]
    waiting: list[TwinDraft]  # drafts waiting for a signature, oldest first
    created: str
    updated: str
    since: NotRequired[str]  # when it first went live
    paused_because: NotRequired[str]


class TwinAsk(TypedDict):
    place: Place
    text: str
    suggestions: list[str]
    follow_up: int
    panel: NotRequired[SetupPanel]  # the working slip this question needs
    channel: NotRequired[ChannelKind]  # with panel "connect"


class TwinDetail(TwinSummary):
    pieces: list[Piece]
    coverage: PlaceCoverage
    ready: bool  # computed: the dress rehearsal may start
    dials: list[StyleDial]
    style_presets: list[str]
    samples: list[Sample]
    pages: list[NotionPage]
    chores: list[ChorePreset]
    memory: list[MemoryFact]
    ask: NotRequired[TwinAsk]  # while setting up: the question still open
    rehearsal: NotRequired[Mission]  # the latest dress rehearsal


class TwinStats(TypedDict):
    """The stat strip. The counts are always known; a weekly sum is omitted until a twin measured it."""

    live: int
    waiting_for_you: int
    missions_open: int
    sent_week: NotRequired[int]
    sent_alone_week: NotRequired[int]
    held_by_risk_week: NotRequired[int]
    cost_usd_week: NotRequired[float]  # est.


class TwinPage(TypedDict):
    twins: list[TwinSummary]
    stats: TwinStats


class Connection(TypedDict):
    """A connected account (ADR 0008). The credential itself never crosses the wire."""

    kind: ChannelKind
    status: ChannelStatus
    writes: bool  # whether it may send or write; off until a twin needs it
    account: NotRequired[str]
    last_checked: NotRequired[str]
    problem: NotRequired[str]  # plain words
    guide: NotRequired[str]  # until connected: how to connect, in plain words (Gmail: your own Google client)


class ConnectionList(TypedDict):
    connections: list[Connection]


class ConnectFlow(TypedDict):
    """A connect in progress: Google's sign-in in the browser, or a Notion key being checked."""

    state: ConnectState
    detail: NotRequired[str]  # plain words
    url: NotRequired[str]  # while waiting: Google's sign-in page, for when the browser did not open


class NewTwinBody(TypedDict):
    space_id: str


class TwinSayBody(TypedDict):
    text: str  # "" when the person picked a suggestion; the first say carries the need
    choice: NotRequired[str]


class PiecesBody(TypedDict):
    pieces: list[str]  # piece ids: inked on confirm, rubbed out (her unconfirmed ones only) on drop


class SamplesBody(TypedDict):
    ids: list[str]


class DialsBody(TypedDict):
    dials: dict[str, int]  # dial id -> DIAL_MIN..DIAL_MAX; the person's values (source "you")
    preset: NotRequired[str]  # a style preset applied first


class PagesBody(TypedDict):
    ids: list[str]


class ChoresBody(TypedDict):
    ids: list[str]


class AutonomyBody(TypedDict):
    channel: ChannelKind
    autonomy: Autonomy
    bar: int
    split: NotRequired[AutonomySplit]


class MemoryBody(TypedDict):
    id: str
    keep: bool
    reason: NotRequired[str]


class RehearseBody(TypedDict):
    goal: str


class MarkBody(TypedDict):
    turn: str
    mark: TwinMark
    edited_text: NotRequired[str]


class NewMissionBody(TypedDict):
    thread: str
    goal: str


class ConnectBody(TypedDict):
    """Gmail: the person's own Google client. Notion: the key."""

    client_id: NotRequired[str]
    client_secret: NotRequired[str]
    key: NotRequired[str]


class DecisionEdit(TypedDict):
    text: str


class DecisionBody(TypedDict):
    """POST /decisions/{card_id}. `edited` is taken on a twin draft's card only."""

    verdict: Verdict
    edited: NotRequired[DecisionEdit]


# The setup stream (POST /twins/{id}/say) is a turn stream: start, text, tool, card, done and error as
# on /run, with the twin's own sketch, ask and coverage lines (the same names as a draft's stage turn,
# twin payloads).


class PieceOp(TypedDict):
    """One change as applied: add/change carry the whole piece after it, remove the piece, dial the
    whole dial after it."""

    op: PieceOpName
    piece: NotRequired[Piece]
    dial: NotRequired[StyleDial]


class TwinSketchEvent(TypedDict):
    type: Literal["sketch"]
    ops: list[PieceOp]


class TwinAskEvent(TypedDict):
    type: Literal["ask"]
    ask: TwinAsk


class TwinCoverageEvent(TypedDict):
    type: Literal["coverage"]
    coverage: PlaceCoverage
    ready: bool
    readiness: int


# The rehearsal stream (POST /twins/{id}/rehearse): each turn as it is played, then the outcome; a
# failed run streams the turn's ErrorEvent.


class TwinTurnEvent(TypedDict):
    type: Literal["turn"]
    turn: MissionTurn


class TwinOutcomeEvent(TypedDict):
    type: Literal["outcome"]
    state: MissionState
    filed: NotRequired[TwinFiled]


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
    "chores": "/chores",
    "chore": "/chores/{id}",
    "drafts": "/drafts",
    "draft": "/drafts/{id}",
    "draft_say": "/drafts/{id}/say",
    "draft_confirm": "/drafts/{id}/confirm",
    "draft_drop": "/drafts/{id}/drop",
    "draft_write": "/drafts/{id}/write",
    "draft_preview": "/drafts/{id}/preview",
    "draft_key": "/drafts/{id}/key",
    "draft_rehearse": "/drafts/{id}/rehearse",
    "draft_verdict": "/drafts/{id}/verdict",
    "twins": "/twins",
    "twin": "/twins/{id}",
    "twin_say": "/twins/{id}/say",
    "twin_confirm": "/twins/{id}/confirm",
    "twin_drop": "/twins/{id}/drop",
    "twin_samples": "/twins/{id}/samples",
    "twin_dials": "/twins/{id}/dials",
    "twin_pages": "/twins/{id}/pages",
    "twin_chores": "/twins/{id}/chores",
    "twin_autonomy": "/twins/{id}/autonomy",
    "twin_memory": "/twins/{id}/memory",
    "twin_rehearse": "/twins/{id}/rehearse",
    "twin_mark": "/twins/{id}/rehearse/mark",
    "twin_golive": "/twins/{id}/golive",
    "twin_pause": "/twins/{id}/pause",
    "twin_missions": "/twins/{id}/missions",
    "twin_mission": "/twins/{id}/missions/{mid}",
    "connectors": "/connectors",
    "connector_connect": "/connectors/{kind}/connect",
    "connector_flow": "/connectors/{kind}/flow",
    "connector_disconnect": "/connectors/{kind}/disconnect",
    "connector_probe": "/connectors/{kind}/probe",
}
