# Demo scenario - "One small business, handed to Athena"

The submission film's scenario: what the viewer sees, what is said, what is real and what is
simulated, and how to stage and record it. The script the film kit reads is
`film/film.json` (kept locally, not in git); this page is its human version and wins where they differ
(update both in one commit).

Judging weights it is written for ([rules](rules.md)): Impact 30%, Use of Meta AI tooling 25%,
Technical depth 20%, Demo 25%. Target length under **3:00** (hard cap 2:59 in `film.json` `maxMs`; re-check
the host's limit before rendering).

## The idea

The film speaks to someone who has never heard of Athena. It opens on one sentence - an AI assistant
that does your work for you, instead of only talking about it - and three promises a chatbot can't
make:

1. She automates any task you do in a browser or an app.
2. Her Twin answers your messages in your own voice.
3. One project runs across all your computers.

Then it proves each one by following **one person and one business**, Alex and a small music
channel, and closes on scope (any need, any business) and on Muse. Every chapter opener is a page
turning, so the film looks like the product.

- **Words:** what a first-time viewer understands. No mechanism words on the voice track or on
  screen titles: no "cards", "gate", "ledger", "pencil and ink", connector or product names other
  than Meta's.
- **The person:** Alex, who runs *Low Tide Visuals*, a small channel that makes music videos for
  good tracks by creators nobody has heard of (the business channel concept). Example data.
- **The promise the film keeps:** she does the work, nothing that costs money or can't be undone
  happens without one click from you, and every cost is on record.

## What is real, simulated or added (the boundary, said on screen)

| Layer | In the film |
|---|---|
| Real | The built desktop app and her window, the daemon, the engine's live answers, the sketch, the cards, the gate (a signed card runs once), the test run's score, the ledger rows, Settings, the Devices constellation. |
| Live Meta model | Every live turn runs on **Muse Spark** (`muse-spark-1.3`): the Muse API with a key, else the Muse Code CLI on the same model (see the key status under chapter 1). The bar's lamp names the engine in every shot. |
| Simulated (labelled "simulated") | The music channel's records, stats and routines (`scripts/business_fixture.py`, `scripts/routines_fixture.py`); Gmail and Notion behind Twins (the in-process fakes of `scripts/twin_seam.py`); the chore's practice apps (invented by her, by design). |
| Staged (labelled "two Athenas on one PC") | Devices chapter: the second computer is a second daemon on loopback, as in `scripts/apps_seam.py`, unless the owner's two-PC run has happened by recording day; then film that and drop the label. |
| Added by the film | Chapter leaves, captions, the parity board. Every figure on it is from [chore-onboarding.md](../features/chore-onboarding.md) (run 4, 2026-11-02) or from the take's own `record`. |

No key, token, address, QR payload or account id is ever in frame: the Muse key is pasted from the
clipboard with the field masked; the phone QR beat is blurred by the capture (`ZoomToRect` on the
ring and code, not the QR).

## Chapters and beats

From `film.json` (23 beats, 2:32 measured). The narration is written for a first-time viewer around three promises: she automates any task in a browser or an app, her Twin answers for you, and one project runs across your computers. No mechanism words. The take (`film/capture.py`, 2026-11-04): the chore
chapter ran live on Muse Code (muse-spark-1.3) and its test run found 4 of 4 with no false claim;
everything around the channel is seeded by stand-ins and badged on screen.

### 0. Open - what Athena is

| Beat | Picture | Line |
|---|---|---|
| `cold` | The desktop dashboard and the phone page side by side: what waits on Alex, on both screens. | This is Athena: an AI assistant that does your work for you, instead of only talking about it. |
| `title` | Leaf turns: **Athena on Muse** - *a private companion that does the work, not a chat window.* | Here is how. |
| `what` | The landing: her seal, what waits on you, the five places; three badges in turn: keeps the work, runs the errand, waits for your signature. | She does three things a chatbot can't. She automates any task you do in a browser or an app. Her Twin answers your messages in your own voice. And one project can run across all your computers. You approve anything that matters. |

### 1. Set her up

| Beat | Picture | Line |
|---|---|---|
| `setup-key` | First run's Connect Muse step, "Continue without a key", then Settings > Engine with Muse Code (muse-spark-1.3); the lamp names it. No probe is faked. | Setup takes a minute. Athena runs on Meta's Muse, and the screen always shows which model is working. |
| `setup-engine` | The Settings overview: engine, look, accounts, data, devices. | Everything about her lives in one place, on your own computer. |
| `setup-project` | The projects list, then into the music channel and its brief. | Your work is organized into projects. Each one remembers its own context, and keeps it to itself. |

> **Key status (2026-11-04):** no Muse API key on this machine, so the first launch shows Muse Code
> on `muse-spark-1.3` (the Muse API has never been called from this repo). With a key, the beat
> can show the key paste and live probe instead; re-narrate `setup-key`.

### 2. Hand over a chore - the centrepiece

| Beat | Picture | Line |
|---|---|---|
| `chore-describe` | Alex types the need, live: "Every Friday, check the creators I follow for new Suno tracks and line up the ones worth a video, for me to judge." | Let's automate something. Alex runs a small music channel, and describes a weekly task in plain words. |
| `chore-sketch` | Her first live sketch (Suno, the steps, the signature point, the output) and her question. Badge: live on Muse Code. | Athena asks a few questions and draws the plan as they talk: the sites she will use, the steps, and what Alex gets back. |
| `chore-ink` | Her one pencil guess is inked; Alex answers her question ("Creator pages") in ink. | Alex confirms what is right. Nothing is assumed. |
| `chore-preview` | Five expected cards; Alex marks yes, yes, no and adds "Never publish a video without my yes". | Before anything goes live, she shows exactly what she would do, and Alex says yes or no to each step. |
| `chore-test` | "She found 4 of the 4 you expected"; hero `TestRun` on the right: a ring to 4 / 4, false claims 0, cards Alex said no to filed 0, turns, time, "Exceeds the bar", live on muse-spark-1.3 (all from the take's record). | Then she practices on a safe copy, and is graded against Alex's own answers. Four out of four. |
| `chore-keep` | "This is it" > saved: the hand-off card for the new project (this chore needs no real site, so there is no sign-in step). | Alex saves it. From now on, it runs every Friday. |

### 3. Inside the project

| Beat | Picture | Line |
|---|---|---|
| `project-work` | The channel's report, scrolling to Apps: Gravitone's tools marked "on its own" / "asks you first". | Each project gets its own dashboard, built by Athena, and connects to the apps it needs. |
| `project-sign` | Her whole window, then a gentle zoom onto the render card as Alex signs; "Signed, ran once". | Alex asks for a music video. Anything that costs money or can't be undone waits for one click of approval. |

### 4. A twin that writes for Alex

| Beat | Picture | Line |
|---|---|---|
| `twin-passport` | Twins: the Client desk twin's voice page ("How it sounds"). | Then there is communication. Alex's Twin learns how Alex writes, and answers messages in that voice. |
| `twin-rehearse` | The twin's document: its missions and the drafts waiting. | It works toward a goal in every conversation, and keeps each reply in view. |
| `twin-hold` | A held draft: "Held: risk list", money asked. | When it isn't sure, or money comes up, it hands the conversation back to Alex. |

### 5. Two computers, one Athena

| Beat | Picture | Line |
|---|---|---|
| `devices-sky` | Settings > Devices: the constellation, Studio-PC online, a laptop asking to join; Studio-PC's drawer opens. Badge: staged, two Athenas on one PC. | Video rendering is heavy, so Alex connects a second computer. Athena sees both machines, and what each one can handle. |
| `devices-split` | The project's Apps: Gravitone with its "on Studio-PC" copy. | Now one project runs on both. The studio PC does the heavy lifting, and Alex still approves from here. |

### 6. Any need, any business

| Beat | Picture | Line |
|---|---|---|
| `any` | The chores shelf: the four library chores (invented cases) and the Friday chore just kept ("found 4 of 4, Muse Code"). | The music channel is just one example. An insurance appeal, a home renovation, a monthly bill: if you can describe it, Athena can learn it, test it, and run it for you. |

### 7. Why Muse

| Beat | Picture | Line |
|---|---|---|
| `proof-parity` | Hero `ParityBoard`: ten onboarding cases graded blind. Muse Code on muse-spark-1.3: 10 of 10, 3.90 / 5, slowest 21 s. Sonnet: 10 of 10, 4.62, slowest 79 s. | She thinks with Meta's Muse. We tested it against a leading model on ten real setups, graded blind. Muse completed all ten, and its slowest answer came almost four times sooner. |
| `proof-arch` | Hero `OneGate`: four engines, one gate, one ledger. | And whichever model she uses, the rules stay the same: nothing important happens without you, and every cost is on record. |

### 8. Close

| Beat | Picture | Line |
|---|---|---|
| `end` | Her window at rest, the bookmark gone; end card. | Athena. An assistant that does the work, speaks for you, and runs across your computers. Built on Muse. |

## Staging, before the take

1. **Machine.** Notifications off, a clean desktop, 1920x1080 at 100% scale, the app built
   (`pnpm -C apps/desktop app` debug build with `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9222`, as athena-portable's capture did).
2. **Data folder.** A fresh one per take. Seed the channel with
   `uv run python scripts/business_fixture.py <data>` and the routines with the routines fixture; the
   twins with the twin fixture's flow (fakes on). The first-run beats use a second, empty data
   folder (the wizard flag lives in the store).
3. **Engine.** Settings > Engine = Muse (key) or Muse Code with `--model muse-spark-1.3`. Run the
   chore chapter once off camera the same morning: it is live, and writing can take minutes (it is a
   background job; the capture cuts between `chore-ink` and `chore-preview`).
4. **The need.** Use the line above word for word in rehearsal and take; if her questions differ,
   the narration still holds because it names the steps, not her words.
5. **Gravitone** running locally with its agent door (`scripts/apps_seam.py` documents the setup),
   and for chapter 5 the second daemon (`apps_seam.py` B role) or the real studio PC.
6. **Pre-flight** ([submission checklist](submission-checklist.md#video-pre-flight)): no key on
   screen, simulated parts labelled, costs labelled est., every figure traceable.

## Recording

The cut is a command, with the demo-film kit used by athena-portable (`ai-registry/skills/demo-film`).
Reused from there: the narrator voice (ElevenLabs, the same voice id and settings), the
voice-first method (narrate and measure before recording), the CDP-driven capture with per-beat
sync marks, the check and render steps. Not reused: the scenario, the plates' look and its heroes.
The steps are in `film/README.md` (local).

Visual grammar for this film, so it does not read as athena-portable's:

- **Dark Loop Tide**, not a light paper look: `#060a17` ground, `#4aa3ff` her blue, `#f472b6` the
  person's pink. Chapter titles in a book serif, body in Outfit (the app's face).
- **Leaves, not slams.** Chapter openers are a bespoke `Leaf` hero (a page turning onto the chapter
  title, the way The Spread turns), instead of `TitleSlam` / `KineticClaim`.
- **Footage leads.** Rendered at the `sandwich` balance by default (footage framed in a device,
  ~30% motion); captions as `LowerThird` and `Callout` only where a word on screen needs pointing at;
  `ZoomToRect` for her window and the cards.
- **Bespoke heroes** in `film/local/`: `Leaf` (chapter openers), `TestRun` (the test run's figures
  beside its footage), `ParityBoard` (the blind grades as two facing pages), `OneGate` (engines into
  one gate and one ledger), and `Badge` (the corner label on simulated or staged beats).
- **Music**: one bed, two cues (calm under chapters 0-3, lifting under 4-5, resolving at the end),
  ducked under the voice.
