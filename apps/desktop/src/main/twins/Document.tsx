// The twin's document: an open spread being filled in (Passport). Her proposals in pencil (dashed
// violet, an "Ink" button beside each), your words in ink. Each section is a fixed place on the spread,
// so a new entry writes itself into its place and nothing already written moves. During the dress
// rehearsal it folds to its trip page; going live presses the issue seal into it.

import type { ReactNode } from "react";
import type { MissionTurn, Piece, Place, StyleDial, TwinDetail } from "../../lib/contract";
import { day, firstSentence } from "./format";
import { Icon, Portrait, Stamp } from "./marks";
import { piecesAt, type RehearsalStep } from "./select";
import type { ConnectView, SetupState } from "./types";
import { CHANNEL_LABEL, PLACE_LABEL, SECTION, SECTION_EMPTY, TWINS_WORDS as w } from "./words";

export interface DocumentProps {
  s: SetupState;
  /** The section her question is about. */
  lit: Place | null;
  /** The person inks one of her proposals. */
  onInk: (id: string) => void;
  /** The voice section's "sounds like" line opens the voice page. */
  onVoice?: () => void;
  /** The day the seal reads, and whose seal it is. */
  issued: { date: string; by: string };
  /** The twin's latest exchange, for the "sounds like" line. */
  soundsLike?: string;
}

interface PieceProps {
  p: Piece;
  s: SetupState;
  onInk: (id: string) => void;
  tag?: "li" | "div";
  className?: string;
  detail?: boolean;
  evidence?: boolean;
  /** The detail shows only while its section is being asked about (otherwise on hover). */
  optional?: boolean;
  chip?: boolean;
  role?: string;
}

/** One piece: her pencil until the person inks it, then ink with a pink rule when it is their words. */
export function PieceLine({ p, s, onInk, tag = "li", className = "", detail = true, evidence = true, optional = false, chip = false }: PieceProps) {
  const pencil = !p.confirmed;
  const fresh = s.arrived.includes(p.id);
  const inked = s.inked.includes(p.id);
  const ev = p.evidence?.length;
  const tip = [p.detail, ev ? `from ${ev} of your mails` : ""].filter(Boolean).join(", ");
  const Tag = tag;
  return (
    <Tag
      className={`pc ${className} ${fresh ? "is-new" : ""} ${inked ? "is-inked" : ""}`.replace(/\s+/g, " ").trim()}
      data-state={pencil ? "pencil" : "ink"}
      data-origin={p.origin}
      data-piece={p.id}
      data-role={pencil ? "piece-pencil" : "piece-ink"}
      title={tip || undefined}
    >
      <span className="pc__l">{p.label}</span>
      {detail && p.detail && <span className={`pc__d ${optional ? "pc__d--opt" : ""}`.trim()}>{p.detail}</span>}
      {evidence && ev ? <span className="pc__ev">from {ev === 1 ? "one" : ev} of your mails</span> : null}
      {pencil && (
        <button
          type="button"
          className={`pc__ink ${chip ? "pc__ink--chip" : ""}`.trim()}
          title="Ink her proposal: make it yours"
          aria-label={`Ink: ${p.label}`}
          onClick={() => onInk(p.id)}
        >
          <Icon name="nib" />
          <span>Ink</span>
        </button>
      )}
    </Tag>
  );
}

interface SecProps {
  place: Place;
  s: SetupState;
  lit: Place | null;
  /** Printed: the section keeps its blank form under "Your answer lands here". */
  printed?: boolean;
  className?: string;
  aside?: ReactNode;
  children?: ReactNode;
}

function Sec({ place, s, lit, printed = false, className = "", aside, children }: SecProps) {
  const cov = s.twin?.coverage[place] ?? 0;
  const isLit = lit === place;
  const busy = isLit && (s.phase === "thinking" || s.phase === "sending");
  const has = children !== undefined && children !== null && children !== false;
  const slot = isLit ? (
    <p className="sec__land">
      <Icon name="arrow" />
      <span>{busy ? w.writingHere : w.landsHere}</span>
    </p>
  ) : (
    <p className="sec__empty">{SECTION_EMPTY[place]}</p>
  );
  return (
    <section
      className={`sec sec--${place} ${className} ${printed ? "sec--printed" : ""}`.replace(/\s+/g, " ").trim()}
      data-lit={String(isLit)}
      data-cov={String(cov)}
      data-busy={busy ? "true" : undefined}
      data-role={isLit ? "section-lit" : "doc-section"}
    >
      <h3 className="sec__h">
        <span className="cov" data-cov={String(cov)} aria-hidden="true" />
        <span className="sec__n">{SECTION[place]}</span>
        <span className="sec__p">{PLACE_LABEL[place]}</span>
        {aside}
      </h3>
      {printed ? (
        <>
          {isLit && slot}
          {children}
        </>
      ) : has ? (
        children
      ) : (
        slot
      )}
    </section>
  );
}

const byId = (t: TwinDetail | null, id: string) => t?.pieces.find((p) => p.id === id);
const named = (t: TwinDetail | null, place: Place, pred: (p: Piece) => boolean) => piecesAt(t, place).find(pred);

// --- the left page ---------------------------------------------------------------------------------

function Identity({ s, onInk }: { s: SetupState; onInk: (id: string) => void }) {
  const t = s.twin;
  const who = piecesAt(t, "who");
  const name = byId(t, "p_name") ?? who.find((p) => p.detail?.includes("name"));
  const sign = who.find((p) => /^signs as/i.test(p.label));
  const purpose = who.find((p) => p !== name && p !== sign);
  const pic = name ? <Portrait letter={name.label[0] ?? ""} size={76} pencil={!name.confirmed} /> : <Portrait letter="" size={76} blank />;
  const fld = (k: string, p: Piece | undefined, cls = "") => (
    <div className={`fld ${cls}`.trim()}>
      <span className="fld__k">{k}</span>
      {p ? <PieceLine p={p} s={s} onInk={onInk} tag="div" detail={k !== "Name"} /> : <span className="fld__none">-</span>}
    </div>
  );
  return (
    <div className={`ident ${!name && !purpose ? "ident--blank" : ""}`.trim()}>
      <div className="ident__pic">{pic}</div>
      <div className="ident__f">
        {fld("Name", name, "fld--name")}
        {fld("Signs as", sign)}
        {fld("Purpose", purpose)}
      </div>
    </div>
  );
}

function visaState(s: SetupState, kind: "gmail" | "notion"): ConnectView | "empty" | "connected" {
  const t = s.twin;
  if (t?.channels.some((c) => c.kind === kind && c.status === "connected")) return "connected";
  const asked = s.ask?.panel === "connect" && s.ask.channel === kind;
  const piece = piecesAt(t, "channels").find((p) => p.label.toLowerCase() === kind);
  if (!piece && !asked) return "empty";
  return s.connect[kind];
}

function Visa({ s, kind }: { s: SetupState; kind: "gmail" | "notion" }) {
  const st = visaState(s, kind);
  const t = s.twin;
  const piece = piecesAt(t, "channels").find((p) => p.label.toLowerCase() === kind);
  const account = t?.channels.find((c) => c.kind === kind)?.account ?? piece?.detail ?? "";
  const fresh = st === "connected" && !!piece && s.arrived.includes(piece.id);
  let body: ReactNode;
  if (st === "empty") body = <span className="visa__w">No visa yet{t?.pieces.length ? "" : `: ${kind === "gmail" ? "sign in with Google" : "your Notion key"}`}</span>;
  else if (st === "idle") body = <span className="visa__w">Not stamped: {kind === "gmail" ? "sign in with Google" : "paste your Notion key"}</span>;
  else if (st === "waiting")
    body = (
      <span className="visa__w">
        <Icon name="clock" />
        Waiting for you in the browser
      </span>
    );
  else if (st === "checking")
    body = (
      <span className="visa__w">
        <Icon name="clock" />
        Checking the key with Notion
      </span>
    );
  else if (st === "failed") body = <span className="visa__w">Sign-in did not finish. Nothing was saved.</span>;
  else if (st === "rejected") body = <span className="visa__w">Notion did not accept that key</span>;
  else body = <span className="visa__v">{account}</span>;
  return (
    <div className="visa" data-kind={kind} data-state={st} data-pencil={piece && !piece.confirmed && st !== "connected" ? "true" : undefined} data-role="visa">
      <div className="visa__k" title={kind === "gmail" ? "read and send" : "read chosen pages"}>
        <Icon name={kind} />
        <b>{CHANNEL_LABEL[kind]}</b>
        {st === "connected" && <Stamp text="Stamped" tone="success" fresh={fresh} className="visa__stamp" role="visa-stamp" />}
      </div>
      {body}
    </div>
  );
}

function Particulars({ dials, blank, pencil }: { dials: readonly StyleDial[]; blank: boolean; pencil: boolean }) {
  return (
    <div className="parts" data-state={blank ? "blank" : pencil ? "pencil" : "ink"} aria-label="Particulars: its style, and where each value came from">
      <span className="parts__k">
        Particulars <span>{blank ? "set from your samples" : "from your mail, unless marked"}</span>
      </span>
      {dials.map((d) => (
        <div key={d.id} className="part" data-src={d.source} title={`${d.label}: ${d.low} to ${d.high}, ${d.value} of 5`}>
          <span className="part__l">{d.label}</span>
          <span className="pips" aria-label={blank ? "not set" : `${d.value} of 5`}>
            {[1, 2, 3, 4, 5].map((i) => (
              <i key={i} data-on={String(!blank && i <= d.value)} />
            ))}
          </span>
          <span className="part__s">{blank || d.source === "learned" ? "" : d.source === "you" ? "you" : "preset"}</span>
        </div>
      ))}
    </div>
  );
}

/** The eight dials before anything is learned: the printed form, unset. */
const BLANK_DIALS: StyleDial[] = [
  ["formality", "Formality"],
  ["warmth", "Warmth"],
  ["humor", "Humour"],
  ["energy", "Energy"],
  ["length", "Length"],
  ["directness", "Directness"],
  ["expressiveness", "Expressiveness"],
  ["detail", "Detail"],
].map(([id, label]) => ({ id: id!, label: label!, low: "", high: "", value: 0, source: "learned" }));

/** The voice section's one stat: how its latest reply sounds. It opens the voice page. */
function SoundsLike({ line, voiced, onOpen }: { line?: string; voiced: boolean; onOpen: () => void }) {
  const shown = line ? `"${line}"` : voiced ? w.soundsLikeAsk : "not written yet";
  return (
    <button type="button" className="sounds" data-role="sounds-like" onClick={onOpen} title={`${w.soundsLike}: ${line ?? (voiced ? w.soundsLikeAsk : w.soundsLikeNone)}`}>
      <span className="sounds__k">{w.soundsLike}</span>
      <span className="sounds__t">{shown}</span>
      <Icon name="arrow" />
    </button>
  );
}

function Voice({ s, onInk }: { s: SetupState; onInk: (id: string) => void }) {
  const t = s.twin;
  const traits = piecesAt(t, "voice");
  const sample = t?.samples.find((x) => x.picked) ?? t?.samples[0];
  const learned = (t?.dials.length ?? 0) > 0;
  const voicePencil = traits.some((p) => !p.confirmed);
  if (!traits.length || !sample) {
    return (
      <>
        <blockquote className="specimen specimen--blank">
          <span className="specimen__t">Specimen: a few lines of your own sent mail go here</span>
        </blockquote>
        <Particulars dials={learned ? t!.dials : BLANK_DIALS} blank={!learned} pencil />
      </>
    );
  }
  return (
    <>
      <blockquote className="specimen" title={`Specimen of your writing, from your mail to ${sample.to}, ${day(sample.date)}`}>
        <span className="specimen__t">
          <span className="specimen__k">Specimen, your mail to {sample.to}:</span> {firstSentence(sample.excerpt)}
        </span>
      </blockquote>
      <ul className="pcs pcs--lines pcs--voice">
        {traits.map((p) => (
          <PieceLine key={p.id} p={p} s={s} onInk={onInk} />
        ))}
      </ul>
      <Particulars dials={t!.dials} blank={false} pencil={voicePencil && !t!.dials.some((d) => d.source === "you")} />
    </>
  );
}

// --- the right page --------------------------------------------------------------------------------

function Chips({ s, place, onInk }: { s: SetupState; place: Place; onInk: (id: string) => void }) {
  const list = piecesAt(s.twin, place);
  if (!list.length) return null;
  return (
    <ul className="pcs pcs--chips">
      {list.map((p) => (
        <PieceLine key={p.id} p={p} s={s} onInk={onInk} optional chip />
      ))}
    </ul>
  );
}

function Permits({ s, onInk }: { s: SetupState; onInk: (id: string) => void }) {
  const list = piecesAt(s.twin, "chores");
  const coming = list.length || s.ask?.panel === "chores" ? (s.twin?.chores ?? []).filter((c) => c.coming) : [];
  if (!list.length && !coming.length) return null;
  const toolName = (tool: string) => tool.slice(0, 1).toUpperCase() + tool.slice(1);
  return (
    <ul className="pcs pcs--permits">
      {list.map((p) => (
        <PieceLine key={p.id} p={p} s={s} onInk={onInk} className="permit" optional chip />
      ))}
      {coming.length > 0 && (
        <li
          className="permit permit--blank"
          title={`${coming.map((c) => `${c.name}: ${c.does}`).join(" ")} These tools are not connected in this app yet, so these permits cannot be issued.`}
        >
          <span className="pc__l">{coming.map((c) => toolName(c.tool)).join(", ")}</span>
          <span className="tag">coming</span>
        </li>
      )}
    </ul>
  );
}

function Lines({ s, place, onInk, className = "", optional = false, hit }: { s: SetupState; place: Place; onInk: (id: string) => void; className?: string; optional?: boolean; hit?: string }) {
  const list = piecesAt(s.twin, place);
  if (!list.length) return null;
  return (
    <ul className={`pcs pcs--lines ${className}`.trim()}>
      {list.map((p) => (
        <PieceLine key={p.id} p={p} s={s} onInk={onInk} optional={optional} className={hit === p.id ? "is-hit" : ""} />
      ))}
    </ul>
  );
}

export function IssuedSeal({ letter, issued }: { letter: string; issued: { date: string; by: string } }) {
  return (
    <div className="issued" aria-label={`Issued ${issued.date}`} data-role="seal">
      <svg viewBox="0 0 168 168" width="168" height="168" aria-hidden="true" focusable="false">
        <defs>
          <path id="issued-ring" d="M84 84 m-62 0 a62 62 0 1 1 124 0 a62 62 0 1 1 -124 0" />
        </defs>
        <circle cx="84" cy="84" r="80" className="issued__r1" />
        <circle cx="84" cy="84" r="74" className="issued__r2" />
        <circle cx="84" cy="84" r="50" className="issued__r2" />
        <text className="issued__t">
          <textPath href="#issued-ring">
            ISSUED · {issued.date.toUpperCase()} · {issued.by.toUpperCase()} ·
          </textPath>
        </text>
      </svg>
      <span className="issued__pic">
        <Portrait letter={letter} size={70} />
      </span>
    </div>
  );
}

/** The open spread: identity, visas and voice on the left; the rest on the right. */
export function TwinDocument({ s, lit, onInk, onVoice, issued, soundsLike }: DocumentProps) {
  const t = s.twin;
  const blank = !t || !t.pieces.length;
  let status = "Blank: say what it is for";
  if (!blank) status = t.ready ? "Ready to rehearse" : "Being issued";
  if (s.sealed) status = `Issued ${issued.date}`;
  const name = byId(t, "p_name") ?? named(t, "who", (p) => !!p.detail?.includes("name"));
  const kindLine = (
    <span className="doc__line">
      <span className="doc__kind">
        <Icon name="book" />
        Twin document
      </span>
      <span className="doc__status" data-state={s.sealed ? "issued" : t?.ready ? "ready" : "draft"}>
        {status}
      </span>
    </span>
  );
  const asked = (p: Place) => s.ask?.place === p || s.ask?.panel === "connect";
  const has = (p: Place) => piecesAt(t, p).length > 0;
  const visasShown = !blank && (piecesAt(t, "channels").length > 0 || asked("channels"));
  const notionShown = !!t?.channels.some((c) => c.kind === "notion") || piecesAt(t, "channels").some((p) => p.label.toLowerCase() === "notion");
  return (
    <article className={`doc ${s.sealed ? "doc--sealed" : ""} ${blank ? "doc--blank" : ""}`.replace(/\s+/g, " ").trim()} aria-label={`The twin's document: ${name?.label ?? "unnamed"}`}>
      <div className="spread">
        <div className="page page--l">
          <Sec place="who" s={s} lit={lit} printed={blank} aside={kindLine}>
            <Identity s={s} onInk={onInk} />
          </Sec>
          <Sec place="channels" s={s} lit={lit} printed={!visasShown}>
            <div className="visas">
              {visasShown ? <Visa s={s} kind="gmail" /> : <EmptyVisa kind="gmail" first />}
              {visasShown && notionShown ? <Visa s={s} kind="notion" /> : <EmptyVisa kind="notion" first={!visasShown} />}
            </div>
          </Sec>
          <Sec
            place="voice"
            s={s}
            lit={lit}
            printed={!piecesAt(t, "voice").length}
            aside={
              onVoice && !blank ? (
                <SoundsLike line={soundsLike} voiced={piecesAt(t, "voice").some((p) => p.confirmed)} onOpen={onVoice} />
              ) : undefined
            }
          >
            <Voice s={s} onInk={onInk} />
          </Sec>
        </div>
        <div className="page page--r">
          <div className="pair">
            <Sec place="knowledge" s={s} lit={lit}>
              {has("knowledge") ? <Chips s={s} place="knowledge" onInk={onInk} /> : null}
            </Sec>
            <Sec place="chores" s={s} lit={lit}>
              {has("chores") || s.ask?.panel === "chores" ? <Permits s={s} onInk={onInk} /> : null}
            </Sec>
          </div>
          <Sec place="never" s={s} lit={lit}>
            {has("never") ? <Lines s={s} place="never" onInk={onInk} className="pcs--never" /> : null}
          </Sec>
          <Sec place="autonomy" s={s} lit={lit}>
            {has("autonomy") ? <Lines s={s} place="autonomy" onInk={onInk} /> : null}
          </Sec>
          <Sec place="memory" s={s} lit={lit}>
            {has("memory") ? <Lines s={s} place="memory" onInk={onInk} /> : null}
          </Sec>
          <Sec place="mission" s={s} lit={lit}>
            {has("mission") ? <Lines s={s} place="mission" onInk={onInk} optional /> : null}
          </Sec>
        </div>
        {s.sealed && <IssuedSeal letter={name?.label[0] ?? "T"} issued={issued} />}
      </div>
    </article>
  );
}

function EmptyVisa({ kind, first }: { kind: "gmail" | "notion"; first: boolean }) {
  return (
    <div className="visa" data-state="empty">
      <div className="visa__k">
        <Icon name={kind} />
        <b>{CHANNEL_LABEL[kind]}</b>
      </div>
      <span className="visa__w">No visa yet{first ? `: ${kind === "gmail" ? "sign in with Google" : "your Notion key"}` : ""}</span>
    </div>
  );
}

// --- the trip page: the document during its dress rehearsal ---------------------------------------

export interface TripProps {
  s: SetupState;
  step: RehearsalStep;
  turns: readonly MissionTurn[];
  where: string;
  onInk: (id: string) => void;
}

/** The restriction a held draft's risk list (or a hand-back's reason) names: its words are in it. */
function hitOf(s: SetupState, turns: readonly MissionTurn[], step: RehearsalStep): string | undefined {
  let text = "";
  if (step === "handed") text = s.twin?.rehearsal?.note ?? "";
  else if (step === "held" || step === "editing") {
    text = [...turns].reverse().find((t) => t.side === "twin" && t.risks?.length)?.risks?.join(" ") ?? "";
  }
  if (!text) return undefined;
  const said = text.toLowerCase();
  return piecesAt(s.twin, "never").find((p) => {
    const words = p.label.toLowerCase().replace(/^never\s+/, "");
    const long = words.split(/\s+/).filter((x) => x.length > 4);
    return said.includes(words) || long.filter((x) => said.includes(x)).length >= 2;
  })?.id;
}

export function TripPage({ s, step, turns, where, onInk }: TripProps) {
  const t = s.twin;
  const name = byId(t, "p_name") ?? piecesAt(t, "who")[0];
  const sign = piecesAt(t, "who").find((p) => /^signs as/i.test(p.label));
  const lit = step === "held" || step === "editing";
  const twinTurns = turns.filter((x) => x.side === "twin");
  const first = twinTurns[0];
  const held = twinTurns.find((x) => x.kind === "reply" && x.decision === "waits");
  const alone = twinTurns.find((x) => x.decision === "sent_alone");
  const ent: ReactNode[] = [];
  if (first && step !== "waits") ent.push(<Stamp key="w" text="Waited for you" tone="human" sub={first.mark === "me" ? "you said: that's me" : "first message"} />);
  if (step === "waits") ent.push(<Stamp key="w" text="Waits for you" tone="human" sub="first message" fresh />);
  if (held) ent.push(<Stamp key="h" text="Held" tone="warning" sub={`${held.confidence} of ${held.bar ?? "-"}${held.risks?.length ? `, ${held.risks.length === 1 ? "one risk" : `${held.risks.length} risks`}` : ""}`} fresh={step === "held"} />);
  if (held?.mark === "edited") ent.push(<Stamp key="e" text="You edited" tone="human" sub="it learned" fresh={step === "edited"} />);
  if (alone) ent.push(<Stamp key="a" text="Sent on its own" tone="success" sub={`${alone.confidence} of ${alone.bar ?? "-"}, no risks`} fresh={step === "sent"} />);
  if (step === "resolved") ent.push(<Stamp key="r" text="Resolved" tone="success" sub="filed to Notion" fresh />);
  if (step === "handed") ent.push(<Stamp key="b" text="Handed back" tone="human" sub="asked for money" fresh />);
  const hit = hitOf(s, turns, step);
  return (
    <article className="doc doc--trip" aria-label="The twin's document, on its first trip">
      <header className="doc__head">
        <span className="doc__kind">
          <Icon name="book" />
          Twin document
        </span>
        <span className="doc__status">First trip</span>
        <span className="doc__where">on the practice page</span>
      </header>
      <div className="trip">
        <div className="trip__id">
          <Portrait letter={name?.label[0] ?? "T"} size={54} />
          <div>
            <b>{name?.label ?? "Your twin"}</b>
            <span>{sign?.label ?? ""}</span>
          </div>
        </div>
        <section className="sec sec--autonomy">
          <h3 className="sec__h">
            <span className="cov" data-cov="1" />
            <span className="sec__n">Clearance</span>
            <span className="sec__p">what it may send alone</span>
          </h3>
          <Lines s={s} place="autonomy" onInk={onInk} />
        </section>
        <section className="sec sec--never" data-lit={String(lit)}>
          <h3 className="sec__h">
            <span className="cov" data-cov="1" />
            <span className="sec__n">Restrictions</span>
            <span className="sec__p">what it must never do</span>
          </h3>
          <Lines s={s} place="never" onInk={onInk} className="pcs--never" hit={hit} />
        </section>
        <section className="sec sec--entries">
          <h3 className="sec__h">
            <span className="sec__n">Entries</span>
            <span className="sec__p">{where.replace("Notion practice page: ", "practice page ")}</span>
          </h3>
          {ent.length ? <div className="entries">{ent}</div> : <p className="sec__empty">Each draft gets a stamp here.</p>}
        </section>
      </div>
    </article>
  );
}
