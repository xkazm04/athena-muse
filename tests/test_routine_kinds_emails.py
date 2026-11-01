"""A creator's business email addresses (business Phase 2, WP2.2): optional, lower-cased and
de-duplicated, a malformed one refused by name; the inbox matches a sender against them."""

from __future__ import annotations

import pytest

from athena.errors import ApiError
from athena.records.kinds import CATALOG, validate

CREATOR = {"name": "Lumen", "channel_url": "https://youtube.example/@lumen", "followed": True}


def test_emails_are_optional() -> None:
    assert "emails" not in validate("creator", CREATOR)
    assert "emails" not in validate("creator", {**CREATOR, "emails": [" "]})


def test_emails_are_lower_cased_and_de_duplicated() -> None:
    body = validate(
        "creator",
        {**CREATOR, "emails": ["Lumen@Creators.Example", " lumen@creators.example ", "b@x.example"]},
    )
    assert body["emails"] == ["lumen@creators.example", "b@x.example"]


@pytest.mark.parametrize(
    "bad", ["lumen", "lumen@", "@creators.example", "a b@x.example", "a@x", "a@@x.example"]
)
def test_a_malformed_address_is_refused_by_name(bad: str) -> None:
    with pytest.raises(ApiError) as refused:
        validate("creator", {**CREATOR, "emails": [bad]})
    assert "is not an email address" in refused.value.reason


def test_emails_must_be_a_list_of_text() -> None:
    with pytest.raises(ApiError):
        validate("creator", {**CREATOR, "emails": "lumen@creators.example"})


def test_the_composer_is_told_about_emails() -> None:
    assert "emails" in CATALOG["creator"]["fields"]
