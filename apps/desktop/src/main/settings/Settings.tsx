// Settings (ADR 0012), ported from portable's setup module: an overview that reads, and a level per
// item where the writes are (portable ADR 0029, in this window's hash-route idiom). The daemon holds
// every row; this page holds only what is about this visit: which writes were refused, beside the
// control that made them, and the accounts it read.

import { useCallback, useEffect, useMemo, useState } from "react";
import * as api from "../../lib/api";
import type { Connection, EngineId, Look, SettingsView } from "../../lib/contract";
import { MOTION_CHOICES, THEME_CHOICES, TYPE_SCALES, applyLook } from "../../ui/look";
import { Connection as MuseKey } from "../athena/AthenaView";
import { reasonOf, useMain } from "../store";
import {
  ENGINE_HINT,
  ENGINE_LABEL,
  ITEMS,
  ITEM_NAME,
  MOTION_HINT,
  STANDING_TONE,
  THEME_HINT,
  TYPE_SCALE_HINT,
  accountLabel,
  accountsFact,
  dataFact,
  engineBlocked,
  engineFact,
  isItem,
  lookFact,
  type Fact,
  type Item,
} from "./model";
import "./settings.css";

/** The writes made here whose refusal is shown where the choice was made. */
type Write = "engine" | keyof Look;
type Refusals = Partial<Record<Write, string>>;

interface Accounts {
  list: Connection[] | null;
  problem: string;
}

export function SettingsView({ item }: { item: string | null }) {
  const view = useMain((s) => s.settings);
  const problem = useMain((s) => s.settingsProblem);
  const loadSettings = useMain((s) => s.loadSettings);
  const [accounts, setAccounts] = useState<Accounts>({ list: null, problem: "" });

  useEffect(() => {
    void loadSettings();
    let live = true;
    void (async () => {
      try {
        const list = await api.connections();
        if (live) setAccounts({ list: Array.isArray(list) ? list : [], problem: "" });
      } catch (e) {
        if (live) setAccounts({ list: null, problem: reasonOf(e, "the daemon did not answer") });
      }
    })();
    return () => {
      live = false;
    };
  }, [loadSettings]);

  const facts = useMemo<Record<Item, Fact>>(
    () => ({
      engine: engineFact(view),
      look: lookFact(view?.look ?? null),
      accounts: accountsFact(accounts.list, accounts.problem),
      data: dataFact(view),
    }),
    [view, accounts],
  );

  return (
    <div className="m-settings">
      {problem && (
        <div className="plane m-problem" role="alert">
          <p>
            <strong>Settings could not be read.</strong> {problem}
          </p>
          <button type="button" className="btn" onClick={() => void loadSettings()}>
            Read again
          </button>
        </div>
      )}
      {item === null ? (
        <Overview facts={facts} />
      ) : isItem(item) ? (
        <Level item={item} fact={facts[item]} view={view} accounts={accounts} />
      ) : (
        <Missing name={item} />
      )}
    </div>
  );
}

function Badge({ fact }: { fact: Fact }) {
  if (!fact.word) return null;
  const tone = fact.standing ? STANDING_TONE[fact.standing] : undefined;
  return (
    <span className="badge" data-tone={tone}>
      {fact.word}
    </span>
  );
}

function Overview({ facts }: { facts: Record<Item, Fact> }) {
  const setWelcome = useMain((s) => s.setWelcome);
  return (
    <>
      <header className="m-settings__head">
        <h1 className="m-title">Settings</h1>
        <p className="m-lead">The engine she thinks with, how she looks, and where it all lives.</p>
      </header>
      <ul className="m-settings__tiles" aria-label="Settings">
        {ITEMS.map((item) => (
          <li key={item}>
            <a className="m-settings__tile" href={`#settings/${item}`}>
              <span className="m-settings__name">{ITEM_NAME[item]}</span>
              <Badge fact={facts[item]} />
              <span className="m-settings__line">{facts[item].line}</span>
            </a>
          </li>
        ))}
      </ul>
      <section className="plane m-section" aria-labelledby="st-welcome">
        <h2 id="st-welcome" className="m-h2">
          The welcome
        </h2>
        <p className="m-muted">Read the first run again. Nothing already set is changed.</p>
        <div className="m-row">
          <button type="button" className="btn btn-quiet" onClick={() => setWelcome(true)}>
            Show the welcome again
          </button>
        </div>
      </section>
    </>
  );
}

/** The page's writes: refusals kept beside their controls, and the stored rows read again after one. */
function useWrites(view: SettingsView | null) {
  const putSettings = useMain((s) => s.putSettings);
  const loadSettings = useMain((s) => s.loadSettings);
  const [refusals, setRefusals] = useState<Refusals>({});
  const [pending, setPending] = useState<Write | null>(null);

  const attempt = useCallback(
    async (what: Write, write: () => Promise<SettingsView>) => {
      setRefusals((now) => ({ ...now, [what]: undefined }));
      setPending(what);
      try {
        putSettings(await write());
      } catch (e) {
        setRefusals((now) => ({ ...now, [what]: reasonOf(e, "The daemon did not answer") }));
        // A look painted before its write settles back to the stored one.
        await loadSettings();
      } finally {
        setPending(null);
      }
    },
    [putSettings, loadSettings],
  );

  const chooseEngine = (id: EngineId) => void attempt("engine", () => api.chooseEngine(id));

  // The look is painted before it is written: the person is looking at the result.
  const setLook = <K extends keyof Look>(key: K, value: Look[K]) => {
    if (view) applyLook({ ...view.look, [key]: value });
    void attempt(key, () => api.setLook({ [key]: value }));
  };

  return { refusals, pending, chooseEngine, setLook };
}

function Level({
  item,
  fact,
  view,
  accounts,
}: {
  item: Item;
  fact: Fact;
  view: SettingsView | null;
  accounts: Accounts;
}) {
  const navigate = useMain((s) => s.navigate);
  const writes = useWrites(view);
  return (
    <>
      <button type="button" className="btn btn-quiet m-back" onClick={() => navigate({ view: "settings", item: null })}>
        Back to all settings
      </button>
      <header className="m-settings__head">
        <p className="eyebrow">
          <Badge fact={fact} />
        </p>
        <h1 className="m-title">{ITEM_NAME[item]}</h1>
        <p className="m-lead">{fact.line}</p>
      </header>
      {item === "engine" && <EngineLevel view={view} writes={writes} />}
      {item === "look" && <LookLevel view={view} writes={writes} />}
      {item === "accounts" && <AccountsLevel accounts={accounts} />}
      {item === "data" && <DataLevel view={view} />}
    </>
  );
}

type Writes = ReturnType<typeof useWrites>;

/** A refused write, beside the control that made it: the daemon's words, and the stored row is back. */
function Refused({ what, reason }: { what: string; reason: string | undefined }) {
  if (!reason) return null;
  return (
    <div className="m-probe m-probe--bad" role="alert">
      <span className="badge" data-tone="error">
        not stored
      </span>
      <p className="m-probe__head">{what} was not stored. The stored choice is shown again.</p>
      <p className="m-probe__remedy">{reason}</p>
    </div>
  );
}

interface Choice<T extends string> {
  value: T;
  label: string;
  hint: string;
  /** Present when it cannot be chosen; shown on the control, never merely implied. */
  blocked?: string;
}

/** One choice of several, as radio buttons a keyboard can walk. */
function Choices<T extends string>({
  label,
  value,
  options,
  onChoose,
  busy,
}: {
  label: string;
  value: T | undefined;
  options: readonly Choice<T>[];
  onChoose: (value: T) => void;
  busy: boolean;
}) {
  return (
    <div className="m-settings__choices" role="radiogroup" aria-label={label} aria-busy={busy}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          className="m-settings__choice"
          disabled={o.blocked !== undefined}
          onClick={() => {
            if (o.value !== value) onChoose(o.value);
          }}
        >
          <span className="m-settings__choice-name">{o.label}</span>
          <span className="m-settings__choice-hint">{o.blocked ?? o.hint}</span>
        </button>
      ))}
    </div>
  );
}

function EngineLevel({ view, writes }: { view: SettingsView | null; writes: Writes }) {
  if (!view) return <p className="m-muted">Reading the engines...</p>;
  const options = view.engines.map((o) => ({
    value: o.id,
    label: ENGINE_LABEL[o.id],
    hint: ENGINE_HINT[o.id],
    blocked: engineBlocked(view, o.id),
  }));
  return (
    <>
      <section className="plane m-section" aria-labelledby="st-engine">
        <h2 id="st-engine" className="m-h2">
          Which engine runs her turns
        </h2>
        <Choices
          label="Engine"
          value={view.engine}
          options={options}
          onChoose={writes.chooseEngine}
          busy={writes.pending === "engine"}
        />
        <Refused what="The engine" reason={writes.refusals.engine} />
        <p className="m-muted">
          {view.source === "env"
            ? "ATHENA_ENGINE is set in this computer's environment, so it decides; unset it to choose here."
            : "A choice reaches her next turn; nothing restarts, and nothing she remembers is dropped."}
        </p>
      </section>
      <MuseKey />
    </>
  );
}

function LookLevel({ view, writes }: { view: SettingsView | null; writes: Writes }) {
  if (!view) return <p className="m-muted">Reading the look...</p>;
  const { look } = view;
  return (
    <>
      <section className="plane m-section" aria-labelledby="st-theme">
        <h2 id="st-theme" className="m-h2">
          Theme
        </h2>
        <Choices
          label="Theme"
          value={look.theme}
          options={THEME_CHOICES.map((v) => ({ value: v, label: v, hint: THEME_HINT[v] }))}
          onChoose={(v) => writes.setLook("theme", v)}
          busy={writes.pending === "theme"}
        />
        <Refused what="The theme" reason={writes.refusals.theme} />
      </section>
      <section className="plane m-section" aria-labelledby="st-text">
        <h2 id="st-text" className="m-h2">
          Text size
        </h2>
        <Choices
          label="Text size"
          value={look.type_scale}
          options={TYPE_SCALES.map((v) => ({ value: v, label: v, hint: TYPE_SCALE_HINT[v] }))}
          onChoose={(v) => writes.setLook("type_scale", v)}
          busy={writes.pending === "type_scale"}
        />
        <Refused what="The text size" reason={writes.refusals.type_scale} />
      </section>
      <section className="plane m-section" aria-labelledby="st-motion">
        <h2 id="st-motion" className="m-h2">
          Motion
        </h2>
        <Choices
          label="Motion"
          value={look.motion}
          options={MOTION_CHOICES.map((v) => ({ value: v, label: v, hint: MOTION_HINT[v] }))}
          onChoose={(v) => writes.setLook("motion", v)}
          busy={writes.pending === "motion"}
        />
        <Refused what="The motion setting" reason={writes.refusals.motion} />
      </section>
      <p className="m-muted">Both windows wear the look at once.</p>
    </>
  );
}

const ACCOUNT_STATUS: Record<Connection["status"], { word: string; tone?: string }> = {
  connected: { word: "connected", tone: "success" },
  needs_sign_in: { word: "needs sign-in", tone: "warning" },
  disconnected: { word: "not connected" },
};

function AccountsLevel({ accounts }: { accounts: Accounts }) {
  return (
    <section className="plane m-section" aria-labelledby="st-accounts">
      <h2 id="st-accounts" className="m-h2">
        Connected accounts
      </h2>
      {accounts.list === null ? (
        <p className="m-muted">{accounts.problem ? `Could not read them: ${accounts.problem}` : "Reading..."}</p>
      ) : (
        <ul className="m-settings__accounts">
          {accounts.list.map((c) => (
            <li key={c.kind}>
              <span className="m-settings__name">{accountLabel(c.kind)}</span>{" "}
              <span className="badge" data-tone={ACCOUNT_STATUS[c.status].tone}>
                {ACCOUNT_STATUS[c.status].word}
              </span>
              {c.account && <span className="m-mono"> {c.account}</span>}
              {c.problem && <p className="m-muted">{c.problem}</p>}
            </li>
          ))}
        </ul>
      )}
      <p className="m-muted">
        Accounts are connected, and given leave to write, while a twin is set up.{" "}
        <a className="m-link" href="#twins">
          Go to Twins
        </a>
      </p>
    </section>
  );
}

function DataLevel({ view }: { view: SettingsView | null }) {
  return (
    <section className="plane m-section" aria-labelledby="st-data">
      <h2 id="st-data" className="m-h2">
        Where it lives
      </h2>
      <p>
        One folder on this computer: <span className="m-mono">athena.db</span> holds the settings, projects, memory,
        cards and the ledger, and the Meta key and connected accounts are kept in their own files beside it. Copy the
        folder, with Athena closed, to move this computer&apos;s Athena.
      </p>
      {view?.data_dir ? (
        <code className="m-settings__path">{view.data_dir}</code>
      ) : (
        <p className="m-muted">{view ? "This daemon keeps nothing on disk." : "Not known yet."}</p>
      )}
    </section>
  );
}

function Missing({ name }: { name: string }) {
  const navigate = useMain((s) => s.navigate);
  return (
    <section className="plane m-section" aria-labelledby="st-missing">
      <h1 id="st-missing" className="m-title">
        No such setting
      </h1>
      <p>Athena has no setting called {name}.</p>
      <div className="m-row">
        <button type="button" className="btn" onClick={() => navigate({ view: "settings", item: null })}>
          Back to all settings
        </button>
      </div>
    </section>
  );
}
