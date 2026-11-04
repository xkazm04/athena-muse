import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../../lib/api";
import type { App, AppNew, AppTool } from "../../../lib/contract";
import { DaemonError } from "../../../lib/daemon";
import type { DevicesView } from "../../../lib/fleet";
import { OfferedApps } from "../../settings/devices/OfferedApps";
import { resetMain } from "../../store";
import { AddApp } from "./AddApp";
import { AppsSection } from "./AppsSection";
import { KIND_ORDER, argvOf, bodyOf, EMPTY_FORM } from "./words";

vi.mock("../../../lib/api");
vi.mock("../../../lib/daemon", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../lib/daemon")>()),
  subscribe: vi.fn(() => () => undefined),
}));

const READ: AppTool = { name: "list_scenes", description: "Lists the scenes", access: "auto" };
const ACT: AppTool = { name: "render_scene", description: "Renders one scene", access: "gated" };

const app = (over: Partial<App> = {}): App => ({
  app_id: "app_0001",
  kind: "mcp_http",
  label: "Gravitone",
  slug: "gravitone",
  address: "http://127.0.0.1:8080/",
  status: "ok",
  tools: [READ, ACT],
  remotes: [],
  sealed: false,
  ...over,
});

const FOUR: App[] = [
  app({ app_id: "web_aaaaaaaaaa", kind: "website", label: "example.com", slug: "example_com", address: "https://example.com", status: "unchecked", tools: [] }),
  app({ app_id: "web_bbbbbbbbbb", kind: "local_page", label: "localhost:3000", slug: "localhost_3000", address: "http://localhost:3000", status: "unreachable", tools: [], reason: "Nothing answers at localhost:3000." }),
  app(),
  app({ app_id: "app_0002", kind: "mcp_stdio", label: "Notes", slug: "notes", address: "notes-tool --serve", argv: ["notes-tool", "--serve"], status: "refused", tools: [], reason: "The tool stopped as it started." }),
];

const devices = (): DevicesView => ({
  ok: true,
  self: { device_id: "dev_0000000000a1", name: "Study PC" },
  peers: [
    { peer_id: "dev_0000000000a2", name: "Studio PC", kind: "pc", grants: ["chat", "apps"], created: "2026-10-20T09:00:00Z", expires: null, last_seen: null },
    { peer_id: "dev_0000000000a3", name: "Phone", kind: "phone", grants: ["chat"], created: "2026-10-20T09:00:00Z", expires: null, last_seen: null },
  ],
  pending: [],
  beacon: { on: false, url: null },
  overlay: { state: "up" },
  listener: { up: true, address: null, port: 17491, error: null },
  joining: [],
});

const BANNED = ["mcp", "stdio", "record", "hands"];
const bannedIn = (text: string) => BANNED.filter((w) => text.toLowerCase().includes(w));

beforeEach(() => {
  resetMain();
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

/** Opens the chooser, picks a kind by its plain words, and returns the form. */
function pick(words: string) {
  fireEvent.click(screen.getByRole("button", { name: "Add app" }));
  fireEvent.click(screen.getByRole("button", { name: new RegExp(`^${words}`) }));
  return screen.getByRole("form", { name: words });
}

describe("adding an app, kind first", () => {
  const added = vi.fn<(b: AppNew) => Promise<App>>();
  const probe = vi.fn<(id: string) => Promise<App>>();
  const mount = () => render(<AddApp kinds={KIND_ORDER} add={added} probe={probe} />);

  beforeEach(() => {
    added.mockImplementation(async (b) => app({ kind: b.kind, status: "unchecked", tools: [] }));
    probe.mockImplementation(async () => app());
  });

  it("offers the four kinds in plain words", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Add app" }));
    const group = screen.getByRole("group", { name: "What kind of app is it?" });
    const names = within(group)
      .getAllByRole("button")
      .map((b) => b.querySelector(".m-kind__name")?.textContent)
      .filter(Boolean);
    expect(names).toEqual(["A website", "A page on this computer", "An app on this computer", "A tool she starts"]);
  });

  it("a website posts its address and nothing else", async () => {
    mount();
    const form = pick("A website");
    expect(within(form).queryByLabelText(/Access key/)).toBeNull();
    fireEvent.change(within(form).getByLabelText("Address"), { target: { value: " https://example.com " } });
    await act(async () => fireEvent.click(within(form).getByRole("button", { name: "Add this app" })));
    expect(added).toHaveBeenCalledWith({ kind: "website", address: "https://example.com" });
  });

  it("a page on this computer posts its address", async () => {
    mount();
    const form = pick("A page on this computer");
    expect((within(form).getByLabelText("Address") as HTMLInputElement).placeholder).toBe("http://localhost:3000");
    fireEvent.change(within(form).getByLabelText("Address"), { target: { value: "http://localhost:3000" } });
    await act(async () => fireEvent.click(within(form).getByRole("button", { name: "Add this app" })));
    expect(added).toHaveBeenCalledWith({ kind: "local_page", address: "http://localhost:3000" });
  });

  it("an app on this computer carries its access key, typed in a password field and never shown back", async () => {
    mount();
    const form = pick("An app on this computer");
    const key = within(form).getByLabelText("Access key (optional)") as HTMLInputElement;
    expect(key.type).toBe("password");
    fireEvent.change(within(form).getByLabelText("Address"), { target: { value: "http://127.0.0.1:8080/" } });
    fireEvent.change(key, { target: { value: "s3cret-key-value" } });
    await act(async () => fireEvent.click(within(form).getByRole("button", { name: "Add this app" })));
    expect(added).toHaveBeenCalledWith({ kind: "mcp_http", address: "http://127.0.0.1:8080/", token: "s3cret-key-value" });
    expect(document.body.textContent).not.toContain("s3cret-key-value");
  });

  it("a tool she starts posts argv: one part per line, or one line split at its spaces", async () => {
    mount();
    let form = pick("A tool she starts");
    expect(within(form).getByText(/One part per line, the program first\. A single line is split at its spaces\./)).toBeTruthy();
    fireEvent.change(within(form).getByLabelText("Command"), { target: { value: "notes-tool  --serve --port 7" } });
    fireEvent.change(within(form).getByLabelText("Name (optional)"), { target: { value: "Notes" } });
    fireEvent.change(within(form).getByLabelText("Output folder (optional)"), { target: { value: "D:/out" } });
    await act(async () => fireEvent.click(within(form).getByRole("button", { name: "Add this app" })));
    expect(added).toHaveBeenLastCalledWith({ kind: "mcp_stdio", argv: ["notes-tool", "--serve", "--port", "7"], label: "Notes", output_dir: "D:/out" });

    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    form = pick("A tool she starts");
    fireEvent.change(within(form).getByLabelText("Command"), { target: { value: "notes tool\n--title\nMy notes\n" } });
    await act(async () => fireEvent.click(within(form).getByRole("button", { name: "Add this app" })));
    expect(added).toHaveBeenLastCalledWith({ kind: "mcp_stdio", argv: ["notes tool", "--title", "My notes"] });
  });

  it("an access key goes only with the app on this computer", () => {
    const form = { ...EMPTY_FORM, address: "https://example.com", key: "k", command: "a b" };
    expect(bodyOf("website", form)).toEqual({ kind: "website", address: "https://example.com" });
    expect(bodyOf("local_page", form)).toEqual({ kind: "local_page", address: "https://example.com" });
    expect(bodyOf("mcp_stdio", form)).toEqual({ kind: "mcp_stdio", argv: ["a", "b"] });
    expect(bodyOf("mcp_http", form).token).toBe("k");
    expect(argvOf("\n\n")).toEqual([]);
  });

  it("waits while it looks, then shows the tools it found with their marks", async () => {
    let finish: (a: App) => void = () => undefined;
    probe.mockImplementation(() => new Promise<App>((r) => (finish = r)));
    mount();
    const form = pick("An app on this computer");
    fireEvent.change(within(form).getByLabelText("Address"), { target: { value: "http://127.0.0.1:8080/" } });
    await act(async () => fireEvent.click(within(form).getByRole("button", { name: "Add this app" })));
    expect(screen.getByRole("status").textContent).toContain("Athena is looking at what it offers...");
    await act(async () => finish(app()));
    const found = screen.getByRole("status");
    expect(found.textContent).toContain("Found 2 tools.");
    expect(found.textContent).toContain("list_scenes");
    expect(found.textContent).toContain("on its own");
    expect(found.textContent).toContain("asks you first");
  });

  it("shows why it could not be reached", async () => {
    probe.mockResolvedValue(app({ status: "unreachable", tools: [], reason: "Nothing answers at 127.0.0.1:8080." }));
    mount();
    const form = pick("An app on this computer");
    fireEvent.change(within(form).getByLabelText("Address"), { target: { value: "http://127.0.0.1:8080/" } });
    await act(async () => fireEvent.click(within(form).getByRole("button", { name: "Add this app" })));
    expect(screen.getByRole("status").textContent).toContain("can't reach");
    expect(screen.getByRole("status").textContent).toContain("Nothing answers at 127.0.0.1:8080.");
  });

  it("a refusal stays in place beside the form", async () => {
    added.mockRejectedValue(new DaemonError(400, "bad_request", "That is a page on this computer: choose that kind."));
    mount();
    const form = pick("A website");
    fireEvent.change(within(form).getByLabelText("Address"), { target: { value: "http://localhost:3000" } });
    await act(async () => fireEvent.click(within(form).getByRole("button", { name: "Add this app" })));
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toBe("That is a page on this computer: choose that kind.");
    expect(alert.className).toContain("m-error");
    expect(screen.getByRole("form", { name: "A website" })).toBeTruthy();
    expect(probe).not.toHaveBeenCalled();
  });
});

describe("a project's apps", () => {
  const mount = async (apps: App[]) => {
    vi.mocked(api.spaceApps).mockResolvedValue(apps);
    vi.mocked(api.devices).mockResolvedValue(devices());
    render(<AppsSection spaceId="spc_a1" />);
    await act(async () => undefined);
  };
  const rows = () => [...document.querySelectorAll<HTMLElement>('[data-role="app"]')];

  it("lists the four kinds in plain words with status, tools and their marks", async () => {
    await mount(FOUR);
    expect(api.spaceApps).toHaveBeenCalledWith("spc_a1");
    const [web, page, prog, tool] = rows();
    expect(web!.textContent).toContain("A website");
    expect(web!.textContent).toContain("not checked yet");
    expect(page!.textContent).toContain("A page on this computer");
    expect(page!.textContent).toContain("can't reach");
    expect(page!.textContent).toContain("Nothing answers at localhost:3000.");
    expect(prog!.textContent).toContain("An app on this computer");
    expect(prog!.textContent).toContain("2 tools");
    const marks = [...prog!.querySelectorAll<HTMLElement>(".m-tool")].map((t) => [t.dataset.access, t.querySelector(".badge")!.textContent]);
    expect(marks).toEqual([
      ["auto", "on its own"],
      ["gated", "asks you first"],
    ]);
    expect(tool!.textContent).toContain("A tool she starts");
    expect(tool!.textContent).toContain("refused");
    // Only a program has tools and instances.
    expect(web!.querySelector('[data-role="instance"]')).toBeNull();
    expect(prog!.querySelector('[data-role="instance"]')!.textContent).toContain("This computer");
  });

  it("shows a paired computer's copy as an instance with its status", async () => {
    await mount([
      app({
        remotes: [{ peer_id: "dev_0000000000a2", device: "Studio PC", remote_app_id: "app_b001", status: "unreachable", tools: [READ], reason: "Studio PC is asleep." }],
      }),
    ]);
    const instances = [...rows()[0]!.querySelectorAll<HTMLElement>('[data-role="instance"]')];
    expect(instances.map((i) => i.firstChild!.textContent)).toEqual(["This computer", "on Studio PC"]);
    expect(instances[1]!.textContent).toContain("can't reach");
    expect(instances[1]!.textContent).toContain("Studio PC is asleep.");
    // Already attached: no second offer to add it.
    expect(screen.queryByRole("button", { name: "Add Studio PC's copy" })).toBeNull();
  });

  it("adds a paired computer's copy: asks what it offers, then posts the one picked", async () => {
    await mount([app()]);
    // A phone is never offered.
    expect(screen.queryByRole("button", { name: "Add Phone's copy" })).toBeNull();
    vi.mocked(api.peerOffers).mockResolvedValue([{ app_id: "app_b001", kind: "mcp_http", label: "Gravitone", tools: [READ, ACT], has_output: true }]);
    const attached = app({ remotes: [{ peer_id: "dev_0000000000a2", device: "Studio PC", remote_app_id: "app_b001", status: "ok", tools: [READ, ACT] }] });
    vi.mocked(api.attachRemote).mockResolvedValue(attached);
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Add Studio PC's copy" })));
    expect(api.peerOffers).toHaveBeenCalledWith("dev_0000000000a2");
    const offers = screen.getByRole("group", { name: "What Studio PC offers" });
    expect(offers.textContent).toContain("An app on this computer, 2 tools");
    await act(async () => fireEvent.click(within(offers).getByRole("button", { name: "Use Gravitone on Studio PC" })));
    expect(api.attachRemote).toHaveBeenCalledWith("spc_a1", "app_0001", { peer_id: "dev_0000000000a2", remote_app_id: "app_b001" });
    expect(rows()[0]!.textContent).toContain("on Studio PC");
  });

  it("says plainly when a paired computer cannot be asked", async () => {
    await mount([app()]);
    vi.mocked(api.peerOffers).mockRejectedValue(new DaemonError(403, "unauthorized", "Studio PC has not given this computer its apps."));
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Add Studio PC's copy" })));
    expect(screen.getByRole("alert").textContent).toBe("Studio PC has not given this computer its apps.");
  });

  it("removes only after a second press in place", async () => {
    await mount([app()]);
    vi.mocked(api.removeSpaceApp).mockResolvedValue(undefined);
    fireEvent.click(screen.getByRole("button", { name: "Remove Gravitone" }));
    expect(api.removeSpaceApp).not.toHaveBeenCalled();
    const confirm = screen.getByRole("group", { name: "Confirm removing Gravitone" });
    expect(confirm.textContent).toContain("Athena stops using Gravitone in this project.");
    await act(async () => fireEvent.click(within(confirm).getByRole("button", { name: "Remove Gravitone" })));
    expect(api.removeSpaceApp).toHaveBeenCalledWith("spc_a1", "app_0001");
    expect(rows()).toHaveLength(0);
  });

  it("adds through the daemon, then looks once", async () => {
    await mount([]);
    vi.mocked(api.addSpaceApp).mockResolvedValue(app({ status: "unchecked", tools: [] }));
    vi.mocked(api.probeSpaceApp).mockResolvedValue(app());
    const form = pick("An app on this computer");
    fireEvent.change(within(form).getByLabelText("Address"), { target: { value: "http://127.0.0.1:8080/" } });
    await act(async () => fireEvent.click(within(form).getByRole("button", { name: "Add this app" })));
    expect(api.addSpaceApp).toHaveBeenCalledWith("spc_a1", { kind: "mcp_http", address: "http://127.0.0.1:8080/" });
    expect(api.probeSpaceApp).toHaveBeenCalledWith("spc_a1", "app_0001");
    expect(rows()).toHaveLength(1);
    expect(rows()[0]!.textContent).toContain("2 tools");
  });
});

describe("apps this computer offers", () => {
  it("adds only the two program kinds, with the offer switch and the output folder", async () => {
    vi.mocked(api.deviceApps).mockResolvedValue([]);
    vi.mocked(api.addDeviceApp).mockResolvedValue(app({ offered: true, output_dir: "D:/renders" }));
    vi.mocked(api.probeDeviceApp).mockResolvedValue(app({ offered: true, output_dir: "D:/renders" }));
    render(<OfferedApps />);
    await act(async () => undefined);
    expect(screen.getByText(/Paired computers with the “use the apps this computer offers” permission can use/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Add app" }));
    const kinds = screen.getAllByRole("button").filter((b) => b.classList.contains("m-kind"));
    expect(kinds.map((b) => b.dataset.kind)).toEqual(["mcp_http", "mcp_stdio"]);
    fireEvent.click(kinds[0]!);
    const form = screen.getByRole("form", { name: "An app on this computer" });
    fireEvent.change(within(form).getByLabelText("Address"), { target: { value: "http://127.0.0.1:8080/" } });
    fireEvent.change(within(form).getByLabelText("Output folder (optional)"), { target: { value: "D:/renders" } });
    const offer = within(form).getByRole("switch", { name: "Offer to paired computers" });
    expect(offer.getAttribute("aria-checked")).toBe("false");
    fireEvent.click(offer);
    expect(offer.getAttribute("aria-checked")).toBe("true");
    await act(async () => fireEvent.click(within(form).getByRole("button", { name: "Add this app" })));
    expect(api.addDeviceApp).toHaveBeenCalledWith({ kind: "mcp_http", address: "http://127.0.0.1:8080/", output_dir: "D:/renders", offered: true });
    expect(api.probeDeviceApp).toHaveBeenCalledWith("app_0001");
    const row = document.querySelector('[data-role="device-app"]')!;
    expect(row.textContent).toContain("Offered to paired computers");
    expect(row.textContent).toContain("D:/renders");
  });
});

describe("words the screen never uses", () => {
  it("nowhere in the apps section, its forms, or the offered panel", async () => {
    vi.mocked(api.spaceApps).mockResolvedValue([
      ...FOUR,
      app({ app_id: "app_0003", remotes: [{ peer_id: "dev_0000000000a2", device: "Studio PC", remote_app_id: "app_b001", status: "ok", tools: [READ] }] }),
    ]);
    vi.mocked(api.devices).mockResolvedValue(devices());
    vi.mocked(api.deviceApps).mockResolvedValue([app({ offered: true, output_dir: "D:/renders" })]);
    vi.mocked(api.peerOffers).mockResolvedValue([{ app_id: "app_b002", kind: "mcp_stdio", label: "Notes", tools: [], has_output: false }]);
    render(
      <>
        <AppsSection spaceId="spc_a1" />
        <OfferedApps />
      </>,
    );
    await act(async () => undefined);
    const seen: string[] = [document.body.textContent ?? ""];
    await act(async () => fireEvent.click(screen.getAllByRole("button", { name: "Add Studio PC's copy" })[0]!));
    seen.push(document.body.textContent ?? "");
    for (const add of screen.getAllByRole("button", { name: "Add app" })) fireEvent.click(add);
    seen.push(document.body.textContent ?? "");
    for (const kind of KIND_ORDER) {
      const choice = document.querySelector<HTMLButtonElement>(`.m-kind[data-kind="${kind}"]`)!;
      fireEvent.click(choice);
      seen.push(document.body.textContent ?? "");
      const attrs = [...document.querySelectorAll("[placeholder],[aria-label]")].map((e) => `${e.getAttribute("placeholder") ?? ""} ${e.getAttribute("aria-label") ?? ""}`);
      seen.push(attrs.join(" "));
      fireEvent.click(screen.getAllByRole("button", { name: "Choose another kind" })[0]!);
    }
    for (const text of seen) expect(bannedIn(text)).toEqual([]);
  });
});
