"""The kind catalog (business Phase 1): every kind validates one good body and refuses a missing field
and a wrong value in plain words; keys follow each kind's rule, with addresses normalised."""

from __future__ import annotations

import typing
from typing import Any

import pytest

from athena.contracts import TEXT_MAX, RecordKind
from athena.errors import ApiError
from athena.records.kinds import CATALOG, FINDS, key_of, validate

CREATOR = "https://youtube.example/@lumen"
TRACK = "https://youtube.example/watch?v=1"

#: One valid body per kind, the field a missing test drops, and a field with a wrong value.
CASES: dict[RecordKind, tuple[dict[str, Any], str, tuple[str, Any]]] = {
    "creator": ({"name": "Lumen", "channel_url": CREATOR, "followed": True}, "name", ("followed", "yes")),
    "track": (
        {"url": TRACK, "title": "Night Ferry", "creator_key": CREATOR, "found_at": "2026-11-01T12:00:00Z"},
        "title",
        ("verdict", "maybe"),
    ),
    "thread": (
        {"creator_key": CREATOR, "channel": "mail_web", "last_at": "2026-11-01T12:00:00Z"},
        "last_at",
        ("channel", "fax"),
    ),
    "agreement": (
        {"creator_key": CREATOR, "state": "agreed", "thread_key": "offer", "plan": "pro"},
        "thread_key",
        ("plan", "gold"),
    ),
    "file": ({"file_id": "fil_0a1b2c3d4e5f", "track_key": TRACK}, "file_id", ("track_key", 7)),
    "render": ({"track_key": TRACK, "state": "staged"}, "track_key", ("state", "done")),
    "release": (
        {
            "track_key": TRACK,
            "title": "Night Ferry (video)",
            "track_url": TRACK,
            "creator_channel_url": CREATOR,
            "genre": "lo-fi",
            "credits": "Music by Lumen",
        },
        "credits",
        ("track_url", "ftp://youtube.example/x"),
    ),
    "stat": (
        {"metric": "views", "value": 120, "measured_at": "2026-11-01T12:00:00Z"},
        "metric",
        ("value", "a lot"),
    ),
}


def test_the_catalog_has_every_kind_and_only_creators_and_tracks_are_finds() -> None:
    kinds = set(typing.get_args(RecordKind))
    assert set(CATALOG) == kinds == set(CASES)
    for kind, spec in CATALOG.items():
        assert spec["kind"] == kind and spec["description"] and spec["fields"]
        assert set(spec["numeric"]) <= set(spec["fields"])
    assert {"creator", "track"} == FINDS
    assert CATALOG["stat"]["numeric"] == ["value"]


@pytest.mark.parametrize("kind", list(CASES))
def test_a_valid_body_passes_and_a_missing_field_or_a_wrong_value_fails_in_words(kind: RecordKind) -> None:
    good, required, (field, wrong) = CASES[kind]
    cleaned = validate(kind, good)
    assert set(cleaned) <= set(CATALOG[kind]["fields"])
    with pytest.raises(ApiError) as missing:
        validate(kind, {k: v for k, v in good.items() if k != required})
    assert missing.value.error == "bad_request" and required in missing.value.reason
    with pytest.raises(ApiError) as bad:
        validate(kind, {**good, field: wrong})
    assert bad.value.error == "bad_request" and field in bad.value.reason
    assert bad.value.reason.startswith(f"a {kind} record: ")


def test_strings_are_trimmed_and_cut_unknown_fields_dropped_and_empty_optionals_absent() -> None:
    body = {
        "url": f"  {TRACK}  ",
        "title": "  Night Ferry ",
        "creator_key": CREATOR,
        "found_at": "2026-11-01T12:00:00Z",
        "note": "x" * (TEXT_MAX + 50),
        "genre": "   ",
        "views": 9,
    }
    cleaned = validate("track", body)
    assert cleaned["title"] == "Night Ferry" and len(cleaned["note"]) == TEXT_MAX
    assert "genre" not in cleaned and "views" not in cleaned


def test_addresses_must_be_http_and_keys_are_normalised() -> None:
    with pytest.raises(ApiError, match="http"):
        validate("creator", {"name": "L", "channel_url": "javascript:alert(1)", "followed": False})
    cleaned = validate(
        "creator", {"name": "L", "channel_url": "HTTPS://YouTube.Example/@Lumen/", "followed": False}
    )
    assert cleaned["channel_url"] == "https://youtube.example/@Lumen"  # host lower-cased, path kept
    assert key_of("creator", cleaned) == "https://youtube.example/@Lumen"


def test_each_kind_keys_by_its_rule() -> None:
    def key(kind: RecordKind, extra: dict[str, Any] | None = None) -> str:
        return key_of(kind, {**validate(kind, CASES[kind][0]), **(extra or {})})

    assert key("creator") == CREATOR
    assert key("track") == TRACK
    assert key("thread", {"key": " lumen-offer "}) == "lumen-offer"
    assert key("agreement") == CREATOR
    assert key("file") == "fil_0a1b2c3d4e5f"
    assert key("render") == key("release") == TRACK
    assert key("stat") == "views@2026-11-01T12:00:00Z"
    with pytest.raises(ApiError, match="needs a key"):
        key("thread")
    with_url = validate("thread", {**CASES["thread"][0], "url": "https://mail.example/t/1/"})
    assert key_of("thread", with_url) == "https://mail.example/t/1"


def test_an_unknown_kind_and_a_body_that_is_not_an_object_are_refused() -> None:
    with pytest.raises(ApiError, match="no record kind"):
        validate("invoice", {})  # type: ignore[arg-type]
    with pytest.raises(ApiError, match="object"):
        validate("stat", [1, 2])  # type: ignore[arg-type]
    with pytest.raises(ApiError, match="number"):
        validate("stat", {**CASES["stat"][0], "value": True})
    with pytest.raises(ApiError, match="date and time"):
        validate("stat", {**CASES["stat"][0], "measured_at": "yesterday"})
