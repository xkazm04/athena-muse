"""The gate: from a reading of this PC to slots, room and the held reason (ADR 0017, vitals).

One gate per PC reads the sampler's latest reading and answers three things:

``held``
    The named reason background work should wait, as a sentence beginning "Waiting for room", or
    ``None``. It holds on **RAM** at or above :data:`RAM_HOLD_PCT` (until it falls below
    :data:`RAM_RESUME_PCT`), **CPU** at or above :data:`CPU_HOLD_PCT` for :data:`CPU_HOLD_SAMPLES`
    readings in a row (until below :data:`CPU_RESUME_PCT`), **battery** below
    :data:`BATTERY_TASK_FLOOR_PCT` and **disk** under :data:`DISK_HOLD_MB` free. The two lines of
    each hold are hysteresis: a PC hovering at the line does not flap.

``slots``
    ``min(TASKS_RUNNING_CAP, floor(max(0, ram_total * RAM_ROOM_PCT / 100 - used) / charge))``: how
    many tasks the RAM has room for. Nothing runs here to count, so the running term of the portable
    formula is 0.

``room``
    ``full`` when held, ``tight`` when no task fits (``slots == 0``), else ``ok``; ``None`` when RAM
    is unknown.

**Unknown fails open.** A figure the probe could not read never holds work. A reading older than
:data:`VITALS_STALE_S` is unknown too. Each reading that changes ``room``, ``held`` or ``slots``
publishes one ``vitals.changed {room, held, slots}``, and only then.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from contextlib import suppress

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
    Room,
    VitalsView,
)
from athena.vitals.probe import Reading

__all__ = ["Gate", "slots_for"]


def slots_for(
    ram_total_mb: int | None, ram_free_mb: int | None, charge_mb: int = TASK_CHARGE_DEFAULT_MB
) -> int:
    """How many tasks the RAM has room for, capped. Unknown RAM fails open to the cap."""
    if ram_total_mb is None or ram_free_mb is None or ram_total_mb <= 0:
        return TASKS_RUNNING_CAP
    used = ram_total_mb - ram_free_mb
    spare = max(0.0, ram_total_mb * RAM_ROOM_PCT / 100.0 - used)
    return max(0, min(TASKS_RUNNING_CAP, math.floor(spare / max(1, charge_mb))))


def _pct(value: float) -> str:
    return f"{value:.0f}%"


class Gate:
    """One per PC. Thread-safe. ``publish`` is the peer bus's ``publish``, or ``None``."""

    def __init__(
        self,
        *,
        publish: Callable[..., None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.publish = publish
        self._clock = clock
        self._lock = threading.Lock()
        self._reading: Reading | None = None
        self._reading_at: float | None = None
        self._ram_held = False
        self._cpu_high = 0
        self._cpu_held = False
        self._told: tuple[Room | None, str | None, int] | None = None

    def observe(self, reading: Reading) -> None:
        """Take one reading: move the holds, and publish ``vitals.changed`` when room, held or
        slots moved."""
        with self._lock:
            self._reading = reading
            self._reading_at = self._clock()
            # An unknown figure holds nothing, but it is not a reading below the resume line
            # either: the hold is kept across it, so one probe gap does not reopen the gate
            # halfway down the hysteresis band.
            ram = reading.ram_pct
            if ram is None:
                pass
            elif ram >= RAM_HOLD_PCT:
                self._ram_held = True
            elif ram < RAM_RESUME_PCT:
                self._ram_held = False
            cpu = reading.cpu_pct
            if cpu is None:
                self._cpu_high = 0  # a gap breaks a run of high readings
            else:
                self._cpu_high = self._cpu_high + 1 if cpu >= CPU_HOLD_PCT else 0
                if self._cpu_high >= CPU_HOLD_SAMPLES:
                    self._cpu_held = True
                elif cpu < CPU_RESUME_PCT:
                    self._cpu_held = False
        view = self.vitals()
        if view is None:
            return
        told = (view["room"], view["held"], view["slots"])
        with self._lock:
            changed, self._told = told != self._told, told
        if changed and self.publish is not None:
            with suppress(Exception):  # telling never fails a reading
                self.publish("vitals.changed", room=told[0], held=told[1], slots=told[2])

    def held(self) -> str | None:
        """``None`` when background work may start now; otherwise why not."""
        with self._lock:
            return self._held()

    def _fresh(self) -> Reading | None:
        """The latest reading, or ``None`` when there is none or it is stale. Lock held."""
        if self._reading is None or self._reading_at is None:
            return None
        if self._clock() - self._reading_at > VITALS_STALE_S:
            return None
        return self._reading

    def _held(self) -> str | None:
        reading = self._fresh()
        if reading is None:
            return None
        if self._ram_held and reading.ram_pct is not None:
            return (
                f"Waiting for room: RAM is at {_pct(reading.ram_pct)} (resumes below {_pct(RAM_RESUME_PCT)})."
            )
        if self._cpu_held and reading.cpu_pct is not None:
            return (
                f"Waiting for room: CPU is at {_pct(reading.cpu_pct)} (resumes below {_pct(CPU_RESUME_PCT)})."
            )
        if (
            reading.power == "battery"
            and reading.battery_pct is not None
            and reading.battery_pct < BATTERY_TASK_FLOOR_PCT
        ):
            return (
                f"Waiting for room: the battery is at {reading.battery_pct}% "
                f"(tasks resume at {BATTERY_TASK_FLOOR_PCT}% or on mains)."
            )
        if reading.disk_free_mb is not None and reading.disk_free_mb < DISK_HOLD_MB:
            return f"Waiting for room: the disk has {reading.disk_free_mb} MB free (needs {DISK_HOLD_MB} MB)."
        return None

    def vitals(self) -> VitalsView | None:
        """The latest snapshot, or ``None`` before the first reading."""
        with self._lock:
            latest = self._reading
            if latest is None:
                return None
            reading = self._fresh()
            held = self._held()
        if reading is None:  # stale: every figure unknown, the slots at the cap
            return {
                "at": latest.at,
                "cpu_pct": None,
                "cores": None,
                "ram_total_mb": None,
                "ram_free_mb": None,
                "ram_pct": None,
                "gpus": None,
                "power": None,
                "battery_pct": None,
                "disk_free_mb": None,
                "room": None,
                "slots": TASKS_RUNNING_CAP,
                "held": None,
                "runs": None,
                "sleep": None,
            }
        slots = slots_for(reading.ram_total_mb, reading.ram_free_mb)
        return {
            "at": reading.at,
            "cpu_pct": reading.cpu_pct,
            "cores": reading.cores,
            "ram_total_mb": reading.ram_total_mb,
            "ram_free_mb": reading.ram_free_mb,
            "ram_pct": reading.ram_pct,
            "gpus": None if reading.gpus is None else list(reading.gpus),
            "power": reading.power,
            "battery_pct": reading.battery_pct,
            "disk_free_mb": reading.disk_free_mb,
            "room": _room(reading, held, slots),
            "slots": slots,
            "held": held,
            "runs": None,
            "sleep": None,
        }


def _room(reading: Reading, held: str | None, slots: int) -> Room | None:
    if held is not None:
        return "full"
    if reading.ram_pct is None:
        return None
    return "tight" if slots <= 0 else "ok"
