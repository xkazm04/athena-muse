"""Custody of the Meta key. The key never leaves this module except through `get()`."""

from __future__ import annotations

import json
import os
from pathlib import Path

from athena.contracts import KeySource
from athena.errors import ApiError

KEY_MAX = 512
ENV_NAME = "META_API_KEY"
FILE_NAME = "meta-key.json"


class KeyStore:
    def __init__(self, data_dir: Path | None) -> None:
        self._path = data_dir / FILE_NAME if data_dir is not None else None
        self._memory: str | None = None

    def __repr__(self) -> str:
        return f"KeyStore(source={self.source()!r}, key=***)"

    def _env(self) -> str | None:
        value = os.environ.get(ENV_NAME, "").strip()
        return value or None

    def _stored(self) -> str | None:
        if self._path is None:
            return self._memory
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        key = data.get("key") if isinstance(data, dict) else None
        return key if isinstance(key, str) and key.strip() else None

    def source(self) -> KeySource:
        if self._env():
            return "env"
        return "file" if self._stored() else "absent"

    def get(self) -> str | None:
        return self._env() or self._stored()

    def save(self, key: str) -> None:
        key = key.strip()
        if not key:
            raise ApiError("bad_request", "the key is empty")
        if any(c.isspace() for c in key):
            raise ApiError("bad_request", "a key has no spaces in it; check what you pasted")
        if len(key) > KEY_MAX:
            raise ApiError("bad_request", "that is too long to be a key")
        if self._path is None:
            self._memory = key
            return
        tmp = self._path.with_name(self._path.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"key": key}, f)
        os.replace(tmp, self._path)

    def delete(self) -> None:
        self._memory = None
        if self._path is not None:
            self._path.unlink(missing_ok=True)
