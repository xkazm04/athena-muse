// Athena's bottom panel on the setup page, composed from the stage's parts: her one line, the one
// question with the section it lands in, three suggestions (keys 1-3), your own words, "Ink all her
// pencil", what she still needs and, once the twin is ready, "That's enough, rehearse it". During the
// rehearsal it asks about the draft in front of you, and the exit becomes "Go live".

import type { MissionTurn } from "../../lib/contract";
import { Seal } from "../../theme";
import { useClock } from "../stage/hooks";
import { Composer, EnoughButton, ReplyNotice, StillNeeds, Suggestions } from "../stage/parts";
import { STAGE_WORDS, type StageWords } from "../stage/words";
import { NEED_PHRASE, TWIN_RUBRIC } from "./format";
import { Icon, Meter } from "./marks";
import { SLOW_MS } from "../stage/select";
import { pencilOf, type RehearsalStep } from "./select";
import type { SetupState, TwinsAction } from "./types";
import { PLACE_LABEL, REHEARSAL_ASK, SECTION, TWINS_WORDS as w, type RehearsalAsk } from "./words";

export interface AthenaPanelProps {
  s: SetupState;
  step: RehearsalStep;
  turn?: MissionTurn;
  /** Who the practice page's other side is. */
  other: string;
  goliveLine: string;
  /** The first reply after which the rehearsal may start. */
  readyFrom: boolean;
  dispatch: (a: TwinsAction) => void;
  onBack: () => void;
}

/**
 * The stage's parts take StageWords, whose strings are typed as the chore's own literals (`as const`).
 * The twin's panel says its own words through the same parts; this is the one place they are swapped
 * in (reported: StageWords could widen its strings, and the cast would go).
 */
function stageWords(own: Partial<Record<keyof StageWords, string>>): StageWords {
  return { ...STAGE_WORDS, ...own } as unknown as StageWords;
}

/** What the panel asks now: her line, the question, its suggestions, and where it is about. */
function asked(p: AthenaPanelProps): (RehearsalAsk & { about: "place" | "practice" | "issued" }) | null {
  const { s, step, turn } = p;
  if (s.sealed) return { ...REHEARSAL_ASK.golive(p.goliveLine), about: "issued" };
  if (s.rehearsal) {
    const r = s.rehearsal;
    const ask = (() => {
      switch (step) {
        case "waits":
          return REHEARSAL_ASK.waits(turn?.confidence ?? 0, turn?.risks?.length ?? 0);
        case "held":
          return REHEARSAL_ASK.held(turn?.confidence ?? 0, turn?.bar, turn?.risks ?? []);
        case "editing":
          return REHEARSAL_ASK.editing();
        case "edited":
          return REHEARSAL_ASK.edited(turn?.learned ?? "it learns from what you changed");
        case "sent":
          return REHEARSAL_ASK.sent(turn?.confidence ?? 0, turn?.bar);
        case "resolved":
          return r.outcome?.filed
            ? REHEARSAL_ASK.resolved(r.outcome.filed.where)
            : REHEARSAL_ASK.resolvedNote(s.twin?.rehearsal?.note ?? "It got what the goal asked for.");
        case "handed":
          return REHEARSAL_ASK.handed(s.twin?.rehearsal?.note ?? "It stopped and handed the conversation back to you.");
        default:
          return REHEARSAL_ASK.running(p.other);
      }
    })();
    return { ...ask, about: "practice" };
  }
  if (!s.twin || !s.twin.pieces.length) {
    const [a, b, c] = w.describeSuggestions;
    return { line: w.describeLine, ask: w.describeAsk, suggestions: [a, b, c], about: "place" };
  }
  if (!s.ask) return null;
  const [a = "", b = "", c = ""] = s.ask.suggestions;
  return { line: s.line, ask: s.ask.text, suggestions: [a, b, c], about: "place" };
}

/** Her line; while she answers, what you said and how long it has taken; a failure with a retry. */
function Line({ s, line, onRetry }: { s: SetupState; line: string; onRetry: () => void }) {
  const replying = s.phase === "sending" || s.phase === "thinking";
  const secs = useClock(s.startedAt, replying);
  const quiet = useClock(s.heardAt, replying);
  if (!replying && s.phase !== "failed") {
    return (
      <div className="ath__line">
        <Seal state="rest" size={30} label="Athena" />
        <p aria-live="polite">{line}</p>
      </div>
    );
  }
  const phase = s.phase === "failed" ? "failed" : quiet * 1000 >= SLOW_MS ? "slow" : "thinking";
  const words = stageWords({
    thinking: `Thinking ${secs} s`,
    slow: `Still thinking: ${secs} s. Slower than usual; nothing is lost.`,
    failed: w.failed,
    retry: w.retry,
    sayDifferently: w.sayDifferently,
  });
  return (
    <div className="ath__line" data-state={phase}>
      <Seal state={phase === "failed" ? "rest" : "working"} size={30} label="Athena" />
      <div className="ath__say">
        {phase !== "failed" && s.youSaid && <span className="you">You: {s.youSaid}</span>}
        <ReplyNotice phase={phase} problem={s.problem} onRetry={onRetry} words={words} />
      </div>
    </div>
  );
}

export function AthenaPanel(props: AthenaPanelProps) {
  const { s, step, dispatch, onBack } = props;
  const a = asked(props);
  const working = !!s.work;
  const pencil = pencilOf(s.twin).length;
  const twin = s.twin;
  const pick = (i: number) => (s.sealed && i === 0 ? onBack() : dispatch({ type: "pick", index: i }));
  const about =
    a?.about === "issued" ? (
      <span className="about">
        <Icon name="check" />
        Issued
      </span>
    ) : a?.about === "practice" ? (
      <span className="about">
        <Icon name="notion" />
        Practice page
      </span>
    ) : (
      <span className="about" data-place={s.ask?.place ?? "who"}>
        <Icon name="arrow" />
        {SECTION[s.ask?.place ?? "who"]}
      </span>
    );
  const words = stageWords({ ownWords: w.ownWords, send: w.send });

  let side;
  if (s.sealed) {
    side = (
      <div className="ath__side">
        <button type="button" className="btn btn-primary" data-role="exit" data-ready="true" onClick={onBack}>
          {w.backToTwins}
          <Icon name="arrow" />
        </button>
        <p className="sp-still">{w.issuedNothingMore}</p>
      </div>
    );
  } else if (s.rehearsal) {
    const can = step === "resolved" || step === "handed";
    side = (
      <div className="ath__side">
        <button type="button" className="btn btn-primary" data-role="exit" disabled={!can || working} onClick={() => dispatch({ type: "golive" })}>
          {w.goLive}
          <Icon name="arrow" />
        </button>
        <p className="sp-still">{can ? w.goLiveNow : s.rehearsal.outcome ? w.goLiveMarks : w.goLiveWhen}</p>
      </div>
    );
  } else if (twin && twin.pieces.length) {
    const needs = <StillNeeds coverage={twin.coverage} rubric={TWIN_RUBRIC} words={{ stillNeeds: w.stillNeeds, ready: w.allFilled, needPhrase: NEED_PHRASE }} />;
    const inkAll = pencil > 0 && (
      <button type="button" className="btn ath__inkall" disabled={working} onClick={() => dispatch({ type: "ink_all" })}>
        <Icon name="nib" />
        {w.inkAll(pencil)}
      </button>
    );
    side =
      twin.ready && props.readyFrom ? (
        <div className="ath__side">
          <EnoughButton
            coverage={twin.coverage}
            rubric={TWIN_RUBRIC}
            agreed={twin.ready}
            disabled={working}
            onEnough={() => dispatch({ type: "enough" })}
            words={{ enough: w.enough, leftOpen: w.leftOpen, slot: PLACE_LABEL }}
          />
          {inkAll}
        </div>
      ) : (
        <div className="ath__side ath__side--needs">
          <span className="ath__ready">
            <Meter value={twin.readiness} />
            {w.filled(twin.readiness)}
          </span>
          {needs}
          {inkAll}
        </div>
      );
  } else {
    side = (
      <div className="ath__side ath__side--needs">
        <span className="ath__ready">
          <Meter value={0} />
          {w.filled(0)}
        </span>
        <p className="sp-still">She fills in its document while you talk.</p>
      </div>
    );
  }

  return (
    <section className="athena" aria-label="Athena" data-role="note">
      <div className="ath__main">
        <Line s={s} line={a?.line ?? s.line} onRetry={() => dispatch({ type: "retry" })} />
        {a && (
          <div className="ath__ask" data-role="question">
            {about}
            <h2 data-role="ask-text">{a.ask}</h2>
          </div>
        )}
        {a && (
          <div className="ath__answers">
            <Suggestions suggestions={a.suggestions.filter(Boolean)} onPick={(choice) => pick(a.suggestions.indexOf(choice))} disabled={working} words={words} />
            <Composer
              key={a.ask}
              onSay={(text) => dispatch(s.twin?.pieces.length ? { type: "say", text } : { type: "describe", need: text })}
              disabled={working}
              words={words}
              label={w.ownWords}
            />
          </div>
        )}
        {s.note && <p className="ath__note">{s.note}</p>}
      </div>
      {side}
    </section>
  );
}
