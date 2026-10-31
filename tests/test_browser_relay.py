"""The relay to her browser: one answer per call, deadlines, and a shell that is not there."""

from __future__ import annotations

import threading

from athena.browser.relay import Relay


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_no_shell_answers_no_browser_at_once() -> None:
    relay = Relay()
    result = relay.call("tabs", timeout=5)
    assert result == {
        "ok": False,
        "reason": "no_browser",
        "output": "Her browser is not open; the desktop app runs it.",
    }


def test_a_call_is_handed_to_the_shell_and_answered_once() -> None:
    relay = Relay()
    got: list[dict[str, object]] = []

    def shell() -> None:
        call = relay.next(2)
        assert call is not None
        got.append(call)
        assert relay.done(call["id"], {"ok": True, "output": "first"})
        assert not relay.done(call["id"], {"ok": True, "output": "second"})

    worker = threading.Thread(target=shell)
    relay.next(0)  # the shell has polled: it is there
    worker.start()
    result = relay.call("page_read", {"ref": "ref_x_1"}, tab=3, load=2, url="http://127.0.0.1:8781/a")
    worker.join(2)
    assert result == {"ok": True, "output": "first"}
    assert got[0]["hand"] == "page_read" and got[0]["tab"] == 3 and got[0]["load"] == 2
    assert got[0]["args"] == {"ref": "ref_x_1"} and got[0]["url"] == "http://127.0.0.1:8781/a"


def test_a_call_past_its_deadline_is_timeout_and_a_late_answer_is_dropped() -> None:
    relay = Relay()
    relay.next(0)
    result = relay.call("page_wait", timeout=0.05)
    assert result["reason"] == "timeout"
    assert relay.next(0) is None  # the expired call was taken back from the queue
    assert not relay.done("hand_000000000000", {"ok": True, "output": "late"})


def test_a_shell_that_stopped_polling_is_gone() -> None:
    clock = Clock()
    relay = Relay(clock)
    relay.next(0)
    assert relay.connected()
    clock.now += 41
    assert not relay.connected()
