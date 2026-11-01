"""The kind catalog: one entry per RecordKind, the body validator and the key rule.

A body is cleaned, never trusted: strings are trimmed and cut at TEXT_MAX, an empty optional string
is an absent field, unknown fields are dropped, enums and types are checked, and every address must
be http(s). An address used as a key is normalised (lower-cased scheme and host, no trailing slash),
so the same page found twice is one record. Whether a `file_id` is a row of the project's files is
the store's question (it knows the project), not this module's.
"""

from __future__ import annotations

import math
import typing
from datetime import datetime
from typing import Any, TypedDict
from urllib.parse import urlsplit, urlunsplit

from athena.contracts import (
    TEXT_MAX,
    AgreementState,
    RecordKind,
    RenderState,
    SunoPlan,
    ThreadChannel,
    TrackVerdict,
)
from athena.errors import ApiError

#: The kinds Athena may put on her own, as finds (the rest file a card).
FINDS: frozenset[RecordKind] = frozenset({"creator", "track"})

KINDS: tuple[RecordKind, ...] = typing.get_args(RecordKind)
KEY_MAX = 512  # a given key (a thread's), and any computed one
LIST_MAX = 50  # items in a list field (bio links, job ids, reasons)


class KindSpec(TypedDict):
    kind: RecordKind
    description: str  # read by the report composer; generated docs come from here (one authority)
    fields: dict[str, str]  # field -> plain description, for the composer
    numeric: list[str]  # fields a block may sum, take last of or draw as a series


CATALOG: dict[RecordKind, KindSpec] = {
    "creator": {
        "kind": "creator",
        "description": "A music creator the channel follows or has found. Keyed by their channel address.",
        "fields": {
            "name": "The creator's name",
            "channel_url": "Their channel's address (the key)",
            "followed": "Whether the channel follows them (true or false)",
            "bio_links": "Optional: addresses from their bio",
            "note": "Optional: a note about them",
        },
        "numeric": [],
    },
    "track": {
        "kind": "track",
        "description": "A song found on a creator's channel, with the person's verdict once given "
        "(keep, pass or later). Keyed by its address; a track without a verdict is in the queue.",
        "fields": {
            "url": "The song's address (the key)",
            "title": "The song's title",
            "creator_key": "The creator's key (their channel address)",
            "found_at": "When it was found (ISO 8601)",
            "verdict": "Optional: keep, pass or later; absent means not judged yet",
            "genre": "Optional: the genre the person gave it",
            "note": "Optional: the person's note",
            "file_id": "Optional: the project's file of its audio (fil_...)",
        },
        "numeric": [],
    },
    "thread": {
        "kind": "thread",
        "description": "A conversation with a creator: by mail on the web, a bio message or a comment. "
        "Keyed by the key it was given.",
        "fields": {
            "creator_key": "The creator's key",
            "channel": "mail_web, bio or comment",
            "last_at": "When it last moved (ISO 8601)",
            "subject": "Optional: its subject",
            "url": "Optional: its address",
            "snippet": "Optional: a line of the last message",
        },
        "numeric": [],
    },
    "agreement": {
        "kind": "agreement",
        "description": "A licence agreement with a creator: proposed, agreed or declined, with the "
        "thread it was agreed in as evidence and the creator's plan. Keyed by the creator's key.",
        "fields": {
            "creator_key": "The creator's key (the key)",
            "state": "proposed, agreed or declined",
            "thread_key": "The thread it was agreed in (the evidence)",
            "plan": "Optional: the creator's plan: free, pro, premier or unknown",
            "terms": "Optional: the terms in plain words",
        },
        "numeric": [],
    },
    "file": {
        "kind": "file",
        "description": "One of the project's files kept as a record, optionally for a track. Keyed by "
        "its file id.",
        "fields": {"file_id": "The file's id (fil_..., the key)", "track_key": "Optional: the track's key"},
        "numeric": [],
    },
    "render": {
        "kind": "render",
        "description": "A music video made for a track: staged, running, rendered, refused or failed. "
        "Keyed by the track's key.",
        "fields": {
            "track_key": "The track's key (the key)",
            "state": "staged, running, rendered, refused or failed",
            "job_ids": "Optional: the render jobs",
            "reasons": "Optional: why it was refused or failed",
            "output_file_id": "Optional: the video's file id",
        },
        "numeric": [],
    },
    "release": {
        "kind": "release",
        "description": "A video ready to publish, with its credits. Keyed by the track's key.",
        "fields": {
            "track_key": "The track's key (the key)",
            "title": "The video's title",
            "track_url": "The original song's address",
            "creator_channel_url": "The creator's channel address",
            "genre": "The genre",
            "credits": "The credits line",
        },
        "numeric": [],
    },
    "stat": {
        "kind": "stat",
        "description": "One measurement of the channel (views, subscribers...) at the time it was read. "
        "Keyed by metric and time; a series of one metric draws a trend.",
        "fields": {
            "metric": "What was measured, like views or subscribers",
            "value": "The number read",
            "measured_at": "When it was read (ISO 8601), never a claimed time",
        },
        "numeric": ["value"],
    },
}


# --- field checks ---------------------------------------------------------------------------------


def _bad(reason: str) -> ApiError:
    return ApiError("bad_request", reason)


def normalise_url(raw: str) -> str:
    """An http(s) address with its scheme and host lower-cased and no trailing slash; or ApiError."""
    text = raw.strip()
    try:
        parts = urlsplit(text)
    except ValueError:
        raise _bad(f"not a web address: {text[:80]}") from None
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https") or not parts.netloc:
        raise _bad(f"an address must start with http:// or https:// ({text[:80]})")
    path = parts.path.rstrip("/")
    return urlunsplit((scheme, parts.netloc.lower(), path, parts.query, parts.fragment))


def normalise_ref(raw: str) -> str:
    """A key as a caller names it: an address is normalised as a key address is, anything else trimmed."""
    text = raw.strip()
    if text.lower().startswith(("http://", "https://")):
        try:
            return normalise_url(text)
        except ApiError:
            return text
    return text


def _text(body: dict[str, Any], name: str, *, required: bool) -> str | None:
    value = body.get(name)
    if value is None:
        if required:
            raise _bad(f"{name} is required")
        return None
    if not isinstance(value, str):
        raise _bad(f"{name} must be text")
    text = value.strip()[:TEXT_MAX]
    if not text:
        if required:
            raise _bad(f"{name} is required")
        return None
    return text


def _url(body: dict[str, Any], name: str, *, required: bool) -> str | None:
    text = _text(body, name, required=required)
    if text is None:
        return None
    try:
        return normalise_url(text)
    except ApiError as e:
        raise _bad(f"{name}: {e.reason}") from None


def _ref(body: dict[str, Any], name: str, *, required: bool) -> str | None:
    text = _text(body, name, required=required)
    if text is None:
        return None
    if len(text) > KEY_MAX:
        raise _bad(f"{name} is at most {KEY_MAX} characters")
    return normalise_ref(text)


def _when(body: dict[str, Any], name: str, *, required: bool) -> str | None:
    text = _text(body, name, required=required)
    if text is None:
        return None
    try:
        datetime.fromisoformat(text)
    except ValueError:
        raise _bad(f"{name} must be a date and time like 2026-11-01T12:00:00Z") from None
    return text


def _choice(body: dict[str, Any], name: str, allowed: Any, *, required: bool) -> str | None:
    text = _text(body, name, required=required)
    if text is None:
        return None
    options = typing.get_args(allowed)
    if text not in options:
        raise _bad(f"{name} must be one of {', '.join(options)}")
    return text


def _flag(body: dict[str, Any], name: str) -> bool:
    value = body.get(name)
    if not isinstance(value, bool):
        raise _bad(f"{name} must be true or false")
    return value


def _number(body: dict[str, Any], name: str) -> float:
    value = body.get(name)
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise _bad(f"{name} must be a number")
    return float(value)


def _texts(body: dict[str, Any], name: str, *, urls: bool = False) -> list[str] | None:
    value = body.get(name)
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise _bad(f"{name} must be a list of text")
    out: list[str] = []
    for item in value:
        text = item.strip()[:TEXT_MAX]
        if not text:
            continue
        if urls:
            try:
                text = normalise_url(text)
            except ApiError as e:
                raise _bad(f"{name}: {e.reason}") from None
        if text not in out:
            out.append(text)
    if len(out) > LIST_MAX:
        raise _bad(f"{name} holds at most {LIST_MAX} items")
    return out or None


def _put(out: dict[str, Any], name: str, value: Any) -> None:
    if value is not None:
        out[name] = value


# --- the validators -------------------------------------------------------------------------------


def _creator(b: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "name": _text(b, "name", required=True),
        "channel_url": _url(b, "channel_url", required=True),
        "followed": _flag(b, "followed"),
    }
    _put(out, "bio_links", _texts(b, "bio_links", urls=True))
    _put(out, "note", _text(b, "note", required=False))
    return out


def _track(b: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "url": _url(b, "url", required=True),
        "title": _text(b, "title", required=True),
        "creator_key": _ref(b, "creator_key", required=True),
        "found_at": _when(b, "found_at", required=True),
    }
    _put(out, "verdict", _choice(b, "verdict", TrackVerdict, required=False))
    _put(out, "genre", _text(b, "genre", required=False))
    _put(out, "note", _text(b, "note", required=False))
    _put(out, "file_id", _ref(b, "file_id", required=False))
    return out


def _thread(b: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "creator_key": _ref(b, "creator_key", required=True),
        "channel": _choice(b, "channel", ThreadChannel, required=True),
        "last_at": _when(b, "last_at", required=True),
    }
    _put(out, "subject", _text(b, "subject", required=False))
    _put(out, "url", _url(b, "url", required=False))
    _put(out, "snippet", _text(b, "snippet", required=False))
    return out


def _agreement(b: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "creator_key": _ref(b, "creator_key", required=True),
        "state": _choice(b, "state", AgreementState, required=True),
        "thread_key": _ref(b, "thread_key", required=True),
    }
    _put(out, "plan", _choice(b, "plan", SunoPlan, required=False))
    _put(out, "terms", _text(b, "terms", required=False))
    return out


def _file(b: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"file_id": _ref(b, "file_id", required=True)}
    _put(out, "track_key", _ref(b, "track_key", required=False))
    return out


def _render(b: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "track_key": _ref(b, "track_key", required=True),
        "state": _choice(b, "state", RenderState, required=True),
    }
    _put(out, "job_ids", _texts(b, "job_ids"))
    _put(out, "reasons", _texts(b, "reasons"))
    _put(out, "output_file_id", _ref(b, "output_file_id", required=False))
    return out


def _release(b: dict[str, Any]) -> dict[str, Any]:
    return {
        "track_key": _ref(b, "track_key", required=True),
        "title": _text(b, "title", required=True),
        "track_url": _url(b, "track_url", required=True),
        "creator_channel_url": _url(b, "creator_channel_url", required=True),
        "genre": _text(b, "genre", required=True),
        "credits": _text(b, "credits", required=True),
    }


def _stat(b: dict[str, Any]) -> dict[str, Any]:
    metric = _text(b, "metric", required=True)
    if metric is not None and ("@" in metric or len(metric) > 80):
        raise _bad("metric is a short name without @, like views")
    return {
        "metric": metric,
        "value": _number(b, "value"),
        "measured_at": _when(b, "measured_at", required=True),
    }


_VALIDATORS = {
    "creator": _creator,
    "track": _track,
    "thread": _thread,
    "agreement": _agreement,
    "file": _file,
    "render": _render,
    "release": _release,
    "stat": _stat,
}


def no_such_kind(kind: object) -> str:
    return f"there is no record kind {str(kind)[:40]!r}; the kinds are {', '.join(KINDS)}"


def check_kind(kind: object) -> RecordKind:
    if kind not in KINDS:
        raise _bad(no_such_kind(kind))
    return kind


def validate(kind: RecordKind, body: dict[str, Any]) -> dict[str, Any]:
    """The body, cleaned, or ApiError("bad_request", <plain reason>)."""
    kind = check_kind(kind)
    if not isinstance(body, dict):
        raise _bad(f"a {kind} record's body must be an object")
    try:
        return _VALIDATORS[kind](body)
    except ApiError as e:
        raise _bad(f"a {kind} record: {e.reason}") from None


def key_of(kind: RecordKind, body: dict[str, Any]) -> str:
    """The record's key under its kind's rule (track: url, stat: `<metric>@<measured_at>`, ...).

    `body` is a cleaned body; a thread's key is not one of its fields and comes in `body["key"]`
    (record_put carries it), else its address when it has one."""
    if kind == "creator":
        key = str(body["channel_url"])
    elif kind == "track":
        key = str(body["url"])
    elif kind == "thread":
        given = body.get("key")
        if isinstance(given, str) and given.strip():
            key = normalise_ref(given)
        elif body.get("url"):
            key = str(body["url"])
        else:
            raise _bad("a thread record needs a key (a short name for the conversation)")
    elif kind == "agreement":
        key = str(body["creator_key"])
    elif kind == "file":
        key = str(body["file_id"])
    elif kind in ("render", "release"):
        key = str(body["track_key"])
    elif kind == "stat":
        key = f"{body['metric']}@{body['measured_at']}"
    else:
        raise _bad(f"there is no record kind {kind!r}")
    if len(key) > KEY_MAX:
        raise _bad(f"a record's key is at most {KEY_MAX} characters")
    return key
