"""The apps seam (ADR 0025, 0026): two daemons on this computer and a REAL local app (Gravitone's agent
door), through the daemons' own routes, her tool dispatch and a real loopback peer socket.

    GT_TOKEN=<an act-scope token> uv run python scripts/apps_seam.py [--url http://localhost:3150/api/mcp]
        [--out runs/apps-seam.json]

A holds the project; B ("Studio-PC") wires the same Gravitone at device level, offers it, and names an
output folder. Both daemons run in this process (B's peer listener admits loopback, as the peer tests
do; the real overlay is the owner's two-computer run). What it walks:
1. A wires Gravitone in the project as an app on this computer, with its token; the check lists its tools
   and their class (gt_read/gt_spend on their own, gt_launch/gt_job ask first).
2. B wires it at device level, offered, with an output folder; A sees B's offer and attaches it.
3. Her tools: `<slug>__gt_read` and `<slug>_on_studio_pc__gt_read`; no offered schema keeps a top-level
   combinator an engine would refuse.
4. A read runs at once on this computer's copy and on B's, each answering Gravitone's project list.
5. A gated `gt_job status` on B's copy files a card on A; signed, it runs once and B's audit holds the
   card's id.
6. `app_fetch` brings a file from B's output folder into A's project files, byte-identical.
Nothing spends: every Gravitone call here reads, or asks a job's status. Pass/fail per step, exit 1 on any fail.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from starlette.testclient import TestClient  # noqa: E402

from athena.app import Daemon  # noqa: E402
from athena.apps import tools as apps_tools  # noqa: E402
from athena.engine import ToolCall  # noqa: E402
from athena.peer.listener import PeerHost  # noqa: E402
from athena.peer.overlay import Overlay  # noqa: E402
from athena.server import create_app  # noqa: E402
from athena.turn import dispatch  # noqa: E402

LOCAL = "loopback-seam"
H = {"Authorization": f"Bearer {LOCAL}"}
RENDER = b"RIFF" + bytes(range(256)) * 64 + b"seam-render"


class MemorySeal:
    kind = "memory"

    def __init__(self) -> None:
        self.held: dict[str, str] = {}

    def seal(self, name: str, value: str) -> None:
        self.held[name] = value

    def unseal(self, name: str) -> str | None:
        return self.held.get(name)

    def destroy(self, name: str) -> None:
        self.held.pop(name, None)


def peer_host(root: Path) -> PeerHost:
    up = Overlay("up", "127.0.0.1")
    return PeerHost(root, port=0, probe=lambda: up, seal=MemorySeal(), admit_loopback=True)  # type: ignore[arg-type]


class Seam:
    def __init__(self, root: Path, url: str, token: str) -> None:
        self.steps: list[dict[str, Any]] = []
        self.url, self.token = url, token
        self.a, self.b = Daemon.open(root / "a"), Daemon.open(root / "b")
        self.ha, self.hb = peer_host(root / "pa"), peer_host(root / "pb")
        self.a.peers, self.b.peers = self.ha, self.hb
        self.a_id = self.ha.identity.identity.device_id
        self.b_id = self.hb.identity.identity.device_id
        self.hb.registry.admit(self.a_id, name="Laptop", kind="pc", grants=["apps"], token="tok-a", expires_days=None)
        self.ha.registry.admit(self.b_id, name="Studio-PC", kind="pc", grants=["chat"], token="tok-b", expires_days=None)
        self.ca = TestClient(create_app(self.a, LOCAL), headers=H)
        self.cb = TestClient(create_app(self.b, LOCAL), headers=H)
        self.hb.reconcile()
        assert self.hb.bound is not None
        self.ha.keys.keep(self.b_id, f"http://127.0.0.1:{self.hb.bound[1]}", "tok-a")
        self.out = root / "renders-on-b"
        self.out.mkdir()
        (self.out / "take1.wav").write_bytes(RENDER)

    def step(self, name: str, ok: bool, **seen: Any) -> bool:
        self.steps.append({"step": name, "ok": ok, **seen})
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {json.dumps(seen)[:600]}"))
        return ok

    def call(self, space: str, name: str, args: dict[str, Any]) -> Any:
        return dispatch(self.a, space, ToolCall(f"seam_{len(self.steps)}", name, args))

    def run(self) -> None:
        a, ca, cb = self.a, self.ca, self.cb
        space = ca.post("/spaces", json={"name": "Music channel"}).json()["id"]

        made = ca.post(f"/spaces/{space}/apps", json={"kind": "mcp_http", "label": "Gravitone", "address": self.url, "token": self.token})
        app = made.json()
        checked = ca.post(f"/spaces/{space}/apps/{app.get('app_id')}/probe").json()
        access = {t["name"]: t["access"] for t in checked.get("tools", [])}
        self.step(
            "1 A wires Gravitone; the check lists its tools and their class",
            made.status_code == 201 and checked.get("status") == "ok" and access.get("gt_read") == "auto"
            and access.get("gt_launch") == "gated" and access.get("gt_job") == "gated"
            and self.token not in json.dumps(checked) and checked.get("sealed") is True,
            status=checked.get("status"), reason=checked.get("reason"), access=access,
        )

        offered = cb.post("/apps", json={"kind": "mcp_http", "label": "Gravitone", "address": self.url, "token": self.token, "offered": True, "output_dir": str(self.out)}).json()
        cb.post(f"/apps/{offered.get('app_id')}/probe")
        seen = ca.get(f"/devices/{self.b_id}/apps")
        offers = seen.json().get("offered", [])
        attached = ca.post(f"/spaces/{space}/apps/{app['app_id']}/remotes", json={"peer_id": self.b_id, "remote_app_id": offered.get("app_id")})
        remotes = attached.json().get("remotes", []) if attached.status_code == 200 else []
        self.step(
            "2 B offers its Gravitone; A sees the offer (no address, token or folder) and attaches it",
            seen.status_code == 200 and len(offers) == 1 and attached.status_code == 200 and len(remotes) == 1
            and all(s not in seen.text for s in (self.url, self.token, "output_dir", str(self.out).replace("\\", "\\\\"))),
            offers=offers[:1], attach=attached.status_code, body=attached.text[:300],
        )

        tools = {t["function"]["name"]: t["function"] for t in apps_tools.offered(a, space)}
        slug = app.get("slug", "gravitone")
        local_read, remote_read = f"{slug}__gt_read", f"{slug}_on_studio_pc__gt_read"
        combinators = [n for n, f in tools.items() if any(k in f["parameters"] for k in ("oneOf", "anyOf", "allOf"))]
        self.step(
            "3 her tools name both copies, and no schema keeps a top-level combinator",
            local_read in tools and remote_read in tools and f"{slug}_on_studio_pc__gt_job" in tools and not combinators,
            names=sorted(tools), combinators=combinators,
        )

        here = self.call(space, local_read, {"op": "projects"})
        there = self.call(space, remote_read, {"op": "projects"})
        self.step(
            "4 a read runs at once on this computer's copy and on Studio-PC's",
            not here.refused and not there.refused and here.card is None and there.card is None
            and "answered" in here.result and "answered" in there.result,
            here=here.result[:300], there=there.result[:300],
        )

        filed = self.call(space, f"{slug}_on_studio_pc__gt_job", {"op": "status", "jobId": "job:seam:none"})
        card = filed.card or {}
        before = len(self._audit())
        signed = ca.post(f"/decisions/{card.get('id')}", json={"verdict": "approve"}) if card else None
        time.sleep(0.5)
        calls = [r for r in self._audit()[before:] if r.get("tool") == "gt_job"]
        self.step(
            "5 a gated call on Studio-PC's copy is a card here; signed, it runs once with the card's id",
            bool(card) and card.get("action") == "app_act" and signed is not None and signed.status_code == 200
            and len(calls) == 1 and calls[0].get("approval_id") == card.get("id"),
            card=card.get("label"), signed=None if signed is None else signed.text[:300], audit=calls,
        )

        fetched = self.call(space, "app_fetch", {"app": f"{slug}_on_studio_pc", "path": "take1.wav"})
        files = a.files.list(space)
        got = next((f for f in files if f["name"] == "take1.wav"), None)
        same = got is not None and a.files.path(got).read_bytes() == RENDER
        self.step(
            "6 a file from Studio-PC's output folder lands in the project's files, byte-identical",
            not fetched.refused and same and got is not None and "Studio-PC" in got["origin"],
            answer=fetched.result[:300], file=got,
        )

    def _audit(self) -> list[dict[str, Any]]:
        path = self.hb.audit.path
        if not path.exists():
            return []
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [r for r in rows if r.get("act") == "app_call"]

    def close(self) -> None:
        self.ha.close()
        self.hb.close()
        for d in (self.a, self.b):
            d.app_clients.shutdown()
            d.store.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:3150/api/mcp")
    parser.add_argument("--out", default="")
    opts = parser.parse_args()
    token = os.environ.get("GT_TOKEN", "")
    if not token:
        print("Set GT_TOKEN to an act-scope Gravitone token (node pipeline/token.mts mint --name athena --scope act).")
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        seam = Seam(Path(tmp), opts.url, token)
        try:
            seam.run()
        finally:
            seam.close()
    ok = all(s["ok"] for s in seam.steps)
    print(f"{sum(s['ok'] for s in seam.steps)}/{len(seam.steps)} steps passed")
    if opts.out:
        Path(opts.out).parent.mkdir(parents=True, exist_ok=True)
        Path(opts.out).write_text(json.dumps({"steps": seam.steps}, indent=2), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
