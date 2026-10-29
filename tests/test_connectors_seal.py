"""Where a credential rests: this platform's seal round-trips, the file is born 0600 and swapped in
whole, and every seal's failure is typed. The keystore is a stand-in module, never the machine's.
Ported from athena-portable's `tests/connectors/test_seal.py`, with the platform round-trip added."""

from __future__ import annotations

import os
import stat
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from athena.connectors.seal import FileSeal, KeyringSeal, SealUnavailable, select_seal
from athena.connectors.spec import load_builtin
from athena.connectors.vault import Vault, VaultError
from connectors_kit import FakeProvider

POSIX = os.name == "posix"
VALUE = "ntn_round_trip_0123456789"


def test_this_platforms_seal_round_trips_and_destroys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DPAPI on Windows; elsewhere the keystore when installed (stood in here), else the owner-only file."""
    if sys.platform != "win32":
        monkeypatch.setitem(sys.modules, "keyring", _MemoryKeyring("keyring"))
    seal = select_seal(tmp_path / "sealed")
    assert seal.kind == ("dpapi" if sys.platform == "win32" else "keyring")
    seal.seal("notion.token", VALUE)
    assert seal.unseal("notion.token") == VALUE
    for path in (tmp_path / "sealed").glob("*"):
        assert VALUE.encode() not in path.read_bytes(), "the value rests sealed, never in plain text"
    seal.destroy("notion.token")
    assert seal.unseal("notion.token") is None


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows only")
def test_a_vault_on_windows_seals_with_dpapi_and_survives_a_restart(tmp_path: Path) -> None:
    provider = FakeProvider()
    root = tmp_path / "connectors"
    first = Vault(root, specs=load_builtin(), transport=provider)
    assert first.connect_token("notion", VALUE).seal == "dpapi"
    blobs = list((root / "sealed").glob("*.sealed"))
    assert blobs and all(VALUE.encode() not in b.read_bytes() for b in blobs)
    again = Vault(root, specs=load_builtin(), transport=provider)
    assert again.request("notion", "GET", "https://api.notion.com/v1/users/me")[0] == 200
    assert provider.seen[-1].headers["Authorization"] == f"Bearer {VALUE}"


def test_without_the_keystore_elsewhere_the_file_seal_is_chosen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("athena.connectors.seal.sys.platform", "linux")
    monkeypatch.setitem(sys.modules, "keyring", None)  # an import of it raises ImportError
    assert select_seal(tmp_path / "sealed").kind == "file"


def test_an_unknown_preference_is_refused_not_fallen_through(tmp_path: Path) -> None:
    with pytest.raises(SealUnavailable, match="unknown seal"):
        select_seal(tmp_path, prefer="paper")


def test_a_sealed_file_is_created_exclusive_with_mode_0600_and_swapped_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[tuple[str, int, int]] = []
    real_open = os.open

    def spy(path: Any, flags: int, mode: int = 0o777, *args: Any, **kwargs: Any) -> int:
        opened.append((str(path), flags, mode))
        return real_open(path, flags, mode, *args, **kwargs)

    seal = FileSeal(tmp_path / "sealed")
    monkeypatch.setattr("athena.connectors.seal.os.open", spy)
    seal.seal("gmail.token", "first")
    seal.seal("gmail.token", "second")
    assert seal.unseal("gmail.token") == "second"
    assert len(opened) == 2
    for path, flags, mode in opened:
        assert path.endswith(".tmp") and not path.endswith("gmail.token.sealed")
        assert flags & os.O_CREAT and flags & os.O_EXCL and flags & os.O_WRONLY
        assert mode == 0o600
    assert sorted(p.name for p in (tmp_path / "sealed").iterdir()) == ["gmail.token.sealed"]
    if POSIX:
        mode_on_disk = stat.S_IMODE((tmp_path / "sealed" / "gmail.token.sealed").stat().st_mode)
        assert mode_on_disk == 0o600


def test_a_failed_swap_keeps_the_old_value_and_leaves_no_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seal = FileSeal(tmp_path / "sealed")
    seal.seal("notion.token", "kept")

    def boom(*_: object) -> None:
        raise OSError("disk went away")

    monkeypatch.setattr("athena.connectors.seal.os.replace", boom)
    with pytest.raises(SealUnavailable, match="could not be written"):
        seal.seal("notion.token", "lost")
    assert seal.unseal("notion.token") == "kept"
    assert [p.name for p in (tmp_path / "sealed").iterdir()] == ["notion.token.sealed"]


def test_a_file_that_cannot_be_created_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seal = FileSeal(tmp_path / "sealed")

    def refused(*_: object, **__: object) -> int:
        raise PermissionError("no")

    monkeypatch.setattr("athena.connectors.seal.os.open", refused)
    with pytest.raises(SealUnavailable, match="PermissionError"):
        seal.seal("notion.token", "x")


@pytest.mark.skipif(not POSIX, reason="file modes are POSIX")
def test_on_posix_a_file_born_readable_by_others_is_refused_not_swallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seal = FileSeal(tmp_path / "sealed")
    real_fstat = os.fstat

    def loose(fd: int) -> Any:
        found = real_fstat(fd)
        return types.SimpleNamespace(st_mode=(found.st_mode & ~0o777) | 0o644)

    monkeypatch.setattr("athena.connectors.seal.os.fstat", loose)
    with pytest.raises(SealUnavailable, match="mode 644"):
        seal.seal("notion.token", "x")
    assert list((tmp_path / "sealed").iterdir()) == [], "nothing is left behind"


class _MemoryKeyring(types.ModuleType):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.kept: dict[str, str] = {}

    def set_password(self, service: str, name: str, value: str) -> None:
        self.kept[name] = value

    def get_password(self, service: str, name: str) -> str | None:
        return self.kept.get(name)

    def delete_password(self, service: str, name: str) -> None:
        self.kept.pop(name, None)


class _BrokenKeyring(types.ModuleType):
    """A keyring whose backend fails the way a locked keychain does: with its own error type."""

    class BackendError(Exception):
        pass

    def set_password(self, service: str, name: str, value: str) -> None:
        raise self.BackendError("the keychain is locked")

    def get_password(self, service: str, name: str) -> str | None:
        raise self.BackendError("the keychain is locked")

    def delete_password(self, service: str, name: str) -> None:
        raise self.BackendError("the keychain is locked")


@pytest.fixture
def broken_keyring(monkeypatch: pytest.MonkeyPatch) -> KeyringSeal:
    monkeypatch.setitem(sys.modules, "keyring", _BrokenKeyring("keyring"))
    return KeyringSeal()


def test_a_keystore_error_is_typed_on_set_and_get(broken_keyring: KeyringSeal) -> None:
    with pytest.raises(SealUnavailable, match="BackendError"):
        broken_keyring.seal("notion.token", "x")
    with pytest.raises(SealUnavailable, match="BackendError"):
        broken_keyring.unseal("notion.token")
    broken_keyring.destroy("notion.token")  # a destroy never raises


def test_the_vault_turns_a_seal_failure_into_its_own_vocabulary(
    tmp_path: Path, broken_keyring: KeyringSeal
) -> None:
    vault = Vault(
        tmp_path / "connectors", specs=load_builtin(), transport=FakeProvider(), seal=broken_keyring
    )
    with pytest.raises(VaultError, match="could not be stored"):
        vault.connect_token("notion", "ntn_test_token_0123456789")
    with pytest.raises(VaultError, match="could not be read"):
        vault.probe("notion")


class _ReadBrokenKeyring(_MemoryKeyring):
    """A keystore that stores and deletes but can no longer read: a keychain locked after the connect."""

    readable = True

    def get_password(self, service: str, name: str) -> str | None:
        if not self.readable:
            raise RuntimeError("the keychain is locked")
        return self.kept.get(name)


def test_a_seal_that_cannot_be_read_does_not_keep_a_credential_the_person_disconnected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _ReadBrokenKeyring("keyring")
    monkeypatch.setitem(sys.modules, "keyring", store)
    vault = Vault(tmp_path / "connectors", specs=load_builtin(), transport=FakeProvider(), seal=KeyringSeal())
    vault.connect_token("notion", "ntn_test_token_0123456789")
    assert "notion.token" in store.kept
    store.readable = False
    record = vault.disconnect("notion")
    assert record.status == "disconnected" and not vault.is_live("notion")
    assert store.kept == {}, "every sealed value was destroyed"
