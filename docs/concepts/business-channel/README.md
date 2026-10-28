# A business run through Athena - the AI-music channel, and the gaps it finds

Status: **designed, not built** (2026-10-28). A plan and a gap map. Nothing here is built until [Chore onboarding v2](../chore-onboarding-v2/README.md) has shipped. The phases below then run in order.

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

## Open for the owner

- The partnership offer itself: what you give, what you ask in return, and the first message. The Twin starts from your words.
- The genres you will use in verdicts. A short closed list keeps the report's counts meaningful.
- Whether the business uses your personal channel and mailbox, or new ones made for it.
