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
SITES_MAX = 24  # a project's sites (ADR 0014)
SITE_FRESH_S = 300  # a look at a site stands this long before the overview or a hand looks again
# Apps by kind (ADR 0025) and apps offered to paired devices (ADR 0026).
APP_LABEL_MAX = 60
APP_TOOLS_MAX = 64  # tools one app lists; the rest are dropped with a reason
APP_TOOL_NAME_MAX = 64  # a tool name she is offered, `<slug>__<tool>` included; longer is dropped
APP_CALL_TIMEOUT_S = 20  # one call to an app; a long job detaches and is read on a later call
APP_IDLE_S = 600  # a tool she starts (stdio) is stopped after this long unused, and at shutdown
APP_FILE_MAX_BYTES = 1073741824  # one file pulled from an app's output folder (1 GiB)
DEVICE_APPS_MAX = 24  # apps wired on this device outside every project
RECORDS_PAGE_MAX = 500  # records one list answers (business Phase 1)
BLOCKS_MAX = 12  # blocks in one report
CHAT_BLOCKS_MAX = 3  # report parts in one chat reply (ADR 0022)
REPORT_TITLE_MAX = 80
CALLOUT_MAX = 280
RECOMPOSE_MIN_S = 3600  # a shape change recomposes at most this often
VOCAB = 1  # the report's block vocabulary version
CADENCE_MIN_S = 900  # a routine runs at most every 15 minutes
ROUTINE_CEILING_CENTS = 25  # a run's default spend ceiling, in US cents (est.)
RUNS_KEPT = 50  # runs kept per routine
PASTE_MAX = 4000  # one pasted message of the person's, for the voice
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
Surface = Literal["turn", "probe", "design", "rehearsal", "twin", "report", "routine"]
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
    "page_open",
    "page_read",
    "page_find",
    "page_wait",
    "page_scroll",
    "tabs_read",
    "file_list",
    "page_click",
    "page_fill",
    "page_select",
    "page_submit",
    "page_upload",
    "page_download",
    "wheel_handoff",
    "setup_read",
    "setup_act",
    "record_list",
    "record_put",
    "twin_send_web",
    "show_report",
    "show_blocks",
    "app_read",
    "app_act",
    "app_fetch",
]
AppEventType = Literal[
    "card_filed",
    "card_resolved",
    "space_changed",
    "active_space",
    "engine",
    "turn_done",
    "settings",
    "wheel",
    "site",
    "report",
    "routine",
    "draft_job",
    "app",
]
#: Her browser's answer when a hand did not run (ADR 0013).
HandReason = Literal["no_browser", "no_tab", "moved", "refused", "timeout", "failed", "unknown_ref"]
WheelState = Literal["back", "closed", "timeout"]
#: A project's site (ADR 0014): what the last look found. `unknown` is "not looked yet, or could not
#: look", never "fine".
SiteAccess = Literal["signed_in", "signed_out", "unknown"]
#: A site on a draft's access step: still to do, signed in (the look said so), or skipped by the person.
AccessState = Literal["open", "signed_in", "skipped"]
#: What the person does with one site on the access step.
AccessAct = Literal["sign_in", "check", "skip", "use_moved"]

# Records and the report (business Phase 1). Kinds are a catalog in code; a project picks from it.
RecordKind = Literal["creator", "track", "thread", "agreement", "file", "render", "release", "stat"]
#: Who wrote a revision.
RecordBy = Literal["person", "athena", "routine", "daemon"]
TrackVerdict = Literal["keep", "pass", "later"]
AgreementState = Literal["proposed", "agreed", "declined"]
#: The creator's Suno plan: a free-plan song cannot be licensed for commercial use.
SunoPlan = Literal["free", "pro", "premier", "unknown"]
ThreadChannel = Literal["mail_web", "bio", "comment"]
RenderState = Literal["staged", "running", "rendered", "refused", "failed"]
BlockKind = Literal["stat", "trend", "queue", "pipeline", "list", "thread", "cards", "callout"]
BindingAgg = Literal["count", "sum", "last", "series"]

# Routines (business Phase 2): the daemon's only background host.
RoutineKind = Literal["watch", "inbox", "stats", "outreach", "twin"]
RoutineState = Literal["on", "paused"]
#: ran = did its work; partial = stopped at its ceiling or a missing page, with what it covered;
#: skipped = not admitted (see SkipReason); failed = an error, said in plain words.
RunOutcome = Literal["ran", "partial", "skipped", "failed"]
SkipReason = Literal[
    "running", "live_turn", "paused", "no_browser", "signed_out", "no_engine", "no_twin", "nothing_to_do"
]

# Settings (ADR 0012): the look both windows paint, and how the engine is chosen.
ThemeChoice = Literal["auto", "dark", "light"]  # auto follows the system
TypeScale = Literal["standard", "large"]  # large adds 2 px to every size under the headings
MotionChoice = Literal["system", "calm"]  # calm stills every animation, whatever the system asks
EngineSource = Literal["env", "setting", "default"]  # who decided the engine turns run on
EngineReadiness = Literal["ready", "no_key", "not_installed", "simulated"]

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
    # Her browser (ADR 0013). The class is the floor: a page hand on a tab whose site is not one of
    # the project's sites (ADR 0014: set up only by a chore's onboarding) files a card whatever its
    # class says, and a signed card runs only on the tab and the page load it was asked on.
    "page_open": "auto",
    "page_read": "auto",
    "page_find": "auto",
    "page_wait": "auto",
    "page_scroll": "auto",
    "tabs_read": "auto",
    "file_list": "auto",
    "page_click": "gated",
    "page_fill": "gated",
    "page_select": "gated",
    "page_submit": "gated",
    "page_upload": "gated",
    "page_download": "gated",
    "wheel_handoff": "gated",
    # Setting up the private network for several devices (ADR 0017): offered only in the setup
    # conversation. A read answers at once; every change files a card, one per machine-changing step.
    "setup_read": "auto",
    "setup_act": "gated",
    # A project's records (business Phase 1). A read answers at once. The class is the floor: a put of
    # a find (creator, track) runs at once, a put of any other kind files a card.
    "record_list": "auto",
    "record_put": "auto",
    # A twin's message on a web channel (business Phase 2): Proton mail, a bio link or a comment, sent
    # through her browser. Always a card; never sent alone.
    "twin_send_web": "gated",
    # A view inside an agent host (ADR 0021): the project's report as text, structured figures and a
    # rendered view. Offered only to an outside client's lease on a project that keeps records.
    "show_report": "auto",
    # Report parts in a chat reply (ADR 0022): 1 to 3 parts of the same kit, bound to the project's
    # records. Offered only to a chat turn in a project that keeps records; it reads and changes nothing.
    "show_blocks": "auto",
    # Apps by kind (ADR 0025): a tool whose annotations say it only reads answers at once, any other
    # files a card; on a paired device's instance the card is filed here (ADR 0026). app_fetch pulls a
    # file from an app's output folder into the project's files.
    "app_read": "auto",
    "app_act": "gated",
    "app_fetch": "auto",
}

# --- chores (ADR 0005) ---------------------------------------------------------------------------

SenseName = Literal["paper", "call", "walk", "circle"]
FeaturedStatus = Literal["proven", "rehearsed", "failing", "unproven"]
BenchWord = Literal["exceeds", "meets", "short"]
ProofOp = Literal[">=", "<="]
ChoreOrigin = Literal["library", "yours"]  # the app's playbooks/ or the person's <data_dir>/chores/

# --- drafts: a chore written in conversation (ADR 0007) ------------------------------------------

DraftStep = Literal["describe", "shape", "author", "preview", "rehearse", "verdict", "access", "saved"]
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
#: A connected account (ADR 0008).
ConnectorKind = Literal["gmail", "notion"]
#: Where a twin speaks: a connected account, or a web channel through her browser (business Phase 2),
#: which is never sent alone.
ChannelKind = Literal["gmail", "notion", "mail_web", "bio", "comment"]
Autonomy = Literal["review", "assist", "auto"]
TwinState = Literal["setting_up", "live", "paused"]
ChannelStatus = Literal["connected", "needs_sign_in", "disconnected"]
ChannelHealth = Literal["active", "quiet", "stale"]  # omitted on a channel that has never spoken
MissionState = Literal["open", "resolved", "handed_back"]
SendDecision = Literal["sent_alone", "waits"]
WaitReason = Literal["review", "assist", "first_message", "below_bar", "risk", "paused", "web_channel"]
TwinMark = Literal["me", "edited", "not_me"]
ChoreKind = Literal["outcome", "inbox", "test", "channel"]
DialSource = Literal["learned", "preset", "you"]
TwinTurnSide = Literal["twin", "other"]
TwinMessageKind = Literal["first_message", "reply"]
MissionSource = Literal["page", "notion"]  # given on the twins page, or taken from its task inbox
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
THREADS_MAX = 20  # recent Gmail conversations the new entry slip offers
SNIPPET_MAX = 200  # characters of a conversation's last message the slip shows
GOALS_MAX = 3  # goals Athena suggests for a new mission
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
    kinds: NotRequired[list[RecordKind]]  # the record kinds it keeps; omitted when none
    draft: NotRequired[DraftBadge]  # its open (not yet saved) draft; omitted when none


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


# --- settings (ADR 0012) --------------------------------------------------------------------------


class Look(TypedDict):
    """How both windows are painted. An unknown stored value reads as its default."""

    theme: ThemeChoice
    type_scale: TypeScale
    motion: MotionChoice


class LookBody(TypedDict):
    """POST /settings/look: any of the three; an omitted one keeps what is stored."""

    theme: NotRequired[ThemeChoice]
    type_scale: NotRequired[TypeScale]
    motion: NotRequired[MotionChoice]


class EngineOption(TypedDict):
    """One engine as Settings offers it, read without calling it (a key on file, a program on PATH)."""

    id: EngineId
    readiness: EngineReadiness
    reason: NotRequired[str]  # plain words: why it cannot be chosen, and the fix


class SettingsView(TypedDict):
    """GET /settings: everything the Settings page reads in one answer."""

    look: Look
    engine: EngineId  # the engine the next turn runs on
    source: EngineSource
    choice: NotRequired[EngineId]  # the stored choice; omitted when none was made
    engines: list[EngineOption]
    data_dir: NotRequired[str]  # where this daemon keeps its files; omitted when nothing is on disk


class EngineChoiceBody(TypedDict):
    engine: EngineId


class Card(TypedDict):
    id: str
    space_id: str
    action: ActionName
    label: str  # plain words: what will happen if signed
    args: dict[str, Any]
    state: CardState
    created: str
    resolved: NotRequired[str]
    outcome: NotRequired[str]  # what a signed card's run said, in plain words


# Every stored part carries `at_ms` (ADR 0024): milliseconds from the turn's start to the part's first
# event, timed by the daemon. Omitted on parts stored before moments were kept.


class TextPart(TypedDict):
    """A run of her words between two other parts of the turn."""

    kind: Literal["text"]
    text: str
    at_ms: NotRequired[int]


#: A tool line of the turn, as it streamed: the action, its label (the dispatch's own words for what
#: happened, or what a filed card asks) and its class. `class` is a Python keyword, hence this form.
ToolPart = TypedDict(
    "ToolPart",
    {
        "kind": Literal["tool"],
        "name": ActionName,
        "label": str,
        "class": ActionClass,
        "at_ms": NotRequired[int],
    },
)


class CardPart(TypedDict):
    """A card the turn filed, by id; the card itself (and its outcome) comes from the gate."""

    kind: Literal["card"]
    card_id: str
    at_ms: NotRequired[int]


class BlocksPart(TypedDict):
    """Report parts she showed in the reply (ADR 0022), with the figures computed when she showed them."""

    kind: Literal["blocks"]
    shown: ShownBlocks
    at_ms: NotRequired[int]


#: One part of a settled Athena turn, in the order the stream delivered it.
TurnPart = TextPart | ToolPart | CardPart | BlocksPart


class Turn(TypedDict):
    id: str
    space_id: str
    role: Role
    text: str
    created: str
    cost_usd: NotRequired[float]
    card_id: NotRequired[str]
    # An Athena turn's parts in emitted order. Omitted on a person's turn and on turns stored before
    # parts were kept, which show as `text` and `card_id` alone.
    parts: NotRequired[list[TurnPart]]
    # ADR 0024: how long an Athena turn took, from its start to the moment it was stored (the daemon's
    # steady clock). Omitted on a person's turn and on turns stored before it was kept.
    duration_ms: NotRequired[int]
    # ADR 0024: the engine stopped this Athena turn, in plain words; its parts are what streamed first.
    # Omitted on a turn that finished.
    stopped: NotRequired[str]


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


class NodeSite(TypedDict):
    """The real website an `app` node happens on (ADR 0014). Athena proposes it in pencil
    (`confirmed: false`); the person confirms it in ink. Only confirmed sites go to the access step."""

    origin: str  # scheme://host[:port]
    url: str  # the address she looks at to see whether the person is signed in
    label: str
    confirmed: bool


class SketchNode(TypedDict):
    id: str
    kind: SketchKind
    slot: Slot
    label: str  # <= LABEL_MAX
    origin: NodeOrigin  # "you": the person's own words, confirmed when added; "athena": a proposal
    confirmed: bool
    detail: NotRequired[str]
    quote: NotRequired[str]  # on the person's nodes: their own words it was drawn from, verbatim
    site: NotRequired[NodeSite]  # `app` nodes only: the real website, when she knows it


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


class DraftSite(TypedDict):
    """One real site on the draft's access step (ADR 0014)."""

    origin: str
    label: str
    probe_url: str
    state: AccessState
    reason: NotRequired[str]  # plain words: what the last look found, when it was not signed in
    tab: NotRequired[int]  # her browser's tab while the person signs in there
    moved_to: NotRequired[str]  # a look ended on another site, not a sign-in page: offered instead


#: A draft's background job: writing the chore, previewing its cards, or the test run.
DraftJobKind = Literal["write", "preview", "rehearse"]
#: `failed`: an engine error or her answer could not be used; `stopped`: the person pressed Stop, or
#: the daemon closed while it ran (found at the next start).
DraftJobState = Literal["running", "done", "failed", "stopped"]


class DraftJob(TypedDict):
    """The draft's last background job. It runs on a daemon thread, survives a closed window, and any
    window re-attaches with `GET /drafts/{id}/job?after=n` (the follow stream). No wall-clock limit on
    `write`; `POST /drafts/{id}/job/stop` ends the model process."""

    kind: DraftJobKind
    state: DraftJobState
    started: str  # ISO 8601 UTC
    events: int  # events the job has emitted so far: the follow cursor
    ended: NotRequired[str]  # once not running
    reason: NotRequired[str]  # failed / stopped: plain words, screen copy


class DraftNotes(TypedDict):
    """What the person says while she works (the stage's "meanwhile"): lines that pre-fill the key at
    the check. Absent before the person says anything; an empty list is "said nothing"."""

    expect: list[str]  # cards they expect her to find; at the check, the ones she missed become missing lines
    never: list[str]  # "she must never" lines


class DraftBadge(TypedDict):
    """A Project's open draft, on `SpaceSummary.draft`: where it stands, for a badge."""

    id: str
    step: DraftStep
    job: NotRequired[DraftJobState]  # the last job's state; absent before the first job


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
    sites: NotRequired[list[DraftSite]]  # from the keep on: the real sites the access step signs in to
    job: NotRequired[DraftJob]  # the last background job; absent before the first
    notes: NotRequired[DraftNotes]  # what the person said while she worked
    rubbed: NotRequired[list[str]]  # her guesses the person rubbed out (labels); not proposed again


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


class NotesBody(TypedDict):
    """PUT /drafts/{id}/notes: the whole notes, replaced. Allowed at any step before `verdict`."""

    expect: list[str]
    never: list[str]


class KeyBody(TypedDict):
    marks: list[KeyMark]
    missing: list[str]
    never: list[str]


class VerdictBody(TypedDict):
    verdict: DraftVerdict
    note: NotRequired[str]


class AccessBody(TypedDict):
    """POST /drafts/{id}/access, at step `access`; the reply is the Draft.

    - `sign_in` opens the site's address in her browser, in front, and hands the person the wheel
      (the tab is on the draft's site as `tab`). Signing in happens only on the site's own page.
    - `check` looks at the site now: `signed_in` when the look says so, else the site stays `open`
      with the reason in plain words.
    - `skip` leaves the site `skipped`; the project keeps it as signed out, a blocker from day one.
    When no site is `open`, the draft moves to `saved`. A `wheel` app event for the site's tab is the
    desktop's cue to send `check`; nothing is checked on its own.
    """

    origin: str
    act: AccessAct


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


class BlocksEvent(TypedDict):
    """Chat turns only (ADR 0022): report parts she chose to show, in place among her words."""

    type: Literal["blocks"]
    shown: ShownBlocks


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


class PreviewStarted(TypedDict):
    type: Literal["previewing"]


class PreviewDone(TypedDict):
    type: Literal["previewed"]
    expected: list[ExpectedCard]


class JobSnapshot(TypedDict):
    """The first line of every job stream: where the job stands when the stream opens."""

    type: Literal["job"]
    job: DraftJob


class JobStopped(TypedDict):
    type: Literal["stopped"]
    reason: str  # plain words


# The job streams (POST /drafts/{id}/write, /preview, /rehearse start a job and follow it; GET
# /drafts/{id}/job?after=n follows the running or last job). Protocol, in order: one `job` snapshot;
# then the job's events from index `after` (0 for a POST), as they happen - write: writing, repair*,
# then written | author_failed | error; preview: previewing, then previewed | error; rehearse: phase,
# card*, then scored | error; any kind may end in `stopped`. The stream ends after the terminal event.
# A follow on a job that already ended replays its events from `after` (kept in memory until the
# daemon closes; after a restart the snapshot alone, with the stored state). A client that leaves
# changes nothing: the job runs on. A POST while a job runs answers 409 `space_busy`.


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


class Site(TypedDict):
    """One of a project's sites (ADR 0014): the browser's trust list. Written only by a chore's
    onboarding (its access step); a look (the overview, a hand, "Sign in again") changes only
    `access`, `checked_at` and `reason`. Erased with the project."""

    origin: str
    label: str
    probe_url: str  # the address a look opens
    access: SiteAccess
    blocks: list[str]  # the kept chores that need it, by title
    checked_at: NotRequired[str]  # when it was last looked at; omitted = never
    reason: NotRequired[str]  # plain words: what the last look found


class SiteList(TypedDict):
    sites: list[Site]


# --- apps by kind (ADR 0025) and offered across paired devices (ADR 0026) --------------------------

#: website / local_page: an origin her browser drives (kept in `spaces.apps`, the kind is derived:
#: a loopback host is local_page). mcp_http: an app on this computer answering MCP on a loopback URL.
#: mcp_stdio: a tool she starts as a child process (argv). The screen never says "MCP".
AppKind = Literal["website", "mcp_http", "mcp_stdio", "local_page"]
#: What the last probe found. `unchecked` = never probed (or could not be), never "fine".
AppStatus = Literal["unchecked", "ok", "unreachable", "refused"]


class AppTool(TypedDict):
    """One tool an app lists. `access` comes from its annotations: readOnlyHint, or not destructive
    and not open-world, is auto; anything else is gated."""

    name: str  # the app's own tool name
    description: str
    access: ActionClass
    input_schema: NotRequired[dict[str, Any]]  # the tool's inputSchema as the app listed it; omitted = none


class AppRemote(TypedDict):
    """The same app wired on a paired device and offered to this one; attached to a project app."""

    peer_id: str
    device: str  # the peer's name, as Devices shows it
    remote_app_id: str  # its app_id on that device
    status: AppStatus
    tools: list[AppTool]  # as that device listed them at the last look
    checked_at: NotRequired[str]
    reason: NotRequired[str]


class App(TypedDict):
    """One app of a project (space_id) or of this device outside every project (space ""). For
    website/local_page `app_id` is `web_` + 10 hex of sha1(origin), `address` the origin; for
    mcp_http the URL; for mcp_stdio the command line as shown (argv joined by spaces)."""

    app_id: str  # app_<hex> | web_<hex>
    kind: AppKind
    label: str
    slug: str  # the prefix of her tool names: lowercase [a-z0-9_], unique in its space
    address: str
    status: AppStatus
    tools: list[AppTool]  # [] for website/local_page
    remotes: list[AppRemote]  # [] when none; always [] for a device-level app
    sealed: bool  # a token is kept for it (never sent back)
    argv: NotRequired[list[str]]  # mcp_stdio only
    offered: NotRequired[bool]  # device-level only: paired devices with the `apps` grant may use it
    output_dir: NotRequired[str]  # the only folder files may be pulled from; omitted = none
    checked_at: NotRequired[str]
    reason: NotRequired[str]


class AppList(TypedDict):
    apps: list[App]


class AppNew(TypedDict):
    """POST body. website/local_page: address is an origin (local_page: a loopback one); mcp_http:
    a loopback http(s) URL; mcp_stdio: argv, address omitted. token is sealed and never returned."""

    kind: AppKind
    label: NotRequired[str]  # defaults to the host or the command's name
    address: NotRequired[str]
    argv: NotRequired[list[str]]
    token: NotRequired[str]
    output_dir: NotRequired[str]
    offered: NotRequired[bool]  # device-level only


class AppRemoteNew(TypedDict):
    peer_id: str
    remote_app_id: str


class OfferedApp(TypedDict):
    """What a device offers its paired devices (`GET /peer/apps`): never an address, argv or token."""

    app_id: str
    kind: AppKind  # mcp_http or mcp_stdio only
    label: str
    tools: list[AppTool]
    has_output: bool  # it names an output folder files may be pulled from


class OfferedList(TypedDict):
    offered: list[OfferedApp]


class PeerAppCall(TypedDict):
    """`POST /peer/apps/{app_id}/call`. A gated tool without `approval_id` is refused 403
    `approval_missing`; the id is A's card, recorded in the offering device's audit, not verified."""

    tool: str
    arguments: dict[str, Any]
    approval_id: NotRequired[str]


class AppAnswer(TypedDict):
    """One call's answer, local or remote: the tool's text content joined, and whether it was an error."""

    text: str
    is_error: bool


class SiteBody(TypedDict):
    origin: str


class SignInStarted(TypedDict):
    """POST /spaces/{id}/sites/sign_in: the site is open in her browser, in front, and the person has
    the wheel. The desktop sends `POST /spaces/{id}/sites/check` once the `wheel` event for this tab
    arrives (or the person says they are done)."""

    origin: str
    tab: int


class WheelNote(TypedDict):
    """The person was handed her browser's tab (`wheel_handoff`) and the page moved on (`back`), the
    tab was closed, or 30 minutes passed."""

    tab: int
    state: WheelState


class AppEvent(TypedDict):
    """One SSE message on `/events`. Payload keys by type:
    card_filed / card_resolved: `card`; space_changed: `space_id` (and `erased: true` on erase);
    active_space: `space_id`; engine: `status`; turn_done: `space_id`, `turn_id`; settings: `look`;
    wheel: `wheel`; site: `space_id`, `site` (a look at one of the project's sites changed what it found);
    report: `space_id` (Athena arranged that project's report again);
    routine: `space_id`, `routine` (a routine ran, skipped or changed);
    draft_job: `space_id`, `draft_id`, `job` (a draft's job started or ended).
    """

    type: AppEventType
    card: NotRequired[Card]
    space_id: NotRequired[str]
    erased: NotRequired[bool]
    status: NotRequired[EngineStatus]
    turn_id: NotRequired[str]
    look: NotRequired[Look]
    wheel: NotRequired[WheelNote]
    routine: NotRequired[Routine]
    site: NotRequired[Site]
    draft_id: NotRequired[str]
    job: NotRequired[DraftJob]


# --- twins (ADR 0008-0010) ------------------------------------------------------------------------
# Field names follow docs/features/twins/reference/shared/SCHEMA.md. The daemon computes every
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
    page: NotRequired[str]  # the task inbox: the Notion page it reads, one the twin may read


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
        "source": NotRequired[MissionSource],  # where the person gave it (a real mission only)
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


class TaskInbox(TypedDict):
    """The task inbox at work (the `task-inbox` preset): the Notion page it reads for new missions, one
    line each ("<who or thread>: <goal>"), and what it made of the page when it last read it."""

    page: str  # the Notion page id
    title: str
    taken: int  # lines it started a mission for, ever
    unplaced: list[str]  # lines it could not place at its last read, each with why; it left them alone
    checked_at: NotRequired[str]  # its last read of the page
    problem: NotRequired[str]  # the page could not be read, plain words


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
    inbox: NotRequired[TaskInbox]  # when the task inbox is picked and reads a page


class TwinAsk(TypedDict):
    place: Place
    text: str
    suggestions: list[str]
    follow_up: int
    panel: NotRequired[SetupPanel]  # the working slip this question needs
    channel: NotRequired[ConnectorKind]  # with panel "connect"


class TwinPreview(TypedDict):
    """How it sounds now (the Mirror's live preview, nested on the voice section): one message from the
    other side and the twin's reply in its current voice. The daemon writes it with one engine call and
    keeps it until the compiled voice changes."""

    inbound: str  # a short message from the other side: the latest one it answered, or an invented one
    text: str  # its reply in its voice now
    changed: list[str]  # what changed in its voice since the last preview, plain words; [] the first time


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
    preview: NotRequired[TwinPreview]  # how it sounds, when one is kept for its voice as it is now


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


# `with` is a Python keyword, so this one is spelled the functional way.
ThreadSummary = TypedDict(
    "ThreadSummary",
    {
        "id": str,  # the Gmail thread id: what a new mission's `thread` names
        "with": str,  # the other side: a name, else an address
        "subject": str,
        "snippet": str,  # an excerpt of its last message (<= SNIPPET_MAX): their words, untrusted
        "last_at": str,  # its last message, ISO 8601 UTC
        "theirs_last": bool,  # the other side spoke last: answering it is a reply
    },
)


class ThreadList(TypedDict):
    """GET /twins/{id}/threads: recent Gmail conversations, newest first, at most THREADS_MAX."""

    threads: list[ThreadSummary]


class GoalList(TypedDict):
    """POST /twins/{id}/goals: Athena's suggested goals for a new mission (her pencil), at most
    GOALS_MAX, each <= LABEL_MAX; [] when she has none. The person's own goal always works."""

    goals: list[str]


class Connection(TypedDict):
    """A connected account (ADR 0008). The credential itself never crosses the wire."""

    kind: ConnectorKind
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
    inbox: NotRequired[str]  # with `task-inbox`: the picked Notion page it reads


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
    thread: str  # a Gmail thread id, or the one address of someone new
    goal: str


class GoalsBody(TypedDict):
    """One of the two: the conversation chosen, or the one address of someone new."""

    thread: NotRequired[str]
    to: NotRequired[str]


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


# --- her browser and the MCP server (ADR 0013, 0015) -------------------------------------------
#
# The relay's protocol (the shell is its only client, with the daemon's bearer):
# - `GET /browser/next?wait=N` (N <= 25 s) answers `BrowserNext`: `{call}` as soon as one waits, or
#   `{}` when N passes. The shell polls again at once; a shell that has not polled for 40 s is gone
#   and every hand answers `no_browser`.
# - The shell answers each call exactly once with `POST /browser/done` `BrowserDone`; the reply is
#   `{accepted}`. An answer after the caller's deadline (the caller already got `timeout`), or to
#   an id never issued, is `accepted: false` and changes nothing.
# - `POST /browser/note` `WheelNote`: the page of a handed tab moved on; published as the `wheel`
#   app event. No reply body beyond `{}`.
# A call carrying `load` and `url` is bound to that page: the shell answers `moved` and does nothing
# when the tab is on another.
#
# The MCP server's protocol (ADR 0015): `POST /mcp` takes one JSON-RPC 2.0 message per request
# (Streamable HTTP, JSON replies only, no SSE); a request gets one JSON-RPC response, a notification
# gets 202 and no body. The bearer is an MCP lease (`POST /mcp/lease`, or minted by a turn), never
# the daemon's token: a lease names one project and expires. Methods: `initialize`, `ping`,
# `tools/list`, `tools/call`. A gated call answers `structuredContent: {pending: {card_id}}` and
# runs once, when the person signs; nothing else a caller sends can run it.


class TabInfo(TypedDict):
    id: int
    url: str
    title: str
    load: int  # page loads finished in this tab


class HandFile(TypedDict):
    path: str  # where the shell put a download, inside the project's files folder
    name: str


class HandResult(TypedDict):
    ok: bool
    output: str
    reason: NotRequired[HandReason]
    tab: NotRequired[TabInfo]
    tabs: NotRequired[list[TabInfo]]
    file: NotRequired[HandFile]
    measured: NotRequired[dict[str, int]]  # an upload's bytes, parts and milliseconds


class BrowserCall(TypedDict):
    id: str
    hand: str  # open | tabs | tab | close | wheel | upload | download | page_*
    args: dict[str, Any]
    tab: NotRequired[int]
    load: NotRequired[int]
    url: NotRequired[str]


class BrowserNext(TypedDict):
    call: NotRequired[BrowserCall]


class BrowserDone(TypedDict):
    id: str
    result: HandResult


class BrowserAccepted(TypedDict):
    accepted: bool


class FileItem(TypedDict):
    id: str
    space_id: str
    name: str
    mime: str
    size: int
    sha256: str
    origin: str  # the site it was downloaded from
    created: str


class FileList(TypedDict):
    files: list[FileItem]


class McpLeaseAsk(TypedDict):
    space_id: str


class McpLease(TypedDict):
    url: str
    token: str
    space_id: str
    expires: str


# --- records and the report (business Phase 1) ---------------------------------------------------
# An absent value is an omitted key, never null or 0. A body is validated per kind by
# athena.records.kinds; the shapes below are the wire's, one per kind.


class CreatorBody(TypedDict):
    name: str
    channel_url: str  # the record's key
    followed: bool
    bio_links: NotRequired[list[str]]
    emails: NotRequired[list[str]]  # business addresses, for matching the inbox (business Phase 2)
    note: NotRequired[str]


class TrackBody(TypedDict):
    url: str  # the record's key
    title: str
    creator_key: str
    found_at: str
    verdict: NotRequired[TrackVerdict]
    genre: NotRequired[str]
    note: NotRequired[str]
    file_id: NotRequired[str]  # a `fil_...` of this project


class ThreadBody(TypedDict):
    creator_key: str
    channel: ThreadChannel
    last_at: str
    subject: NotRequired[str]
    url: NotRequired[str]
    snippet: NotRequired[str]


class AgreementBody(TypedDict):
    creator_key: str  # the record's key
    state: AgreementState
    thread_key: str  # the evidence: the thread it was agreed in
    plan: NotRequired[SunoPlan]
    terms: NotRequired[str]


class FileRecordBody(TypedDict):
    file_id: str  # the record's key; must be a row in this project's files
    track_key: NotRequired[str]


class RenderBody(TypedDict):
    track_key: str  # the record's key
    state: RenderState
    job_ids: NotRequired[list[str]]
    reasons: NotRequired[list[str]]
    output_file_id: NotRequired[str]


class ReleaseBody(TypedDict):
    track_key: str  # the record's key
    title: str
    track_url: str
    creator_channel_url: str
    genre: str
    credits: str


class StatBody(TypedDict):
    metric: str
    value: float
    measured_at: str  # when it was read, never a claimed time; key `<metric>@<measured_at>`


class RecordItem(TypedDict):
    id: str  # `rec_...`, one per revision
    space_id: str
    kind: RecordKind
    key: str
    rev: int  # 1 for the first; a change is a new revision, never an edit
    body: dict[str, Any]
    by: RecordBy
    created: str


class RecordList(TypedDict):
    records: list[RecordItem]


class RecordPutBody(TypedDict):
    kind: RecordKind
    body: dict[str, Any]


class TrackVerdictBody(TypedDict):
    verdict: TrackVerdict
    genre: NotRequired[str]
    note: NotRequired[str]


class KindsBody(TypedDict):
    kinds: list[RecordKind]


class MayRender(TypedDict):
    ok: bool
    reasons: list[str]  # plain words, empty when ok


class Binding(TypedDict):
    kind: RecordKind
    filter: NotRequired[dict[str, str | bool | None]]  # body field equals; None means the field is absent
    agg: NotRequired[BindingAgg]
    field: NotRequired[str]  # summed / last / series field (a stat's `value`)


class Block(TypedDict):
    id: str  # minted once; a recompose keeps it
    kind: BlockKind
    title: str
    span: int  # 1..12 columns
    binding: NotRequired[Binding]
    config: dict[str, Any]


class ReportSpec(TypedDict):
    v: int  # 1
    vocab: int  # the block vocabulary version it was composed against (VOCAB)
    title: str
    blocks: list[Block]
    callout: NotRequired[str]


class SeriesPoint(TypedDict):
    t: str
    v: float


class StageCount(TypedDict):
    label: str
    count: int


class BlockValue(TypedDict):
    count: NotRequired[int]
    value: NotRequired[float]
    series: NotRequired[list[SeriesPoint]]
    items: NotRequired[list[RecordItem]]
    stages: NotRequired[list[StageCount]]
    cards: NotRequired[list[Card]]


class ReportView(TypedDict):
    spec: ReportSpec
    default: bool  # True: no composed spec yet (or the last compose failed); the kinds' default layout
    rendered_at: str
    dropped: int  # blocks the validation door removed
    reasons: list[str]  # why each was removed, plain words
    values: dict[str, BlockValue]  # by block id, computed from records, never from the model
    pinned: list[str]  # block ids
    composed_at: NotRequired[str]


class PinsBody(TypedDict):
    pinned: list[str]


class ShownBlocks(TypedDict):
    """Report parts shown in a chat reply (ADR 0022): the same kit and validation door as the report,
    each part full width, every figure computed from records when it was shown, never by the model."""

    blocks: list[Block]  # what survived the door, in her order; may be empty when every part was dropped
    values: dict[str, BlockValue]  # by block id
    dropped: int  # parts the door removed
    reasons: list[str]  # why each was removed, plain words


# --- the report as other assistants see it (ADR 0021, ADR 0024) ---------------------------------


class HostFigure(TypedDict):
    """One computed figure of a part. A stat's one figure has an empty label (the title names it)."""

    label: str
    value: float | None  # None: no reading yet
    unit: NotRequired[str]


class HostBlock(TypedDict):
    id: str
    kind: BlockKind
    title: str
    figures: list[HostFigure]  # at most INLINE_MAX
    rows: list[str]  # at most INLINE_MAX, one plain line per record
    more: int  # figures and rows past INLINE_MAX
    text: NotRequired[str]  # a callout part's sentence


class HostProject(TypedDict):
    id: str
    name: str


class HostView(TypedDict):
    """What the `show_report` view renders (its structuredContent)."""

    project: HostProject
    title: str
    callout: NotRequired[str]
    default: bool
    rendered_at: str
    blocks: list[HostBlock]


class HostReport(TypedDict):
    """GET /spaces/{id}/report/elsewhere: what `show_report` answers another assistant, read by the app
    behind its own token. `text` is the fallback a host that renders nothing reads, word for word."""

    view: HostView
    text: str


# --- routines (business Phase 2) -----------------------------------------------------------------


class RoutineRun(TypedDict):
    id: str  # `run_...`
    routine_id: str
    started: str
    outcome: RunOutcome
    found: int  # items the run read (tracks, threads, readings), of `of` available when known
    kept: int  # records it kept
    cards: int  # cards it filed
    ended: NotRequired[str]
    reason: NotRequired[SkipReason]  # a skip's named reason
    note: NotRequired[str]  # plain words: what it covered, why it stopped
    of: NotRequired[int]  # how many were there to read (the denominator), when known
    spent_usd: NotRequired[float]  # est.; omitted when the engine gives no price


class Routine(TypedDict):
    id: str  # `rtn_...`; `twin:<twin_id>` routines are a twin's missions
    space_id: str
    kind: RoutineKind
    name: str  # plain words: "Watch followed creators"
    cadence_s: int
    ceiling_usd: float
    state: RoutineState
    last_run: NotRequired[RoutineRun]
    next_at: NotRequired[str]  # omitted while paused
    url: NotRequired[str]  # the page it reads (an inbox, an analytics page); watch reads each creator's


class RoutineList(TypedDict):
    routines: list[Routine]


class RunList(TypedDict):
    runs: list[RoutineRun]


class RoutineBody(TypedDict):
    state: NotRequired[RoutineState]
    cadence_s: NotRequired[int]
    url: NotRequired[str]


class PasteBody(TypedDict):
    """A message the person wrote, pasted for the voice (a new mailbox has no sent mail)."""

    text: str
    channel: ChannelKind


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
    "settings": "/settings",
    "settings_look": "/settings/look",
    "settings_engine": "/settings/engine",
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
    "draft_job": "/drafts/{id}/job",
    "draft_job_stop": "/drafts/{id}/job/stop",
    "draft_notes": "/drafts/{id}/notes",
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
    "twin_preview": "/twins/{id}/preview",
    "twin_threads": "/twins/{id}/threads",
    "twin_goals": "/twins/{id}/goals",
    "connectors": "/connectors",
    "connector_connect": "/connectors/{kind}/connect",
    "connector_flow": "/connectors/{kind}/flow",
    "connector_disconnect": "/connectors/{kind}/disconnect",
    "connector_probe": "/connectors/{kind}/probe",
    "space_files": "/spaces/{id}/files",
    "space_sites": "/spaces/{id}/sites",
    "space_apps": "/spaces/{id}/apps",
    "space_app": "/spaces/{id}/apps/{app_id}",
    "space_app_probe": "/spaces/{id}/apps/{app_id}/probe",
    "space_app_remotes": "/spaces/{id}/apps/{app_id}/remotes",
    "device_apps": "/apps",
    "device_app": "/apps/{app_id}",
    "device_app_probe": "/apps/{app_id}/probe",
    "peer_offers": "/devices/{peer_id}/apps",
    "space_site_check": "/spaces/{id}/sites/check",
    "space_site_sign_in": "/spaces/{id}/sites/sign_in",
    "draft_access": "/drafts/{id}/access",
    "browser_next": "/browser/next",
    "browser_done": "/browser/done",
    "browser_note": "/browser/note",
    "mcp": "/mcp",
    "mcp_lease": "/mcp/lease",
    "space_records": "/spaces/{id}/records",
    "record_history": "/records/{id}/history",
    "record_verdict": "/records/{id}/verdict",
    "space_kinds": "/spaces/{id}/kinds",
    "space_report": "/spaces/{id}/report",
    "space_report_compose": "/spaces/{id}/report/compose",
    "space_report_pins": "/spaces/{id}/report/pins",
    "space_report_elsewhere": "/spaces/{id}/report/elsewhere",
    "space_routines": "/spaces/{id}/routines",
    "routine": "/routines/{id}",
    "routine_run": "/routines/{id}/run",
    "routine_runs": "/routines/{id}/runs",
    "twin_paste": "/twins/{id}/paste",
}
