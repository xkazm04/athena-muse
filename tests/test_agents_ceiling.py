"""An agent's unattended calls, the rule alone (spark agent-leases): only a signed, live, unexpired
ceiling that names an app tool and has a call left runs a call without a card; only app tools can be
named; eight calls at once against five allowed run five."""

from __future__ import annotations

import threading
from typing import Any

import pytest

from athena.agents.ceiling import Ceiling, check, verdict
from athena.contracts import AGENT_CALLS_MAX, AGENT_FILE_MB_MAX, AGENT_MINUTES_MAX
from athena.errors import ApiError

APP = ["queue__erase", "queue__look", "queue_on_studio_pc__erase"]


def _rule(**over: Any) -> str:
    given: dict[str, Any] = {
        "signed": True,
        "ended": False,
        "deadline": 100.0,
        "now": 50.0,
        "tools": ["queue__erase"],
        "used": 0,
        "max_calls": 3,
        "name": "queue__erase",
    }
    return verdict(**{**given, **over})


def test_only_a_signed_live_unexpired_named_call_with_one_left_runs() -> None:
    assert _rule() == "ok"
    assert _rule(signed=False) == "unsigned"
    assert _rule(ended=True) == "ended"
    assert _rule(now=100.0) == "expired"
    assert _rule(name="queue__look") == "not_named"
    assert _rule(used=3) == "used_up"
    assert _rule(used=2) == "ok"


NEVER = ["page_click", "page_open", "twin_send", "add_app", "remember", "forget", "record_put", "setup_act"]


@pytest.mark.parametrize(
    "name", [*NEVER, "agent_grant", "app_fetch", "propose_brief", "portal_act", "app_act"]
)
def test_no_action_outside_the_apps_runs_unattended_even_when_named(name: str) -> None:
    assert _rule(tools=[name], name=name) == "not_named"


def test_a_ceiling_names_only_the_projects_app_tools_the_agent_may_use() -> None:
    limits = {"tools": ["queue__erase"], "max_calls": 5, "minutes": 30}
    assert check(limits, APP, APP) == (["queue__erase"], 5, 30, None)
    assert check({**limits, "file_mb": 2}, APP, APP)[3] == 2 * 1024 * 1024
    for name in ("page_click", "twin_send", "add_app", "remember", "record_put", "setup_act", "agent_grant"):
        with pytest.raises(ApiError, match="Only an app's own tools") as refused:
            check({**limits, "tools": [name]}, [*APP, name], [*APP, name])
        assert refused.value.status == 400
    with pytest.raises(ApiError, match="Only an app's own tools"):
        check({**limits, "tools": ["app_fetch"]}, APP, [*APP, "app_fetch"])
    with pytest.raises(ApiError, match="cannot use queue__erase"):
        check(limits, APP, ["queue__look"])
    for bad in (
        {**limits, "tools": []},
        {**limits, "max_calls": 0},
        {**limits, "max_calls": AGENT_CALLS_MAX + 1},
        {**limits, "max_calls": True},
        {**limits, "minutes": AGENT_MINUTES_MAX + 1},
        {**limits, "file_mb": AGENT_FILE_MB_MAX + 1},
        "five calls",
    ):
        with pytest.raises(ApiError):
            check(bad, APP, APP)


def test_eight_calls_at_once_against_five_allowed_run_five() -> None:
    ceiling = Ceiling(["queue__erase"], 5, deadline=float("inf"), signed=True)
    kept: list[int] = []
    start = threading.Barrier(8)
    said: list[str] = []

    def one() -> None:
        start.wait()
        said.append(ceiling.take("queue__erase", lambda c: kept.append(c.used)))

    threads = [threading.Thread(target=one) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(said) == ["ok"] * 5 + ["used_up"] * 3
    assert ceiling.used == 5 and kept == [1, 2, 3, 4, 5]  # written under the lock, never backwards


def test_a_ceiling_never_grows_and_its_view_is_the_wire_shape() -> None:
    ceiling = Ceiling(["queue__erase"], 2, deadline=0.0, file_bytes=1024, card_id="card_1")
    view = ceiling.view()
    assert view == {
        "tools": ["queue__erase"],
        "max_calls": 2,
        "used": 0,
        "deadline": "1970-01-01T00:00:00Z",
        "signed": False,
        "file_bytes": 1024,
        "card_id": "card_1",
    }
    assert "fetched" not in view and ceiling.stored()["fetched"] == 0
