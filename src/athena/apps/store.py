"""The apps of a project and of this device (ADR 0025, 0026).

Truth: website/local_page apps are the origins in ``spaces.apps`` (unchanged column, unchanged
consumers); their ``app_id`` is ``web_`` + the first 10 hex of sha1(origin). mcp_http/mcp_stdio apps,
device-level apps (space ``""``) and remote instances live in the ``apps`` and ``app_remotes`` tables,
erased with their space. A token is sealed with the connectors seal and never leaves this module
except through :meth:`Apps.token`.

- A web app's kind is derived from its host: a loopback host is a ``local_page``. Its status is what
  the project's ``sites`` row last found (signed in = ok, signed out = refused), else ``unchecked``.
- Wiring a local page through the form is its onboarding (ADR 0025, amending 0014 for loopback only):
  it writes the project's ``sites`` row, so her browser trusts it.
- Removing a web app takes its origin out of ``spaces.apps``; its ``sites`` row is left alone (a
  chore's onboarding may have written it, and only onboarding removes one).
- The project cap APPS_MAX counts web and process apps together; outside every project the cap is
  DEVICE_APPS_MAX and only process apps are wired there.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlsplit

from athena.clock import mint, now_iso
from athena.connectors.seal import SealPort, SealUnavailable, select_seal
from athena.contracts import (
    APP_LABEL_MAX,
    APP_TOOLS_MAX,
    APPS_MAX,
    DEVICE_APPS_MAX,
    App,
    AppKind,
    AppNew,
    AppRemote,
    AppStatus,
    AppTool,
    SiteAccess,
)
from athena.errors import ApiError
from athena.store import Store

if TYPE_CHECKING:
    from athena.events import Events

#: The kinds that live in the `apps` table (the web kinds live in `spaces.apps`).
PROCESS_KINDS: tuple[AppKind, ...] = ("mcp_http", "mcp_stdio")
WEB_PREFIX = "web_"
APP_PREFIX = "app_"
#: What the project's sites overview says needs a local page wired through the form.
WIRED_BY_YOU = "wired by you"
SLUG_MAX = 24
ARGV_MAX = 64  # parts of one command line
ARGV_PART_MAX = 1000
ADDRESS_MAX = 500
TOKEN_MAX = 4096
_SEAL_DIR = ("apps", "sealed")
_SITE_STATUS: dict[SiteAccess, AppStatus] = {
    "signed_in": "ok",
    "signed_out": "refused",
    "unknown": "unchecked",
}
_NOT_SLUG = re.compile(r"[^a-z0-9]+")


def _bad(reason: str) -> ApiError:
    return ApiError("bad_request", reason)


def web_id(origin: str) -> str:
    return WEB_PREFIX + hashlib.sha1(origin.encode("utf-8")).hexdigest()[:10]


def loopback(host: str | None) -> bool:
    """localhost, 127.0.0.0/8 or ::1 (brackets allowed)."""
    if not host:
        return False
    host = host.strip("[]").lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def web_kind(origin: str) -> AppKind:
    return "local_page" if loopback(urlsplit(origin).hostname) else "website"


def _host(origin: str) -> str:
    return urlsplit(origin).netloc or origin


def slugify(text: str) -> str:
    """Lowercase [a-z0-9_], never empty, never starting with a digit, at most SLUG_MAX."""
    slug = _NOT_SLUG.sub("_", text.lower()).strip("_")[:SLUG_MAX].strip("_")
    if not slug:
        return "app"
    return slug if not slug[0].isdigit() else ("app_" + slug)[:SLUG_MAX].strip("_")


def _unique(slug: str, taken: set[str]) -> str:
    if slug not in taken:
        return slug
    n = 2
    while True:
        suffix = f"_{n}"
        candidate = slug[: SLUG_MAX - len(suffix)] + suffix
        if candidate not in taken:
            return candidate
        n += 1


def _label(raw: object, fallback: str) -> str:
    if raw is None:
        text = fallback
    elif isinstance(raw, str):
        text = " ".join(raw.split()) or fallback
    else:
        raise _bad("a name for the app must be text")
    return text[:APP_LABEL_MAX]


def _command_name(argv0: str) -> str:
    name = re.split(r"[\\/]", argv0.strip())[-1]
    stem, dot, _ = name.rpartition(".")
    return stem if dot and stem else name


def forget_tokens(data_dir: object | None, app_ids: list[str]) -> None:
    """Destroys the sealed tokens of apps that are gone (a project erased). Never raises."""
    if data_dir is None or not app_ids:
        return
    try:
        seal = select_seal(Path(str(data_dir)).joinpath(*_SEAL_DIR))
    except SealUnavailable:
        return
    for app_id in app_ids:
        with suppress(Exception):
            seal.destroy(_seal_name(app_id))


def _seal_name(app_id: str) -> str:
    return f"app.{app_id}"


@dataclass(frozen=True)
class AppRow:
    """One app as the daemon uses it internally (the wire shape is :class:`~athena.contracts.App`)."""

    app_id: str
    space_id: str  # "" = device-level
    kind: AppKind
    label: str
    slug: str
    address: str  # origin | URL | argv joined by spaces
    status: AppStatus
    tools: list[AppTool] = field(default_factory=list)
    argv: list[str] | None = None
    offered: bool = False
    output_dir: str | None = None
    checked_at: str | None = None
    reason: str | None = None


def _row(r: Any) -> AppRow:
    return AppRow(
        app_id=r["app_id"],
        space_id=r["space_id"],
        kind=cast("AppKind", r["kind"]),
        label=r["label"],
        slug=r["slug"],
        address=r["address"],
        status=cast("AppStatus", r["status"]),
        tools=json.loads(r["tools"] or "[]"),
        argv=json.loads(r["argv"]) if r["argv"] else None,
        offered=bool(r["offered"]),
        output_dir=r["output_dir"] or None,
        checked_at=r["checked_at"] or None,
        reason=r["reason"] or None,
    )


def _remote(r: Any) -> AppRemote:
    out: AppRemote = {
        "peer_id": r["peer_id"],
        "device": r["device"],
        "remote_app_id": r["remote_app_id"],
        "status": cast("AppStatus", r["status"]),
        "tools": json.loads(r["tools"] or "[]"),
    }
    if r["checked_at"]:
        out["checked_at"] = r["checked_at"]
    if r["reason"]:
        out["reason"] = r["reason"]
    return out


class Apps:
    def __init__(self, store: Store, data_dir: object | None = None, events: Events | None = None) -> None:
        self.store = store
        self.data_dir = data_dir
        self.events = events  # where `app` is published; None = nowhere (a bare store in a test)
        self._seal: SealPort | None = None

    # -- reading ---------------------------------------------------------------------------------

    def _origins(self, space_id: str) -> list[str]:
        if space_id == "":
            return []
        rows = self.store.query("SELECT apps FROM spaces WHERE id = ?", (space_id,))
        return list(json.loads(rows[0]["apps"])) if rows else []

    def _table(self, space_id: str) -> list[AppRow]:
        rows = self.store.query("SELECT * FROM apps WHERE space_id = ? ORDER BY rowid", (space_id,))
        return [_row(r) for r in rows]

    def _sealed(self, space_id: str, app_id: str) -> bool:
        rows = self.store.query(
            "SELECT token_sealed FROM apps WHERE space_id = ? AND app_id = ?", (space_id, app_id)
        )
        return bool(rows and rows[0]["token_sealed"])

    def _web_rows(self, space_id: str, taken: set[str]) -> list[AppRow]:
        """The derived web apps, their slugs kept clear of `taken` (the table's), in list order."""
        out: list[AppRow] = []
        seen = set(taken)
        for origin in self._origins(space_id):
            site = self.store.query(
                "SELECT access, checked_at, reason FROM sites WHERE space_id = ? AND origin = ?",
                (space_id, origin),
            )
            slug = _unique(slugify(_host(origin)), seen)
            seen.add(slug)
            out.append(
                AppRow(
                    app_id=web_id(origin),
                    space_id=space_id,
                    kind=web_kind(origin),
                    label=_host(origin)[:APP_LABEL_MAX],
                    slug=slug,
                    address=origin,
                    status=_SITE_STATUS.get(site[0]["access"], "unchecked") if site else "unchecked",
                    checked_at=(site[0]["checked_at"] or None) if site else None,
                    reason=(site[0]["reason"] or None) if site else None,
                )
            )
        return out

    def _view(self, row: AppRow, sealed: bool, remotes: list[AppRemote]) -> App:
        out: App = {
            "app_id": row.app_id,
            "kind": row.kind,
            "label": row.label,
            "slug": row.slug,
            "address": row.address,
            "status": row.status,
            "tools": list(row.tools),
            "remotes": remotes,
            "sealed": sealed,
        }
        if row.argv is not None:
            out["argv"] = list(row.argv)
        if row.space_id == "":
            out["offered"] = row.offered
        if row.output_dir:
            out["output_dir"] = row.output_dir
        if row.checked_at:
            out["checked_at"] = row.checked_at
        if row.reason:
            out["reason"] = row.reason
        return out

    def _one(self, row: AppRow) -> App:
        if row.kind in PROCESS_KINDS:
            remotes = self.remotes(row.space_id, row.app_id) if row.space_id else []
            return self._view(row, self._sealed(row.space_id, row.app_id), remotes)
        return self._view(row, False, [])

    def views(self, space_id: str) -> list[App]:
        """Every app of the space, the derived web ones first, in the order they were added."""
        table = self._table(space_id)
        web = self._web_rows(space_id, {r.slug for r in table})
        return [self._one(r) for r in (*web, *table)]

    def rows(self, space_id: str) -> list[AppRow]:
        """The process kinds only (mcp_http, mcp_stdio): what tools are offered from."""
        return self._table(space_id)

    def get(self, space_id: str, app_id: str) -> AppRow:
        """ApiError unknown_ref when the space has no such app."""
        if app_id.startswith(WEB_PREFIX):
            table = self._table(space_id)
            for row in self._web_rows(space_id, {r.slug for r in table}):
                if row.app_id == app_id:
                    return row
        else:
            rows = self.store.query(
                "SELECT * FROM apps WHERE space_id = ? AND app_id = ?", (space_id, app_id)
            )
            if rows:
                return _row(rows[0])
        raise ApiError("unknown_ref", "that app is not one of these apps")

    def view(self, space_id: str, app_id: str) -> App:
        return self._one(self.get(space_id, app_id))

    # -- writing ---------------------------------------------------------------------------------

    def _publish(self, space_id: str, *, space_changed: bool = False) -> None:
        if self.events is None:
            return
        self.events.publish({"type": "app", "space_id": space_id})
        if space_changed:
            self.events.publish({"type": "space_changed", "space_id": space_id})

    def _space(self, space_id: str) -> None:
        if space_id and not self.store.query("SELECT 1 FROM spaces WHERE id = ?", (space_id,)):
            raise ApiError("unknown_ref", "no such project")

    def _room(self, space_id: str) -> None:
        if space_id == "":
            n = self.store.query("SELECT COUNT(*) AS n FROM apps WHERE space_id = ''")[0]["n"]
            if n >= DEVICE_APPS_MAX:
                raise _bad(f"this computer holds at most {DEVICE_APPS_MAX} apps outside the projects")
            return
        n = self.store.query("SELECT COUNT(*) AS n FROM apps WHERE space_id = ?", (space_id,))[0]["n"]
        if n + len(self._origins(space_id)) >= APPS_MAX:
            raise _bad(f"a project holds at most {APPS_MAX} apps")

    def _taken(self, space_id: str) -> set[str]:
        table = self._table(space_id)
        return {r.slug for r in table} | {r.slug for r in self._web_rows(space_id, set())}

    def add(self, space_id: str, body: AppNew) -> App:
        """Validates by kind (400 bad_request in plain words), seals the token, writes, publishes `app`."""
        if not isinstance(body, dict):
            raise _bad("send the app as an object")
        self._space(space_id)
        kind: object = body.get("kind")
        if kind == "website" or kind == "local_page":
            return self._add_web(space_id, kind, body)
        if kind == "mcp_http" or kind == "mcp_stdio":
            return self._add_process(space_id, kind, body)
        raise _bad("choose what kind of app this is")

    def _add_web(self, space_id: str, kind: AppKind, body: AppNew) -> App:
        from athena.browser.sites import Sites
        from athena.spaces import normalise_origin

        if space_id == "":
            raise _bad("a web page is wired inside a project")
        for key, why in (
            ("argv", "a web page has no command to start"),
            ("token", "a web page signs in through her browser; it takes no token"),
            ("output_dir", "a web page has no folder files are pulled from"),
            ("offered", "only an app wired outside every project can be offered to other devices"),
        ):
            if key in body:
                raise _bad(why)
        raw = body.get("address", "")
        if kind == "local_page" and isinstance(raw, str) and "://" not in raw:
            raw = "http://" + raw.strip()  # a page on this computer is typed bare, and served plain
        origin = normalise_origin(raw)
        if kind == "website" and loopback(urlsplit(origin).hostname):
            raise _bad("that is a page on this computer - choose that kind")
        if kind == "local_page" and not loopback(urlsplit(origin).hostname):
            raise _bad("a page on this computer has an address on localhost or 127.0.0.1")
        label = _label(body.get("label"), _host(origin))
        with self.store.tx() as db:
            origins = self._origins(space_id)
            if origin in origins:
                raise _bad("that address is already one of this project's apps")
            self._room(space_id)
            db.execute(
                "UPDATE spaces SET apps = ?, updated = ? WHERE id = ?",
                (json.dumps([*origins, origin]), now_iso(), space_id),
            )
            if kind == "local_page":
                Sites(self.store).add(space_id, origin, label, origin + "/", WIRED_BY_YOU)
        self._publish(space_id, space_changed=True)
        return self.view(space_id, web_id(origin))

    def _add_process(self, space_id: str, kind: AppKind, body: AppNew) -> App:
        argv: list[str] | None = None
        if kind == "mcp_http":
            if "argv" in body:
                raise _bad("an app answering at an address has no command to start")
            address = self._loopback_url(body.get("address"))
            fallback = _host(address)
        else:
            if "address" in body:
                raise _bad("a tool she starts is given as its command, not an address")
            argv = self._argv(body.get("argv"))
            address = " ".join(argv)
            fallback = _command_name(argv[0])
        offered = body.get("offered", False)
        if "offered" in body:
            if space_id != "":
                raise _bad("only an app wired outside every project can be offered to other devices")
            if not isinstance(offered, bool):
                raise _bad("offered is yes or no")
        output_dir = self._output_dir(body["output_dir"]) if "output_dir" in body else None
        token = body.get("token")
        if token is not None and (not isinstance(token, str) or not token.strip()):
            raise _bad("a token must be text")
        if isinstance(token, str) and len(token) > TOKEN_MAX:
            raise _bad("that token is too long")
        label = _label(body.get("label"), fallback)
        app_id = mint(APP_PREFIX)
        handle: str | None = None
        if isinstance(token, str):
            handle = _seal_name(app_id)
            self._seal_token(handle, token.strip())
        try:
            with self.store.tx() as db:
                self._room(space_id)
                slug = _unique(slugify(label), self._taken(space_id))
                db.execute(
                    "INSERT INTO apps(app_id, space_id, kind, label, slug, address, argv, token_sealed, "
                    "offered, output_dir, tools, status, checked_at, reason, created) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        app_id,
                        space_id,
                        kind,
                        label,
                        slug,
                        address,
                        json.dumps(argv) if argv is not None else None,
                        handle,
                        1 if offered else 0,
                        output_dir,
                        "[]",
                        "unchecked",
                        None,
                        None,
                        now_iso(),
                    ),
                )
        except BaseException:
            if handle is not None:
                self._forget(handle)
            raise
        self._publish(space_id)
        return self.view(space_id, app_id)

    @staticmethod
    def _loopback_url(raw: object) -> str:
        if not isinstance(raw, str) or not raw.strip():
            raise _bad("an app on this computer needs the address it answers at")
        text = raw.strip()
        if len(text) > ADDRESS_MAX:
            raise _bad("that address is too long")
        try:
            parts = urlsplit(text)
            _ = parts.port  # a bad port raises here
        except ValueError:
            raise _bad("that is not a web address") from None
        if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
            raise _bad("the address starts with http:// or https://")
        if parts.username is not None or parts.password is not None:
            raise _bad("the address cannot carry a user name")
        if not loopback(parts.hostname):
            raise _bad("only an app on this computer can be wired this way (localhost or 127.0.0.1)")
        return text

    @staticmethod
    def _argv(raw: object) -> list[str]:
        if not isinstance(raw, list) or not raw:
            raise _bad("a tool she starts needs its command")
        if len(raw) > ARGV_MAX:
            raise _bad(f"a command has at most {ARGV_MAX} parts")
        argv: list[str] = []
        for part in raw:
            if not isinstance(part, str):
                raise _bad("each part of the command must be text")
            if len(part) > ARGV_PART_MAX:
                raise _bad("a part of the command is too long")
            argv.append(part)
        if not argv[0].strip():
            raise _bad("a tool she starts needs its command")
        return argv

    @staticmethod
    def _output_dir(raw: object) -> str:
        if not isinstance(raw, str) or not raw.strip():
            raise _bad("the output folder must be a folder on this computer")
        path = Path(raw.strip())
        if not path.is_absolute():
            raise _bad("the output folder must be a full folder path")
        if not path.is_dir():
            raise _bad("that output folder does not exist")
        return str(path)

    def remove(self, space_id: str, app_id: str) -> None:
        row = self.get(space_id, app_id)  # unknown_ref first
        if row.kind not in PROCESS_KINDS:
            with self.store.tx() as db:
                origins = [o for o in self._origins(space_id) if o != row.address]
                db.execute(
                    "UPDATE spaces SET apps = ?, updated = ? WHERE id = ?",
                    (json.dumps(origins), now_iso(), space_id),
                )
            self._publish(space_id, space_changed=True)
            return
        sealed = self.store.query(
            "SELECT token_sealed FROM apps WHERE space_id = ? AND app_id = ?", (space_id, app_id)
        )
        with self.store.tx() as db:
            db.execute("DELETE FROM app_remotes WHERE space_id = ? AND app_id = ?", (space_id, app_id))
            db.execute("DELETE FROM apps WHERE space_id = ? AND app_id = ?", (space_id, app_id))
        if sealed and sealed[0]["token_sealed"]:
            self._forget(sealed[0]["token_sealed"])
        self._publish(space_id)

    # -- the token ---------------------------------------------------------------------------------

    def _seal_port(self) -> SealPort:
        if self._seal is not None:
            return self._seal
        if self.data_dir is None:
            raise _bad("Athena keeps nothing on disk here, so it cannot keep a token safely")
        try:
            self._seal = select_seal(Path(str(self.data_dir)).joinpath(*_SEAL_DIR))
        except SealUnavailable:
            raise _bad("this computer has no safe place to keep a token, so it was not kept") from None
        return self._seal

    def _seal_token(self, handle: str, token: str) -> None:
        try:
            self._seal_port().seal(handle, token)
        except SealUnavailable:
            raise _bad("the token could not be kept safely, so nothing was kept") from None

    def _forget(self, handle: str) -> None:
        with suppress(ApiError, SealUnavailable):
            self._seal_port().destroy(handle)

    def token(self, space_id: str, app_id: str) -> str | None:
        """The unsealed token for a call, or None."""
        rows = self.store.query(
            "SELECT token_sealed FROM apps WHERE space_id = ? AND app_id = ?", (space_id, app_id)
        )
        if not rows or not rows[0]["token_sealed"]:
            return None
        try:
            return self._seal_port().unseal(rows[0]["token_sealed"])
        except (ApiError, SealUnavailable):
            return None

    # -- what a probe found, and the instances on other devices -------------------------------------

    def set_probe(
        self, space_id: str, app_id: str, status: AppStatus, tools: list[AppTool], reason: str | None
    ) -> App:
        """Records a probe's finding (checked_at = now) and publishes `app`."""
        row = self.get(space_id, app_id)
        if row.kind not in PROCESS_KINDS:
            raise _bad("a web page's look is kept with the project's sites")
        self.store.run(
            "UPDATE apps SET status = ?, tools = ?, reason = ?, checked_at = ? "
            "WHERE space_id = ? AND app_id = ?",
            (status, json.dumps(list(tools)[:APP_TOOLS_MAX]), reason, now_iso(), space_id, app_id),
        )
        self._publish(space_id)
        return self.view(space_id, app_id)

    def remotes(self, space_id: str, app_id: str) -> list[AppRemote]:
        rows = self.store.query(
            "SELECT * FROM app_remotes WHERE space_id = ? AND app_id = ? ORDER BY rowid", (space_id, app_id)
        )
        return [_remote(r) for r in rows]

    def put_remote(self, space_id: str, app_id: str, remote: AppRemote) -> App:
        """Attach or refresh a paired device's instance of this app; publishes `app`."""
        row = self.get(space_id, app_id)
        if space_id == "":
            raise _bad("an app wired outside every project is the one other devices use")
        if row.kind not in PROCESS_KINDS:
            raise _bad("a web page has no copy on another device to attach")
        self.store.run(
            "INSERT INTO app_remotes(space_id, app_id, peer_id, device, remote_app_id, status, tools, "
            "checked_at, reason, created) VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(app_id, peer_id) DO UPDATE SET device = excluded.device, "
            "remote_app_id = excluded.remote_app_id, status = excluded.status, tools = excluded.tools, "
            "checked_at = excluded.checked_at, reason = excluded.reason",
            (
                space_id,
                app_id,
                remote["peer_id"],
                remote["device"],
                remote["remote_app_id"],
                remote["status"],
                json.dumps(list(remote["tools"])[:APP_TOOLS_MAX]),
                remote.get("checked_at") or now_iso(),
                remote.get("reason"),
                now_iso(),
            ),
        )
        self._publish(space_id)
        return self.view(space_id, app_id)

    def drop_remote(self, space_id: str, app_id: str, peer_id: str) -> None:
        n = self.store.run(
            "DELETE FROM app_remotes WHERE space_id = ? AND app_id = ? AND peer_id = ?",
            (space_id, app_id, peer_id),
        )
        if n:
            self._publish(space_id)

    def offered(self) -> list[AppRow]:
        """Device-level apps marked offered (space "")."""
        rows = self.store.query("SELECT * FROM apps WHERE space_id = '' AND offered = 1 ORDER BY rowid")
        return [_row(r) for r in rows]
