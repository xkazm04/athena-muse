from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from athena.errors import ApiError
from athena.keys import KeyStore


@pytest.fixture(autouse=True)
def _no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("META_API_KEY", raising=False)


def test_absent_then_file(tmp_path: Path) -> None:
    ks = KeyStore(tmp_path)
    assert ks.source() == "absent"
    assert ks.get() is None
    ks.save("  sk-secret-1  ")
    assert ks.source() == "file"
    assert ks.get() == "sk-secret-1"
    assert json.loads((tmp_path / "meta-key.json").read_text()) == {"key": "sk-secret-1"}
    ks.delete()
    assert ks.source() == "absent"


def test_env_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ks = KeyStore(tmp_path)
    ks.save("from-file")
    monkeypatch.setenv("META_API_KEY", "from-env")
    assert ks.source() == "env"
    assert ks.get() == "from-env"


def test_memory_only_without_data_dir() -> None:
    ks = KeyStore(None)
    ks.save("abc")
    assert ks.source() == "file"
    ks.delete()
    assert ks.get() is None


@pytest.mark.parametrize("bad", ["", "   ", "has space", "tab\tin", "x" * 513])
def test_refuses_bad_keys(bad: str) -> None:
    with pytest.raises(ApiError) as e:
        KeyStore(None).save(bad)
    assert e.value.error == "bad_request"
    assert "xxxxxxxxxx" not in e.value.reason


def test_repr_masks(tmp_path: Path) -> None:
    ks = KeyStore(tmp_path)
    ks.save("sk-very-secret")
    assert "sk-very-secret" not in repr(ks)


@pytest.mark.skipif(os.name == "nt", reason="POSIX modes")
def test_file_is_owner_only(tmp_path: Path) -> None:
    ks = KeyStore(tmp_path)
    ks.save("k")
    assert (tmp_path / "meta-key.json").stat().st_mode & 0o077 == 0
