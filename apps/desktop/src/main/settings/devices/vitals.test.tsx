import { cleanup, render as mount } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BUS_KINDS, busEventFromJson, type DevicesView } from "../../../lib/fleet";
import type { Vitals } from "../../../lib/vitals";
import { DevicesLevel } from "./Devices";
import { Drawer, SELF } from "./Constellation";
import { VIEW, model } from "./fixtures";
import { devicesHandler } from "./store";
import {
  HeldLine,
  Meter,
  VITALS_REREAD_MS,
  VitalsFacts,
  gb,
  gpuWords,
  powerWords,
  roomSaid,
  roomWord,
  useVitalsReread,
  withRoom,
} from "./vitals";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const VITALS: Vitals = {
  at: "2026-10-24T12:00:00+00:00",
  cpu_pct: 34.5,
  cores: 16,
  ram_total_mb: 65536,
  ram_free_mb: 30000,
  ram_pct: 54.2,
  gpus: [{ name: "RTX 4090", util_pct: 21, vram_total_mb: 24564, vram_used_mb: 1391 }],
  power: "mains",
  battery_pct: null,
  disk_free_mb: 200_000,
  room: "ok",
  slots: 3,
  held: null,
  runs: null,
  sleep: null,
};
const html = (node: React.ReactElement) => renderToStaticMarkup(node);

describe("the room's words", () => {
  it("says the gate's word, and nothing when the room is unknown", () => {
    expect(roomWord(VITALS)).toBe("room ok");
    expect(roomWord({ ...VITALS, room: "tight" })).toBe("tight");
    expect(roomWord({ ...VITALS, room: null })).toBeNull();
    expect(roomWord(null)).toBeNull();
    expect(withRoom("Online", VITALS)).toBe("Online · room ok");
    expect(withRoom("Online", { ...VITALS, room: null })).toBe("Online");
    expect(roomSaid({ ...VITALS, room: "full" })).toBe("no room");
    expect(roomSaid(undefined)).toBeNull();
  });

  it("writes figures as a person reads them", () => {
    expect(gb(24564)).toBe("24 GB");
    expect(gb(1391)).toBe("1.4 GB");
    expect(gpuWords(VITALS.gpus![0]!)).toBe("RTX 4090 · 1.4 of 24 GB VRAM · 21% busy");
    expect(gpuWords({ name: "Tesla T4", util_pct: null, vram_total_mb: null, vram_used_mb: null })).toBe("Tesla T4");
    expect(powerWords({ power: "battery", battery_pct: 27 })).toBe("On battery, 27%");
    expect(powerWords({ power: null, battery_pct: null })).toBe("unknown");
  });
});

describe("the meter", () => {
  it("is a bar with its figure in words, in the warning hue at the gate's line", () => {
    const h = html(<Meter label="RAM" value={0.93} text="RAM 93%" high />);
    expect(h).toContain('role="meter"');
    expect(h).toContain('aria-valuenow="93"');
    expect(h).toContain('data-high="1"');
  });

  it("draws no bar for an unknown figure, only the words (unknown is never zero)", () => {
    const h = html(<Meter label="CPU" value={null} text="CPU unknown" />);
    expect(h).not.toContain("role=\"meter\"");
    expect(h).toContain("CPU unknown");
  });
});

describe("the drawer's facts", () => {
  it("gives the room, the load, the GPU, the power and the disk, and no runs or sleep rows", () => {
    const h = html(<VitalsFacts vitals={VITALS} presence="online" />);
    for (const word of ["Room", "room ok", "3 task slots", "CPU 35%", "RAM 54% of 64 GB", "RTX 4090", "On mains", "195 GB free"]) {
      expect(h, word).toContain(word);
    }
    expect(h).not.toContain("Sleep");
    expect(h).not.toContain("Runs");
  });

  it("leaves a GPU row out when the probe could not run, and says none when it found none", () => {
    expect(html(<VitalsFacts vitals={{ ...VITALS, gpus: null }} presence="online" />)).not.toContain("GPU");
    expect(html(<VitalsFacts vitals={{ ...VITALS, gpus: [] }} presence="online" />)).toContain("none");
  });

  it("reads every unknown as unknown", () => {
    const blank: Vitals = { ...VITALS, cpu_pct: null, ram_pct: null, ram_total_mb: null, room: null, disk_free_mb: null, power: null };
    const h = html(<VitalsFacts vitals={blank} presence="online" />);
    for (const word of ["room unknown", "CPU unknown", "RAM unknown", "unknown"]) expect(h, word).toContain(word);
    expect(h).not.toContain('role="meter"');
  });

  it("says why a computer has no vitals: none yet, or none lately", () => {
    expect(html(<VitalsFacts vitals={null} presence="online" />)).toContain("No vitals yet");
    expect(html(<VitalsFacts vitals={null} presence="asleep" />)).toContain("Not heard lately");
    expect(html(<VitalsFacts vitals={undefined} presence="unreachable" />)).toContain("Not heard lately");
  });

  it("shows the held reason in the gate's own words, and nothing when nothing waits", () => {
    const held = "Waiting for room: RAM is at 93% (resumes below 85%).";
    expect(html(<HeldLine vitals={{ ...VITALS, held }} />)).toContain(held);
    expect(html(<HeldLine vitals={VITALS} />)).toBe("");
  });
});

const withVitals = (self: Vitals | null, laptop: Vitals | null): DevicesView => ({
  ...VIEW,
  self: { ...VIEW.self, vitals: self },
  peers: VIEW.peers.map((p) => (p.name === "Laptop" ? { ...p, vitals: laptop } : p)),
});

describe("on the constellation", () => {
  const tight: Vitals = { ...VITALS, room: "tight", slots: 0 };

  it("puts the room word after each computer's caption and in its name for a screen reader", () => {
    const h = html(<DevicesLevel model={model({}, withVitals(VITALS, tight))} />);
    expect(h).toContain("network ready · room ok");
    expect(h).toContain("· tight");
    expect(h).toContain("Study PC, this computer. Private network: ready. Room ok. Show its details.");
    expect(h).toContain("Laptop, computer, online, room is tight. Show its details.");
  });

  it("changes nothing for a computer with no vitals", () => {
    const h = html(<DevicesLevel model={model({}, withVitals(null, null))} />);
    expect(h).not.toContain("room ok");
    expect(h).toContain('aria-label="Laptop, computer, online. Show its details."');
  });

  it("opens this computer's drawer on its figures and the held line", () => {
    const held = { ...VITALS, room: "full" as const, held: "Waiting for room: the disk has 900 MB free (needs 1024 MB)." };
    const h = html(<Drawer model={model({}, withVitals(held, null))} selected={SELF} onClose={() => {}} />);
    expect(h).toContain("Load");
    expect(h).toContain("m-vitals__held");
    expect(h).toContain("the disk has 900 MB free");
  });

  it("opens a peer's drawer on its vitals, and a phone's on none", () => {
    const laptop = html(<Drawer model={model({}, withVitals(VITALS, tight))} selected="dev_0000000000a2" onClose={() => {}} />);
    expect(laptop).toContain("0 task slots");
    const phone = html(<Drawer model={model({}, withVitals(VITALS, tight))} selected="dev_0000000000a3" onClose={() => {}} />);
    expect(phone).not.toContain("Vitals");
    expect(phone).not.toContain("Load");
  });

  it("says a peer it has not heard lately has no vitals, not an empty room", () => {
    const h = html(<Drawer model={model({}, withVitals(VITALS, null))} selected="dev_0000000000a4" onClose={() => {}} />);
    expect(h).toContain("Not heard lately");
  });
});

describe("keeping the figures fresh", () => {
  it("reads the list again on the hello's beat while a computer is open, and stops when it closes", () => {
    vi.useFakeTimers();
    const load = vi.fn(async () => {});
    function Probe({ active }: { active: boolean }) {
      useVitalsReread(active, load);
      return null;
    }
    const view = mount(<Probe active />);
    vi.advanceTimersByTime(VITALS_REREAD_MS * 2);
    expect(load).toHaveBeenCalledTimes(2);
    view.rerender(<Probe active={false} />);
    vi.advanceTimersByTime(VITALS_REREAD_MS * 2);
    expect(load).toHaveBeenCalledTimes(2);
  });
});

describe("the bus", () => {
  it("knows vitals.changed and re-reads the list on it", () => {
    expect(BUS_KINDS).toContain("vitals.changed");
    const frame = JSON.stringify({ kind: "vitals.changed", room: "full", held: "Waiting for room", slots: 0 });
    expect(busEventFromJson(frame)).toMatchObject({ kind: "vitals.changed", room: "full", slots: 0 });
    const changed = vi.fn();
    devicesHandler(changed)({ kind: "vitals.changed", room: "ok", held: null, slots: 3 });
    expect(changed).toHaveBeenCalledTimes(1);
  });
});
