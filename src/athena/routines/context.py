"""The seam between the host (WP2.1) and the routine kinds (WP2.2).

A kind is `def run(ctx: RunContext) -> None`. It raises `Skip` when it cannot start (no browser, signed
out, nothing to do, no twin), `Partial` when it stops part-way (a page it could not read), and lets
`CeilingReached` from `extract` end the run; the host records each as the run's outcome. It counts
what it covered on `ctx` (`found`, `of`, `kept`, `cards`) and may leave one plain-words `note`.

- `read` opens a page in a hidden tab of her browser with no turn (as a site's look does), decides
  signed-out with the sites' own table, reads the page's text (every part of a long page, up to
  READ_PARTS_MAX) and closes the tab.
- `extract` is one tool-less model call on surface `routine` with one ledger row. The ceiling is
  checked BEFORE each call: when what the run has spent leaves no room, CeilingReached. A call the
  engine gives no price for counts as a tenth of the ceiling, so an unpriced engine stops after ten.
  It answers the first JSON object in the answer that has `key` (the whole object, as `_ask` does).
- `put` goes through the records' door (`records.actions.put_as`, by `routine`): creator, track,
  thread and stat are kept at once (ROUTINE_FINDS), any other kind files a card.
- `draft` asks the project's twin for a message on a web channel (`twins.web.draft`), filed as a card.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from athena.contracts import ChannelKind, RecordItem, RecordKind, Routine, SkipReason

if TYPE_CHECKING:
    from athena.app import Daemon
    from athena.engine import Engine

#: The most parts of one long page a read follows (each part is one packet of her browser's).
READ_PARTS_MAX = 8
#: An unpriced call counts as this share of the ceiling.
UNPRICED_SHARE = 10
_EPS = 1e-9


class Skip(Exception):
    def __init__(self, reason: SkipReason, note: str = "") -> None:
        super().__init__(note or reason)
        self.reason: SkipReason = reason
        self.note = note


class Partial(Exception):
    """Stopped part-way; the message says what was covered and why it stopped."""


class CeilingReached(Exception):
    """The next model call would pass the run's ceiling."""


@dataclass(frozen=True)
class PageText:
    url: str  # where the hidden tab ended
    text: str  # the page's text; the caller fences it as page data
    signed_out: bool  # it ended on a sign-in page (a password field showed)


def _money(usd: float) -> str:
    return f"${usd:.2f}"


@dataclass
class RunContext:
    daemon: Daemon
    space_id: str
    routine: Routine
    found: int = 0
    of: int | None = None
    kept: int = 0
    cards: int = 0
    note: str = ""
    spent_usd: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)  # the host's own bookkeeping
    engine_of: Callable[[], Engine] | None = None  # the host's engine provider; built on first use
    unpriced: int = 0  # calls the engine gave no price for

    # --- the engine and the ceiling -----------------------------------------------------------------

    def engine(self) -> Engine:
        """The run's engine, built once. Skip("no_engine") when none can be built."""
        from athena.engine import EngineError
        from athena.errors import ApiError

        built = self.extra.get("_engine")
        if built is not None:
            return built  # type: ignore[no-any-return]
        if self.engine_of is None:
            raise Skip("no_engine", "Athena has no engine to work with.")
        try:
            built = self.engine_of()
        except EngineError as e:
            raise Skip("no_engine", e.reason) from e
        except ApiError as e:
            raise Skip("no_engine", e.reason) from e
        self.extra["_engine"] = built
        return built

    @property
    def ceiling(self) -> float:
        return float(self.routine["ceiling_usd"])

    def counted(self) -> float:
        """What the run has spent against its ceiling: its priced calls, and a tenth of the ceiling for
        each call that had no price."""
        return (self.spent_usd or 0.0) + self.unpriced * self.ceiling / UNPRICED_SHARE

    def check_ceiling(self) -> None:
        """CeilingReached when what the run has spent leaves no room for another call."""
        if self.counted() >= self.ceiling - _EPS:
            raise CeilingReached(f"It stopped at its spending limit of {_money(self.ceiling)} (est.).")

    def charge(self, cost: float | None) -> None:
        if cost is None:
            self.unpriced += 1
        else:
            self.spent_usd = (self.spent_usd or 0.0) + cost

    def ledger_mark(self) -> int:
        """The newest ledger row's id now: `charge_since` counts the rows after it."""
        rows = self.daemon.store.query("SELECT COALESCE(MAX(id), 0) AS m FROM ledger")
        return int(rows[0]["m"])

    def charge_since(self, mark: int, surfaces: tuple[str, ...] | None = None) -> None:
        """Charges the run with the ledger rows of its space written after `mark` (a twin's missions
        and a draft call the model themselves; their rows are what they spent)."""
        sql = "SELECT cost_usd FROM ledger WHERE id > ? AND space_id = ? AND ok = 1"
        params: list[Any] = [mark, self.space_id]
        if surfaces:
            sql += f" AND surface IN ({','.join('?' for _ in surfaces)})"
            params.extend(surfaces)
        for r in self.daemon.store.query(sql, tuple(params)):
            self.charge(None if r["cost_usd"] is None else float(r["cost_usd"]))

    # --- the four doors -----------------------------------------------------------------------------

    def read(self, url: str) -> PageText:
        """Open `url` in a hidden tab of her browser, read its text, close it. Raises Skip("no_browser")
        when the desktop is not running, Skip("signed_out") when it lands on a sign-in page, Partial on
        a timeout or a site the project does not keep."""
        from athena.browser import sites

        daemon = self.daemon
        origin = sites.origin_of(url)
        if not origin:
            raise Partial(f"{url[:120]} is not a web address, so it was not read.")
        host = sites.host_of(origin)
        if not daemon.relay.connected():
            raise Skip("no_browser", "Her browser is not open.")
        if not daemon.sites.trusted(self.space_id, origin):
            raise Partial(f"{host} is not one of this project's sites, so it was not read.")
        opened = daemon.relay.call("open", {"url": url, "hidden": True}, timeout=sites.OPEN_WAIT_S)
        if opened.get("reason") == "no_browser":
            raise Skip("no_browser", "Her browser is not open.")
        tab = (opened.get("tab") or {}).get("id")
        try:
            if not opened.get("ok") or not isinstance(tab, int):
                why = str(opened.get("output") or opened.get("reason") or "no answer")
                raise Partial(f"Her browser could not open {host}: {why[:160]}")
            if sites.SETTLE_S:
                time.sleep(sites.SETTLE_S)
            seen = daemon.relay.call("tab", tab=tab)
            final = str((seen.get("tab") or {}).get("url") or (opened.get("tab") or {}).get("url") or url)
            found = daemon.relay.call("page_find", {"role": "password"}, tab=tab)
            output = str(found.get("output", ""))
            password = bool(found.get("ok")) and output.strip() != "nothing matched" and "password" in output
            access, reason = sites.decide(origin, sites.Seen(True, url=final, password=password))
            if access == "signed_out":
                raise Skip("signed_out", reason)
            return PageText(final, self._text(tab, host) + self._links(tab), False)
        finally:
            if isinstance(tab, int):
                daemon.relay.call("close", tab=tab)

    def _text(self, tab: int, host: str) -> str:
        """Every part of the page's text (a long page comes in packets that name the next cursor)."""
        parts: list[str] = []
        cursor = ""
        for _ in range(READ_PARTS_MAX):
            result = self.daemon.relay.call("page_read", {"cursor": cursor} if cursor else {}, tab=tab)
            if not result.get("ok"):
                if result.get("reason") == "no_browser":
                    raise Skip("no_browser", "Her browser closed while a page was read.")
                why = str(result.get("output") or result.get("reason") or "no answer")
                if parts:
                    break
                raise Partial(f"Her browser could not read {host}: {why[:160]}")
            output = str(result.get("output", ""))
            lines = output.split("\n")
            head = lines[0] if lines else ""
            if head.startswith("cursor: cur_"):
                parts.append("\n".join(lines[1:-1]))
                cursor = head.split()[1]
                continue
            if head.startswith("chars ") and "of" in head:
                parts.append("\n".join(lines[1:-1]))
            else:
                parts.append(output)
            break
        return "\n".join(parts)

    def _links(self, tab: int) -> str:
        """The page's links (label and address): page text carries no addresses, and an upload or a
        thread is only kept with one. Empty when the page has none or the hand did not answer."""
        found = self.daemon.relay.call("page_links", {}, tab=tab)
        output = str(found.get("output", "")).strip()
        if not found.get("ok") or not output or output == "no links":
            return ""
        return "\n\nLinks on the page (label, then address):\n" + output

    def extract(self, system: str, user: str, key: str) -> dict[str, Any]:
        """One tool-less model call (surface `routine`, one ledger row), answered as the JSON object under
        `key`. Adds its cost to `spent_usd`; raises CeilingReached before a call when the spend so far
        leaves no room (a call with no price counts as a tenth of the ceiling)."""
        from athena.drafts.author import first_object

        self.check_ceiling()
        engine = self.engine()
        text, cost = call(
            self.daemon,
            engine,
            self.space_id,
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        self.charge(cost)
        found = first_object(text, key)
        if not isinstance(found, dict):
            raise Partial("Athena did not answer in the shape asked, so the run stopped there.")
        return found

    def put(self, kind: RecordKind, body: dict[str, Any], key: str | None = None) -> RecordItem | None:
        """Keep a record through the records' own door (records.actions), by the routine: finds at
        once with the person's track fields kept; any other kind files a card (counted in `cards`).
        Answers the record, or None when it was refused or filed. Counts `kept` when a revision was
        appended."""
        from athena.records.actions import ROUTINE_FINDS, put_as

        done = put_as(self.daemon, self.space_id, kind, body, key=key, by="routine", finds=ROUTINE_FINDS)
        if done.card is not None:
            self.cards += 1
            return None
        if done.item is None:
            self.extra["refused"] = int(self.extra.get("refused", 0)) + 1
            return None
        if done.appended:
            self.kept += 1
        return done.item

    def draft(
        self,
        channel: ChannelKind,
        creator_key: str,
        purpose: str,
        context: str,
        thread_key: str | None = None,
    ) -> str | None:
        """A message in the project's twin's voice on `channel`, filed as a `twin_send_web` card the
        person may edit (twins.web.draft). Answers the card id, or None when the project has no live
        twin (the caller then raises Skip("no_twin")). Counts `cards`."""
        from athena.twins import web

        found = self.daemon.records.latest(self.space_id, "creator", creator_key)
        to: dict[str, Any] = dict(found[0]["body"]) if found else {"channel_url": creator_key}
        self.check_ceiling()
        engine = self.engine()
        mark = self.ledger_mark()
        try:
            card = web.draft(self.daemon, engine, self.space_id, channel, to, purpose, context, thread_key)
        finally:
            self.charge_since(mark)
        if card is None:
            return None
        self.cards += 1
        return card["id"]


def call(
    daemon: Daemon, engine: Engine, space_id: str, messages: list[dict[str, Any]]
) -> tuple[str, float | None]:
    """One model call with no tools, ledgered on surface `routine`: (its text, its cost or None when the
    engine gives no price). Raises EngineError (after ledgering it) when the call fails. The drafts'
    `call_model`, answering the cost too."""
    from athena.engine import EngineError, TextDelta, Usage
    from athena.engine.prices import estimate

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
            surface="routine",
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
        if cost is None and engine.cost_estimated:
            cost = estimate(engine.model, usage.input_tokens, usage.output_tokens)
    daemon.ledger.record(
        surface="routine",
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
    return "".join(parts), cost
