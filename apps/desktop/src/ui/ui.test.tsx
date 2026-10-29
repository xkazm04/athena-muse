import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Card, LedgerRow, SpaceSummary } from "../lib/contract";
import { DaemonError } from "../lib/daemon";
import { COST_COLUMNS } from "../main/athena/AthenaView";
import { CardView } from "./CardView";
import { Ledger } from "./Ledger";
import { ProjectPill } from "./ProjectPill";
import { StatStrip } from "./StatStrip";

afterEach(cleanup);

const card: Card = {
  id: "card_1",
  space_id: "spc_1",
  action: "propose_brief",
  label: "Change this project's brief to: file by April",
  args: { brief: "file by April" },
  state: "waiting",
  created: "2026-10-26T12:00:00Z",
};

const space = (id: string, name: string): SpaceSummary => ({
  id, name, brief: "", apps: [], hue: 210, created: "", updated: "", counts: { episodes: 0, facts: 0 },
});

describe("CardView", () => {
  it("signs once and reports the resolved card", async () => {
    const decided = { ...card, state: "approved" as const };
    const onDecide = vi.fn().mockResolvedValue(decided);
    const onResolved = vi.fn();
    render(<CardView card={card} onDecide={onDecide} onResolved={onResolved} />);
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Sign" })));
    expect(onDecide).toHaveBeenCalledWith("approve");
    expect(onResolved).toHaveBeenCalledWith(decided);
  });

  it("shows a resolved card without buttons", () => {
    render(<CardView card={{ ...card, state: "approved" }} onDecide={vi.fn()} />);
    expect(screen.getByText("Signed, ran once")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("gives an ordinary card no text to edit", () => {
    render(<CardView card={card} onDecide={vi.fn()} />);
    expect(screen.queryByRole("textbox")).toBeNull();
  });
});

describe("CardView on a twin's draft", () => {
  const draft: Card = {
    ...card,
    action: "twin_send",
    label: "Send a reply to Lumen Vale as you",
    args: { text: "You'd get a free visualizer and a credit.", to: "lumen@vale.example" },
  };

  it("signs the draft as it is without an edit", async () => {
    const onDecide = vi.fn().mockResolvedValue({ ...draft, state: "approved" });
    render(<CardView card={draft} onDecide={onDecide} />);
    const field = screen.getByRole("textbox", { name: /The message/ }) as HTMLTextAreaElement;
    expect(field.value).toBe("You'd get a free visualizer and a credit.");
    fireEvent.change(field, { target: { value: "You'd get a free visualizer and a credit.  " } });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Sign" })));
    expect(onDecide).toHaveBeenCalledWith("approve");
  });

  it("sends the person's words only when they changed them", async () => {
    const onDecide = vi.fn().mockResolvedValue({ ...draft, state: "approved" });
    render(<CardView card={draft} onDecide={onDecide} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: " A visualizer and a credit. Friday? " } });
    expect(screen.getByText("Your words: they are sent as the message")).toBeTruthy();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Sign your words" })));
    expect(onDecide).toHaveBeenCalledWith("approve", { text: "A visualizer and a credit. Friday?" });
  });

  it("puts its words back, never signs an empty message, and declines without the edit", async () => {
    const onDecide = vi.fn().mockResolvedValue({ ...draft, state: "declined" });
    render(<CardView card={draft} onDecide={onDecide} />);
    const field = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(field, { target: { value: "   " } });
    expect((screen.getByRole("button", { name: "Sign your words" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Put its words back" }));
    expect(field.value).toBe(draft.args.text);
    fireEvent.change(field, { target: { value: "Something else" } });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Decline" })));
    expect(onDecide).toHaveBeenCalledWith("decline");
  });

  it("keeps the words and shows the problem when the send failed", async () => {
    const onDecide = vi.fn().mockRejectedValue(new DaemonError(400, "bad_request", "Gmail did not send it: it said no"));
    render(<CardView card={draft} onDecide={onDecide} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "My words" } });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Sign your words" })));
    expect(screen.getByRole("alert").textContent).toBe("Gmail did not send it: it said no");
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("My words");
    expect(screen.getByText("Needs your signature")).toBeTruthy();
  });

  it("shows a sent draft's text without a field, in plain words", () => {
    render(<CardView card={{ ...draft, state: "approved" }} onDecide={vi.fn()} />);
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.getByText(draft.args.text as string)).toBeTruthy();
    expect(screen.getByText("Send this email")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/\b(token|connector|oauth|api|prompt|node|slot)s?\b/i);
  });
});

describe("ProjectPill", () => {
  it("names the active project and switches through the menu", () => {
    const onSelect = vi.fn();
    render(<ProjectPill spaces={[space("spc_1", "Taxes"), space("spc_2", "Garden")]} activeId="spc_1" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /Taxes/ }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: /Garden/ }));
    expect(onSelect).toHaveBeenCalledWith("spc_2");
  });

  it("reads Core when no project is active and says when a switch waits", () => {
    render(<ProjectPill spaces={[space("spc_1", "Taxes")]} activeId="" pendingId="spc_1" onSelect={vi.fn()} />);
    expect(screen.getByText("Core")).toBeTruthy();
    expect(screen.getByText("switches after this reply")).toBeTruthy();
  });
});

describe("StatStrip", () => {
  it("shows an unmeasured value as a dash, never 0", () => {
    render(
      <StatStrip
        label="At a glance"
        tiles={[
          { key: "a", label: "Sent this week", value: 23, unit: "14 on their own" },
          { key: "b", label: "Held back" },
          { key: "c", label: "Live", value: 0 },
        ]}
      />,
    );
    const tiles = screen.getAllByText(/Sent this week|Held back|Live/).map((l) => l.parentElement!);
    expect(tiles.map((t) => t.querySelector("b")!.textContent)).toEqual(["23", "-", "0"]);
    expect(tiles[0]!.getAttribute("data-role")).toBe("stat-tile");
  });

  it("reads as quiet placeholders while busy, with no numbers", () => {
    const { container } = render(<StatStrip label="At a glance" tiles={[]} busy={3} />);
    expect(container.querySelectorAll(".ui-stat--wait")).toHaveLength(3);
    expect(container.textContent).toBe("");
  });
});

const ledgerRow = (id: number, ok = true): LedgerRow => ({
  id,
  ts: "2026-10-26T12:00:00Z",
  surface: "turn",
  space_id: "",
  engine: "scripted",
  model: "muse-1",
  input_tokens: 1200,
  output_tokens: 300,
  cost_usd: id === 2 ? undefined : 0.0123,
  cost_estimated: true,
  latency_ms: 840,
  ok,
  error: ok ? undefined : "engine_unavailable",
});

describe("Ledger", () => {
  it("draws the Athena page's Costs table exactly as before it moved", () => {
    const rows = [ledgerRow(1), ledgerRow(2, false)];
    const where = () => "Core";
    const before = render(<CostsBefore rows={rows} where={where} />).container.innerHTML;
    cleanup();
    const after = render(<Ledger className="m-table" wrapClassName="m-table-wrap" columns={COST_COLUMNS(where)} rows={rows} rowKey={(r) => r.id} />)
      .container.innerHTML;
    expect(after).toBe(before);
  });

  it("puts the totals line in the foot and a full-width line when empty", () => {
    const cols = [
      { key: "n", head: "Name", cell: (r: { n: string }) => r.n },
      { key: "m", head: "More", cell: () => "x" },
    ];
    const { container, rerender } = render(<Ledger label="Things" columns={cols} rows={[{ n: "a" }]} rowKey={(r) => r.n} totals={["1 thing", "est. $0.10"]} totalsCellClassNames={[undefined, "wide"]} />);
    expect(container.querySelector("tfoot td.wide")!.textContent).toBe("est. $0.10");
    rerender(<Ledger label="Things" columns={cols} rows={[]} rowKey={(r) => r.n} empty="Nothing yet" emptyClassName="none" />);
    const td = container.querySelector("tbody tr.none td")!;
    expect(td.getAttribute("colspan")).toBe("2");
    expect(td.textContent).toBe("Nothing yet");
  });
});

/** The Costs table's markup before Ledger, verbatim, to hold the refactor to "no visual change". */
function CostsBefore({ rows, where }: { rows: LedgerRow[]; where: (r: LedgerRow) => string }) {
  const money = (usd: number) => (usd < 1 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`);
  const latency = (ms: number) => (ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`);
  const time = (iso: string) => new Date(iso).toLocaleString();
  const tokens = (n?: number) => (n === undefined ? "-" : n.toLocaleString());
  return (
    <div className="m-table-wrap">
      <table className="m-table">
        <thead>
          <tr>
            <th scope="col">Time</th>
            <th scope="col">Where</th>
            <th scope="col">Model</th>
            <th scope="col" className="m-num">
              Tokens in / out
            </th>
            <th scope="col" className="m-num">
              est. $
            </th>
            <th scope="col" className="m-num">
              Latency
            </th>
            <th scope="col">Result</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{time(r.ts)}</td>
              <td>{where(r)}</td>
              <td className="m-mono">
                {r.model}
                {r.engine === "scripted" && " (simulated)"}
              </td>
              <td className="m-num">
                {tokens(r.input_tokens)} / {tokens(r.output_tokens)}
              </td>
              <td className="m-num">{r.cost_usd === undefined ? "unpriced" : `est. ${money(r.cost_usd)}`}</td>
              <td className="m-num">{latency(r.latency_ms)}</td>
              <td>
                {r.ok ? (
                  <span className="badge" data-tone="success">
                    ok
                  </span>
                ) : (
                  <span className="badge" data-tone="error" title={r.error}>
                    {r.error ?? "failed"}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
