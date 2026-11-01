// The Devices level of Settings (portable ADR 0140, ADR 0017 here).
//
// Every device is a full Athena; this is where one meets the others. Two layers on one stage:
//
// 1. The constellation: this computer at the centre, the paired devices on an orbit around it with
//    their presence, the requests waiting here as pulsing nodes, and two '+' nodes. A node opens its
//    details in a drawer under the stage.
// 2. The pairing wizard: it grows out of the '+' node that was pressed, the constellation dims
//    behind it, and Back or Escape folds it back into that node.
//
// `DevicesLevel` is a pure function of the model (the store's mirror of `GET /devices` plus `now`)
// and of three facts of presentation kept here: which node is open, which wizard is open, and which
// pairing windows this person already answered (a spent window is replaced, not shown again).
// Nothing here decides a grant: the approve card's rules are the store's. `DevicesPanel` wires the
// store to it and follows the bus while it is on screen.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DeviceKind } from "../../../lib/fleet";
import { Constellation, ADD_SPOT, DevicesList, Drawer, percentOf } from "./Constellation";
import type { Answered, DevicesModel } from "./parts";
import { startDevices, useDevices } from "./store";
import { SetupSection } from "./SetupSection";
import { Wizard, isLive, type PcBranch } from "./Wizard";
import "./devices.css";

export { ARM_MS } from "./store";

/** What a test or a preview opens the level on; a person always starts on the bare constellation. */
export interface DevicesOpening {
  selected?: string;
  wizard?: DeviceKind;
  branch?: PcBranch;
}

export function DevicesLevel({ model, opening = {} }: { model: DevicesModel; opening?: DevicesOpening }) {
  const { state } = model;
  if (!state.loaded && state.problem) {
    return (
      <div className="plane m-problem" role="alert">
        <p>
          <strong>Athena could not read this computer&apos;s devices.</strong> {state.problem}
        </p>
        <button type="button" className="btn" onClick={() => void model.actions.load()}>
          Read again
        </button>
      </div>
    );
  }
  if (state.view === null) {
    return (
      <p className="m-muted" role="status">
        Reading the devices...
      </p>
    );
  }
  return <Devices model={model} opening={opening} />;
}

function Devices({ model, opening }: { model: DevicesModel; opening: DevicesOpening }) {
  const { state } = model;
  const [selected, setSelected] = useState<string | null>(opening.selected ?? null);
  const [wizard, setWizard] = useState<DeviceKind | null>(opening.wizard ?? null);
  const [spent, setSpent] = useState<readonly string[]>([]);
  const adds = useRef<Record<DeviceKind, HTMLButtonElement | null>>({ phone: null, pc: null });
  const refocus = useRef<DeviceKind | null>(null);

  // The fold finished and the sky is live again: the focus goes back to the node it grew from.
  useEffect(() => {
    if (wizard !== null || refocus.current === null) return;
    adds.current[refocus.current]?.focus();
    refocus.current = null;
  }, [wizard]);

  const addRef = useCallback(
    (kind: DeviceKind) => (el: HTMLButtonElement | null) => {
      adds.current[kind] = el;
    },
    [],
  );

  const open = (kind: DeviceKind) => {
    setSelected(null);
    // A phone's window is opened on the press: the person came to scan. A computer's waits for the
    // choice of which side shows the code.
    if (kind === "phone" && !(isLive(state.opened.phone, Date.now(), spent) && state.opened.phone?.url)) {
      void model.actions.openPairing("phone");
    }
    setWizard(kind);
  };

  const closed = useCallback(() => {
    refocus.current = wizard;
    setWizard(null);
  }, [wizard]);

  const answered = useCallback(
    (a: Answered) => setSpent((s) => (s.includes(a.pairingId) ? s : [...s, a.pairingId])),
    [],
  );

  return (
    <>
      {state.problem ? (
        <div className="plane m-problem" role="alert">
          <p>
            <strong>What is drawn below may be out of date.</strong> {state.problem}
          </p>
          <button type="button" className="btn" onClick={() => void model.actions.load()}>
            Read again
          </button>
        </div>
      ) : null}
      <section className="m-devices" aria-label="Devices">
        <div className="m-devices__stage">
          <Constellation
            model={model}
            selected={selected}
            onSelect={setSelected}
            onAdd={open}
            dim={wizard !== null}
            addRef={addRef}
          />
          {wizard ? (
            <Wizard
              model={model}
              kind={wizard}
              origin={percentOf(ADD_SPOT[wizard])}
              spent={spent}
              onAnswered={answered}
              onClosed={closed}
              initialBranch={opening.branch ?? null}
            />
          ) : null}
        </div>
        <DevicesList model={model} />
        {selected !== null && wizard === null ? (
          <Drawer model={model} selected={selected} onClose={() => setSelected(null)} onAnswered={answered} />
        ) : null}
        <SetupSection />
      </section>
    </>
  );
}

/** The level wired to the store: it reads now, follows `/devices/events` while it is shown, and lets go. */
export function DevicesPanel() {
  const state = useDevices();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => startDevices(), []);

  // The cards' arm delay and the presence captions read `now`; a slow beat keeps them honest.
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const model = useMemo<DevicesModel>(
    () => ({
      state,
      now,
      actions: {
        load: state.load,
        rename: state.rename,
        setBeacon: state.setBeacon,
        openPairing: state.openPairing,
        join: state.join,
        toggleGrant: state.toggleGrant,
        answer: state.answer,
        revoke: state.revoke,
        send: state.send,
      },
    }),
    [state, now],
  );
  return <DevicesLevel model={model} />;
}
