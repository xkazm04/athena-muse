import { act, cleanup, fireEvent, render as mount, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ADD_SPOT, SKY, orbitSpots, skyNodes } from "./Constellation";
import { DevicesLevel, type DevicesOpening } from "./Devices";
import { DEVICES_NOW, EMPTY_VIEW, PC_WINDOW, PENDING, PHONE_WINDOW, VIEW, armed, model } from "./fixtures";
import type { DevicesModel } from "./parts";
import { groupCode, joinPicks, wizardStep } from "./Wizard";

const html = (m: DevicesModel, opening?: DevicesOpening) => renderToStaticMarkup(<DevicesLevel model={m} opening={opening} />);
const count = (h: string, needle: string) => h.split(needle).length - 1;
const withPending = { ...VIEW, pending: [PENDING] };

afterEach(cleanup);

describe("loading and failing", () => {
  it("says it is reading, and says it could not read, as two different facts", () => {
    expect(html(model({}, null))).toContain("Reading the devices");
    const failed = html(model({ problem: "The daemon did not answer." }, null));
    expect(failed).toContain("could not read");
    expect(failed).toContain("The daemon did not answer.");
    expect(failed).not.toContain('class="m-sky"');
  });

  it("keeps the drawing when a later read fails, with the problem above it", () => {
    const h = html(model({ problem: "The daemon did not answer." }));
    expect(h).toContain("may be out of date");
    expect(h).toContain("Read again");
    expect(h).toContain('class="m-sky"');
  });
});

describe("the constellation", () => {
  it("alone: this computer at the centre, the two '+' nodes, and one sentence inviting to pair", () => {
    const h = html(model({}, EMPTY_VIEW));
    expect(h).toContain("m-cnode--self");
    expect(h).toContain("Study PC");
    expect(count(h, "m-cnode m-cnode--add")).toBe(2);
    expect(h).toContain("+ phone");
    expect(h).toContain("+ PC");
    expect(h).toContain("Only this computer so far");
    expect(h).not.toContain("m-cnode--peer");
    expect(h).not.toContain("m-sky__legend");
    expect(h).toContain("network not set up");
  });

  it("draws each peer with its presence, and each presence once", () => {
    const h = html(model());
    for (const presence of ["online", "asleep", "unreachable", "none", "removed"]) {
      expect(count(h, `data-presence="${presence}"`), presence).toBe(1);
    }
    expect(count(h, "m-sky__flow")).toBe(1);
    expect(h).toMatch(/data-state="unreachable"><line[^>]*><\/line><line/);
    expect(h).toContain('aria-label="Laptop, computer, online. Show its details."');
    expect(h).toContain("Studio PC, computer, asleep · seen 2 h ago.");
    expect(h).toContain("Attic tower, computer, out of reach · seen 2 d ago.");
    expect(h).toContain("Kitchen phone, phone, not seen yet.");
    expect(h).toContain("Removed there · seen 3 h ago");
  });

  it("keys every line style the sky draws, and only those", () => {
    for (const m of [model(), model({}, withPending), model({}, EMPTY_VIEW)]) {
      const h = html(m);
      const drawn = new Set([...h.matchAll(/class="m-sky__link" data-state="([a-z_]+)"/g)].map((x) => x[1]));
      const keyed = new Set([...h.matchAll(/<li data-state="([a-z_]+)">/g)].map((x) => x[1]));
      expect(keyed).toEqual(drawn);
    }
  });

  it("puts a waiting request on the orbit as a pulsing node that wants to join", () => {
    const h = html(model({}, withPending));
    expect(h).toContain("m-cnode m-cnode--pending");
    expect(h).toContain('aria-label="Kitchen phone, a phone, wants to join. Answer it."');
    expect(h).toContain('class="m-sky__link" data-state="pending"');
  });

  it("draws a computer this one asked to join as a dotted node", () => {
    const h = html(model());
    expect(h).toContain("m-cnode m-cnode--joining");
    expect(h).toContain("Office PC");
    expect(h).toContain("asked to join it");
  });

  it("places the nodes by a stable order, one alone at the top of the orbit", () => {
    expect(orbitSpots(1)).toEqual([{ x: SKY.cx, y: SKY.cy - SKY.ry }]);
    const reversed = { ...VIEW, peers: [...VIEW.peers].reverse() };
    expect(skyNodes(reversed).map((n) => n.key)).toEqual(skyNodes(VIEW).map((n) => n.key));
    expect(skyNodes(VIEW).map((n) => n.role)).toEqual(["peer", "peer", "peer", "peer", "peer", "joining"]);
    expect(ADD_SPOT.phone.y).toBeGreaterThan(SKY.cy);
    expect(ADD_SPOT.pc.y).toBeGreaterThan(SKY.cy);
  });

  it("says the same in a list a screen reader reads, one item per node", () => {
    const h = html(model());
    const list = h.slice(h.indexOf('class="m-sr"'), h.indexOf("</ul>", h.indexOf('class="m-sr"')));
    expect(count(list, "<li>")).toBe(1 + 6);
    expect(list).toContain("Laptop: computer, online. May talk to Athena here, answer approvals, share memory.");
  });

  it("is never the phone's pairing address, even with a window open", () => {
    const h = html(model({ opened: { phone: PHONE_WINDOW } }, { ...VIEW, beacon: { on: true, url: "http://100.64.0.7:17491/m/" } }));
    expect(h).not.toContain("claim=");
  });
});

describe("a node's drawer", () => {
  it("for a computer: kind, presence, last seen, grants and Revoke; no message box, no memory line", () => {
    const h = html(model(), { selected: "dev_0000000000a2" });
    expect(h).toContain('class="m-cdrawer"');
    expect(h).toContain('aria-expanded="true"');
    expect(h).toContain(">Computer<");
    expect(h).toContain(">Online<");
    expect(h).toContain("2 min ago");
    expect(h).toContain("talk to Athena here, answer approvals, share memory");
    expect(count(h, ">Revoke<")).toBe(1);
    expect(h).not.toContain("Send a message");
    expect(h).not.toContain("Memory");
  });

  it("for a phone: never probed", () => {
    const h = html(model(), { selected: "dev_0000000000a3" });
    expect(h).toContain("Not probed (a phone)");
    expect(h).toContain("never");
  });

  it("names the mend for a peer the other side removed", () => {
    const h = html(model(), { selected: "dev_0000000000a6" });
    expect(h).toContain("That computer no longer lists this one. Revoke it here, then pair it again.");
  });

  it("for this computer: its name to rename, the private network, and the phone's switch", () => {
    const off = html(model({}, EMPTY_VIEW), { selected: "self" });
    expect(off).toContain("Its name");
    expect(off).toContain(">Rename<");
    expect(off).toContain("Private network: Not set up");
    expect(off).toContain('role="switch" aria-checked="false"');
    const on = html(model({}, { ...VIEW, beacon: { on: true, url: null } }), { selected: "self" });
    expect(on).toContain('aria-checked="true"');
    expect(on).toContain("Listening at 100.64.0.7:17491");
  });

  it("for a request: the card names the address, says what approving replaces, and cannot be approved in its first moment", () => {
    const fresh = html(model({}, withPending), { selected: "pair_0000000000b1" });
    expect(fresh).toContain("Kitchen phone asks to be let in");
    expect(fresh).toContain("Asking from 100.64.0.21");
    expect(fresh).toContain("Approve wakes in a moment");
    expect(fresh).not.toContain('data-armed="1"');
    const ready = html(armed(), { selected: "pair_0000000000b1" });
    expect(ready).toContain('data-armed="1"');
    expect(ready).not.toContain("Approve wakes in a moment");
    // Only what was asked, each ticked: grants narrow, never widen.
    expect(ready.match(/role="checkbox" aria-checked="true"/g)).toHaveLength(2);
    expect(ready).not.toContain(">share memory<");
    const replacing = { ...withPending, pending: [{ ...PENDING, replaces: { peer_id: "dev_0000000000a2", name: "Laptop" } }] };
    expect(html(model({}, replacing), { selected: "pair_0000000000b1" })).toContain("Approving replaces your paired device Laptop");
  });

  it("for this computer's own ask: where it stands", () => {
    expect(html(model(), { selected: "pair_0000000000e1" })).toContain("waiting for the person there to approve");
  });

  it("is not there for a node that went away", () => {
    expect(html(model(), { selected: "dev_gone" })).not.toContain('class="m-cdrawer"');
  });
});

describe("the wizard: a phone", () => {
  it("draws the QR, the code beside it, the address once, and nothing secret in a name", () => {
    const h = html(model({ opened: { phone: PHONE_WINDOW } }), { wizard: "phone" });
    expect(h).toContain('role="dialog"');
    expect(h).toContain('data-step="code"');
    expect(h).toContain('<svg class="m-qr"');
    expect(h).toContain("7Q4-K2P");
    expect(h).toContain("4:00 left");
    expect(h).toContain(`<code class="m-cwizard__url">${PHONE_WINDOW.url}</code>`);
    for (const m of h.matchAll(/(title|aria-label|aria-description|alt)="([^"]*)"/g)) expect(m[2], m[0]).not.toContain("claim=");
  });

  it("shows the code alone when the encoder cannot draw the address", () => {
    const phone = { ...PHONE_WINDOW, url: `http://100.64.0.7:17491/m/#claim=${"x".repeat(300)}` };
    const h = html(model({ opened: { phone } }), { wizard: "phone" });
    expect(h).not.toContain('<svg class="m-qr"');
    expect(h).toContain('<span class="m-lens__code">7Q4-K2P</span>');
    expect(h).toContain("The picture cannot be drawn here");
  });

  it("greys out when the window ran out, and offers a new code and nothing of the old one", () => {
    const phone = { ...PHONE_WINDOW, expires_at: new Date(DEVICES_NOW - 1000).toISOString() };
    const h = html(model({ opened: { phone } }), { wizard: "phone" });
    expect(h).toContain('data-expired="1"');
    expect(h).toContain("This code ran out.");
    expect(h).toContain(">New code<");
    expect(h).not.toContain("claim=");
    expect(h).not.toContain('<svg class="m-qr"');
    expect(h).not.toContain("7Q4-K2P");
  });

  it("offers to show a code when none is open (after a reload, say)", () => {
    const h = html(model({}, EMPTY_VIEW), { wizard: "phone" });
    expect(h).toContain(">Show a code<");
    expect(h).not.toContain('<svg class="m-qr"');
  });

  it("says why there is no address when the listener cannot bind", () => {
    const phone = { ...PHONE_WINDOW, url: null };
    const h = html(model({ opened: { phone } }), { wizard: "phone" });
    expect(h).toContain("cannot listen for the phone");
    expect(h).toContain("7Q4-K2P");
  });

  it("moves on to Approve by itself when the phone asks", () => {
    const requested = { ...PENDING, pairing_id: PHONE_WINDOW.pairing_id };
    const m = model({ opened: { phone: PHONE_WINDOW }, seenAt: { [requested.pairing_id]: DEVICES_NOW - 5000 } }, { ...VIEW, pending: [requested] });
    const approve = html(m, { wizard: "phone" });
    expect(approve).toContain('data-step="approve"');
    expect(approve).toContain("Kitchen phone wants to join");
    expect(approve).toContain('data-armed="1"');
  });
});

describe("the wizard: a computer", () => {
  it("starts with the choice of which side shows the code", () => {
    const h = html(model(), { wizard: "pc" });
    expect(h).toContain('data-step="choose"');
    expect(h).toContain("Show a code on this PC");
    expect(h).toContain("Join another PC");
  });

  it("shows this computer's code and address, with the same ring", () => {
    const h = html(model({ opened: { pc: PC_WINDOW } }), { wizard: "pc", branch: "show" });
    expect(h).toContain('data-step="code"');
    expect(h).toContain("M7K-Q2X");
    expect(h).toContain("100.64.0.7");
    expect(h).toContain('stroke-dasharray="80.00 100"');
    expect(h).toContain("open Settings, then Devices");
  });

  it("joins: the private network's computers to pick from, phones and offline ones left out", () => {
    const overlay = {
      ok: true,
      state: "up" as const,
      self_ip: "100.64.0.9",
      peers: [
        { name: "study", ip: "100.101.7.8", os: "windows", online: true },
        { name: "pixel", ip: "100.101.7.9", os: "android", online: true },
        { name: "attic", ip: "100.101.7.10", os: "linux", online: false },
      ],
      showing: 3,
      total: 25,
      footer: "(showing 3 of 25)",
    };
    const h = html(model({ overlay }, EMPTY_VIEW), { wizard: "pc", branch: "join" });
    expect(h).toContain('data-step="join"');
    expect(h).toContain(">study<");
    expect(h).toContain("100.101.7.8");
    expect(h).not.toContain("pixel");
    expect(h).not.toContain("attic");
    expect(h).toContain("(showing 3 of 25)");
    expect(h).toContain(">Ask to join<");
    expect(html(model({}, EMPTY_VIEW), { wizard: "pc", branch: "join" })).not.toContain("m-picks");
    expect(joinPicks(null)).toEqual({ rows: [], footer: "" });
  });

  it("moves on to Approve when the computer it joined asks back", () => {
    const back = { ...PENDING, pairing_id: "pair_0000000000f9", name: "Office PC", kind: "pc" as const, pair_back: true };
    const h = html(model({}, { ...VIEW, pending: [back] }), { wizard: "pc", branch: "join" });
    expect(h).toContain('data-step="approve"');
    expect(h).toContain("Office PC, which this computer joined, asks to be let in here too");
  });
});

describe("the wizard's step is read from the mirror", () => {
  it("is Done once the answered request has left the list", () => {
    const requested = { ...PENDING, pairing_id: PHONE_WINDOW.pairing_id };
    const { state } = model({ opened: { phone: PHONE_WINDOW } }, { ...VIEW, pending: [requested] });
    const answered = { pairingId: requested.pairing_id, name: "Kitchen phone", choice: "approve" as const };
    expect(wizardStep("phone", null, state, answered).step).toBe("approve");
    const gone = { ...state, view: { ...state.view!, pending: [] } };
    expect(wizardStep("phone", null, gone, answered)).toEqual({ step: "done", pending: null });
    expect(wizardStep("phone", null, gone, null).step).toBe("code");
  });

  it("reads a code as two halves, and leaves anything else as it is", () => {
    expect(groupCode("7Q4K2P")).toBe("7Q4-K2P");
    expect(groupCode("7Q4-K2P")).toBe("7Q4-K2P");
  });
});

describe("not in this port", () => {
  it("has no message box, no vitals, no memory line and no setup conversation", () => {
    const h = html(model(), { selected: "dev_0000000000a2" });
    for (const gone of ["Send a message", "m-vitals__held", "Memory", "room"]) expect(h, gone).not.toContain(gone);
  });
});

describe("driven", () => {
  const byLabel = (label: string) => document.querySelector<HTMLButtonElement>(`[aria-label^="${label}"]`)!;
  const press = (el: Element) => act(() => void fireEvent.click(el));

  it("'+ phone' opens the wizard and asks for a window; Escape folds it back, the focus on the node", () => {
    const openPairing = vi.fn(async () => {});
    mount(<DevicesLevel model={model({}, EMPTY_VIEW, { openPairing })} />);
    press(byLabel("Add a phone"));
    expect(openPairing).toHaveBeenCalledWith("phone");
    const dialog = document.querySelector('[role="dialog"]')!;
    expect(dialog).not.toBeNull();
    expect(document.querySelector(".m-sky")!.hasAttribute("inert")).toBe(true);
    expect(document.activeElement?.id).toBe("cwizard-title");

    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(dialog.getAttribute("data-closing")).toBe("1");
    act(() => void fireEvent.animationEnd(dialog));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.querySelector(".m-sky")!.hasAttribute("inert")).toBe(false);
    expect(document.activeElement).toBe(byLabel("Add a phone"));
  });

  it("does not mint a second window while the first is live", () => {
    const openPairing = vi.fn(async () => {});
    const phone = { ...PHONE_WINDOW, expires_at: "2999-01-01T00:00:00Z" };
    mount(<DevicesLevel model={model({ opened: { phone } }, EMPTY_VIEW, { openPairing })} />);
    press(byLabel("Add a phone"));
    expect(openPairing).not.toHaveBeenCalled();
    expect(document.querySelector("svg.m-qr")).not.toBeNull();
  });

  it("a computer's choice to show a code asks for a window", () => {
    const openPairing = vi.fn(async () => {});
    mount(<DevicesLevel model={model({}, VIEW, { openPairing })} />);
    press(byLabel("Add a computer"));
    press(screen.getByRole("button", { name: /Show a code on this PC/ }));
    expect(openPairing).toHaveBeenCalledWith("pc");
  });

  it("keeps Tab inside the wizard", () => {
    mount(<DevicesLevel model={model()} />);
    press(byLabel("Add a computer"));
    const dialog = document.querySelector('[role="dialog"]')!;
    const stops = [...dialog.querySelectorAll<HTMLElement>("button:not([disabled])")];
    const last = stops[stops.length - 1]!;
    act(() => last.focus());
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(document.activeElement).toBe(stops[0]);
    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
  });

  it("approving in the wizard moves it to Done once the request leaves the list", () => {
    const requested = { ...PENDING, pairing_id: PHONE_WINDOW.pairing_id };
    const answer = vi.fn(async () => {});
    const base = model({ opened: { phone: PHONE_WINDOW }, seenAt: { [requested.pairing_id]: DEVICES_NOW - 5000 } }, { ...VIEW, pending: [requested] }, { answer });
    const view = mount(<DevicesLevel model={base} />);
    press(byLabel("Add a phone"));
    press(screen.getByRole("button", { name: "Approve" }));
    expect(answer).toHaveBeenCalledWith(requested.pairing_id, "approve");
    view.rerender(<DevicesLevel model={{ ...base, state: { ...base.state, view: { ...VIEW, pending: [] } } }} />);
    expect(document.querySelector('[role="dialog"]')!.getAttribute("data-step")).toBe("done");
    expect(document.body.textContent).toContain("Kitchen phone is in");
  });

  it("an approval the daemon refused is titled as not let in, as its body says", () => {
    const requested = { ...PENDING, pairing_id: PHONE_WINDOW.pairing_id };
    const base = model({ opened: { phone: PHONE_WINDOW }, seenAt: { [requested.pairing_id]: DEVICES_NOW - 5000 } }, { ...VIEW, pending: [requested] });
    const view = mount(<DevicesLevel model={base} />);
    press(byLabel("Add a phone"));
    press(screen.getByRole("button", { name: "Approve" }));
    const errors = { [requested.pairing_id]: "The request ran out before it was answered." };
    view.rerender(<DevicesLevel model={{ ...base, state: { ...base.state, errors, view: { ...VIEW, pending: [] } } }} />);
    expect(document.body.textContent).toContain("Nothing was let in.");
    expect(document.querySelector("#cwizard-title")!.textContent).toBe("Kitchen phone was not let in");
  });

  it("a refused rename keeps the name the person typed, and Rename waits while one is out", () => {
    const rename = vi.fn(async () => {});
    const base = model({}, VIEW, { rename });
    const view = mount(<DevicesLevel model={base} />);
    press(byLabel("Study PC, this computer"));
    const input = document.querySelector<HTMLInputElement>(".m-cdrawer input")!;
    fireEvent.change(input, { target: { value: "Attic PC" } });
    const button = () => screen.getByRole("button", { name: "Rename" }) as HTMLButtonElement;
    press(button());
    expect(rename).toHaveBeenCalledWith("Attic PC");
    view.rerender(<DevicesLevel model={{ ...base, state: { ...base.state, busy: { rename: true } } }} />);
    expect(button().disabled).toBe(true);
    view.rerender(<DevicesLevel model={{ ...base, state: { ...base.state, busy: {}, errors: { rename: "A name is at most 40 characters." } } }} />);
    expect(document.querySelector<HTMLInputElement>(".m-cdrawer input")!.value).toBe("Attic PC");
    expect(document.body.textContent).toContain("A name is at most 40 characters.");
    const named = { ...VIEW, self: { ...VIEW.self, name: "Attic PC" } };
    view.rerender(<DevicesLevel model={{ ...base, state: { ...base.state, errors: {}, view: named } }} />);
    expect(document.querySelector<HTMLInputElement>(".m-cdrawer input")!.value).toBe("Attic PC");
    expect(button().disabled).toBe(true);
  });

  it("a refused join keeps the code that was typed, and Ask to join waits while one is out", () => {
    const join = vi.fn(async () => {});
    const base = model({}, EMPTY_VIEW, { join });
    const opening = { wizard: "pc" as const, branch: "join" as const };
    const view = mount(<DevicesLevel model={base} opening={opening} />);
    const [address, code] = [...document.querySelectorAll<HTMLInputElement>(".m-cwizard__join input")];
    fireEvent.change(address!, { target: { value: "100.64.0.7" } });
    fireEvent.change(code!, { target: { value: "123456" } });
    const ask = () => screen.getByRole("button", { name: "Ask to join" }) as HTMLButtonElement;
    press(ask());
    expect(join).toHaveBeenCalledWith("100.64.0.7", "123456");
    const show = (state: Partial<DevicesModel["state"]>) =>
      view.rerender(<DevicesLevel model={{ ...base, state: { ...base.state, ...state } }} opening={opening} />);
    show({ busy: { join: true } });
    expect(ask().disabled).toBe(true);
    show({ busy: {}, errors: { join: "That code is not right." } });
    const values = () => [...document.querySelectorAll<HTMLInputElement>(".m-cwizard__join input")].map((i) => i.value);
    expect(values()).toEqual(["100.64.0.7", "123456"]);
    expect(document.body.textContent).toContain("That code is not right.");
    show({ busy: {}, errors: {} });
    press(ask());
    show({ busy: { join: true } });
    show({ busy: {}, errors: {} });
    expect(values()).toEqual(["100.64.0.7", ""]);
  });

  it("a node opens its drawer and a second press closes it", () => {
    mount(<DevicesLevel model={model()} />);
    press(byLabel("Laptop"));
    expect(document.querySelector(".m-cdrawer")).not.toBeNull();
    press(byLabel("Laptop"));
    expect(document.querySelector(".m-cdrawer")).toBeNull();
  });

  it("revoke and decline reach the store's acts", () => {
    const revoke = vi.fn(async () => {});
    const answer = vi.fn(async () => {});
    mount(<DevicesLevel model={model({}, withPending, { revoke, answer })} />);
    press(byLabel("Laptop"));
    press(screen.getByRole("button", { name: "Revoke" }));
    expect(revoke).toHaveBeenCalledWith("dev_0000000000a2");
    press(byLabel("Kitchen phone, a phone, wants to join"));
    press(screen.getByRole("button", { name: "Decline" }));
    expect(answer).toHaveBeenCalledWith("pair_0000000000b1", "decline");
  });
});

describe("memory replication lines", () => {
  const withMemory = (memory: NonNullable<(typeof VIEW)["peers"][number]["memory"]>) => ({
    ...VIEW,
    peers: VIEW.peers.map((p) => (p.peer_id === "dev_0000000000a2" ? { ...p, memory } : p)),
  });
  const synced = { last_pull_at: new Date(DEVICES_NOW - 60_000).toISOString(), pulled: 3, conflicts: 0, deferred: 0, state: "ok" as const };

  it("says how many came across and when, in the drawer and in the list", () => {
    const m = model({}, withMemory(synced));
    const h = html(m, { selected: "dev_0000000000a2" });
    expect(h).toContain(">Memory<");
    expect(h).toContain("in step, 3 memories pulled, last 1 min ago");
    expect(h).toContain("Memory: in step, 3 memories pulled, last 1 min ago.");
  });

  it("names conflicts and what waits", () => {
    const h = html(model({}, withMemory({ ...synced, pulled: 1, conflicts: 2, deferred: 1 })), { selected: "dev_0000000000a2" });
    expect(h).toContain("1 memory pulled");
    expect(h).toContain("1 waiting");
    expect(h).toContain("2 conflicts kept for a look (the local memory stays)");
  });

  it("puts a refusal in plain words", () => {
    for (const [state, words] of [
      ["not_shared", "not shared by that computer"],
      ["removed_there", "removed there"],
      ["unreachable", "could not reach it"],
    ] as const) {
      const h = html(model({}, withMemory({ ...synced, state })), { selected: "dev_0000000000a2" });
      expect(h, state).toContain(`${words}, 3 memories pulled`);
    }
  });

  it("says nothing before the first pull and nothing for a phone", () => {
    const h = html(model(), { selected: "dev_0000000000a3" });
    expect(h).not.toContain("Memory");
    expect(html(model(), { selected: "dev_0000000000a2" })).not.toContain(">Memory<");
  });
});
