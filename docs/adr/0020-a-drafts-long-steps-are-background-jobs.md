# 0020 - A draft's long steps are background jobs

Status: accepted
Date: 2026-11-02

## Context

Writing a chore, previewing its cards and the test run are the slow steps of chore onboarding
([ADR 0007](0007-a-chore-is-written-in-conversation-and-tested-against-the-users-expectations.md)). Writing ran inside the
HTTP stream: the route pulled the step's generator one line at a time. The parity runs
([feature doc, Measured](../features/chore-onboarding.md#measured)) found three ways this lost work:

- A closed window cut writing off at the next line it sent. A repair round never ran.
- Every CLI call stopped at 300 s. Muse's writing hit the limit once (314 s).
- Sonnet's writing answer could not be read twice, and the raw answer was lost both times.

The owner's doctrine: writing and other heavy steps run as background threads, and the main thread
stays responsive and tracks their status. Writing has no time limit. The person can leave and come
back.

## Decision

- **A job per draft.** `POST /drafts/{id}/write`, `/preview` and `/rehearse` check the step as before.
  Each then starts a job on a daemon thread (`drafts/jobs.py`, one `Jobs` per daemon) and answers its
  follow stream.
  - The job holds the Project's turn slot for its life, as the steps did before.
  - A POST while the job runs answers 409 `space_busy`.
  - The test run's own worker thread is now the job's thread.
- **Followable.** The job keeps its events in memory. `GET /drafts/{id}/job?after=n` follows it from
  any index, from any window.
  - Every stream opens with a `job` snapshot and ends after the terminal event.
  - The terminal event goes out only after the step has released its slot and the end is stored, so
    a window can start the next step straight away.
  - A client that leaves changes nothing.
- **Kept and told.** `Draft.job` is stored at the start and at the end. A `draft_job` app event is
  published both times. At the end, her window shows one line in the draft's Project: the next thing
  to do, or `I stopped: <reason>`. `SpaceSummary.draft` badges a Project's open draft.
- **Stoppable.** `POST /drafts/{id}/job/stop` sets the job's cancel event. The CLI runner kills the
  model's whole process tree (`taskkill /T` on Windows), and the job ends `stopped`. Each step fails
  the way it fails today: a write goes back to `shape`, a preview stays at `preview`, a test run stays
  at `rehearse`.
  - The Muse API engine runs over HTTP and its call cannot be killed. After 5 s the job is marked
    `stopped` anyway. The answer that arrives later is dropped, because `call_model` checks for a Stop
    after every call. The Project stays busy until that call returns.
- **No limit on writing.** Each model call reads `CallLimits(timeout_s, cancel)` from a context
  variable set on the job's thread. Writing runs with `timeout_s=None`. The preview and the test run
  keep the 300 s default. A caller that never sets limits (chat, twins, the bench) gets that default,
  with no Stop.
- **Nothing lost.** Every unusable writing answer is kept as `failed-<n>.txt` in the draft's folder,
  the newest 3. A fenced JSON snippet that lacks the expected key no longer hides the real answer
  written outside the fence.
- **A restart.** No thread survives a restart. A stored job still `running` at daemon start is marked
  `stopped` with the reason "The app closed while she was working.", and an interrupted write goes back
  to `shape`. After a restart, a follow answers the stored snapshot alone.

Rejected alternatives:
- **Keep streaming in the request and just raise the cap.** A closed window still cuts writing off,
  and any cap is wrong for some answer.
- **A long fixed cap for writing (say 15 min).** This fails the doctrine and still loses the rare long
  answer. Stop is how a person ends a write that takes too long.
- **Routines' host ([ADR 0019](0019-routines-are-the-daemons-only-background-host.md)).** That host is
  for recurring, unattended work under a spend ceiling. A draft job runs once, a person starts it, and
  the person watches it. It needs no cadence or admission policy beyond the Project's turn slot.

## Consequences

- A window can close in the middle of a write, and the chore is written all the same. A test runs
  this against a real loopback server (`tests/test_drafts_jobs_window.py`). Before this change, the
  draft stayed at `author`.
- `POST /preview` changes from JSON to the job stream. The wire mirror and the client follow the
  contract in `contracts.py` (the job-stream protocol comment).
- Job events live only in memory until the daemon closes, so a follow after a restart shows the state
  but not the events.
- Draft writes are still whole-row `put`s. A notes `PUT` that lands in the instant between another
  thread's read and its write can be lost. In practice this window is microseconds.
