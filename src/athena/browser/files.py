"""A project's files (ADR 0013): what her browser downloaded, kept by content under the data folder.

A file lives at `<data>/spaces/<space_id>/files/<sha256>` and is named to the model only by its id
(`fil_...`), never by a path. One row per (space, sha256): the same bytes downloaded twice are one
file. Erasing a project removes its rows and its folder. Phase 1's records adopt this table as the
`file` kind.
"""

from __future__ import annotations

import hashlib
import mimetypes
import shutil
from pathlib import Path

from athena.clock import mint, now_iso
from athena.contracts import FileItem
from athena.errors import ApiError
from athena.store import Store

NAME_MAX = 120


def space_dir(data_dir: Path | None, space_id: str) -> Path | None:
    if data_dir is None or not space_id:
        return None
    return data_dir / "spaces" / space_id / "files"


def _item(r: object) -> FileItem:
    row = dict(r)  # type: ignore[call-overload]
    return {
        "id": row["id"],
        "space_id": row["space_id"],
        "name": row["name"],
        "mime": row["mime"],
        "size": row["size"],
        "sha256": row["sha256"],
        "origin": row["origin"],
        "created": row["created"],
    }


def _clean_name(name: str) -> str:
    kept = "".join(c if c.isalnum() or c in ".-_ " else "_" for c in name).strip()
    return kept[:NAME_MAX] or "file"


class Files:
    def __init__(self, store: Store, data_dir: Path | None) -> None:
        self._store = store
        self._data_dir = data_dir

    def incoming(self, space_id: str) -> Path:
        """Where her browser puts a download before it is kept."""
        root = space_dir(self._data_dir, space_id)
        if root is None:
            raise ApiError("bad_request", "files need a project and a data folder")
        path = root / "incoming"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ingest(self, space_id: str, source: Path, name: str, origin: str) -> FileItem:
        """Hash `source`, move it to its place, and keep one row for it (an existing one when the
        same bytes are already kept)."""
        root = space_dir(self._data_dir, space_id)
        if root is None:
            raise ApiError("bad_request", "files need a project and a data folder")
        digest = hashlib.sha256()
        size = 0
        with source.open("rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                digest.update(block)
                size += len(block)
        sha = digest.hexdigest()
        target = root / sha
        if target.exists():
            source.unlink(missing_ok=True)
        else:
            root.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), target)
        found = self._store.query("SELECT * FROM files WHERE space_id = ? AND sha256 = ?", (space_id, sha))
        if found:
            return _item(found[0])
        clean = _clean_name(name)
        mime = mimetypes.guess_type(clean)[0] or "application/octet-stream"
        file_id = mint("fil_")
        self._store.run(
            "INSERT INTO files(id, space_id, name, mime, size, sha256, origin, created) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (file_id, space_id, clean, mime, size, sha, origin, now_iso()),
        )
        return self.get(space_id, file_id)

    def get(self, space_id: str, file_id: str) -> FileItem:
        rows = self._store.query("SELECT * FROM files WHERE id = ? AND space_id = ?", (file_id, space_id))
        if not rows:
            raise ApiError("unknown_ref", "there is no such file in this project")
        return _item(rows[0])

    def path(self, item: FileItem) -> Path:
        root = space_dir(self._data_dir, item["space_id"])
        if root is None:
            raise ApiError("bad_request", "files need a data folder")
        return root / item["sha256"]

    def list(self, space_id: str) -> list[FileItem]:
        rows = self._store.query("SELECT * FROM files WHERE space_id = ? ORDER BY rowid DESC", (space_id,))
        return [_item(r) for r in rows]

    def remove_folder(self, space_id: str) -> None:
        root = space_dir(self._data_dir, space_id)
        if root is not None and root.is_dir():
            shutil.rmtree(root)
