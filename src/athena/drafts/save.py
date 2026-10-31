"""The verdict: `keep` copies the chore into the person's library and sets the Project's brief;
`revise` returns the draft to `shape` with the person's note.

A kept chore's practice apps are invented, so none is added to the Project's apps or sites. The real
sites the person confirmed on the sketch go to the access step (ADR 0014, `access.begin`): `keep`
moves the draft to `access`, or straight to `saved` when the chore needs no real site.

`revise` is taken at the preview, before the run and at the verdict, so "this isn't what I meant" has
a way back to the sketch at each of them; the sketch stays as it was.
"""

from __future__ import annotations

import shutil
from typing import Any, cast

from athena.app import Daemon
from athena.chores.spec import chore_ids, user_library_dir
from athena.contracts import BRIEF_MAX, TEXT_MAX, Draft, DraftVerdict
from athena.drafts import access
from athena.drafts.author import chore_root, load_written, not_busy
from athena.drafts.preview import cut
from athena.errors import ApiError

REVISABLE: frozenset[str] = frozenset({"preview", "rehearse", "verdict"})


def verdict(daemon: Daemon, draft_id: str, word: DraftVerdict, note: str | None) -> Draft:
    if word not in ("keep", "revise"):
        raise ApiError("bad_request", "the verdict is keep or revise")
    if note is not None and not isinstance(note, str):
        raise ApiError("bad_request", "send the note as text")
    note = " ".join((note or "").split())
    if len(note) > TEXT_MAX:
        raise ApiError("bad_request", f"a note is at most {TEXT_MAX} characters")
    draft = daemon.drafts.get(draft_id)
    not_busy(daemon, draft)
    stored = cast("dict[str, Any]", dict(draft))
    stored["verdict"] = word
    if note:
        stored["note"] = note
    else:
        stored.pop("note", None)
    if word == "revise":
        if draft["step"] not in REVISABLE:
            raise ApiError("bad_request", "there is nothing to revise yet; she has not written the chore")
        stored["step"] = "shape"
        return daemon.drafts.put(cast("Draft", stored))
    if draft["step"] != "verdict" or "bench" not in draft:
        raise ApiError("bad_request", "a chore is kept after its test run")
    chore = load_written(daemon, draft)
    target = user_library_dir(daemon.data_dir)
    if target is None:  # load_written already needed a data folder; kept for the type checker
        raise ApiError("bad_request", "drafts need a data folder; start Athena with one")
    if chore.id in chore_ids(daemon.data_dir):
        raise ApiError("bad_request", f"a chore called {chore.id} is already in a library; write it again")
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(chore_root(daemon, draft), target / chore.id)
    promise = " ".join(str(chore.showcase.get("promise", "")).split())
    if promise:
        daemon.spaces.update(draft["space_id"], {"brief": cut(promise, BRIEF_MAX)})
        daemon.events.publish({"type": "space_changed", "space_id": draft["space_id"]})
    title = " ".join(
        str(chore.showcase.get("short_title") or chore.showcase.get("title") or chore.id).split()
    )
    access.begin(daemon, stored, title)  # the chore's real sites, if any: `access`, else `saved`
    return daemon.drafts.put(cast("Draft", stored))
