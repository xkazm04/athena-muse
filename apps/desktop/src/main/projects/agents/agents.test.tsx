import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../../lib/api";
import type { AgentConnect, AgentLease, AgentNote, App, AppTool } from "../../../lib/contract";
import { DaemonError } from "../../../lib/daemon";
import { resetMain } from "../../store";
import { AgentsSection } from "./AgentsSection";
import { bodyOf, deviceSlug, emptyForm, offeredTools } from "./words";

vi.mock("../../../lib/api");
vi.mock("../../../lib/daemon", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../lib/daemon")>()),
  subscribe: vi.fn(() => () => undefined),
}));

// --- fixtures (invented: no real agent, project or secret) ---

const LIST: AppTool = { name: "list_scenes", description: "Lists the scenes", access: "auto" };
const RENDER: AppTool = { name: "render_scene", description: "Renders one scene", access: "gated" };
const PUBLISH: AppTool = { name: "publish", description: "Publishes a finished scene", access: "gated" };

const app = (over: Partial<App> = {}): App => ({
  app_id: "app_0001",
  kind: "mcp_http",
  label: "Gravitone",
  slug: "gravitone",
  address: "http://127.0.0.1:8080/",
  status: "ok",
  tools: [LIST, RENDER],
  remotes: [{ peer_id: "dev_0000000000a2", device: "Studio PC", remote_app_id: "app_b001", status: "ok", tools: [LIST, RENDER, PUBLISH] }],
  sealed: false,
  ...over,
});
const APPS: App[] = [
  app(),
  app({ app_id: "web_aaaaaaaaaa", kind: "website", label: "example.com", slug: "example_com", tools: [RENDER], remotes: [] }),
];

const lease = (over: Partial<AgentLease> = {}): AgentLease => ({
  id: "lse_0001",
  space_id: "spc_a1",
  label: "Claude in the studio",
  state: "connected",
  created: "2026-11-04T12:00:00Z",
  expires: "2026-11-04T14:30:00Z",
  tools: ["gravitone__render_scene", "note_add"],
  notes: 0,
  client: "claude-code",
  ...over,
});

const WAITING = lease({ state: "waiting", ceiling: { tools: ["gravitone__render_scene"], max_calls: 10, used: 0, deadline: "2026-11-04T13:00:00Z", signed: false } });
const CONNECTED = lease({ notes: 2, ceiling: { tools: ["gravitone__render_scene"], max_calls: 10, used: 3, deadline: "2026-11-04T13:00:00Z", signed: true } });
const USED_UP = lease({ id: "lse_0002", label: "Night runner", ceiling: { tools: ["gravitone__render_scene"], max_calls: 5, used: 5, deadline: "2026-11-04T13:00:00Z", signed: true } });
const ENDED = lease({ id: "lse_0003", label: "Yesterday's helper", state: "ended", client: undefined });

const SECRET = "tok_7f3a9c1e5b2d8f4a6c0e9b1d3f5a7c9e";
const CONNECT: AgentConnect = {
  lease: lease({ id: "lse_0009", label: "Builder", state: "connected" }),
  url: "http://127.0.0.1:17490/mcp",
  token: SECRET,
  config: JSON.stringify({ mcpServers: { athena: { type: "http", url: "http://127.0.0.1:17490/mcp", headers: { Authorization: `Bearer ${SECRET}` } } } }, null, 2),
};

const LONG = `${"A long handoff about the scene order and what is left to render. ".repeat(30)}<b>not markup</b>`;
const NOTES: AgentNote[] = [
  { id: "nte_1", label: "Claude in the studio", text: LONG, created: "2026-11-04T12:10:00Z" },
  { id: "nte_2", label: "Someone else", text: "Not this agent's.", created: "2026-11-04T12:11:00Z" },
];

const BANNED = ["lease", "token", "mcp", "ceiling", "record", "hands", "stdio"];
const bannedIn = (text: string) => BANNED.filter((w) => text.toLowerCase().includes(w));

beforeEach(() => {
  resetMain();
  vi.mocked(api.spaceApps).mockResolvedValue(APPS);
  vi.mocked(api.listAgentNotes).mockResolvedValue(NOTES);
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

const mount = async (agents: AgentLease[] | Error) => {
  if (agents instanceof Error) vi.mocked(api.listAgents).mockRejectedValue(agents);
  else vi.mocked(api.listAgents).mockResolvedValue(agents);
  render(<AgentsSection spaceId="spc_a1" />);
  await act(async () => undefined);
};
const section = () => document.querySelector<HTMLElement>('[data-role="agents"]')!;
const rows = () => [...document.querySelectorAll<HTMLElement>('[data-role="agent"]')];
const openConnect = async () => {
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Let an agent use this project" })));
  return screen.getByRole("dialog");
};
const fillName = (dialog: HTMLElement, name: string) => fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: name } });

/** Everything a person reads or a reader announces, except the config block and its developer caption. */
function readable(): string {
  const copy = document.body.cloneNode(true) as HTMLElement;
  copy.querySelectorAll(".m-agent-config").forEach((e) => e.remove());
  const attrs = [...copy.querySelectorAll("[aria-label],[title],[placeholder]")].map(
    (e) => `${e.getAttribute("aria-label") ?? ""} ${e.getAttribute("title") ?? ""} ${e.getAttribute("placeholder") ?? ""}`,
  );
  return `${copy.textContent ?? ""} ${attrs.join(" ")}`;
}

// --- states: each from a fixture, at two window widths ---

type State = { name: string; setup: () => Promise<void>; expect: () => void };

const STATES: State[] = [
  { name: "checking", setup: async () => {
      vi.mocked(api.listAgents).mockReturnValue(new Promise(() => undefined));
      render(<AgentsSection spaceId="spc_a1" />);
    }, expect: () => {
      expect(section().querySelector('[data-role="checking"]')!.textContent).toBe("Checking for agents...");
      expect(section().querySelector('[data-role="none"]')).toBeNull();
    } },
  { name: "none yet", setup: () => mount([]), expect: () => expect(section().querySelector('[data-role="none"]')!.textContent).toBe("No agents yet.") },
  { name: "list read failed", setup: () => mount(new DaemonError(503, "unavailable" as never, "The daemon is starting.")), expect: () => {
      expect(screen.getByRole("alert").textContent).toBe("Could not read the agents. The daemon is starting.");
      expect(section().querySelector('[data-role="none"]')).toBeNull();
    } },
  { name: "waiting", setup: () => mount([WAITING]), expect: () => {
      expect(rows()[0]!.querySelector('[data-role="standing"]')!.textContent).toBe("Waiting for your signature to run calls unattended");
      expect(rows()[0]!.querySelector('[data-role="used"]')).toBeNull();
      expect(rows()[0]!.textContent).toContain("says it is claude-code");
    } },
  { name: "connected", setup: () => mount([CONNECTED]), expect: () => {
      expect(rows()[0]!.querySelector('[data-role="standing"]')!.textContent).toMatch(/^Connected, ends at \d\d:\d\d$/);
      expect(rows()[0]!.querySelector('[data-role="used"]')!.textContent).toBe("Calls without asking: 3 of 10 used");
      expect(rows()[0]!.textContent).toContain("2 notes");
    } },
  { name: "used up", setup: () => mount([USED_UP]), expect: () => {
      expect(rows()[0]!.dataset.usedUp).toBe("yes");
      expect(rows()[0]!.querySelector('[data-role="used"]')!.textContent).toBe("Calls without asking: 5 of 5 used. Each call asks you now.");
    } },
  { name: "ended", setup: () => mount([ENDED]), expect: () => {
      expect(rows()[0]!.querySelector('[data-role="standing"]')!.textContent).toBe("Ended");
      expect(within(rows()[0]!).queryByRole("button", { name: /Revoke/ })).toBeNull();
    } },
  { name: "notes empty", setup: async () => {
      vi.mocked(api.listAgentNotes).mockResolvedValue([]);
      await mount([lease()]);
      await act(async () => fireEvent.click(within(rows()[0]!).getByRole("button", { name: "0 notes" })));
    }, expect: () => expect(rows()[0]!.textContent).toContain("No notes yet.") },
  { name: "notes long", setup: async () => {
      await mount([CONNECTED]);
      await act(async () => fireEvent.click(within(rows()[0]!).getByRole("button", { name: "2 notes" })));
    }, expect: () => {
      const notes = rows()[0]!.querySelectorAll('[data-role="note"]');
      expect(notes).toHaveLength(1); // only the notes this agent left
      expect(notes[0]!.querySelector(".m-agent-note__text")!.textContent).toBe(LONG);
      expect(notes[0]!.querySelector("b")).toBeNull(); // text, never markup
    } },
  { name: "revoke refused", setup: async () => {
      vi.mocked(api.revokeAgent).mockRejectedValue(new DaemonError(404, "unknown_ref", "That agent is not one of this project's."));
      await mount([CONNECTED]);
      await act(async () => fireEvent.click(screen.getByRole("button", { name: "Revoke Claude in the studio" })));
    }, expect: () => {
      expect(within(rows()[0]!).getByRole("alert").textContent).toBe("That agent is not one of this project's.");
      expect(rows()[0]!.dataset.state).toBe("connected");
    } },
  { name: "connect form", setup: async () => {
      await mount([]);
      await openConnect();
    }, expect: () => expect(screen.getByRole("form", { name: "Let an agent use this project" })).toBeTruthy() },
  { name: "without asking", setup: async () => {
      await mount([]);
      const dialog = await openConnect();
      fireEvent.click(within(dialog).getByLabelText("Let it run some calls without asking"));
    }, expect: () => {
      const free = section().querySelector('[data-role="without-asking"]')!;
      // Only what asks first, here and on the paired computer: never what runs on its own.
      expect([...free.querySelectorAll<HTMLElement>("[data-tool]")].map((t) => t.dataset.tool)).toEqual([
        "gravitone__render_scene",
        "gravitone_on_studio_pc__render_scene",
        "gravitone_on_studio_pc__publish",
      ]);
      expect(free.textContent).toContain("Gravitone on Studio PC");
      expect(free.textContent).toContain("You sign once, on a card Athena shows you.");
    } },
  { name: "minting", setup: async () => {
      vi.mocked(api.connectAgent).mockReturnValue(new Promise(() => undefined));
      await mount([]);
      const dialog = await openConnect();
      fillName(dialog, "Builder");
      await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Connect" })));
    }, expect: () => expect(screen.getByRole("button", { name: "Connecting..." })).toHaveProperty("disabled", true) },
  { name: "mint failed", setup: async () => {
      vi.mocked(api.connectAgent).mockRejectedValue(new DaemonError(409, "conflict" as never, "This project already lets in 8 agents."));
      await mount([]);
      const dialog = await openConnect();
      fillName(dialog, "Builder");
      await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Connect" })));
    }, expect: () => {
      const form = screen.getByRole("form", { name: "Let an agent use this project" });
      const alert = within(form).getByRole("alert");
      expect(alert.textContent).toBe("This project already lets in 8 agents.");
      // Under the control: after the Connect button.
      const button = within(form).getByRole("button", { name: "Connect" });
      expect(button.compareDocumentPosition(alert) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    } },
  { name: "shown once", setup: async () => {
      vi.mocked(api.connectAgent).mockResolvedValue(CONNECT);
      await mount([]);
      const dialog = await openConnect();
      fillName(dialog, "Builder");
      await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Connect" })));
    }, expect: () => {
      expect(section().querySelector('[data-role="config"]')!.textContent).toBe(CONNECT.config);
      expect(section().textContent).toContain("Shown once. Paste it into the agent's settings. Revoke ends it.");
    } },
];

const WIDTHS = [360, 1280];

describe("every state, from fixtures, at two widths", () => {
  for (const width of WIDTHS) {
    for (const state of STATES) {
      it(`${state.name} at ${width} px`, async () => {
        window.innerWidth = width;
        window.dispatchEvent(new Event("resize"));
        await state.setup();
        state.expect();
        // Nothing sized inline: the width comes from the sheet, whose rules keep it inside the plane.
        expect(section().querySelectorAll("[style]")).toHaveLength(0);
      });
    }
  }

  it("never says a word the screen keeps out, in any state, fixtures included", async () => {
    for (const state of STATES) {
      await state.setup();
      expect(bannedIn(readable()), state.name).toEqual([]);
      cleanup();
      vi.mocked(api.spaceApps).mockResolvedValue(APPS);
      vi.mocked(api.listAgentNotes).mockResolvedValue(NOTES);
    }
    // The fixtures' own strings a person could see.
    const shown = [WAITING, CONNECTED, USED_UP, ENDED].map((l) => `${l.label} ${l.client ?? ""}`).join(" ") + NOTES.map((n) => n.text).join(" ");
    expect(bannedIn(shown)).toEqual([]);
  });
});

// --- the tool names the daemon offers ---

describe("tool names, as the daemon builds them", () => {
  it("a device's name: lowercase, runs of anything else one underscore, none at the ends", () => {
    expect(deviceSlug("Studio PC")).toBe("studio_pc");
    expect(deviceSlug("  Mia's  Laptop (2) ")).toBe("mia_s_laptop_2");
    expect(deviceSlug("__Big__Box__")).toBe("big_box");
    expect(deviceSlug("Žluťoučký")).toBe("lu_ou_k");
    expect(deviceSlug("ÄÖ")).toBe("device");
  });

  it("<slug>__<tool> here, <slug>_on_<device>__<tool> on a paired computer; programs only, too long or taken twice not offered", () => {
    const long = { name: "x".repeat(60), description: "", access: "gated" as const };
    const names = offeredTools([
      ...APPS,
      app({ app_id: "app_0002", label: "Gravitone again", tools: [RENDER, long], remotes: [] }),
    ]).map((t) => t.name);
    expect(names).toEqual([
      "gravitone__list_scenes",
      "gravitone__render_scene",
      "gravitone_on_studio_pc__list_scenes",
      "gravitone_on_studio_pc__render_scene",
      "gravitone_on_studio_pc__publish",
    ]);
  });
});

// --- connecting ---

describe("connecting an agent", () => {
  it("sends only a name and a time when everything is ticked", async () => {
    vi.mocked(api.connectAgent).mockResolvedValue(CONNECT);
    await mount([]);
    const dialog = await openConnect();
    fillName(dialog, "  Builder  ");
    await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Connect" })));
    expect(api.connectAgent).toHaveBeenCalledWith("spc_a1", { label: "Builder", minutes: 30 });
  });

  it("sends exactly the body asked for: the tools by name and the calls without asking", async () => {
    vi.mocked(api.connectAgent).mockResolvedValue(CONNECT);
    await mount([]);
    const dialog = await openConnect();
    await act(async () => undefined);
    fillName(dialog, "Builder");
    fireEvent.click(within(dialog).getByLabelText("1 h"));
    fireEvent.click(within(dialog).getByRole("checkbox", { name: /^The report/ }));
    fireEvent.click(within(dialog).getByLabelText("Let it run some calls without asking"));
    fireEvent.click(dialog.querySelector('[data-tool="gravitone_on_studio_pc__render_scene"] input')!);
    fireEvent.change(within(dialog).getByLabelText("Up to this many calls"), { target: { value: "5" } });
    expect((within(dialog).getByLabelText("For this many minutes") as HTMLInputElement).value).toBe("60");
    fireEvent.change(within(dialog).getByLabelText("For this many minutes"), { target: { value: "45" } });
    fireEvent.change(within(dialog).getByLabelText("Files up to this many MB (optional)"), { target: { value: "200" } });
    await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Connect" })));
    expect(api.connectAgent).toHaveBeenCalledWith("spc_a1", {
      label: "Builder",
      minutes: 60,
      tools: [
        "gravitone__list_scenes",
        "gravitone__render_scene",
        "gravitone_on_studio_pc__list_scenes",
        "gravitone_on_studio_pc__render_scene",
        "gravitone_on_studio_pc__publish",
        "app_fetch",
        "file_list",
        "note_add",
        "note_list",
        "card_status",
      ],
      ceiling: { tools: ["gravitone_on_studio_pc__render_scene"], max_calls: 5, minutes: 45, file_mb: 200 },
    });
  });

  it("will not send without a name, or with calls without asking but none ticked or out of range", async () => {
    const form = { ...emptyForm(), label: "B", unattended: true, free: ["gravitone__render_scene"], calls: "201" };
    expect(bodyOf({ ...form, calls: "7", fileMb: "" }, APPS).ceiling).toEqual({ tools: ["gravitone__render_scene"], max_calls: 7, minutes: 30 });
    await mount([]);
    const dialog = await openConnect();
    await act(async () => undefined);
    expect(within(dialog).getByRole("button", { name: "Connect" })).toHaveProperty("disabled", true);
    expect(dialog.querySelector('[data-role="not-ready"]')!.textContent).toBe("Give it a name.");
    fillName(dialog, "Builder");
    fireEvent.click(within(dialog).getByLabelText("Let it run some calls without asking"));
    expect(dialog.querySelector('[data-role="not-ready"]')!.textContent).toBe("Tick the calls it may run without asking.");
    fireEvent.click(dialog.querySelector('[data-tool="gravitone__render_scene"] input')!);
    fireEvent.change(within(dialog).getByLabelText("Up to this many calls"), { target: { value: "201" } });
    expect(dialog.querySelector('[data-role="not-ready"]')!.textContent).toBe("Calls without asking: a number from 1 to 200.");
    fireEvent.change(within(dialog).getByLabelText("Up to this many calls"), { target: { value: "10" } });
    fireEvent.change(within(dialog).getByLabelText("For this many minutes"), { target: { value: "31" } });
    expect(dialog.querySelector('[data-role="not-ready"]')!.textContent).toBe("Minutes without asking: a number from 1 to 30.");
  });

  it("shows the config once: only inside its block, never in a name, a title or a value, and gone once closed", async () => {
    vi.mocked(api.connectAgent).mockResolvedValue(CONNECT);
    vi.mocked(api.listAgents).mockResolvedValue([]);
    await mount([]);
    const dialog = await openConnect();
    fillName(dialog, "Builder");
    vi.mocked(api.listAgents).mockResolvedValue([CONNECT.lease]);
    await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Connect" })));
    const block = section().querySelector('[data-role="config"]')!;
    expect(block.textContent).toContain(SECRET);
    // Only in the block: the rest of the page, every name, title and field value is clean.
    const outside = section().cloneNode(true) as HTMLElement;
    outside.querySelector('[data-role="config"]')!.remove();
    expect(outside.innerHTML).not.toContain(SECRET);
    for (const e of document.querySelectorAll("*")) {
      for (const attr of ["aria-label", "title", "value", "aria-description", "data-tool"]) expect(e.getAttribute(attr) ?? "").not.toContain(SECRET);
    }
    for (const input of document.querySelectorAll("input")) expect(input.value).not.toContain(SECRET);
    expect(rows().map((r) => r.textContent).join(" ")).not.toContain(SECRET);
    expect(document.title).not.toContain(SECRET);
    // Copy hands over the config itself.
    const write = vi.fn(async () => undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText: write }, configurable: true });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Copy" })));
    expect(write).toHaveBeenCalledWith(CONNECT.config);
    expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy();
    // Closed: gone from the page, and the list row carries none of it.
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Done" })));
    expect(document.body.innerHTML).not.toContain(SECRET);
    expect(document.body.innerHTML).not.toContain("Bearer");
    expect(rows()[0]!.textContent).toContain("Builder");
  });

  it("Escape after the config closes it too, and it is gone", async () => {
    vi.mocked(api.connectAgent).mockResolvedValue(CONNECT);
    await mount([]);
    const dialog = await openConnect();
    fillName(dialog, "Builder");
    await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Connect" })));
    expect(document.body.innerHTML).toContain(SECRET);
    await act(async () => fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.body.innerHTML).not.toContain(SECRET);
  });
});

// --- revoking ---

describe("revoking", () => {
  it("acts at once, shows it ended, then reads the list again", async () => {
    await mount([CONNECTED]);
    const reads = vi.mocked(api.listAgents).mock.calls.length;
    vi.mocked(api.revokeAgent).mockResolvedValue(undefined);
    vi.mocked(api.listAgents).mockResolvedValue([{ ...CONNECTED, state: "ended" }]);
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Revoke Claude in the studio" })));
    expect(api.revokeAgent).toHaveBeenCalledWith("spc_a1", "lse_0001");
    expect(vi.mocked(api.listAgents).mock.calls.length).toBe(reads + 1);
    expect(vi.mocked(api.revokeAgent).mock.invocationCallOrder[0]!).toBeLessThan(vi.mocked(api.listAgents).mock.invocationCallOrder.at(-1)!);
    expect(rows()[0]!.querySelector('[data-role="standing"]')!.textContent).toBe("Ended");
    expect(screen.queryByRole("button", { name: /Revoke/ })).toBeNull();
  });
});

// --- the keyboard ---

describe("the connect panel keeps the keyboard", () => {
  it("takes the focus, wraps Tab inside, and Escape returns it to the button", async () => {
    await mount([]);
    const dialog = await openConnect();
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    const heading = within(dialog).getByRole("heading", { name: "Let an agent use this project" });
    expect(document.activeElement).toBe(heading);
    const stops = [...dialog.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), [tabindex="0"]')];
    const first = stops[0]!;
    const last = stops.at(-1)!;
    // Shift+Tab from the title goes to the last control; Tab from the last comes back to the first.
    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
    await act(async () => fireEvent.keyDown(document.activeElement!, { key: "Escape" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Let an agent use this project" }));
  });
});
