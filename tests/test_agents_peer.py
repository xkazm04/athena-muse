"""An agent's unattended call to a paired device's copy of an app (spark agent-leases): B still holds
its floor (a gated tool needs an approval id), gets the grant card's id as that approval, and keeps the
agent's name beside it in its audit, as text only. Two daemons over a real loopback socket, B's app the
stdio fake (the pattern of test_peer_apps)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from agents_kit import URL, text
from apps_fake import stdio_argv
from athena.peer import apps as peer_apps
from test_peer_apps import Rig


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    made = Rig(tmp_path)
    yield made
    made.close()


def _call(rig: Rig, token: str, name: str) -> dict[str, object]:
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": {}}}
    got = rig.client_a.post("/mcp", json=body, headers={"Authorization": f"Bearer {token}"})
    assert got.status_code == 200, got.text
    result: dict[str, object] = got.json()["result"]
    return result


def test_the_offering_device_audits_the_agent_beside_the_grant(rig: Rig) -> None:
    rig.a.mcp_url = URL
    space = rig.a.spaces.create({"name": "Mix"})["id"]
    mine = rig.a.apps.add(space, {"kind": "mcp_stdio", "argv": stdio_argv(), "label": "Queue"})
    attached = rig.client_a.post(
        f"/spaces/{space}/apps/{mine['app_id']}/remotes",
        json={"peer_id": rig.b_id, "remote_app_id": rig.app_id},
    )
    assert attached.status_code == 200, attached.text
    made = rig.client_a.post(
        f"/spaces/{space}/agents",
        json={
            "label": "Claude",
            "ceiling": {"tools": ["queue_on_studio_pc__erase"], "max_calls": 1, "minutes": 10},
        },
    )
    assert made.status_code == 201, made.text
    grant = made.json()["lease"]["ceiling"]["card_id"]
    token = made.json()["token"]
    assert rig.client_a.post(f"/decisions/{grant}", json={"verdict": "approve"}).status_code == 200
    ran = _call(rig, token, "queue_on_studio_pc__erase")
    assert "structuredContent" not in ran and "erase ran with {}" in text(ran)  # type: ignore[arg-type]
    filed = _call(rig, token, "queue_on_studio_pc__erase")  # the one allowed call is spent
    assert "structuredContent" in filed
    rows = rig.audit()
    assert [(r["tool"], r["outcome"], r.get("approval_id"), r.get("agent")) for r in rows] == [
        ("erase", "ran", grant, "Claude")
    ]


def test_the_agent_field_is_audit_text_only(rig: Rig) -> None:
    # B's floor stands whatever the agent field says: a gated tool without an approval is refused.
    with pytest.raises(Exception, match="signature"):
        peer_apps.call_remote(rig.a, rig.b_id, rig.app_id, "erase", {}, None, agent="Trusted Agent")
    long = "  An   agent " + "x" * 80
    peer_apps.call_remote(rig.a, rig.b_id, rig.app_id, "look", {}, None, agent=long)
    rows = rig.audit()
    assert [(r["tool"], r["outcome"]) for r in rows] == [("erase", "approval_missing"), ("look", "ran")]
    assert rows[0]["agent"] == "Trusted Agent"
    assert rows[1]["agent"] == ("An agent " + "x" * 80)[: peer_apps.AGENT_MAX]
    peer_apps.call_remote(rig.a, rig.b_id, rig.app_id, "look", {}, None)
    assert "agent" not in rig.audit()[-1]  # absent is fine, and the body is what it always was
