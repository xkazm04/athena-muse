"""The routines fixture for the desktop (business Phase 2): the simulated music channel seeded by
scripts/business_fixture.py, its routines run through the real host against a simulated browser
(tests/browser_kit.FakeShell) and a priced stand-in engine (tests/routines_kit.PricedEngine), so every
row state the front page draws comes from the daemon's own code. Simulated: no real page, no model.

    uv run python scripts/routines_fixture.py apps/desktop/src/main/report/routines.fixture.json

States produced: stats skipped (her browser is closed) then ran; watch stopped at its spending limit
(partial); inbox skipped (no mailbox address set) and then paused; outreach skipped (nothing to do).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

from athena.app import Daemon  # noqa: E402
from browser_kit import FakeShell  # noqa: E402
from business_fixture import SITE, seed  # noqa: E402
from routines_kit import PricedEngine  # noqa: E402

from athena.routines.host import Host  # noqa: E402

ANALYTICS = f"{SITE}/studio/analytics"


def build() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        daemon = Daemon.open(Path(tmp))
        try:
            space = seed(daemon)
            daemon.sites.add(space, SITE, "YouTube (simulated)", f"{SITE}/account", "The channel's site")
            daemon.sites.looked(space, SITE, "signed_in", "simulated")
            routines = {r["kind"]: r for r in daemon.routines.ensure_defaults(space)}
            daemon.routines.change(routines["stats"]["id"], {"url": ANALYTICS})

            pricey = Host(daemon, lambda: PricedEngine(cost=0.3, answer={"tracks": []}))
            cheap = Host(
                daemon,
                lambda: PricedEngine(
                    cost=0.002,
                    answer={
                        "readings": [
                            {"metric": "views", "value": 612},
                            {"metric": "subscribers", "value": 48},
                        ]
                    },
                ),
            )
            cheap.run_now(
                routines["stats"]["id"]
            )  # skipped: her browser is closed (the desktop is not running)
            with FakeShell(daemon.relay):
                pricey.run_now(routines["watch"]["id"])  # partial: the first page spent past the ceiling
                cheap.run_now(routines["stats"]["id"])  # ran
                cheap.run_now(routines["inbox"]["id"])  # skipped: no mailbox address
                cheap.run_now(routines["outreach"]["id"])  # skipped: every kept creator has a conversation
            daemon.routines.change(routines["inbox"]["id"], {"state": "paused"})

            listed = daemon.routines.of_space(space)
            return {
                "simulated": True,
                "routines": {"routines": listed},
                "runs": {r["id"]: {"runs": daemon.routines.runs(r["id"])} for r in listed},
            }
        finally:
            daemon.store.close()


def main() -> int:
    out = Path(sys.argv[1])
    data = build()
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    for r in data["routines"]["routines"]:
        last = r.get("last_run", {})
        print(r["kind"], r["state"], last.get("outcome"), last.get("reason"), last.get("note", "")[:80])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
