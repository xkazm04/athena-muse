"""The gate (hysteresis, slots, room, what is told) and a peer's view off the wire (ADR 0017).

athena/vitals/gate.py and wire.py, fed readings built by hand: no probe, no thread.
"""

from __future__ import annotations

from typing import Any

import pytest

from athena.vitals import (
    BATTERY_TASK_FLOOR_PCT,
    CPU_HOLD_PCT,
    CPU_HOLD_SAMPLES,
    CPU_RESUME_PCT,
    DISK_HOLD_MB,
    RAM_HOLD_PCT,
    RAM_RESUME_PCT,
    RAM_ROOM_PCT,
    TASK_CHARGE_DEFAULT_MB,
    TASKS_RUNNING_CAP,
    VITALS_STALE_S,
    VitalsView,
)
from athena.vitals.gate import Gate, slots_for
from athena.vitals.probe import Reading
from athena.vitals.wire import clean_view

TOTAL = 64_000


def reading(
    *,
    ram_pct: float | None = 40.0,
    cpu: float | None = 10.0,
    power: str | None = "mains",
    battery: int | None = None,
    disk: int | None = 100_000,
    total: int | None = TOTAL,
) -> Reading:
    free = None if ram_pct is None or total is None else round(total * (100 - ram_pct) / 100)
    return Reading(
        at="2026-10-24T12:00:00+00:00",
        cpu_pct=cpu,
        cores=16,
        ram_total_mb=total,
        ram_free_mb=free,
        gpus=[],
        power=power,  # type: ignore[arg-type]
        battery_pct=battery,
        disk_free_mb=disk,
    )


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def told() -> list[dict[str, Any]]:
    return []


@pytest.fixture
def gate(told: list[dict[str, Any]]) -> Gate:
    return Gate(publish=lambda kind, **fields: told.append({"kind": kind, **fields}))


def test_the_constants_are_the_briefs() -> None:
    assert (RAM_HOLD_PCT, RAM_RESUME_PCT, RAM_ROOM_PCT) == (92, 85, 85)
    assert (CPU_HOLD_PCT, CPU_HOLD_SAMPLES, CPU_RESUME_PCT) == (90, 3, 70)
    assert (BATTERY_TASK_FLOOR_PCT, DISK_HOLD_MB, TASK_CHARGE_DEFAULT_MB) == (30, 1024, 600)
    assert VITALS_STALE_S == 90.0


def test_no_reading_no_view_and_nothing_held(gate: Gate) -> None:
    assert gate.vitals() is None
    assert gate.held() is None


def test_ram_holds_at_92_and_resumes_only_below_85(gate: Gate) -> None:
    gate.observe(reading(ram_pct=91.0))
    assert gate.held() is None
    gate.observe(reading(ram_pct=93.0))
    assert gate.held() == "Waiting for room: RAM is at 93% (resumes below 85%)."
    gate.observe(reading(ram_pct=88.0))
    assert gate.held() == "Waiting for room: RAM is at 88% (resumes below 85%).", "hysteresis"
    gate.observe(reading(ram_pct=84.0))
    assert gate.held() is None


def test_cpu_holds_after_three_high_samples_in_a_row_and_resumes_below_70(gate: Gate) -> None:
    gate.observe(reading(cpu=95.0))
    gate.observe(reading(cpu=95.0))
    assert gate.held() is None, "two samples are a spike"
    gate.observe(reading(cpu=50.0))
    gate.observe(reading(cpu=95.0))
    gate.observe(reading(cpu=95.0))
    assert gate.held() is None, "the run was broken"
    gate.observe(reading(cpu=96.0))
    assert gate.held() == "Waiting for room: CPU is at 96% (resumes below 70%)."
    gate.observe(reading(cpu=80.0))
    assert gate.held() is not None, "hysteresis: still above the resume line"
    gate.observe(reading(cpu=69.0))
    assert gate.held() is None


def test_battery_holds_below_30_until_mains(gate: Gate) -> None:
    gate.observe(reading(power="battery", battery=55))
    assert gate.held() is None
    gate.observe(reading(power="battery", battery=29))
    assert gate.held() == "Waiting for room: the battery is at 29% (tasks resume at 30% or on mains)."
    gate.observe(reading(power="mains", battery=29))
    assert gate.held() is None


def test_disk_under_a_gigabyte_holds(gate: Gate) -> None:
    gate.observe(reading(disk=900))
    assert gate.held() == "Waiting for room: the disk has 900 MB free (needs 1024 MB)."
    gate.observe(reading(disk=1024))
    assert gate.held() is None


def test_every_held_reason_is_a_sentence_that_begins_waiting_for_room() -> None:
    for sample in (reading(ram_pct=95.0), reading(power="battery", battery=10), reading(disk=10)):
        fresh = Gate()
        fresh.observe(sample)
        held = fresh.held()
        assert held is not None and held.startswith("Waiting for room") and held.endswith(".")


def test_unknown_figures_hold_nothing_and_room_is_unknown(gate: Gate) -> None:
    gate.observe(reading(ram_pct=None, cpu=None, power="battery", battery=None, disk=None))
    assert gate.held() is None, "an unknown charge on battery does not hold a task"
    view = gate.vitals()
    assert view is not None
    assert view["room"] is None and view["slots"] == TASKS_RUNNING_CAP and view["held"] is None


def test_one_unknown_reading_does_not_erase_the_hysteresis(gate: Gate) -> None:
    gate.observe(reading(ram_pct=95.0))
    gate.observe(reading(ram_pct=None))
    assert gate.held() is None, "an unknown figure holds nothing"
    gate.observe(reading(ram_pct=88.0))
    assert gate.held() == "Waiting for room: RAM is at 88% (resumes below 85%).", "still held"
    gate.observe(reading(ram_pct=84.0))
    assert gate.held() is None


def test_slots_is_the_rooms_formula() -> None:
    # 64 GB, 40% used: 28800 MB spare / 600 = 48 -> capped at 3.
    assert slots_for(64_000, 38_400) == 3
    # 16 GB at 80% used: 13600 - 12800 = 800 spare / 600 = 1.
    assert slots_for(16_000, 3_200) == 1
    # Past the room line: none.
    assert slots_for(16_000, 1_600) == 0
    assert slots_for(None, None) == 3


def test_room_is_ok_tight_or_full(gate: Gate) -> None:
    small = 16_000
    gate.observe(reading(ram_pct=80.0, total=small))
    view = gate.vitals()
    assert view is not None and (view["room"], view["slots"]) == ("ok", 1)
    gate.observe(reading(ram_pct=86.0, total=small))  # past the room line, under the hold line
    view = gate.vitals()
    assert view is not None and (view["room"], view["slots"]) == ("tight", 0)
    gate.observe(reading(ram_pct=93.0, total=small))
    view = gate.vitals()
    assert view is not None and view["room"] == "full"
    assert view["held"] is not None and view["held"].startswith("Waiting for room: RAM")


def test_the_view_carries_every_key_and_no_runs_or_sleep(gate: Gate) -> None:
    gate.observe(reading())
    view = gate.vitals()
    assert view is not None
    assert list(view) == list(VitalsView.__annotations__)
    assert view["ram_pct"] == 40.0 and view["gpus"] == [] and view["power"] == "mains"
    assert view["runs"] is None and view["sleep"] is None


def test_vitals_changed_is_told_only_when_room_held_or_slots_move(
    gate: Gate, told: list[dict[str, Any]]
) -> None:
    gate.observe(reading(ram_pct=40.0, cpu=10.0))
    assert told == [{"kind": "vitals.changed", "room": "ok", "held": None, "slots": 3}]
    gate.observe(reading(ram_pct=45.0, cpu=30.0))
    gate.observe(reading(ram_pct=41.0, cpu=5.0))
    assert len(told) == 1, "numbers that move are not news"
    gate.observe(reading(ram_pct=93.0))
    assert told[-1]["room"] == "full" and told[-1]["held"].startswith("Waiting for room: RAM")
    assert len(told) == 2


def test_a_publish_that_raises_never_fails_a_reading() -> None:
    def boom(kind: str, **fields: Any) -> None:
        raise RuntimeError("bus closed")

    gate = Gate(publish=boom)
    gate.observe(reading())
    assert gate.vitals() is not None


def test_a_reading_older_than_the_staleness_line_is_unknown() -> None:
    clock = Clock()
    gate = Gate(clock=clock)
    gate.observe(reading(ram_pct=95.0))
    assert gate.held() is not None
    clock.now += VITALS_STALE_S  # exactly at the line: still fresh
    assert gate.held() is not None
    clock.now += 1
    assert gate.held() is None, "a frozen RAM hold fails open"
    view = gate.vitals()
    assert view is not None
    figures = ("cpu_pct", "cores", "ram_total_mb", "ram_free_mb", "ram_pct", "gpus")
    figures += ("power", "battery_pct", "disk_free_mb", "room", "held")
    assert all(view[k] is None for k in figures)  # type: ignore[literal-required]
    gate.observe(reading(ram_pct=40.0))
    assert gate.vitals()["ram_pct"] == 40.0  # type: ignore[index]


def test_a_peer_view_is_rebuilt_key_by_key() -> None:
    gate = Gate()
    gate.observe(reading())
    good = gate.vitals()
    assert clean_view(good) == good

    hostile = {
        "at": 7,
        "cpu_pct": "lots",
        "ram_pct": float("nan"),
        "cores": True,
        "gpus": [{"name": "x" * 1000, "util_pct": "9"}, "junk"],
        "power": "solar",
        "room": "roomy",
        "slots": 99,
        "held": "y" * 5000,
        "runs": {"turns": 4},
        "sleep": {"state": "idle"},
        "extra": "dropped",
    }
    view = clean_view(hostile)
    assert view is not None
    assert list(view) == list(VitalsView.__annotations__)
    assert view["at"] == "" and view["cpu_pct"] is None and view["ram_pct"] is None
    assert view["cores"] is None and view["power"] is None and view["room"] is None
    assert view["slots"] == TASKS_RUNNING_CAP
    assert view["held"] is not None and len(view["held"]) == 300
    assert view["gpus"] == [
        {"name": "x" * 300, "util_pct": None, "vram_total_mb": None, "vram_used_mb": None}
    ]
    assert view["runs"] is None and view["sleep"] is None
    assert clean_view("not a view") is None and clean_view(None) is None
