# A business run through Athena - the AI-music channel, and the gaps it finds

Status: **Phases 0-2 built.**

- **Phase 0** (2026-10-31): her browser, Athena's MCP server, and Claude Code with tools on.
- **Phase 1** (2026-11-01, [ADR 0018](../../adr/0018-projects-keep-records-and-her-report-is-composed-from-a-closed-kit.md)): records, `may_render`, and the composed report on a project's front page.
- **Phase 2** (2026-11-01, [ADR 0019](../../adr/0019-routines-are-the-daemons-only-background-host.md)): the routine host with the Twins poller folded in; the watch, inbox, stats and outreach routines; the twin's web channels.

Each phase holds on local simulated pages; nothing has run on the owner's real accounts yet. Phases 3 and 4 are planned in the [plan of record (2026-11-01)](#plan-of-record-2026-11-01---phases-1-4), which supersedes the design brief below where they differ. [Where we stopped](#where-we-stopped-2026-11-01) lists what is next and the follow-ups. A live end-to-end run with the owner signing in follows Phase 4.

Purpose: one real business is walked through Athena step by step, and every step she cannot take today becomes a named feature. The business is a YouTube channel that publishes music videos for good Suno tracks by creators nobody has heard of. It is a real need, and it exercises everything a long-running Project has to do: delegated correspondence, recurring web checks, the owner's judgement, files moving both ways, a peer app doing heavy work, a gated publish, and a report of where things stand.

## Spark

Owner, 2026-10-28 (lightly trimmed):

> As a user I want to use Athena to help me create and maintain business as new project. I want to create youtube channel publishing AI made music videos - many creators generated solid tracks via Suno on youtube, often hidden because they brand is unknown and AI music not trusted. I want to create mechanism to contact them, offer mutual help where I can create music visualizers and publish the tracks and while they are larger they can help me start, I will then help discover once network effect returns. I will need automation for the youtube/email correspondence to set, periodic checks via web on youtube to list new tracks from followed creators for my personal evaluation. Once tracks evaluated, I will need to deliver into Athena which will use Gravitone's skill for music video generation in local drive which she can reuse. Output would be draft in youtube channel covered with description referring original track/author, and high level genre... Now this process will simulate real need expected to go through Athena, it will point gaps in design and needs for new features. We can have personas as inspiration in some of the cases - Twin module for delegated communication, handling of artifacts between user and Athena. On top we will need to design ability to generate custom 'project report' onepager in app, using predefined components from kit and Athena's judgement which to use and how to compose in the report page (like tracks to evaluate, stats for number of views across whole channel, closed partnerships).

Doctrine, from the first wave of the design, in the owner's words:

> The reason why the project was called Athena portable was ability to use the internal browser and access apps through and manipulate cross projects without internal connectors. Gravitone has its own web UI and MCP to manipulate, Youtube is a web app to access into creator studio, Twins and delegated communication would be something brand new to design with inspiration of Personas.

So Athena reaches YouTube Studio and the mailbox the way the owner does, through a browser holding the owner's sessions, and reaches Gravitone through Gravitone's own MCP. She does not get one Python connector per service.

## What it builds on (scouted 2026-10-28)

**This repository.**
- Athena is a chat turn, a memory and a signature gate.
  - Actions: auto `recall | remember | portal_read`; gated `propose_brief | add_app | forget | portal_act` (`src/athena/contracts.py`).
  - Limits: six model calls per turn; built-in tool parameters are strings only.
  - `Gate.resolve` executes an approved card exactly once.
- Portal acts are not real. They only fill a `says` template, and portals are reachable only from the bench ([ADR 0005](../../adr/0005-chores-are-data-rehearsed-on-a-bench.md)).
- The daemon has none of the following: a background task or timer; a subprocess call from a turn; files in or out; typed per-project records; a report, chart or stat component; a per-project ledger query. A Project holds a name, brief, apps and hue ([ADR 0003](../../adr/0003-projects-are-walled-spaces.md)).
- The Claude Code engine runs with `--tools ""` in a temporary directory, so it cannot use a skill or an MCP server.
- The desktop's shared kit is `CardView`, `ProjectPill` and `useAppEvents`, on the Loop Tide tokens.
- The project detail view (`apps/desktop/src/main/projects/Level.tsx`) shows the name, brief, apps, a memory count and Erase.

**athena-portable** (the earlier sibling; no code shared):
- The internal browser: Tauri child webviews with an injected `hands.js`, and one signed-in browsing profile shared by every tab.
- Ten generic hands: read, find, wait, scroll, click, fill, select, submit, screenshot, tabs. They work on DOM text and address elements by opaque refs.
- A per-origin trust gate. On first sight everything is gated. Every page-changing hand is gated. An approval is bound to the tab and the page load, and it is used up once it runs.
- An MCP client configured by `{id, url, token_env}`. Its example entry is Gravitone.
- Missing: file inputs (upload), downloads, iframes and shadow DOM (YouTube Studio needs all three), per-project browser profiles, unattended writes, and any YouTube integration.

**gravitone-gcloud**:
- The music-video pipeline is a headless CLI (`pipeline/music-video.mts plan | run --yes | status --json`). It turns a folder of audio into a 1920x1080 MP4 and a `youtube.txt` with title, description and tags.
- Measured: 31.5 minutes for a 5:02 track on libx264.
- It needs a signed-in Leonardo studio Chrome window and ffmpeg.
- Its MCP (`POST /api/mcp` inside the Next app, CLI bearer token, tools `gt_read | gt_launch | gt_job | gt_spend`) has **no** operation to import audio, run a music video, return outputs or publish.
- Its YouTube publish path forces `private` and sets `containsSyntheticMedia: true`, but only the Floor UI and the worker reach it.
- Nothing in it writes attribution.

**personas** (inspiration):
- Twin:
  - A tone profile per channel: directives, constraints and examples.
  - One prompt compiler feeds every drafting lane.
  - "Approve" only logs; nothing is ever sent.
  - Its own unedited drafts never teach it.
- Drive: a managed file root, snapshotted before and after each run.
- A polling trigger: URL, content hash, interval, back-off.
- The cockpit composer, which is the closest match to the report:
  - Athena emits `{title, widgets: [{id, kind, title, span, config}]}` against a registry of about 30 kinds, guided by per-kind usage notes.
  - An unknown kind renders as an error tile.
  - Pinned widgets survive a recompose.
  - Its faults, not to copy: the server does not validate kinds, and two kind lists disagree.

**Standards read** (registry):
- `schema-driven-ui`:
  - The node vocabulary is closed.
  - Every spec passes one validation door.
  - Repair is honest: what survives renders, and the drop count is shown.
  - Actions in a spec are proposals that go through the consent gate.
  - The renderer is a pure function of the spec and the host's capabilities.
- `companion-runtime` / autonomous cycle hosting:
  - A cycle never overlaps itself or a live turn.
  - It declares its spend before it starts.
  - Its writes land in a class declared in advance, which is "propose only" while the system is young.

**Outside facts** (unverified; check before Phase 2):
- YouTube has no direct messages.
- A creator's business email sits behind a captcha on the About page and is not in the Data API.
- Suno's free-tier songs are not licensed for commercial use, so the creator's plan matters to the agreement.
- YouTube asks uploaders to disclose realistic altered or synthetic content.

## The business, walked through Athena

Each step names what the owner does, what Athena does, and the gap (`G<n>`) that stops her today.

| # | Step | Owner | Athena | Gaps |
|---|---|---|---|---|
| 1 | Set up the business | Describes it on the stage | Sketches it; ends in a Project with routines, record kinds, Twin channels and a first report | G1 |
| 2 | Find and follow creators | Names a few, or accepts her finds | Reads YouTube in her browser and records each creator | G2, G3, G4 |
| 3 | Watch for new tracks | - | A routine every 6 h lists new uploads from followed creators into the queue | G5, G6 |
| 4 | Evaluate | Listens in the report's queue, then Keep / Pass / Later with a note and a genre | Records the verdict | G7, G8 |
| 5 | First contact | Solves the About-page captcha when asked; signs each send | Finds bio links; drafts in the owner's voice for email, a bio channel or a public comment | G9, G10, G11 |
| 6 | Correspondence | Signs replies | A routine reads the mailbox, matches replies to creators, moves the partnership on and drafts the answer | G6, G12 |
| 7 | Agreement and the file | Confirms the agreement | Records the terms with the evidence (the thread); downloads the sent audio into the project's files | G13, G14, G15 |
| 8 | Render | - | Once the track is kept, agreed and has a file, Gravitone renders it within a spend ceiling, with no second card | G16, G17, G18 |
| 9 | Draft on YouTube | Signs the upload | Uploads the MP4 to YouTube Studio as a **private** draft with title, attribution, genre and the synthetic-media disclosure | G19, G20, G21 |
| 10 | Stats | - | A daily routine reads Studio analytics into stat records | G6, G22 |
| 11 | The report | Reads it; pins what matters | Recomposes the project's front page when the records move | G8, G23 |

Publishing the private draft as public stays the owner's act in YouTube Studio, outside Athena.

## Gap map

Every gap is a feature. The phase is where it is built, and the ADR is the decision it needs. ADR numbers are assigned at write time; 0007 is held by onboarding v2.

| Gap | What is missing | Feature | Phase | ADR |
|---|---|---|---|---|
| G0 | The engine cannot call tools; real acts would bypass the gate | **Athena hosts an MCP server.** Claude Code runs with tools on, `--strict-mcp-config` naming only Athena's server. Gated tools file a card and return `pending`; the daemon executes on sign. The same catalog becomes function calling on the Muse API | 0 | Athena's tools reach every engine through one MCP server |
| G1 | The v2 stage writes only chores | A **business branch** on the stage: the sketch ends in routines, record kinds, Twin channels and a first report | 4 | (amends 0007) |
| G2 | No browser | **Port athena-portable's tabs and hands** into muse: child webviews, one signed-in profile, the ten hands, per-origin trust, approvals bound to the page load | 0 | The internal browser and its trust |
| G3 | No typed state per project | **Records**: one table, a `kind`, a JSON body validated per kind, append-only revisions | 1 | Projects keep records and run routines |
| G4 | Nothing says which origins a business uses | The Project's apps (built) become the browser's trust list for its routines | 0 | (in the browser ADR) |
| G5 | No scheduler | **Routines**: hosted cycles with a cadence, a spend ceiling and an allowed tool set; never overlapping themselves or a live turn | 2 | (in the records ADR) |
| G6 | No unattended class | A routine's allowed tools are read hands plus `record_put` for finds, drafts and stats. Anything that changes a page outside that set files a card | 2 | (in the records ADR) |
| G7 | No surface to listen and judge | The report's **queue** block: a YouTube embed and Keep / Pass / Later, with a note and a genre | 1 | Composed reports |
| G8 | No report | **The composed report** (see below) | 1 | Composed reports |
| G9 | No Twin | **Tone profiles** per channel (email, bio message, comment): directives, constraints, examples. Examples grow only from the owner's edits | 2 | The Twin speaks only through cards |
| G10 | The captcha cannot be solved by Athena | **Hand the wheel**: she opens the tab, asks the owner to take over, and resumes when the page changes | 0 | (in the browser ADR) |
| G11 | Posting a comment or sending a message | Gated `page_fill` + `page_submit`, carrying the Twin draft as the card's text; the owner can edit before signing | 2 | (in the Twin ADR) |
| G12 | No inbox reading or thread matching | An inbox routine reads the mailbox's web page, matches sender to creator record, and appends a `thread` record | 2 | (in the Twin ADR) |
| G13 | No rights policy | `may_render(track)`: the track is kept, its creator's `agreement` is `agreed` with a thread as evidence, and a file is present. A function, not prose | 1 | (in the records ADR) |
| G14 | No downloads | `page_download`: a download lands in the project's files and becomes a `file` record (sha256, mime, origin) | 0 | (in the browser ADR) |
| G15 | No files area | `<data_dir>/spaces/<space_id>/files/`, erased with the project; the model refers to a file only by its record id, never by a path | 1 | Projects keep records and run routines |
| G16 | Gravitone's MCP cannot make a music video | **New Gravitone ops** (in gravitone-gcloud): `mv_import{path}`, `mv_plan`, `mv_run{versions}`, `mv_status`, `mv_output` returning the MP4 and the metadata | 3 | (gravitone-gcloud's own ADR) |
| G17 | No MCP client in muse | Port athena-portable's client (`mcp.json`: `{id, url, token_env}`); classes come from the peer's annotations | 3 | Peer apps over MCP |
| G18 | A 30-minute job does not fit a turn | Bounded projection: the routine starts the job, keeps a `render` record, and a later cycle reads `mv_status`; the turn never waits | 3 | (in the peer-apps ADR) |
| G19 | No file upload into a page | `page_upload{ref, file_id}`: sets a file input from a file record. On WebView2 there is no CDP `setFileInputFiles`, so this is the riskiest new piece. **Spike first** | 0 | (in the browser ADR) |
| G20 | Hands stop at iframes and shadow DOM | Hands walk open shadow roots and same-origin frames; Studio's upload dialog is the acceptance test | 0 | (in the browser ADR) |
| G21 | No attribution | A `release` record carries the title, original track URL, creator channel URL, genre and credits line. The description is rendered from it; the synthetic-media box is always ticked yes; privacy is always private | 3 | (in the peer-apps ADR) |
| G22 | No stats | A stats routine reads Studio's analytics page into append-only `stat` records (`measured_at` is the read time, never a claimed time) | 2 | (in the records ADR) |
| G23 | Cost per project is not served | `Ledger.page` gains a space filter, so the report can show what the business costs to run | 1 | - |

## Design decisions

Wave 1 (2026-10-28):
- **Deliverable: a plan and a gap map first.**
  - Rejected: building the first slice in this session.
  - Rejected: splitting into two sparks.
- **Doctrine: apps are reached as the owner reaches them**, through the internal browser and the app's own MCP, not through per-service connectors.
- **Hands: Claude Code with tools on**, resolved in wave 2.
- **Autonomy in v1: four things run on their own.**
  - Watching creators, drafting outreach, reading replies, and rendering after approval.
  - Every send, post and upload is a card.
- **Report: Athena composes it from a closed kit.**
  - Rejected: a fixed template per project type, which drops her judgement.
  - Rejected: a free HTML page, which is off-design and unvalidated.

Wave 2:
- **Hands: tools on, but only Athena's MCP server.** This synthesis keeps both picks: the engine really calls tools, and every act still passes the gate and the ledger.
  - Rejected: Claude's own browser and Gravitone MCP directly. That means no cards, no ledger, and it is gone on the Muse API.
  - Rejected: athena-portable's OP-line grammar with tools off.
- **Browser: port athena-portable's webview**, and extend the hands with upload, iframes and shadow DOM.
  - Rejected: real Chrome over CDP.
  - Rejected: two drivers by tier.
- **Render: extend Gravitone's MCP** with music-video operations, called as a peer app.
  - Rejected: wrapping the CLI as an Athena tool.
  - Rejected: clicking through Gravitone's UI.
- **First contact: all three channels.** An email the owner unlocks, public links in the creator's bio, and a public comment on the track. Each send is a card.

Wave 3:
- **State: records and routines.**
  - Rejected: SQL tables per entity, which needs a migration for every new business.
  - Rejected: memory facts only, which leaves nothing typed to count.
- **Audio: the creator sends the file.** This brings in downloads and a files area.
  - Rejected: a Suno link fetched by Gravitone.
  - Rejected: both.
- **Evaluate: the queue block in the report.** The verdict is the owner's act, not hers, so it needs no card.
  - Rejected: YouTube playlists as the inbox.
  - Rejected: one track at a time in her window.
- **Twin: a tone profile per channel, plus the owner's edits as examples.**
  - Rejected: a written profile only.
  - Rejected: learning the voice from the mailbox.

Wave 4:
- **Setup: extend the v2 stage with a business branch.** The channel is the staged need.
  - Rejected: hand-built first.
  - Rejected: one gated "set up business" card.
- **Report home: the project's front page.**
  - It is recomposed when the records move materially, or on request.
  - Pins persist, and versions are kept.
  - Rejected: its own route composed on demand.
  - Rejected: a scheduled digest.
- **Sequencing: after v2, in phases.**
  - Rejected: the report first as a demo.
  - Rejected: folding this into v2.

Director decisions (convention or judgement; overridable):
- **Routines run while the daemon runs.** On start, a routine whose last run is older than its cadence runs once. It catches up and never back-fills. A background OS service comes later.
- **Default cadences:** watch every 6 h, inbox every 30 min, stats daily. Spend ceilings per run start at $0.25 for reads and $2.00 for a render.
- **Every number on the report is computed from records, never written by the model.** The model chooses and arranges blocks and writes the callout. It never writes a count. This is the coverage rule from v2, applied to a report.
- **Rights before render.** `may_render` is the only door to `mv_run`, and the upload card shows its evidence (the agreement thread).
- **Privacy is private, always.** Athena never makes a video public. The upload card says "private draft" and the hands refuse a visibility control.
- **The browser profile is shared, as in athena-portable.** The business uses the owner's own channel and mailbox sessions. Per-project profiles stay a non-goal.
- **Ledger:** `Surface` gains `routine` and `report`. Every routine run and every report composition writes ledger rows.
- **Strings:** inline English, plain words. The screen says "her browser", "drafts waiting for you", "private draft", never "MCP", "record", "hands".

## Design brief

### Summary

A person describes a business on the stage and Athena sets it up as a Project. It gets routines that watch and read on their own, records of creators, tracks, threads and releases, a Twin that drafts in the person's voice, and a report on the Project's front page that Athena composes from a fixed kit. She works in the person's own web apps through her built-in browser and asks for a signature before anything is sent, posted or uploaded. For the music channel, that means she finds new tracks, the person judges them in the report, she corresponds with the creators and receives their files, and Gravitone renders each video. The video then lands in YouTube Studio as a private draft with full attribution.

### Phases (each phase is one /spark build; work packages are cut at its own design gate)

**Phase 0 - hands and the engine (foundation).**
- Spike first, as a go/no-go:
  - `page_upload` on WebView2 against YouTube Studio's upload dialog.
  - Hands through shadow DOM and iframes.
  - If upload cannot be done in WebView2, return to the browser decision with the measured result.
- Athena's MCP server (loopback, bearer, the action catalog as tools, gated tools filing cards).
- Claude Code engine mode with tools on.
- Ported tabs, hands and origin trust.
- `page_download`, and the hand-the-wheel takeover.
- Acceptance:
  - A scripted session reads a YouTube channel page.
  - The same session files a gated comment card that, once signed, posts exactly once to a test video.
  - It downloads a test file.
  - It uploads an MP4 as a private draft on a test channel.

**Phase 1 - records, files and the report.**
- `records` and `files` with per-kind validation and the `may_render` policy.
- The per-space ledger query.
- The report kit, the composer and the validator.
- The project's front page, with the queue block and verdicts.
- Acceptance:
  - The report composes on seeded records.
  - A spec with an unknown block renders the rest and says how many it dropped.
  - Every number traces to a records query.
  - A verdict appends a revision.

**Phase 2 - routines and the Twin.**
- The routine host: cadence, catch-up, no overlap, spend ceiling, allowed tools.
- The watch, inbox and stats routines.
- Tone profiles, drafts as cards, and edits promoted to examples.
- Acceptance:
  - A routine never runs during a live turn in its space.
  - A draft the owner signs unedited does not become an example; one they edit does.
  - Stats records are append-only.

**Phase 3 - Gravitone and the release.**
- The Gravitone MCP operations (in gravitone-gcloud) and the MCP client in muse.
- A render as bounded projection.
- The `release` record, the description template, and the upload card.
- Acceptance:
  - A kept, agreed track with a file renders under its ceiling without a card.
  - A track missing any of the three is refused with the reason.
  - The upload card shows the attribution and the evidence.
  - The draft is private, with synthetic media declared.

**Phase 4 - the business branch on the stage.**
- The sketch's business slots: `routines`, `records`, `voices`, `report`. These sit beside v2's seven slots.
- Writing the Project from the agreed sketch.
- The first report.
- The music channel is the staged need, and it is v2's second exemplar.

### Data & API (wire-level names; the contract is committed before each phase's packages)

MCP server (Phase 0):
- Served at `POST /mcp` on the daemon's loopback, behind the bearer.
- Tools are the action catalog. Class comes from the catalog, never from the model.
- A gated call returns `{pending: {card_id}}`; on sign, the daemon executes the call once.
- New actions:
  - auto: `page_read | page_find | page_wait | page_scroll | tabs_read | page_screenshot | record_list | record_put | file_list`
  - gated: `page_click | page_fill | page_select | page_submit | page_upload | page_download | wheel_handoff`
  - peer tools arrive as `<peer>__<tool>` with the peer's annotations.
- The report inside agent hosts ([ADR 0021](../../adr/0021-the-project-report-is-also-a-view-inside-agent-hosts.md), 2026-11-03): an outside lease on a project that keeps records gets `show_report`, the report as standalone text, computed figures and the `ui://athena/report` view; `readOnlyHint` says whether a tool writes, and every refusal is `isError`.

Records (Phase 1):
- Table: `records(id TEXT PK, space_id TEXT NOT NULL, kind TEXT NOT NULL, key TEXT, body TEXT, rev INTEGER, created TEXT)`. Append-only: a change is a new revision.
- `RecordKind = "creator"|"track"|"thread"|"agreement"|"file"|"render"|"release"|"stat"`
- Key bodies:
  - `track {url, title, creator_key, found_at, verdict?: "keep"|"pass"|"later", genre?, note?}`
  - `agreement {creator_key, state: "proposed"|"agreed"|"declined", thread_key}`
  - `stat {metric, value, measured_at}`
- Files live at `<data_dir>/spaces/<space_id>/files/<sha256>`.

Routines (Phase 2):
- Table: `routines(id, space_id, name, cadence_s, ceiling_usd, tools TEXT, last_run TEXT, state)`.
- Run event: `RoutineEvent = started | record | card | spent | done | error`.

Report (Phase 1):
- `ReportSpec {v: 1, title, blocks: Block[]}`
- `Block {id, kind: BlockKind, title, span: 1..12, binding?, config, pinned?}`
- `BlockKind = "stat"|"trend"|"queue"|"pipeline"|"list"|"thread"|"cards"|"callout"`
- `binding {kind: RecordKind, filter?, agg?: "count"|"sum"|"last"|"series"}`
- Routes:
  - `GET /spaces/{id}/report` returns `{spec, rendered_at, dropped: n}`.
  - `POST /spaces/{id}/report/compose` streams `TurnEvent`.
  - `PUT /spaces/{id}/report/pins`.
  - `POST /records/{id}/verdict` takes `{verdict, genre?, note?}`.

Absent values: omit the key when unknown. A stat with no reading is absent, never `0`.

### UX/UI spec

- **Front page:**
  - The report replaces the top of `Level.tsx`. The name, brief, apps and Erase move below it.
  - There is a 12-column grid with blocks on Loop Tide tokens.
  - A dropped block shows as "1 block could not be shown" with the reason.
- **Block states:** every block shows loading, empty ("no tracks waiting"), stale ("as of 3 h ago"), and error.
- **The queue block:** an embedded player per track, Keep / Pass / Later, a genre picker and a note. A verdict moves the item out with no reflow of the other blocks.
- **Cards:** the existing `CardView`, in her window and in the report's `cards` block. A Twin draft card has editable text.
- **Hand the wheel:** her browser tab comes forward with one line saying what she needs ("Solve the captcha, I'll take it from there").
- **New primitives:** `StatTile`, `Sparkline`, `Funnel`, `Queue`. They stay local to `main/report/` until a second caller appears. Charts follow the dataviz rules and the 12 px floor.

### Strings

Inline English, plain words, no translation ritual.

### Non-goals

- Making a video public.
- Per-project browser profiles.
- Per-service Python connectors (Gmail API, YouTube Data API).
- Ripping audio from YouTube.
- Athena solving captchas.
- Learning the voice from the mailbox.
- A free-HTML report.
- Numbers written by the model.
- Running routines while the app is closed.
- Rendering on cloud machines.

### Risks

- **Uploading a file inside WebView2 is unproven.**
  - Mitigation: the Phase 0 spike, before anything else is built on it.
  - The fallback goes back to the owner as a decision; it is not taken silently.
- **YouTube Studio's UI changes and breaks the hands.**
  - Mitigation: the hands work on DOM text and labels, not selectors.
  - A failed act is reported, never guessed.
- **A routine reading the mailbox meets hostile content.** A creator's reply is untrusted page data.
  - It is fenced as page data, as portal reads are today.
  - It can only lead to a card, never to an act.
- **Rights.** A kept track whose creator is on Suno's free tier cannot be licensed for commercial use. The agreement record asks for the plan tier, and `may_render` refuses without it.
- **Render cost and time.** 31.5 minutes per 5-minute track (measured, one track). The ceiling holds spend; renders run one at a time on Gravitone's `box.render` lease.
- **Engine swap.** Muse API function calling must carry the same catalog. Phase 0 measures one turn on each engine.
- **Account standing.** Automated comments can look like spam. Every comment is a card, with no batch-sign in v1.

## Phase 0 - hands and the engine (built 2026-10-31)

Built on its own branch for the Director's review. ADRs: [0013](../../adr/0013-her-browser-tabs-hands-and-trust-per-origin.md) (her browser) and [0015](../../adr/0015-athenas-tools-reach-every-engine-through-one-mcp-server.md) (the MCP server). Every acceptance step that needs YouTube ran against local test pages (`athena.browser.fixture`, simulated, labelled on every page). The real-account steps wait for the owner ([checklist](#phase-0-real-account-run-owner-present)).

### The spike: go on the local reproduction, open on real YouTube

The question was whether `page_upload` can be done in WebView2, which has no CDP `setFileInputFiles`, and whether the hands reach through shadow DOM and iframes.

- **Method.** The shell stages the file into the page in base64 parts of 512 KiB through `eval`. The page builds a `File` in the input's own realm (the frame's `File` and `DataTransfer`), assigns it to `input.files` through a `DataTransfer`, and fires `input` and `change`.
- **Reproduction.** The studio page opens a same-origin iframe. The frame's upload dialog is a custom element with an open shadow root holding a hidden `<input type=file>`, a title field and Private / Unlisted / Public. The page hashes the file it was given (SHA-256) and posts the digest back.
- **Measured** (WebView2 on this machine, the built shell, `scripts/browser_seam.py`, 2026-10-31, n=1 each). Each figure is the shell's own measurement, staging and the page's assignment included:

| File | Parts | Staged and given | Page's SHA-256 matched |
|---|---|---|---|
| draft-5mb.mp4 (5,242,880 bytes, seeded) | 10 | 305 ms | yes |
| draft-50mb.mp4 (52,428,800 bytes, seeded) | 100 | 2,798 ms | yes |

- **Verdict: go** on the local reproduction. The browser decision stands, and nothing goes back to the owner as a fallback.
- **Still open** (owner present): the real YouTube Studio upload dialog. Unknowns there: whether Studio's own iframe is same-origin with the top page (a cross-origin frame is unreachable by design), whether its CSP or Trusted Types stop the reply path (`invoke` falls back to `chrome.webview.postMessage`), and how a 500 MB file behaves. Linear from the figures above, 500 MB is about 28 s of staging (est.).
- **Found on the seam, fixed:** Chromium holds a page's second script-started download behind a prompt. The shell now allows "automatic downloads" only while a signed `page_download` has armed that tab. A missing upload part was not caught, because `Array.some` skips the holes of a sparse array; the jsdom test found it.

### Work packages (cut at the design gate by the builder; Director to confirm)

| WP | What | Where |
|---|---|---|
| WP0 | The contract: the new catalog actions, `HandResult`, `BrowserCall`, `FileItem`, `McpLease`, `WheelNote`, the card's `outcome`, the routes, and both stream protocols (the relay's long-poll and MCP's one JSON-RPC message per POST) | `contracts.py`, `contract.ts` |
| WP1 | The MCP server and leases; one `dispatch` for a turn's round and for MCP | `mcp.py`, `routes_mcp.py`, `turn.py` |
| WP2 | Claude Code with tools on: one run per chat turn against the MCP server, streamed | `engine/claude_code.py`, `engine/cli.py` |
| WP3 | The spike and the fixture pages | `browser/fixture.py`, `scripts/browser_seam.py` |
| WP4 | The shell's browser: tabs, the relay, `hands.js` (deep walk, upload), downloads, the wheel, the page capability | `src-tauri/src/browser.rs`, `hands.js`, `capabilities/page.json`, `build.rs` |
| WP5 | The daemon's browser: relay, per-origin trust, cards bound to the page, files, the executor | `browser/relay.py`, `browser/actions.py`, `browser/files.py`, `browser/routes.py` |
| WP6 | The live seam and the owner-present checklist | `scripts/browser_seam.py`, this section |

### What each item does now, and how it was verified

| Item | Does | Verified |
|---|---|---|
| MCP server | `POST /mcp` on the loopback. The bearer is a lease that names one project and expires; the daemon's token is refused there. The tools are the catalog. A gated call answers `{pending: {card_id}}` and runs once, when the person signs | `tests/test_mcp_server.py`. On the seam: tools listed (19), daemon token refused |
| Claude Code, tools on | A chat turn runs `claude -p` with `--tools ""`, only Athena's server under `--strict-mcp-config`, and `--allowedTools` set to the turn's tools. The server's lines and cards stream in order with her words; one ledger row per run. `ATHENA_CLAUDE_TOOLS=0` switches back to op lines | `tests/test_engine_agent.py`. Live: one turn read the channel page through her browser (below) |
| Tabs, hands, trust | A tab is a `page-<n>` window. Ten page hands plus the shell's open, tabs, upload, download and wheel. Walks go through open shadow roots and same-origin frames. The project's apps are the trust list: an AUTO hand runs only on a trusted site and files a card anywhere else. A card runs only on the tab, page load and address it was asked on. A "Public" or "Unlisted" control is refused even when signed | `tests/test_browser_actions.py`, `apps/desktop/src/lib/hands.test.ts`, Rust unit tests. On the seam: a moved page refused the old card; an untrusted site filed a card; Public was refused when signed |
| `page_download` | Arms the tab, clicks, and lands the file in the project's files under its SHA-256 (one row per digest), named to the model only as `fil_...`. A download nobody armed is cancelled | On the seam: a WAV (16,044 bytes), 5 MB and 50 MB, each kept with a matching digest |
| `page_upload` | See the spike | On the seam: both files reached the input in the shadow root inside the iframe |
| Hand the wheel | A gated card brings the tab forward with her line in its title. When the page moves on, the shell posts `back` and the daemon publishes the `wheel` event | On the seam: `{tab: 5, state: back}` was heard. The person's tick was simulated by two signed hands |
| Her window | A card for each new action shows a plain title ("Upload a file", "Take over her browser") | typecheck, the existing CardView tests |

### Acceptance on the local reproduction (simulated)

`uv run python scripts/browser_seam.py --engine claude_code --live-turn` (2026-10-31): **14 of 14 checks pass**. The session is a script over MCP, signing each card through `POST /decisions` the way her window does. No model is used except in the live turn.

| Plan's acceptance step | Local reproduction | Result |
|---|---|---|
| A scripted session reads a YouTube channel page | `/channel`: a creator's three tracks | read, fenced as page data (20 ms) |
| It files a gated comment card that, once signed, posts exactly once to a test video | `/watch?v=t1`: a fill card and a click card | both cards signed, one comment in the journal; the second signature answered 400 "already decided" |
| It downloads a test file | `/downloads`: WAV, 5 MB, 50 MB | 350 / 180 / 521 ms per signed card |
| It uploads an MP4 as a private draft on a test channel | `/studio`: the shadow-DOM dialog in an iframe | 5 MB and 50 MB uploaded; title filled; saved as `private`; Public refused |
| One turn on each engine (Risks) | Claude Code, sonnet | 5.8 s, `page_open` then `page_read`, all three titles named, $0.0214 (CLI's own figure, est.). The Muse API turn is not measured: no key on this machine |

### Director defaults taken (overridable)

- **A window per tab**, not portable's child webviews in one window. This needs no `unstable` Tauri feature and no layout code; handing the wheel means focusing that window.
- **`page_open` is a new AUTO action** (not in the plan's list). Without it nothing can open the channel page. It runs at once on a project app and files a card for any other site.
- **The project's apps are the only trust list**, including for reads. "On first sight" means "not one of the project's apps"; there is no per-origin trust beyond that yet.
- **A minimal `files` table now, adopted by Phase 1's records** as the `file` kind, because upload and download need one in Phase 0.
- **Claude Code's chat turn may make 16 model calls** (`--max-turns 16`), not the turn's six; the stage, the bench and the rehearsals keep op lines.
- **The card keeps its run's words** (`outcome`, additive). A signed browser card's result, such as the saved file's id, is otherwise lost.
- **`page_screenshot`, `record_list` and `record_put` are not in Phase 0.** Records are Phase 1. The screenshot needs WebView2's `CapturePreview`, and no Phase 0 acceptance step needs it.
- **Her browser shares the app's WebView2 profile**, as in athena-portable.

### Phase 0 real-account run (owner present)

Not run: it needs the owner's YouTube test channel and is the open half of the spike.
1. Make or pick a **test** channel with no audience. Start the app on Claude Code (`ATHENA_ENGINE=claude_code`) with a fresh data folder.
2. Make a project with `https://www.youtube.com` and `https://studio.youtube.com` as its apps. Sign in to YouTube once in her browser (open a tab, then hand yourself the wheel).
3. Read: ask her for the titles on a creator's channel page. Expect `page_open` and `page_read` with no card.
4. Comment: ask her to comment on one of **your own test channel's** videos. Sign the fill card and the click card. Check that the comment exists once, then sign the click card again and expect "already decided".
5. Download: from a page you control, download a small file. Check that the project's files list it with its SHA-256.
6. Upload, the spike on the real dialog: in Studio, "Create" -> "Upload videos", then `page_find` with role `file`.
   - Record whether the input is found (same-origin frame or not), whether `page_upload` reaches it, and the shell's measured milliseconds for a small MP4 and for a large one (about 200 MB).
   - Leave visibility on Private. Expect any "Public" control to be refused.
7. Record here what ran, what was refused and why, the est. cost from the ledger, and anything that broke. If the upload cannot reach Studio's input, the browser decision goes back to the owner with the measurement, as the Risks say.

### Owner's answers (2026-10-31)

- **Access is part of onboarding.** Chore onboarding (the stage, [ADR 0007](../../adr/0007-a-chore-is-written-in-conversation-and-tested-against-the-users-expectations.md)) tests the flow and then leads the person to sign in to each real web app the chore needs, in her browser, so that next time Athena reaches it on her own. When a session lapses, the Project's overview shows it as a blocker of the process, naming the site and the way back in. Owner's words: "chore onboarding should test the flow and lead user into auth to the specific webpages, so next time Athena can access on her own. If token expires Project overview should alert blocker of the process."
- **Trust comes only from onboarding.** No separate way to trust a site: the sites a chore needs are added to the project's trust list during its onboarding, and only there ("adding sites into whitelist should be part of the onboarding of chore (project)").
- **A new, clean business profile.** The music channel runs on new accounts made for the business, not the owner's personal channel and mailbox.
- **Built 2026-10-31 ([ADR 0014](../../adr/0014-a-chores-onboarding-signs-in-to-its-real-sites-and-only-onboarding-grants-trust.md)):** a chore's onboarding signs in to its real sites (step `access`, after keep), only onboarding grants her browser trust (project `sites`, apart from `apps`), and a lapsed sign-in blocks on the project overview with "Sign in again". Simulated seam (`scripts/access_seam.py`) 11/11 on the built shell; the real-account run is not done.
- **Still open: Studio's frame.** If the real upload dialog sits in a cross-origin frame, hands cannot reach it by design (inject `hands.js` into every frame, or return to the browser decision). Measured in the Phase 0 real-account run before it is decided.

## Plan of record (2026-11-01) - Phases 1-4

The plan below takes the 2026-10-28 design and adjusts it to what has been built since: Twins (ADRs 0008-0010), devices (ADR 0017) and Phase 0 (ADRs 0013-0015). Where this section and the design brief above differ, this section wins. Each phase is built as its own `/spark`. That spark commits its contract and stubs first, opens the ADR named for it, and confirms the packages below at its own design gate.

### What the code holds today (scouted 2026-11-01)

- **Nothing in Phases 1-4 is built:**
  - no `records` or `routines` table;
  - no report, compose or queue code;
  - no `may_render`;
  - no MCP client (`peer/client.py` is the device-to-device caller, not MCP);
  - no `record_*` actions;
  - no `routine` or `report` surface.
- **Reused as is:**
  - the `files` table and `fil_` ids (`browser/files.py`). The `file` record points at a `files` row and never copies it.
  - the project's `sites` and the overview's blocker (`main/projects/Sites.tsx`).
  - `StatStrip` and `Ledger` (`apps/desktop/src/ui/`).
  - the MCP server and the action catalog.
  - the Twin's voice compiler (`twins/voice.py` `compile_voice`) and its rule that only the owner's edits become examples (`missions.sign`).
- **In tension with the design:**
  - **Twins read and send mail through the Gmail API**, and `sent_alone` sends without a card (`twins/missions.py`).
  - **The voice is learned from sent mail** (`voice.py`), and it is per twin, not per channel.
  - **The Twins poller** (`twins/poller.py`, started in `server.py`'s lifespan, every 300 s) is a second background loop. It has no spend ceiling and no tool list, and it runs beside live turns.
  - **The ledger has no space filter.** `Ledger.page(limit)` cannot filter by space, and Twins compute their weekly cost in their own SQL (`twins/view.py`).
- **Gravitone** (gravitone-gcloud):
  - Its MCP has no music-video operation.
  - `pipeline/music-video.mts` already has `run --detach` and `collect`.
  - Every attempt is an ordinary kernel job (`job:run:mv.<id>.<ts>`, lease `box.render#1`), so `gt_job status | cancel` should already reach it. This is not yet confirmed end to end.
  - Leonardo stills cost credits. Gravitone's own law is that an agent never spends, and `--still` skips Leonardo.
  - A family tool's description is capped at 240 characters, and `gt_read` and `gt_launch` are near that cap.
- **athena-portable's MCP client** (`connectors/mcp/`, 778 lines):
  - The config is `{servers: [{id, url, token_env}]}`.
  - Transport is a Streamable HTTP POST with a 20 s timeout, so a render has to detach.
  - The class comes from annotations: read-only, or not destructive and not open-world, is AUTO; anything else is GATED.

### Decisions (owner, 2026-11-01)

- **The business mail goes through her browser, on Proton Mail (web).**
  - The inbox routine reads `mail.proton.me` as page text, and every send is a gated page act.
  - The Twin's voice compiler and its edits-as-examples rule are the drafting engine, with a tone profile per channel: email, bio message, comment.
  - Twins' own Gmail missions stay as they are.
  - Rejected: reusing Twins' Gmail connector for the business; giving the Twin a second (browser) transport.
- **The Twins poller is folded into the routine host.**
  - Every open Twin mission runs as a routine, with a cadence, a ceiling, an allowed tool set and no overlap with a live turn in its space.
  - Rejected: a second host beside the poller.
- **For a render, the policy replaces the card.**
  - The render routine may call Gravitone's launch operation. `may_render` and the per-render ceiling are the gate.
  - The owner signs the agreement and the upload, not the render.
  - Rejected: a card per render.
- **Renders use a still image, with no Leonardo spend.**
  - Athena passes `--still`: the creator's cover art when it came with the file, otherwise the channel's default image.
  - Gravitone's "an agent never spends" law holds untouched. Leonardo looks are a later option.
  - Rejected: a spend request approved in Gravitone; a standing budget for Athena's token.
- **Phases 1-4 are planned now, Phase 4 included.** The stage's business branch is the onboarding that the live end-to-end run exercises.

### Director decisions (convention or judgement; overridable)

- **The business Project's voice is a Twin.**
  - It is set up through Twins' existing setup, which Phase 4's `voices` slot opens.
  - `TwinChannelKind` grows `mail_web | bio | comment`, and examples carry their channel.
  - `compile_voice(daemon, twin_id, channel=None)` keeps the twin's dials and adds only that channel's examples.
  - A new mailbox has no sent mail, so its samples are the owner's own written offer and messages, pasted in.
- **Business sends are always cards.** `sent_alone` stays a Twins (Gmail) feature and is never offered on a `mail_web | bio | comment` channel. The rule is in `twins/decide.py` with a test.
- **The folded poller keeps Twins' behaviour otherwise.**
  - It keeps the 300 s default and `ATHENA_TWIN_POLL`.
  - Its ceiling is $0.25 per run, the same as the read routines.
  - One routine per live Twin, named `twin:<twin_id>`, replaces the global loop.
- **The live-turn rule is enforced by `busy.py`.** A routine waits while a turn is open in its space; it is never refused, and it runs on the next tick. Today `busy.turn` only counts turns. It gains `busy.idle(space_id)`.
- **Gravitone gets one new family, `gt_mv`,** rather than five operations squeezed into the two families already near the 240-character cap.
  - `import {folder}`: WRITES. It reads the folder's audio and returns the plan.
  - `launch {folder, still, versions, budget_usd: 0}`: LAUNCHES. It is detached, refuses any spend, and returns `{job_ids}`.
  - `collect {folder}`: READS. It returns the MP4 and `youtube.txt` paths with their fields.
  - Status and cancel stay on `gt_job`.
  - This is gravitone-gcloud's own change, under its MCP rules and registry test.
- **The folder hand-off.**
  - Athena stages each render in `<data_dir>/spaces/<space_id>/renders/<render_id>/` (the audio under the track's title, plus the still).
  - Gravitone writes its outputs beside them, and the render routine collects them into `files`.
  - The model never sees a path. It names a `track` record, and the daemon fills in the folder.
- **Athena's MCP client is ported from athena-portable** into `src/athena/peers_mcp/`. The name `peer/` is taken by devices.
  - Peer tools appear as `<id>__<tool>`.
  - The class comes from annotations, except where a routine's allowed tools name a tool and a policy function guards it. `gt_mv.launch` is guarded by `may_render`.
- **Stats are read from Studio's analytics page by the stats routine.** There is no YouTube Data API.

### Phase 1 - records, files and the report

ADR: *Projects keep records, and her report is composed from a closed kit.* Gaps: G3, G7, G8, G13, G15, G23.

| WP | What | Files | Acceptance |
|---|---|---|---|
| 1.0 | The contract and stubs | `contracts.py`, `contract.ts` | `RecordKind`, every record body, `Record`, `ReportSpec`, `Block`, `BlockKind`, `Binding`, `ReportView {spec, rendered_at, dropped, reasons}`, `VerdictBody`, every route's envelope; the parity test passes; `record_list` (auto) and `record_put` (auto, finds only) in the catalog; `Surface` gains `report` |
| 1.1 | Records | `records.py`, `store.py`, `routes_records.py` | The table is append-only (a change is `rev+1`). The latest revision per `(space_id, kind, key)` comes from one query. The body is validated per kind, and an unknown kind is refused. Records are erased with their space. A `file` record refers to a `files` row by id. `may_render(track)` returns `{ok, reasons[]}`, and every missing condition (kept, agreed with a thread, file present, plan tier) is tested |
| 1.2 | The per-space ledger and the compose engine | `ledger.py`, `report/compose.py`, `report/validate.py` | `Ledger.page(limit, space_id=None)`, and Twins' own SQL moves onto it. `validate(spec)` keeps the known blocks and counts the dropped ones with reasons. Every number is computed from a binding by `report/compute.py`, never from the model's text. Compose runs one turn that streams `TurnEvent` and writes a ledger row with surface `report`. Pins survive a recompose, and versions are kept |
| 1.3 | The front page and the kit | `main/report/*`, `projects/Level.tsx` | The report sits above the name, brief and sites in `Level.tsx`. It uses a 12-column grid and the blocks `stat`, `trend` (Sparkline), `queue`, `pipeline` (Funnel), `list`, `thread`, `cards` and `callout`. Every block shows loading, empty, stale and error states. The queue block has an embedded player with Keep / Pass / Later, a genre and a note, and a verdict causes no reflow. "1 block could not be shown". No page scroll at 1024x700, the 12 px floor, the dataviz rules |

Phase 1's live check: a report composed on seeded music-channel records, where every number traces to a records query, followed by a verdict that appends a revision.

#### Phase 1, as built (2026-11-01, [ADR 0018](../../adr/0018-projects-keep-records-and-her-report-is-composed-from-a-closed-kit.md))

- **Records.**
  - A project keeps records of the kinds it picks from a fixed catalog of eight: creator, track, thread, agreement, file, render, release and stat.
  - Each kind is code. It checks the fields, cleans the text and decides the key: a creator by channel address, a track by its address, a stat by metric and time.
  - A record is never edited. A change adds a new revision, and an unchanged put adds nothing.
  - Athena keeps what she finds (creators and tracks) at once. Any other kind waits for the person to sign a card. Her later find of a track never drops the person's verdict, genre or note.
  - A file record points at one of the project's own files.
  - `may_render` answers, in plain words, what stands between a track and a video.
  - `scripts/business_fixture.py` seeds a simulated music channel through the daemon's own code.
- **The report.**
  - The kit's registry (`report/vocab.py`) is the one authority. The composer's instructions are generated from it and from the kind catalog.
  - One validation door (`report/validate.py`) checks a spec when it is composed and again when it is shown. Every dropped part gets a reason in screen words.
  - A digit in anything the model writes is refused. Every figure is computed from records (`report/compute.py`): a count of nothing is a real zero, and a sum or reading with no records is absent.
  - Composing is one engine call on surface `report` that returns the view. The design brief above said it streams; the built route returns the view instead.
  - A failed compose keeps the last good spec.
  - Pins reach the composer as constraints, and a pinned part comes back by id.
  - A kind going from none to some, or from some to none, rearranges the report at most once an hour. A verdict never does.
  - The ledger answers per project (`GET /ledger?space=`).
- **The front page.**
  - A project that keeps records opens on its report, under the crumb and above the name, brief and sites. Any other project looks as before.
  - The title row says when Athena arranged it ("Athena has not arranged this yet" until she has), beside "Arrange again".
  - Below it come her one sentence, then "1 part could not be shown" with the reasons behind a fold, then the parts on a 12-column grid.
  - The grid scrolls inside its own region, so the window does not scroll at 1024x700.
  - Each part says when it is reading, empty, old ("as of 3 h ago") or unreadable, and has a pin.
  - The queue plays a YouTube track in place, one at a time. It takes Keep / Pass / Later with a genre, suggested from the project's own tracks, and a note. A verdict takes the track out without moving anything else.
  - The trend is one thin line, and the funnel is one bar per stage with its count.
- **Verified.**
  - Gates: 865+ Python tests and 575 desktop tests.
  - Screenshots at 1024x700 and 1440x900, light and dark, on the daemon-generated simulated channel.
  - The live seam (`uv run python scripts/report_seam.py claude_code <out>`, 2026-11-01, n=1) passed 7 of 7 checks: a real daemon over the simulated channel, one composition on Claude Code, and a verdict.
    - The composition took 17.9 s and cost $0.036 (est., from the ledger).
    - She kept every default part's id and added a subscribers trend and a callout with no figure in it: "No video has been rendered or released yet, so the next steps are judging the waiting tracks and signing the agreements."
    - The verdict appended revision 2, and the queue shrank by one.
- **Known gaps:**
  - The drop reasons of a composition are not stored, so a later read shows only the drops found at render time.
  - The simulated engine cannot compose; the default layout stands in.
  - The fixture's tracks are not on YouTube, so the player shows only in the preview.
  - `RecordPutBody` has no `key` for a thread.
  - A verdict does not refresh "Latest tracks" until the next read.
  - No screen chooses a project's kinds yet; that comes in Phase 4.

### Phase 2 - routines, the folded poller and the Twin's channels

ADR: *Routines are the daemon's only background host.* Gaps: G5, G6, G9, G11, G12, G22.

| WP | What | Files | Acceptance |
|---|---|---|---|
| 2.0 | The contract and stubs | `contracts.py`, `contract.ts` | `Routine`, `RoutineEvent = started\|record\|card\|spent\|done\|error` with the stream's protocol written out (event order, how a run ends, and what a run that finds a live turn does), `TwinChannelKind` grows, `Surface` gains `routine` |
| 2.1 | The routine host | `routines/host.py`, `routines/store.py`, `busy.py`, `server.py` | A cadence with one catch-up run on start and no back-fill. A routine never overlaps itself or a live turn in its space (`busy.idle`). A run that reaches its ceiling stops, with the reason recorded. Outside its allowed tools, a call files a card. Every run writes a ledger row. Each rule has a test |
| 2.2 | Fold the poller | `twins/poller.py` (removed), `twins/missions.py`, `routines/twin.py` | Twins' existing tests pass unchanged except where a mission now waits for a live turn, and that case gets its own test. `ATHENA_TWIN_POLL` is honoured. The Twins overview shows the same counts |
| 2.3 | The business routines and channels | `routines/watch.py`, `inbox_web.py`, `stats.py`, `twins/voice.py`, `twins/decide.py` | **Watch:** reads each followed creator's videos page every 6 h and puts `track` records, deduplicated by URL. **Inbox:** reads Proton's thread list every 30 min, matches a sender to a `creator`, appends a `thread`, and drafts a reply card in that channel's voice. **Stats:** reads Studio analytics once a day into append-only `stat` records. A business send is always a card, with a test. An unedited signed draft never becomes an example and an edited one does, with a test. Every routine runs against a simulated fixture page (`browser/fixture.py` gains a creator videos page, a Proton inbox and a Studio analytics page) |

Phase 2's live check: on the built shell, the watch routine finds a new upload on the fixture's creator page during a live turn and runs only once the turn ends. The inbox routine files exactly one draft card per new reply.

#### Phase 2, as built (2026-11-01, [ADR 0019](../../adr/0019-routines-are-the-daemons-only-background-host.md))

Owner's design answers (2026-11-01):
- Code reads a page and one tool-less model call extracts what it found.
- One card per message, with a recipe that finds each control again when it is signed.
- Twin setup screens in this phase.
- The routines strip on the front page.
- An outreach routine.

- **The host.**
  - `routines/host.py` is the daemon's only background host. It ticks every 30 s while the app runs.
  - One admission decision records `paused`, `running`, `live_turn` (chat turns only: `busy.live`) and `no_engine` as named skips, each written once.
  - A routine is due a cadence after its last completed run. Catch-up runs once and never back-fills.
  - The ceiling is $0.25 per run (est.) and is checked before every model call. A run that reaches it ends `partial` and says so.
  - The Twins poller is folded in: each live twin has a `twin:<id>` routine.
  - A routine keeps its finds at once (creator, track, thread, stat). Anything else is a card.
- **The routines.**
  - `watch`: new uploads become tracks.
  - `inbox`: replies matched to a creator's `emails` become threads, and the twin drafts one answer when the last message is theirs.
  - `stats`: the analytics figures become stats, measured at the read time.
  - `outreach`: one drafted offer per creator of a kept track with no conversation, by mail, else bio link, else comment; at most five per run.
  - Each routine reads a page in a hidden tab of her browser, with its links (`page_links`). The page is fenced as data.
- **The twin's web channels.**
  - `mail_web`, `bio` and `comment` need no account. The voice comes from messages the person pastes, per channel.
  - Every web message waits for a signature (`web_channel`). A twin on web channels only is never sent to connect Gmail or Notion.
  - On sign:
    - A reply or new mail is sent in her browser, finding each control again by its label.
    - A comment is posted under the track.
    - A bio link opens in front of the person, who sends it.
  - A missing control stops, names the step, and leaves the card waiting.
  - Only an edited, signed message becomes an example, for its channel.
  - Until the person writes their offer, a placeholder offer fact stands in, and drafts promise nothing concrete.
- **Security.** A tool round now runs only what it was offered. Scouting found a model could name any catalog action and have it run.
- **The screens.**
  - Under the report, "What Athena does on her own" lists each routine with:
    - its last run in plain words, and the daemon's note;
    - the next run;
    - spend (est., only when priced);
    - Pause / Resume, Run now, and a fold with the last runs;
    - the "Mailbox address" or "Analytics page" field when one is missing.
  - A signed-out run points to the project's "Sign in again".
  - A twin's web channels show as "Always yours to sign", with no Auto. "Your own messages" takes a pasted message and its channel.
  - `twin_send_web` cards show their channel and editable text.
- **Verified.**
  - Gates: 989 Python tests and 602 desktop tests.
  - The live seam on the built shell (`uv run python scripts/routines_seam.py --engine claude_code`, simulated pages, 2026-11-01, n=1) passed 9 of 9 for $0.09 (est., from the ledger):
    - watch kept all 4 uploads;
    - asked during a live chat turn, it skipped `live_turn`, then kept exactly the new upload;
    - inbox kept both creators' threads and drafted one reply each;
    - a second inbox run filed nothing, and a new reply filed exactly one more card;
    - stats kept 3 figures measured now;
    - a signed reply went out once through her browser, as the simulated mailbox's journal showed.
  - **Before the `page_links` fix the same seam passed 3 of 9.** Page text carries no link addresses, so watch kept no upload and the reply recipe opened a guessed address. No unit test could see it, because the stand-in shell's text included addresses.
- **Known gaps:**
  - A run does not count the pages it read, so a partial watch says "4 creators to read, found 0" rather than "read 1 of 4".
  - A pasted sample carries its channel only in its words.
  - The daemon's development CORS origin is fixed to port 1420.
  - The mailbox site is recognised by its address or name.
  - The wheel's line is cut at 200 characters.
  - A draft for a creator who asks a concrete question (their plan) stays vague until the owner writes the offer.
  - Proton's and Studio's real pages are the end-to-end run's first unknowns.

### Phase 3 - Gravitone and the release

ADR: *Peer apps over MCP, with a policy as the gate.* Plus gravitone-gcloud's own change. Gaps: G16, G17, G18, G21.

| WP | What | Files | Acceptance |
|---|---|---|---|
| 3.0 | Gravitone's `gt_mv` family (in gravitone-gcloud) | `app/_server/mcp/mv.ts`, its registry entry, `docs/mcp.md` | `import`, `launch` (detached, `budget_usd: 0`, a still is required, otherwise refused) and `collect`. The registry test and the 240-character test pass. `gt_job status` is confirmed end to end on a `job:run:mv.*` job |
| 3.1 | The contract and the MCP client | `contracts.py`, `contract.ts`, `peers_mcp/*`, `mcp.json` handling | The client is ported. Peer tools are listed as `<id>__<tool>`, and the class comes from annotations. A key in `mcp.json` other than `{id, url, token_env}` is refused. The 20 s timeout is tested |
| 3.2 | The render routine | `routines/render.py`, `renders.py` | It stages the folder. It calls `gt_mv.launch` only after `may_render` passes and within the ceiling, keeps a `render` record, and reads `gt_job status` on a later cycle; the turn never waits. Once the job is done it collects the outputs into `files` and moves the render to `rendered`. A refusal writes its reasons to the `render` record |
| 3.3 | The release and the upload card | `releases.py`, `browser/actions.py`, `CardView` | A `release` record (title, original track URL, creator channel URL, genre, credits line) renders the description. The upload card shows the attribution and the agreement thread as evidence. The draft is private, synthetic media is declared, and a Public control is refused |

Phase 3's live check: a kept, agreed fixture track with a file renders on the real Gravitone with no card. A track missing any one condition is refused with its reason. The upload reaches the fixture studio as a private draft.

### Phase 4 - the business branch on the stage

ADR: amends 0007 (and 0010, for a third rubric). Gap: G1.

| WP | What | Files | Acceptance |
|---|---|---|---|
| 4.0 | The contract | `contracts.py`, `contract.ts` | `BUSINESS_RUBRIC` slots: the seven chore slots plus `routines`, `records`, `voices` and `report`. The sketch node kinds for each |
| 4.1 | The rubric and writing the Project | `drafts/rubric.py`, `drafts/save.py` | Coverage for the new slots is computed from the sketch. At the keep, the agreed sketch writes the Project's routines (paused until access ends), its record kinds, a Twin with the `mail_web`, `bio` and `comment` channels, and a first report spec |
| 4.2 | The stage's views | `main/stage/*` | Both views (Drawing, Orbit) draw the four new slots. The `voices` slot opens Twins' setup for the business Twin and comes back. The access step covers YouTube, Studio and Proton. The hand-off card lands on the first report |
| 4.3 | The staged need and the seam | `scripts/stage_seam.py`, `stage_fixture.py` | The music channel is the second staged need. The seam walks it from describe to keep and the first report on Claude Code, with no page scroll, no console error and no banned word, and records the cost from the ledger (est.) |

### Where we stopped (2026-11-01)

**Built and on `main`:**
- Phase 1 (through f8a28b8).
- Phase 2 (through 8b6d9c9).

Each phase has its "as built" section above, with its measured seam.

**Next, in order:**
1. **Phase 3 - Gravitone and the release.** Start with WP 3.0 in gravitone-gcloud: the `gt_mv` family (`import`, `launch` with `--still` and `budget_usd: 0`, `collect`) under its MCP rules and its 240-character test, and confirm `gt_job status` on a `job:run:mv.*` job. Then:
   - the MCP client ported from athena-portable into `src/athena/peers_mcp/`;
   - the render routine, gated by `may_render` and its ceiling;
   - the `release` record and the private-draft upload card.
2. **Phase 4 - the business branch on the stage.** `BUSINESS_RUBRIC`, writing the Project (kinds, routines, the Twin on web channels, the first report), and the music channel as the second staged need.
3. **The live end-to-end run** (the parked spark `youtube-live-e2e`), on the new business YouTube channel and Proton mailbox.

**Follow-ups found while building, each small:**
- **A routine run does not count the pages it read.** A partial watch says "4 creators to read, found 0". Add `read` to `RoutineRun`.
- **A pasted sample carries its channel only in its words.** Add `channel` to `Sample`.
- **Development CORS is fixed to port 1420.** An environment variable for extra development origins would fix it.
- **The mailbox site is recognised by "mail" or "proton" in its address or name.** Phase 4's onboarding should set the channel's compose page.
- **The drop reasons of a report composition are not stored.** Add a `reasons` column to `reports`.
- **The simulated engine cannot compose a report.** It should echo the current spec.
- **`RecordPutBody` has no `key` for a thread.**
- **A verdict does not refresh "Latest tracks" until the next read.**
- **The wheel's line is cut at 200 characters.** A clipboard hand would carry the whole draft.

**Waiting on the owner:**
- The partnership offer: the Twin drafts from a placeholder and promises nothing concrete until then.
- The genre list.
- The new business YouTube channel and Proton mailbox, for the end-to-end run.

### After Phase 4: the live end-to-end run

The parked spark `youtube-live-e2e` resumes. A guided runner on the built shell walks the business from describe to a private draft in Studio, using the new business YouTube channel and Proton mailbox. It stops at the gates only the owner can pass: signing in to each site, solving a captcha, signing a card. It also scores the UX at every step.

### Risks this plan adds

- **Proton's web page is a single-page app over encrypted mail.** Reading needs the decrypted page text after sign-in. The inbox routine is built on a fixture first, and the real page is the end-to-end run's first unknown.
- **Folding the poller changes Twins' timing.** A mission can now wait behind a long live turn. The Twins overview's counts are compared before and after.
- **`gt_job` on music-video jobs is unconfirmed.** 3.0 confirms it first. If it fails, `gt_mv` gains a `status` operation.
- **A still image is plainer than Leonardo's looks.** The channel's visual quality is judged at the end-to-end run, and a spend path stays a later decision.

## Open for the owner

- The partnership offer itself: what you give, what you ask in return, and the first message. The Twin starts from your words.
- The genres you will use in verdicts. A short closed list keeps the report's counts meaningful.
- ~~Personal or new accounts~~: new, clean business accounts (answered 2026-10-31).
