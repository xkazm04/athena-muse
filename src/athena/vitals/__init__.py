"""A PC's room, measured with the standard library, and the gate that reads it (ADR 0017).

The daemon samples its own CPU, RAM and GPU, its power and the free space on the data directory;
the :class:`~athena.vitals.gate.Gate` turns the samples into how many background tasks could run
now (``slots``), how much room there is (``room``) and, when none may start, the sentence that says
why (``held``). The snapshot rides the presence probe's authorized hello to every paired PC and is
shown on Settings > Devices.

Two properties hold everywhere in this package:

- **Unknown is ``None``, never zero.** A figure the probe could not read is ``None``, and a gate
  that needs it fails open: it never holds work on a number it does not have. ``gpus`` is ``[]``
  when the probe ran and found none, ``None`` when it could not run.
- **Every key is always present** in :data:`VitalsView`, the wire shape, so the window and the
  peers never have to tell "absent" from "unknown".

The modules: :mod:`~athena.vitals.probe` (one reading of the host, per OS),
:mod:`~athena.vitals.sampler` (the thread that keeps it fresh), :mod:`~athena.vitals.gate` (slots,
room and the held reason, with hysteresis), :mod:`~athena.vitals.wire` (a peer's view cleaned) and
:mod:`~athena.vitals.service` (the pieces for one daemon, and ``GET /vitals``).

Trimmed from the portable build: this daemon has no sleep cycle, no task runner and no ledger runs
summary, so ``runs`` and ``sleep`` are always ``None`` and the slots count the tasks that would fit.
"""

from __future__ import annotations

from typing import Literal, TypedDict

__all__ = [
    "BATTERY_TASK_FLOOR_PCT",
    "CPU_HOLD_PCT",
    "CPU_HOLD_SAMPLES",
    "CPU_RESUME_PCT",
    "DISK_HOLD_MB",
    "GPU_EVERY_S",
    "RAM_HOLD_PCT",
    "RAM_RESUME_PCT",
    "RAM_ROOM_PCT",
    "SAMPLE_EVERY_S",
    "TASKS_RUNNING_CAP",
    "TASK_CHARGE_DEFAULT_MB",
    "VITALS_STALE_S",
    "GpuView",
    "Room",
    "VitalsView",
]

#: CPU and RAM are sampled this often; a GPU reading costs a subprocess, so it is taken less often.
SAMPLE_EVERY_S = 5.0
GPU_EVERY_S = 30.0
#: RAM above this holds background work until it falls below the resume line (hysteresis).
RAM_HOLD_PCT = 92.0
RAM_RESUME_PCT = 85.0
#: The share of RAM the slot arithmetic lets tasks fill.
RAM_ROOM_PCT = 85.0
#: CPU holds only when it stays above the line for this many samples in a row.
CPU_HOLD_PCT = 90.0
CPU_HOLD_SAMPLES = 3
CPU_RESUME_PCT = 70.0
#: On battery, tasks wait below this charge.
BATTERY_TASK_FLOOR_PCT = 30
#: Less free disk than this on the data directory's volume holds work.
DISK_HOLD_MB = 1024
#: What one task is charged (there is no ledger here to measure it).
TASK_CHARGE_DEFAULT_MB = 600
#: The most tasks the slots ever count.
TASKS_RUNNING_CAP = 3
#: A peer's vitals older than this are not shown: a stale "room ok" is worse than none.
VITALS_STALE_S = 90.0

Room = Literal["ok", "tight", "full"]


class GpuView(TypedDict):
    name: str
    util_pct: float | None
    vram_total_mb: int | None
    vram_used_mb: int | None


class VitalsView(TypedDict):
    """The wire shape of one PC's vitals: ``GET /vitals``, the hello, ``GET /devices``.

    ``runs`` and ``sleep`` are kept for the shape's sake and are always ``None`` in this daemon.
    """

    at: str
    cpu_pct: float | None
    cores: int | None
    ram_total_mb: int | None
    ram_free_mb: int | None
    ram_pct: float | None
    gpus: list[GpuView] | None
    power: Literal["mains", "battery"] | None
    battery_pct: int | None
    disk_free_mb: int | None
    room: Room | None
    slots: int
    held: str | None
    runs: None
    sleep: None
