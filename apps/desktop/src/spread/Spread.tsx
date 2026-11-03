// The Spread (ADR 0024): the conversation as a book read one spread at a time. Her window shows it
// folded to one page; the main window's Athena place shows it open, with its back pages. The head
// carries her presence, the bookmark for what waits on the person and the look's two switches; the
// ribbon (or, folded, the compact bar) turns the pages, and so does the book's one keymap.

import { useEffect, useLayoutEffect, useMemo, useRef, useState, type MouseEvent, type ReactNode } from "react";
import { STATE_WORDS, sealOf, useHer, waitingCount } from "../athena/store";
import { Seal } from "../theme";
import { ProjectPill } from "../ui";
import { motionStilled } from "../ui/look";
import { bookCommand, turnTo } from "./keymap";
import { LookSwitches } from "./look";
import { bookmarkTarget, exchangesOf, NOW, strayWaiting, WAITING, waitsWords } from "./model";
import { exchangePage, NowLeft, NowRight, WaitingLeft, WaitingRight, type BackPage, type Page } from "./pages";
import "./spread.css";

export interface SpreadProps {
  /** "folded" in her window (one page at a time), "open" in the main window (two pages and the ribbon). */
  layout: "open" | "folded";
  /** The window's own pages after the conversation. */
  back?: readonly BackPage[];
  /** Her window shows the project pill in the head; the main window's bar already has it. */
  pill?: boolean;
  /** Controls the window adds at the end of the head (her window's Hide). */
  chrome?: ReactNode;
  /** Her window drags by its head. */
  onHeadMouseDown?: (e: MouseEvent<HTMLElement>) => void;
  /** Ask the window to show this page (the bookmark or a link elsewhere); changes when it changes. */
  open?: { key: string } | null;
}

export function Spread({ layout, back = [], pill = false, chrome, onHeadMouseDown, open }: SpreadProps) {
  const turns = useHer((s) => s.turns);
  const cards = useHer((s) => s.cards);
  const live = useHer((s) => s.live);
  const status = useHer((s) => s.status);
  const problem = useHer((s) => s.problem);
  const boot = useHer((s) => s.boot);

  const composer = useRef<HTMLTextAreaElement>(null);
  const xs = useMemo(() => exchangesOf(turns), [turns]);
  const liveParts = useMemo(() => live?.parts ?? [], [live]);
  const [at, setAt] = useState<string | null>(null);
  // The cards waiting on no page of this book. While the person is on their page, a card they just
  // signed stays on it (signed), so the page does not vanish under their hand.
  const waitingNow = useMemo(() => strayWaiting(xs, cards, liveParts).map((c) => c.id), [xs, cards, liveParts]);
  const [seen, setSeen] = useState<string[]>([]);
  useEffect(() => {
    setSeen((was) => (at === WAITING ? [...new Set([...was, ...waitingNow])] : []));
  }, [at, waitingNow]);
  const stray = useMemo(
    () => [...new Set([...seen, ...waitingNow])].flatMap((id) => (cards[id] ? [cards[id]] : [])),
    [seen, waitingNow, cards],
  );

  const go = (key: string) => setAt(key);
  const pages: Page[] = [
    ...xs.map((_, i) => exchangePage(xs, i, cards, go)),
    {
      key: NOW,
      kind: "now",
      num: "+",
      label: "Write a new page",
      sub: live ? "she is writing it" : "ask her something",
      live: live !== null && !live.done && live.error === undefined,
      waiting: liveParts.some((p) => p.kind === "card" && cards[p.id]?.state === "waiting"),
      left: <NowLeft ref={composer} empty={xs.length === 0 && status === "ready"} />,
      right: <NowRight />,
      leftLabel: "Left page: a new page",
      rightLabel: "Right page: her answer",
    },
    ...(stray.length > 0
      ? [
          {
            key: WAITING,
            kind: "back" as const,
            num: "◆",
            label: "Waiting for your signature",
            sub: waitingNow.length > 0 ? waitsWords(waitingNow.length).replace(" for your signature", "") : "signed",
            waiting: waitingNow.length > 0,
            left: <WaitingLeft count={waitingNow.length} />,
            right: <WaitingRight stray={stray} />,
            leftLabel: "Left page: cards waiting elsewhere",
            rightLabel: "Right page: the cards",
          },
        ]
      : []),
    ...back.map((b) => ({ ...b, kind: "back" as const, num: b.glyph })),
  ];
  const nowAt = xs.length;
  const firstBack = nowAt + 1;
  // The page shown: the one asked for, else the newest exchange (or the page being written).
  const fallback = xs.length > 0 ? xs[xs.length - 1]!.key : NOW;
  const index = Math.max(0, pages.findIndex((p) => p.key === (at ?? fallback)));
  const page = pages[index] ?? pages[nowAt]!;

  // A finished page settles into the book: the window turns to the page it became, unless words wait
  // in the composer for the next page.
  const draft = useHer((s) => s.draft);
  const wasLive = useRef(live !== null);
  useEffect(() => {
    if (wasLive.current && live === null && (at === NOW || at === null) && xs.length > 0 && !draft) setAt(xs[xs.length - 1]!.key);
    wasLive.current = live !== null;
  }, [live, at, xs, draft]);

  // A turn begun elsewhere in this window (handed words, Try again) is followed to the page being written.
  useEffect(() => {
    if (live !== null && !live.done) setAt(NOW);
  }, [live?.started]); // eslint-disable-line react-hooks/exhaustive-deps


  // Another project is another book: it opens on its newest page.
  // (the project named at boot is the first book, not a switch: a page asked for stays asked for)
  const activeId = useHer((s) => s.activeId);
  const shownBook = useRef<string | null>(null);
  useEffect(() => {
    if (status !== "ready") return;
    if (shownBook.current !== null && shownBook.current !== activeId) setAt(null);
    shownBook.current = activeId;
  }, [activeId, status]);

  // A page asked for by the window (the main window's route).
  useEffect(() => {
    if (open) setAt(open.key);
  }, [open]);

  // ---- turning: the leaf, and each page's own scroll ----
  const book = useRef<HTMLElement>(null);
  const left = useRef<HTMLElement>(null);
  const right = useRef<HTMLElement>(null);
  const scrolls = useRef<Record<string, [number, number, number]>>({});
  const shown = useRef(page.key);
  const [leaf, setLeaf] = useState<"" | "fwd" | "back">("");
  useLayoutEffect(() => {
    if (shown.current === page.key) return;
    const from = pages.findIndex((p) => p.key === shown.current);
    if (book.current && left.current && right.current) {
      scrolls.current[shown.current] = [left.current.scrollTop, right.current.scrollTop, book.current.scrollTop];
      const keep = scrolls.current[page.key] ?? [0, 0, 0];
      left.current.scrollTop = keep[0];
      right.current.scrollTop = keep[1];
      book.current.scrollTop = keep[2];
    }
    shown.current = page.key;
    setLeaf(motionStilled() || from < 0 ? "" : index > from ? "fwd" : "back");
  }, [page.key]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- the keymap ----
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented) return;
      const cmd = bookCommand(e);
      if (!cmd) return;
      e.preventDefault();
      const to = turnTo(cmd, index, pages.length, nowAt);
      setAt(pages[to]!.key);
      if (e.target instanceof HTMLElement && e.target.classList.contains("sp-tab")) tabs.current[to]?.focus();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  // ---- the bookmark ----
  const waiting = useHer(waitingCount);
  const openBookmark = () => {
    const target = bookmarkTarget(xs, cards, liveParts);
    if (!target) return;
    setAt(target);
    window.setTimeout(() => {
      const sign = book.current?.querySelector<HTMLButtonElement>(".card--waiting .card-sign");
      sign?.scrollIntoView?.({ block: "center" });
      sign?.focus();
    }, 30);
  };

  // On the page being written, the field is ready: when the page opens and when the window is shown.
  useEffect(() => {
    if (page.key !== NOW) return;
    composer.current?.focus();
    const onFocus = () => composer.current?.focus();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [page.key]);

  return (
    <div className="sp" data-spread="" data-layout={layout}>
      <Head pill={pill} chrome={chrome} onMouseDown={onHeadMouseDown} waiting={waiting} onBookmark={openBookmark} />
      <main
        ref={book}
        className={`sp-book${page.single ? " is-single" : ""}${leaf ? ` turn-${leaf} turned` : ""}`}
        data-role="book"
        data-page={page.key}
        onAnimationEnd={(e) => {
          if ((e.target as Element).classList.contains("sp-leaf")) setLeaf("");
        }}
      >
        <section ref={left} className="sp-page sp-page-l" tabIndex={-1} aria-label={page.single ? page.label : page.leftLabel} data-role="page-left">
          {status === "reading" && <p className="sp-placeholder">Reading...</p>}
          {status === "offline" ? (
            <div className="sp-stopped" role="alert">
              <p>{problem}</p>
              <button type="button" className="btn btn-sm" onClick={() => void boot()}>
                Try again
              </button>
            </div>
          ) : (
            page.left
          )}
          {status === "ready" && problem && (
            <p className="sp-foot" role="status">
              {problem}
            </p>
          )}
        </section>
        <section ref={right} className="sp-page sp-page-r" tabIndex={-1} aria-label={page.rightLabel} data-role="page-right">
          {status !== "offline" && page.right}
        </section>
        <div className="sp-gutter" aria-hidden="true" />
        <div className="sp-leaf" aria-hidden="true" />
      </main>
      {layout === "open" ? (
        <nav className="sp-ribbon" aria-label="Pages of the conversation" data-role="ribbon">
          {pages.map((p, i) => (
            <Tab key={p.key} page={p} current={i === index} sep={i === firstBack} onClick={() => setAt(p.key)} refFn={(el) => (tabs.current[i] = el)} />
          ))}
        </nav>
      ) : (
        <nav className="sp-compact" aria-label="Pages of the conversation" data-role="compact">
          <button type="button" className="btn btn-sm" aria-label="Previous page" onClick={() => setAt(pages[Math.max(0, index - 1)]!.key)}>
            &larr;
          </button>
          <label className="sp-sr" htmlFor="sp-page-select">
            Go to page
          </label>
          <select id="sp-page-select" value={page.key} onChange={(e) => setAt(e.target.value)}>
            {pages.map((p) => (
              <option key={p.key} value={p.key}>
                {fullName(p)}
              </option>
            ))}
          </select>
          <button type="button" className="btn btn-sm" aria-label="Next page" onClick={() => setAt(pages[Math.min(pages.length - 1, index + 1)]!.key)}>
            &rarr;
          </button>
        </nav>
      )}
    </div>
  );
}

const fullName = (p: Page): string => (p.kind === "exchange" ? `${p.num}: ` : "") + p.label + (p.sub ? ` (${p.sub})` : "");

function Tab({ page, current, sep, onClick, refFn }: { page: Page; current: boolean; sep: boolean; onClick: () => void; refFn: (el: HTMLButtonElement | null) => void }) {
  const cls = ["sp-tab", page.kind === "now" && "is-now", page.kind === "back" && "is-back", page.stopped && "is-stopped"].filter(Boolean).join(" ");
  return (
    <>
      {sep && <span className="sp-tab-sep" aria-hidden="true" />}
      <button ref={refFn} type="button" className={cls} title={fullName(page)} aria-label={fullName(page)} aria-current={current ? "page" : undefined} onClick={onClick} data-key={page.key}>
        <span className="sp-tab-n">
          <span>{page.num}</span>
          {page.live ? <span className="sp-mark-live" /> : page.waiting ? <span className="sp-mark-pin" /> : null}
        </span>
        <span className="sp-tab-l">{page.label}</span>
        <span className="sp-tab-c">{page.sub}</span>
      </button>
    </>
  );
}

interface HeadProps {
  pill: boolean;
  chrome?: ReactNode;
  onMouseDown?: ((e: MouseEvent<HTMLElement>) => void) | undefined;
  waiting: number;
  onBookmark: () => void;
}

function Head({ pill, chrome, onMouseDown, waiting, onBookmark }: HeadProps) {
  const seal = useHer(sealOf);
  const settle = useHer((s) => s.settle);
  const spaces = useHer((s) => s.spaces);
  const activeId = useHer((s) => s.activeId);
  const pendingId = useHer((s) => s.pendingId);
  const select = useHer((s) => s.select);
  const simulated = useHer((s) => s.engine?.simulated === true);
  const words = STATE_WORDS[seal];
  return (
    <header className="sp-top" onMouseDown={onMouseDown} data-role="head">
      <div className="sp-presence">
        <Seal state={seal} size={44} count={waiting} label={waiting > 0 ? `Athena - ${words}, ${waiting} waiting` : `Athena - ${words}`} onSettled={settle} />
        <div>
          <p className="eyebrow">Athena</p>
          <p className="sp-state" data-s={seal} aria-live="polite">
            {words}
          </p>
        </div>
      </div>
      {pill && <ProjectPill compact spaces={spaces} activeId={activeId} pendingId={pendingId} onSelect={(id) => void select(id)} />}
      <span className="sp-spacer" />
      {waiting > 0 && (
        <button
          type="button"
          className="sp-bookmark"
          data-role="bookmark"
          aria-label={`${waiting} waiting for your signature. Open the page that holds ${waiting === 1 ? "it" : "the first"}`}
          onClick={onBookmark}
        >
          <span className="sp-bm-fabric">
            <span>{waitsWords(waiting)}</span>
            <small>Open its page</small>
          </span>
        </button>
      )}
      <div className="sp-tools">
        <span className="sp-hint" aria-hidden="true">
          &larr; &rarr; turn the page
        </span>
        {simulated && (
          <span className="badge" data-tone="warning" title="No Muse key; replies are simulated">
            Simulated
          </span>
        )}
        <LookSwitches />
        {chrome}
      </div>
    </header>
  );
}
