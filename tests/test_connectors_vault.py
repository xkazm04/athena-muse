"""The vault: admission by probe, the one outbound door, the switches, and no secret surface.

Ported from athena-portable's `tests/connectors/test_vault.py`; the records-file and account-switch
cases are kept whole, the catalog listener and the surface view (replaced by `Connection`) are not.
"""

from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator, Mapping
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from athena.connectors.part import Connectors
from athena.connectors.seal import FileSeal, MemorySeal
from athena.connectors.spec import load_builtin
from athena.connectors.vault import (
    CredentialRefused,
    HostRefused,
    NeedsReauth,
    NoAnswer,
    NotConnected,
    UrllibTransport,
    Vault,
    VaultError,
    redact,
)
from connectors_kit import FakeProvider, vault_over

TOKEN = "ntn_test_token_0123456789"


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def vault(tmp_path: Path, provider: FakeProvider) -> Iterator[Vault]:
    built = vault_over(tmp_path / "connectors", provider)
    try:
        yield built
    finally:
        built.close()


@pytest.fixture
def notion(vault: Vault) -> Vault:
    """The vault with Notion connected through a pasted key."""
    vault.connect_token("notion", TOKEN)
    return vault


def _vault(tmp_path: Path, provider: FakeProvider) -> Vault:
    return vault_over(tmp_path / "connectors", provider)


# -- admission ------------------------------------------------------------------------------------


def test_a_pasted_key_is_probed_before_it_is_sealed(vault: Vault, provider: FakeProvider) -> None:
    record = vault.connect_token("notion", TOKEN)
    assert record.status == "connected"
    assert record.identity == "Test User"
    assert record.health == "healthy" and record.health_at
    assert record.seal == "file"
    probe = provider.seen[0]
    assert probe.method == "GET" and probe.path == "/v1/users/me"
    assert probe.headers["Authorization"] == f"Bearer {TOKEN}"
    assert probe.headers["Notion-Version"] == "2022-06-28"
    assert vault.is_live("notion")


def test_a_refused_key_seals_nothing(tmp_path: Path) -> None:
    vault = _vault(tmp_path, FakeProvider(script=lambda *_: (401, {"message": "invalid token"})))
    with pytest.raises(CredentialRefused, match="refused the credential with 401"):
        vault.connect_token("notion", TOKEN)
    assert not vault.is_live("notion")
    assert vault.record("notion").status == "disconnected"
    assert list((tmp_path / "connectors" / "sealed").glob("*")) == []


def test_the_record_on_disk_never_carries_a_value(notion: Vault, tmp_path: Path) -> None:
    text = (tmp_path / "connectors" / "connections.json").read_text(encoding="utf-8")
    assert TOKEN not in text
    assert json.loads(text)["notion"]["status"] == "connected"
    assert TOKEN not in json.dumps(Connectors(notion).connections())


def test_a_key_service_does_not_take_a_sign_in_and_vice_versa(vault: Vault) -> None:
    with pytest.raises(VaultError, match="connects with a pasted key"):
        vault.connect_oauth("notion", client_id="x", client_secret="y", open_browser=False)
    with pytest.raises(VaultError, match="connects by signing in"):
        vault.connect_token("gmail", "ya29.something")


def test_the_records_survive_a_restart(notion: Vault, tmp_path: Path, provider: FakeProvider) -> None:
    again = _vault(tmp_path, provider)
    assert again.is_live("notion")
    assert again.record("notion").identity == "Test User"
    status, _ = again.request("notion", "GET", "https://api.notion.com/v1/users/me")
    assert status == 200


def test_with_no_root_nothing_is_written_and_the_seal_is_memory(provider: FakeProvider) -> None:
    vault = Vault(None, specs=load_builtin(), transport=provider)
    assert vault.root is None and vault.seal_kind == "memory"
    record = vault.connect_token("notion", TOKEN)
    assert record.status == "connected" and record.seal == "memory"
    vault.set_writes("notion", True)
    assert vault.request("notion", "GET", "https://api.notion.com/v1/users/me")[0] == 200


# -- the outbound door ----------------------------------------------------------------------------


def test_the_credential_rides_every_request_and_only_to_the_specs_hosts(
    notion: Vault, provider: FakeProvider
) -> None:
    status, _ = notion.request("notion", "POST", "https://api.notion.com/v1/search", {"query": "x"})
    assert status == 200
    sent = provider.seen[-1]
    assert sent.headers["Authorization"] == f"Bearer {TOKEN}"
    assert sent.json == {"query": "x"}
    with pytest.raises(HostRefused):
        notion.request("notion", "GET", "https://evil.example/v1/users/me")
    with pytest.raises(HostRefused, match=r"api\.notion\.com"):
        notion.request("notion", "GET", "http://api.notion.com/v1/users/me")  # not https
    assert len(provider.seen) == 2, "a refused host never reached the transport"


def test_a_disconnected_or_switched_off_connection_is_refused_before_the_wire(
    vault: Vault, provider: FakeProvider
) -> None:
    with pytest.raises(NotConnected):
        vault.request("notion", "GET", "https://api.notion.com/v1/users/me")
    vault.connect_token("notion", TOKEN)
    vault.set_enabled("notion", False)
    assert not vault.is_live("notion")
    with pytest.raises(NotConnected):
        vault.request("notion", "GET", "https://api.notion.com/v1/users/me")
    assert len(provider.seen) == 1, "only the probe went out"


def test_a_provider_error_body_is_returned_redacted(tmp_path: Path) -> None:
    def script(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> tuple[int, Any]:
        if url.endswith("/users/me"):
            return 200, {"name": "n"}
        return 500, f"boom Bearer {TOKEN} and again {TOKEN}".encode()

    vault = _vault(tmp_path, FakeProvider(script=script))
    vault.connect_token("notion", TOKEN)
    status, text = vault.request("notion", "GET", "https://api.notion.com/v1/pages/1")
    assert status == 500
    assert TOKEN not in text
    assert "[redacted]" in text


def test_redact_strips_bearer_tokens_and_known_prefixes() -> None:
    assert redact("x Bearer abcdefghijklmnop y", []) == "x Bearer [redacted] y"
    assert redact("key ntn_abcdefghijklmnop", []) == "key [redacted]"
    assert redact("a secret", ["secret"]) == "a [redacted]"


def test_a_response_over_the_cap_is_refused(tmp_path: Path) -> None:
    def script(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> tuple[int, Any]:
        if url.endswith("/users/me"):
            return 200, {"name": "n"}
        return 200, b"x" * (1_048_576 + 1)

    vault = _vault(tmp_path, FakeProvider(script=script))
    vault.connect_token("notion", TOKEN)
    with pytest.raises(VaultError, match="more than"):
        vault.request("notion", "GET", "https://api.notion.com/v1/pages/1")


# -- the switches ---------------------------------------------------------------------------------


def test_writes_are_off_by_default_and_the_allowlist_is_normalised(notion: Vault) -> None:
    record = notion.record("notion")
    assert record.writes_enabled is False and record.allowlist == []
    notion.set_writes("notion", True)
    notion.set_allowlist("notion", [" Abc-DEF ", "abc-def", "", "xyz"])
    record = notion.record("notion")
    assert record.writes_enabled is True
    assert record.allowlist == ["abc-def", "xyz"]


# -- disconnect -----------------------------------------------------------------------------------


def test_disconnect_destroys_the_sealed_value_and_keeps_the_switches(notion: Vault, tmp_path: Path) -> None:
    notion.set_writes("notion", True)
    notion.set_allowlist("notion", ["page1"])
    record = notion.disconnect("notion")
    assert record.status == "disconnected" and record.identity == ""
    assert record.writes_enabled is True and record.allowlist == ["page1"]
    assert not notion.is_live("notion")
    assert list((tmp_path / "connectors" / "sealed").glob("*")) == []
    with pytest.raises(NotConnected):
        notion.request("notion", "GET", "https://api.notion.com/v1/users/me")


def test_probe_records_a_broken_credential_with_its_time(tmp_path: Path) -> None:
    calls = {"n": 0}

    def script(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> tuple[int, Any]:
        calls["n"] += 1
        return (200, {"name": "n"}) if calls["n"] == 1 else (401, {"message": "gone"})

    vault = _vault(tmp_path, FakeProvider(script=script))
    vault.connect_token("notion", TOKEN)
    record = vault.probe("notion")
    assert record.health == "broken" and record.health_at
    assert "401" in record.health_detail and TOKEN not in record.health_detail


# -- the grant ------------------------------------------------------------------------------------


def test_an_expired_grant_with_no_refresh_needs_a_new_sign_in(tmp_path: Path) -> None:
    vault = _vault(tmp_path, FakeProvider())
    # Admit a grant the way the sign-in exchange would, but already at its floor and with no refresh.
    vault._admit(vault.specs["gmail"], "ya29.access", refresh="", expires_in=1)
    assert vault.is_live("gmail")
    with pytest.raises(NeedsReauth, match="sign in again"):
        vault.request("gmail", "GET", "https://gmail.googleapis.com/gmail/v1/users/me/profile")
    assert vault.record("gmail").status == "needs_reauth"
    assert not vault.is_live("gmail")


def test_an_expired_grant_is_renewed_before_the_call(tmp_path: Path) -> None:
    def script(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> tuple[int, Any]:
        if url.endswith("/token"):
            return 200, {"access_token": "ya29.renewed", "expires_in": 3600}
        return 200, {"emailAddress": "me@example.test"}

    provider = FakeProvider(script=script)
    vault = _vault(tmp_path, provider)
    vault._admit(vault.specs["gmail"], "ya29.access", refresh="1//r", expires_in=1, client=("cid", "cs"))
    status, _ = vault.request("gmail", "GET", "https://gmail.googleapis.com/gmail/v1/users/me/profile")
    assert status == 200
    assert provider.seen[-2].path == "/token" and provider.seen[-2].form["refresh_token"] == "1//r"
    assert provider.seen[-1].headers["Authorization"] == "Bearer ya29.renewed"


def test_the_transport_follows_no_redirect_so_the_credential_stays_on_the_pinned_host() -> None:
    hits: list[str] = []

    class Target(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            hits.append(self.headers.get("Authorization", ""))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args: Any) -> None:
            pass

    target = HTTPServer(("127.0.0.1", 0), Target)

    class Bounce(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{target.server_port}/stolen")
            self.end_headers()

        def log_message(self, *args: Any) -> None:
            pass

    first = HTTPServer(("127.0.0.1", 0), Bounce)
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (target, first)]
    for thread in threads:
        thread.start()
    try:
        status, _, _ = UrllibTransport()(
            "GET", f"http://127.0.0.1:{first.server_port}/", {"Authorization": "Bearer secret"}, None, 5.0
        )
    finally:
        for server in (target, first):
            server.shutdown()
            server.server_close()
    assert status == 302
    assert hits == [], "the second host received a request"


# -- the records file -----------------------------------------------------------------------------

UNREADABLE = {
    "truncated": b'{"notion": {"status": "conn',
    "empty": b"",
    "nul": b"\x00\x00\x00\x00",
    "not-an-object": b"[]",
}


@pytest.mark.parametrize("name", sorted(UNREADABLE))
def test_an_unreadable_records_file_is_kept_and_said_aloud(
    name: str, tmp_path: Path, provider: FakeProvider
) -> None:
    root = tmp_path / "connectors"
    root.mkdir()
    (root / "connections.json").write_bytes(UNREADABLE[name])
    vault = _vault(tmp_path, provider)
    copies = sorted(root.glob("connections.json.unreadable-*"))
    assert len(copies) == 1 and copies[0].read_bytes() == UNREADABLE[name]
    assert "could not be read" in vault.records_notice and copies[0].name in vault.records_notice
    listed = Connectors(vault).connections()["connections"]
    assert all(c.get("problem") == vault.records_notice for c in listed)
    assert not vault.is_live("notion")


def test_the_switches_set_afterwards_do_not_destroy_the_copy(tmp_path: Path, provider: FakeProvider) -> None:
    root = tmp_path / "connectors"
    root.mkdir()
    (root / "connections.json").write_bytes(UNREADABLE["truncated"])
    vault = _vault(tmp_path, provider)
    vault.set_writes("notion", True)
    vault.set_allowlist("notion", ["page1"])
    (copy,) = root.glob("connections.json.unreadable-*")
    assert copy.read_bytes() == UNREADABLE["truncated"]
    assert json.loads((root / "connections.json").read_text(encoding="utf-8"))["notion"]["writes_enabled"]
    again = _vault(tmp_path, provider)
    assert again.records_notice and copy.name in again.records_notice, "the copy stays in view"


def test_a_readable_file_gives_no_notice(notion: Vault) -> None:
    assert notion.records_notice == ""
    assert "problem" not in Connectors(notion).connection("notion")


def test_a_crash_during_the_write_leaves_the_previous_file(
    notion: Vault, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "connectors" / "connections.json"
    before = path.read_bytes()

    def boom(*_: object) -> None:
        raise OSError("disk went away")

    monkeypatch.setattr("athena.connectors.vault.os.replace", boom)
    with pytest.raises(VaultError, match="could not be saved"):
        notion.set_writes("notion", True)
    assert path.read_bytes() == before
    assert list(path.parent.glob("*.tmp")) == [], "no temp file is left behind"


# -- the switches belong to the account -----------------------------------------------------------


def _accounts(tmp_path: Path, names: list[str]) -> Vault:
    """A vault whose probe answers with the next name in `names` each time it is asked."""
    asked = {"n": 0}

    def script(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> tuple[int, Any]:
        who = names[min(asked["n"], len(names) - 1)]
        asked["n"] += 1
        return 200, ({"name": who, "id": f"id-{who}"} if who else {"name": who})

    return Vault(
        tmp_path / "connectors",
        specs=load_builtin(),
        transport=FakeProvider(script=script),
        seal=FileSeal(tmp_path / "connectors" / "sealed"),
    )


def test_a_connect_as_a_different_account_turns_writes_off_and_empties_the_list(tmp_path: Path) -> None:
    vault = _accounts(tmp_path, ["A", "B"])
    vault.connect_token("notion", TOKEN)
    vault.set_writes("notion", True)
    vault.set_allowlist("notion", ["page1"])
    vault.disconnect("notion")
    assert vault.record("notion").writes_enabled, "the disconnect keeps them"
    record = vault.connect_token("notion", TOKEN)
    assert record.identity == "B"
    assert record.writes_enabled is False and record.allowlist == []
    assert "Connected as B" in record.notice and "set under A" in record.notice
    problem = Connectors(vault).connection("notion")["problem"]  # type: ignore[typeddict-item]
    assert "Connected as B" in problem and "Writing was turned off" in problem


def test_a_reconnect_as_the_same_account_keeps_the_switches(tmp_path: Path) -> None:
    vault = _accounts(tmp_path, ["A"])
    vault.connect_token("notion", TOKEN)
    vault.set_writes("notion", True)
    vault.set_allowlist("notion", ["page1"])
    vault.disconnect("notion")
    record = vault.connect_token("notion", TOKEN)
    assert record.writes_enabled is True and record.allowlist == ["page1"]
    assert record.notice == "" and record.health_detail == ""


def test_the_identity_is_kept_across_a_restart_and_a_disconnect(tmp_path: Path) -> None:
    vault = _accounts(tmp_path, ["A", "B"])
    vault.connect_token("notion", TOKEN)
    vault.set_allowlist("notion", ["page1"])
    vault.disconnect("notion")
    again = _accounts(tmp_path, ["B"])
    assert again.record("notion").switches_identity == "A"
    assert again.connect_token("notion", TOKEN).allowlist == []


def test_switches_set_before_any_connect_have_no_identity_and_are_reset(tmp_path: Path) -> None:
    vault = _accounts(tmp_path, ["A"])
    vault.set_writes("notion", True)
    vault.set_allowlist("notion", ["page1"])
    record = vault.connect_token("notion", TOKEN)
    assert record.writes_enabled is False and record.allowlist == []
    assert "without a known account" in record.notice


def test_a_probe_that_names_no_account_never_matches(tmp_path: Path) -> None:
    vault = _accounts(tmp_path, ["A", ""])
    vault.connect_token("notion", TOKEN)
    vault.set_writes("notion", True)
    vault.disconnect("notion")
    record = vault.connect_token("notion", TOKEN)
    assert record.writes_enabled is False and "did not name" in record.notice


class _BrokenOpener:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    def open(self, request: Any, timeout: float) -> Any:
        raise self.error


@pytest.mark.parametrize(
    "error",
    [http.client.BadStatusLine("garbage"), http.client.IncompleteRead(b"half")],
    ids=["bad-status-line", "incomplete-read"],
)
def test_a_garbled_answer_is_the_vaults_own_error_never_an_http_client_one(
    monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    monkeypatch.setattr("athena.connectors.vault._OPENER", _BrokenOpener(error))
    with pytest.raises(NoAnswer, match=type(error).__name__):
        UrllibTransport()("POST", "https://api.notion.com/v1/pages", {}, b"{}", 5.0)


def test_memory_seal_is_the_default_without_a_root() -> None:
    assert isinstance(Vault(None, specs=load_builtin())._seal, MemorySeal)
