// The setup page (Passport): the twin's document as an open spread with one working slip beside it,
// and Athena's panel across the bottom. During the dress rehearsal the spread folds to its trip page
// beside the practice page; going live presses the seal. It takes the whole window, like the stage.

import { useEffect } from "react";
import type { TwinDetail } from "../../lib/contract";
import { AthenaPanel } from "./Athena";
import { TripPage, TwinDocument } from "./Document";
import { firstSentence } from "./format";
import { PracticePage } from "./Practice";
import { currentTurn, litPlace, piecesAt, rehearsalStep, turnsOf } from "./select";
import { Slip } from "./Slip";
import type { SetupState, TwinsAction } from "./types";
import { LEVEL } from "./words";

/** The practice page's own words, when the example names them. */
export interface PracticeWords {
  where: string;
  playedBy: string;
}

export interface SetupProps {
  s: SetupState;
  dispatch: (a: TwinsAction) => void;
  onBack: () => void;
  onVoice: () => void;
  practice?: PracticeWords;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Everything the setup says about going live, read from the twin itself. */
export function liveWords(t: TwinDetail | null) {
  const name = t?.name ?? "Your twin";
  const stays: string[] = [];
  for (const c of t?.channels ?? []) {
    const label = c.kind === "gmail" ? "Gmail" : c.scope ? "Notion practice page" : "Notion";
    const lvl = (a: "review" | "assist" | "auto") => `${LEVEL[a].label}${a === "auto" && c.kind === "gmail" ? ` at ${c.bar}` : ""}`;
    if (c.split) {
      stays.push(`${label} first messages: ${lvl(c.split.first_message)}`, `${label} replies: ${lvl(c.split.reply)}`);
    } else stays.push(`${label}: ${lvl(c.autonomy)}`);
  }
  const gmail = t?.channels.find((c) => c.kind === "gmail");
  const how = gmail?.split
    ? `First messages ${gmail.split.first_message === "auto" ? "may go on their own" : "wait for you"}; replies ${gmail.split.reply === "auto" ? "may go on their own" : "wait for you"}.`
    : gmail?.autonomy === "auto"
      ? "It sends on its own when it is sure and its risk list is empty."
      : "Every send waits for you.";
  const d = new Date(t?.since ?? t?.updated ?? Date.now());
  const sign = piecesAt(t, "who").find((p) => /^signs as/i.test(p.label))?.label ?? "";
  return {
    line: `${name} is live. ${how} You'll find it on your twins page.`,
    stays,
    issued: { date: `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`, by: sign.split(/\s+from\s+/i)[1] ?? name },
  };
}

const signsAs = (t: TwinDetail | null) => {
  const sign = piecesAt(t, "who").find((p) => /^signs as/i.test(p.label));
  return sign ? sign.label.replace(/^signs as\s+/i, "").split(/\s+from\s+/i)[0]! : "you";
};

/** How it sounds, in one line: the first words of the preview the daemon keeps for its voice as it
 * is now. None while there is no such preview (the voice page writes one). */
export function soundsLikeOf(t: TwinDetail | null): string | undefined {
  return t?.preview ? firstSentence(t.preview.text) : undefined;
}

/** The setup's own keys: 1-3 pick her suggestions, unless the person is typing. */
function useKeys(dispatch: (a: TwinsAction) => void, onBack: () => void, sealed: boolean) {
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const el = document.activeElement;
      if (el instanceof HTMLElement && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return;
      if (e.metaKey || e.ctrlKey || e.altKey || !/^[123]$/.test(e.key)) return;
      e.preventDefault();
      const i = Number(e.key) - 1;
      if (sealed && i === 0) onBack();
      else dispatch({ type: "pick", index: i });
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [dispatch, onBack, sealed]);
}

export function Setup({ s, dispatch, onBack, onVoice, practice }: SetupProps) {
  useKeys(dispatch, onBack, s.sealed);
  const step = rehearsalStep(s);
  const turn = currentTurn(s);
  const t = s.twin;
  const name = piecesAt(t, "who").find((p) => p.id === "p_name")?.label ?? t?.name ?? "Your twin";
  const other = (t?.rehearsal?.with ?? practice?.where.replace(/^.*'Practice: (.*)'$/, "$1") ?? "the other side").replace(
    /\s*\(practice\)$/,
    "",
  );
  const where = practice?.where ?? `Notion practice page: 'Practice: ${other}'`;
  const playedBy = practice?.playedBy ?? `Athena plays ${other}`;
  const live = liveWords(t);
  const trip = !!s.rehearsal && !s.sealed;
  const ink = (id: string) => dispatch({ type: "ink", pieces: [id] });
  return (
    <>
      {trip ? (
        <div className="work" data-mode="trip">
          <TripPage s={s} step={step} turns={turnsOf(s.rehearsal!, t)} where={where} onInk={ink} />
          <PracticePage
            s={s}
            step={step}
            turns={turnsOf(s.rehearsal!, t)}
            current={turn}
            name={name}
            signsAs={signsAs(t)}
            other={other}
            playedBy={playedBy}
            goal={s.rehearsal!.goal}
            choreName={(id) => t?.chores.find((c) => c.id === id)?.name ?? id}
            dispatch={dispatch}
          />
        </div>
      ) : (
        <div className="work" data-mode={s.sealed ? "sealed" : "doc"}>
          <TwinDocument s={s} lit={litPlace(s)} onInk={ink} onVoice={onVoice} issued={live.issued} soundsLike={soundsLikeOf(t)} />
          <Slip s={s} dispatch={dispatch} where={where} playedBy={playedBy} goliveLine={live.line} stays={live.stays} onBack={onBack} />
        </div>
      )}
      <AthenaPanel
        s={s}
        step={step}
        turn={turn}
        other={other}
        goliveLine={live.line}
        readyFrom={!!t?.ready}
        dispatch={dispatch}
        onBack={onBack}
      />
    </>
  );
}
