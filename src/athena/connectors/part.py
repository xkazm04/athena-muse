"""The daemon's connected accounts: the vault and its services, worded for the screen (ADR 0008).

This is the `connectors` part on `Daemon`. The routes call it for the contract shapes
(`ConnectionList`, `Connection`, `ConnectFlow`); the twins package calls it for the services (Gmail
reads and sends, Notion pages) and for the writes switch. Every sentence a surface can see is
written here in plain words, from the vault's record and never from a value: a `Connection` has no
field that could hold a credential.

The vault lives under `<data_dir>/connectors/`. A daemon with no data dir (tests) keeps nothing on
disk and reaches nothing: its vault holds records and credentials in memory, its transport refuses
every call and it opens no browser, so a test must hand in a fake provider to connect anything.
"""

from __future__ import annotations

import typing
from collections.abc import Mapping
from pathlib import Path

from athena.connectors.oauth import OAuthFlow
from athena.connectors.service import Service, services_for
from athena.connectors.vault import (
    CodeRefused,
    ConnectionRecord,
    CredentialRefused,
    NoAnswer,
    NoSeal,
    Vault,
    VaultError,
)
from athena.contracts import (
    ChannelKind,
    ChannelStatus,
    ConnectBody,
    ConnectFlow,
    Connection,
    ConnectionList,
    ConnectState,
)
from athena.errors import ApiError

KINDS: tuple[ChannelKind, ...] = typing.get_args(ChannelKind)
SECRET_MAX = 512  # a pasted key, a client id or a client secret

PHASES: dict[str, ConnectState] = {
    "awaiting_consent": "waiting",
    "exchanging": "exchanging",
    "done": "done",
    "failed": "failed",
}

NO_SEAL = "This computer has no safe place to keep a sign-in, so nothing was connected."
NO_CLIENT = "Paste the client id and the client secret of your own Google client first."


def _offline(
    method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float
) -> tuple[int, bytes]:
    raise VaultError("a daemon with no data dir reaches no service")


def _no_browser(url: str) -> bool:
    return False


class Connectors:
    def __init__(self, vault: Vault) -> None:
        self.vault = vault
        self.services: dict[str, Service] = services_for(vault)

    @classmethod
    def open(cls, data_dir: Path | None) -> Connectors:
        if data_dir is None:
            return cls(Vault(None, transport=_offline, open_browser=_no_browser))
        return cls(Vault(data_dir / "connectors"))

    def service(self, kind: ChannelKind) -> Service:
        return self.services[kind]

    def close(self) -> None:
        self.vault.close()

    # -- what a surface sees ------------------------------------------------------------------------

    def connections(self) -> ConnectionList:
        return {"connections": [self.connection(kind) for kind in KINDS]}

    def connection(self, kind: ChannelKind) -> Connection:
        rec = self.vault.record(kind)
        out: Connection = {"kind": kind, "status": _status(rec), "writes": rec.writes_enabled}
        if rec.status != "disconnected":
            if rec.identity:
                out["account"] = rec.identity
            checked = max(rec.health_at, rec.attempt_at)
            if checked:
                out["last_checked"] = checked
        problem = self._problem(kind, rec)
        if problem:
            out["problem"] = problem
        guide = self.vault.spec(kind).auth.guide
        if rec.status != "connected" and guide:
            out["guide"] = guide
        return out

    def _problem(self, kind: ChannelKind, rec: ConnectionRecord) -> str:
        label = self.vault.spec(kind).label
        if self.vault.records_notice:
            return self.vault.records_notice
        if not self.vault.seal_kind:
            return NO_SEAL
        if rec.status == "needs_reauth":
            if kind == "gmail":
                return "Google asked you to sign in again."
            return f"{label} needs to be connected again."
        if rec.status != "connected":
            return ""
        if rec.health == "broken":
            if kind == "notion":
                return "Notion stopped accepting the key at the last check. Paste a new one."
            return f"{label} turned Athena away at the last check."
        if rec.attempt_detail:
            return f"The last check could not reach {label}. It is still connected."
        if rec.notice:
            return (
                f"Connected as {rec.identity or 'an account the service did not name'}. Writing was "
                "turned off, because it had been allowed for another account."
            )
        return ""

    # -- connecting ---------------------------------------------------------------------------------

    def connect(self, kind: ChannelKind, body: ConnectBody) -> ConnectFlow:
        """Gmail starts Google's sign-in in the browser and answers `waiting`; Notion checks the key
        at once and answers `done` or `failed`. A body that cannot be used is a 400."""
        pasted = (body.get("client_id", ""), body.get("client_secret", ""), body.get("key", ""))
        if any(len(value) > SECRET_MAX for value in pasted):
            raise ApiError("bad_request", "That is too long to be what was asked for; check what you pasted.")
        if kind == "notion":
            return self._connect_key(body)
        return self._connect_google(body)

    def _connect_key(self, body: ConnectBody) -> ConnectFlow:
        if "client_id" in body or "client_secret" in body:
            raise ApiError("bad_request", "Notion connects with a key: paste the key, not a Google client.")
        key = body.get("key", "").strip()
        if not key:
            raise ApiError("bad_request", "Paste your Notion key.")
        try:
            record = self.vault.connect_token("notion", key)
        except CredentialRefused:
            return _failed("Notion did not accept that key. Check that you copied all of it.")
        except NoSeal:
            return _failed(NO_SEAL)
        except VaultError:
            return _failed("Notion could not be reached. Check the internet connection and try again.")
        return _done(record.identity)

    def _connect_google(self, body: ConnectBody) -> ConnectFlow:
        if "key" in body:
            raise ApiError("bad_request", "Gmail connects by signing in with Google, not with a key.")
        client_id, secret = body.get("client_id", "").strip(), body.get("client_secret", "").strip()
        if bool(client_id) != bool(secret):
            raise ApiError("bad_request", "Paste both the client id and the client secret.")
        if not client_id and not self.vault.client_kept("gmail"):
            raise ApiError("bad_request", NO_CLIENT)
        try:
            flow = self.vault.connect_oauth(
                "gmail", client_id=client_id, client_secret=secret, reuse_client=not client_id
            )
        except NoSeal:
            return _failed(NO_SEAL)
        except VaultError:
            raise ApiError("bad_request", NO_CLIENT) from None
        return self._flow_view(flow)

    def flow(self, kind: ChannelKind) -> ConnectFlow:
        """Where Google's sign-in stands. A Notion key is checked inside its connect, so it is idle."""
        flow = self.vault.flows.for_connector(kind)
        return self._flow_view(flow) if flow is not None else {"state": "idle"}

    def _flow_view(self, flow: OAuthFlow) -> ConnectFlow:
        state = PHASES.get(flow.phase, "failed")
        if state == "waiting":
            return {
                "state": state,
                "detail": "Finish signing in with Google in your browser.",
                "url": flow.authorize_url,
            }
        if state == "exchanging":
            return {"state": state, "detail": "Google said yes. Checking the account."}
        if state == "done":
            return _done(self.vault.record(flow.connector_id).identity)
        return _failed(_google_failure(flow))

    # -- the acts on a connection -------------------------------------------------------------------

    def disconnect(self, kind: ChannelKind) -> Connection:
        """Tells the service to forget the permission when it can, destroys every sealed value and
        forgets the sign-in in progress. The writes switch is the person's and is kept."""
        self.vault.flows.forget(kind, "disconnected")
        try:
            self.vault.disconnect(kind)
        except VaultError as exc:
            raise ApiError("bad_request", f"It could not be disconnected: {exc}.") from None
        return self.connection(kind)

    def probe(self, kind: ChannelKind) -> Connection:
        try:
            self.vault.probe(kind)
        except VaultError:
            raise ApiError("bad_request", "The saved sign-in could not be read on this computer.") from None
        return self.connection(kind)

    def set_writes(self, kind: ChannelKind, on: bool) -> Connection:
        """The writes switch. Off on every new connection; the twins package turns it on when a twin
        needs to send or write (ADR 0008)."""
        self.vault.set_writes(kind, on)
        return self.connection(kind)


def _status(rec: ConnectionRecord) -> ChannelStatus:
    if rec.status == "connected":
        return "connected"
    return "needs_sign_in" if rec.status == "needs_reauth" else "disconnected"


def _done(identity: str) -> ConnectFlow:
    return {"state": "done", "detail": f"Connected as {identity}." if identity else "Connected."}


def _failed(detail: str) -> ConnectFlow:
    return {"state": "failed", "detail": detail}


def _google_failure(flow: OAuthFlow) -> str:
    """A failed sign-in in plain words, by what failed: the exchange's own error when it raised one,
    else the flow's own word (a refusal on Google's page, a page left unanswered, a newer sign-in)."""
    error = flow.error
    if isinstance(error, CodeRefused):
        return "Google did not accept the sign-in. Check the client id and secret, then try again."
    if isinstance(error, CredentialRefused):
        return (
            "Google signed you in, but Gmail would not let Athena in. Check that Gmail is on in your project."
        )
    if isinstance(error, NoSeal):
        return NO_SEAL
    if isinstance(error, NoAnswer):
        return "Google did not answer in time. Try again."
    if isinstance(error, VaultError):
        return "Google could not be reached. Check the internet connection and try again."
    detail = flow.detail
    if "access_denied" in detail:
        return "You said no on Google's page, so nothing was connected."
    if "not answered in time" in detail:
        return "Google's page was not answered in time. Try again."
    if "newer flow" in detail:
        return "A newer sign-in took this one's place."
    if detail == "disconnected":
        return "The sign-in was stopped."
    return "Signing in with Google did not finish. Try again."
