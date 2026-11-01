"""Signing a twin's web card (business Phase 2): one recipe per channel through her browser, every
control found again by its label at sign time, a missing control stops with the step in plain words,
and only an edit becomes an example for that channel."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.testclient import TestClient

from athena.app import Daemon
from athena.contracts import ROUTES, Card
from athena.twins import web
from athena.twins.voice import compile_voice
from twins_web_kit import (
    ADDRESS,
    BIO_URL,
    COMPOSE,
    CREATOR,
    DRAFTED,
    INBOX,
    MAILBOX,
    THREAD_URL,
    TRACK,
    TRACK_URL,
    DraftEngine,
    WebShell,
    mailbox,
    thread,
    web_twin,
)

EDITED = "Hi Mira! Your track stopped me mid-scroll. Could I make it a visualizer, with a credit to you?"


def drafted(daemon: Daemon, channel: str, *, reply: bool = False) -> tuple[Card, str]:
    space, twin_id = web_twin(daemon)
    mailbox(daemon, space)
    key = thread(daemon, space) if reply else None
    to = TRACK if channel == "comment" else CREATOR
    card = web.draft(
        daemon, DraftEngine(subject="A visualizer for you"), space, channel, to, "offer", "", key
    )  # type: ignore[arg-type]
    assert card is not None
    return card, twin_id


def sign(client: TestClient, card: Card, text: str | None = None) -> Any:
    body: dict[str, Any] = {"verdict": "approve"}
    if text is not None:
        body["edited"] = {"text": text}
    return client.post(ROUTES["decision"].format(card_id=card["id"]), json=body)


def hands(shell: WebShell) -> list[tuple[str, ...]]:
    """The relay calls that act or open, in order: (hand, page or url, label, value)."""
    out: list[tuple[str, ...]] = []
    for call in shell.calls:
        if call["hand"] in ("open", "wheel"):
            out.append((call["hand"], str(call["args"].get("url") or call["args"].get("say"))))
    return out


def examples(daemon: Daemon, twin_id: str) -> list[dict[str, Any]]:
    return daemon.twins.rows("examples", twin_id)


def test_a_mail_reply_opens_the_thread_finds_the_reply_box_fills_and_sends(
    daemon: Daemon, client: TestClient
) -> None:
    card, twin_id = drafted(daemon, "mail_web", reply=True)
    with WebShell(daemon.relay) as shell:
        r = sign(client, card)
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "approved"
    assert r.json()["outcome"] == f"Sent to {ADDRESS} by mail, in the conversation on 127.0.0.1:8790."
    assert hands(shell) == [("open", THREAD_URL)]
    assert all(not c["args"].get("hidden") for c in shell.calls if c["hand"] == "open")  # in front of her
    assert shell.acts == [
        ("click", THREAD_URL, "Reply", ""),
        ("fill", f"{THREAD_URL}#reply", "Reply", DRAFTED),
        ("click", f"{THREAD_URL}#reply", "Send", ""),
    ]
    assert examples(daemon, twin_id) == []  # signed as drafted: no example
    assert daemon.twins.one("channels", twin_id, "mail_web")["last_at"]  # type: ignore[index]


def test_a_new_mail_opens_new_message_on_the_mailbox_and_fills_to_subject_and_body(
    daemon: Daemon, client: TestClient
) -> None:
    card, twin_id = drafted(daemon, "mail_web")
    with WebShell(daemon.relay) as shell:
        r = sign(client, card, EDITED)
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == f"Sent to {ADDRESS} by mail from 127.0.0.1:8790."
    assert hands(shell) == [("open", INBOX)]  # the mailbox site's own address
    assert shell.acts == [
        ("click", INBOX, "New message", ""),
        ("fill", COMPOSE, "To", ADDRESS),
        ("fill", COMPOSE, "Subject", "A visualizer for you"),
        ("fill", COMPOSE, "Message", EDITED),  # the person's words, not the draft's
        ("click", COMPOSE, "Send", ""),
    ]
    kept = examples(daemon, twin_id)
    assert [(e["channel"], e["text"]) for e in kept] == [("mail_web", EDITED)]  # one example, its channel
    assert EDITED in compile_voice(daemon, twin_id, "mail_web")
    assert EDITED not in compile_voice(daemon, twin_id, "comment")


def test_a_comment_opens_the_track_fills_the_comment_box_and_posts(
    daemon: Daemon, client: TestClient
) -> None:
    card, twin_id = drafted(daemon, "comment")
    with WebShell(daemon.relay) as shell:
        r = sign(client, card)
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "Commented on Night Drive in Glass."
    assert hands(shell) == [("open", TRACK_URL)]
    assert shell.acts == [("fill", TRACK_URL, "Add a comment", DRAFTED), ("click", TRACK_URL, "Comment", "")]
    assert examples(daemon, twin_id) == []


def test_a_bio_message_opens_the_link_in_front_and_hands_the_wheel(
    daemon: Daemon, client: TestClient
) -> None:
    card, twin_id = drafted(daemon, "bio")
    with WebShell(daemon.relay) as shell:
        r = sign(client, card, EDITED)
    assert r.status_code == 200, r.text
    assert r.json()["outcome"].startswith("Handed you the message to send yourself, on linktr.ee")
    opened, handed = hands(shell)
    assert opened == ("open", BIO_URL)
    assert handed[0] == "wheel" and handed[1].startswith('Send this yourself: "Hi Mira!')
    assert shell.acts == []  # she types nothing on a creator's page; the person sends it
    assert [(e["channel"], e["text"]) for e in examples(daemon, twin_id)] == [("bio", EDITED)]


@pytest.mark.parametrize(
    ("channel", "page", "gone", "said"),
    [
        ("comment", TRACK_URL, "Comment", 'could not find the "Comment" button (step 2 of 2, posting)'),
        ("comment", TRACK_URL, "Add a comment", "could not find the comment box (step 1 of 2, the comment)"),
        ("mail_web", COMPOSE, "Subject", "could not find the Subject field (step 3 of 5, the subject)"),
    ],
)
def test_a_missing_control_stops_says_which_step_and_the_card_waits(
    daemon: Daemon, client: TestClient, channel: str, page: str, gone: str, said: str
) -> None:
    card, twin_id = drafted(daemon, channel)
    with WebShell(daemon.relay) as shell:
        shell.controls[page] = [c for c in shell.controls[page] if c[1] != gone]
        r = sign(client, card, EDITED)
    assert r.status_code == 400
    reason = r.json()["reason"]
    assert reason.startswith("Nothing was sent") and said in reason
    assert daemon.gate.get(card["id"])["state"] == "waiting"  # it can be signed again
    assert not any(a[0] == "click" and a[2] in ("Send", "Comment") for a in shell.acts)  # nothing sent
    assert examples(daemon, twin_id) == []  # nothing went, so nothing is learned


def test_with_her_browser_closed_nothing_is_sent_and_the_card_waits(
    daemon: Daemon, client: TestClient
) -> None:
    card, _ = drafted(daemon, "comment")
    r = sign(client, card)
    assert r.status_code == 400
    assert r.json()["reason"] == web.CLOSED
    assert daemon.gate.get(card["id"])["state"] == "waiting"
    with WebShell(daemon.relay):
        assert sign(client, card).status_code == 200  # signed again once her browser is open


def test_mail_never_writes_on_a_page_that_is_not_one_of_the_projects_sites(
    daemon: Daemon, client: TestClient
) -> None:
    card, _ = drafted(daemon, "mail_web", reply=True)
    daemon.sites.remove(card["space_id"], MAILBOX)
    with WebShell(daemon.relay) as shell:
        r = sign(client, card)
    assert r.status_code == 400
    assert "127.0.0.1:8790 is not one of this project's sites" in r.json()["reason"]
    assert shell.calls == []  # her browser was never asked


def test_mail_waits_for_the_person_to_sign_in_again(daemon: Daemon, client: TestClient) -> None:
    card, _ = drafted(daemon, "mail_web")
    mailbox(daemon, card["space_id"], access="signed_out")
    with WebShell(daemon.relay) as shell:
        r = sign(client, card)
    assert r.status_code == 400
    assert "you are not signed in to 127.0.0.1:8790" in r.json()["reason"]
    assert shell.acts == []


def test_a_declined_web_card_sends_nothing_and_learns_nothing(daemon: Daemon, client: TestClient) -> None:
    card, twin_id = drafted(daemon, "comment")
    with WebShell(daemon.relay) as shell:
        r = client.post(ROUTES["decision"].format(card_id=card["id"]), json={"verdict": "decline"})
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "declined"
    assert shell.acts == [] and examples(daemon, twin_id) == []
