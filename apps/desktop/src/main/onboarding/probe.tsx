// Checking the Muse key: save (when a new key is given), then ask Muse to answer once. Shared by the
// first run and the Athena view so both say the same thing in the same states.

import { useCallback, useState } from "react";
import * as api from "../../lib/api";
import type { Probe } from "../../lib/contract";
import type { SealState } from "../../theme";
import { reasonOf, useMain } from "../store";

export type ProbePhase = "idle" | "checking" | "ok" | "invalid" | "network" | "failed";

export interface ProbeState {
  phase: ProbePhase;
  probe?: Probe;
  /** the reason in Meta's or the daemon's words, when the check failed */
  reason?: string;
}

/** The daemon words its probe failures in plain text; these two get their own remedy. */
export function classify(p: Probe): ProbePhase {
  if (p.ok) return "ok";
  const error = (p.error ?? "").toLowerCase();
  if (error.includes("refused")) return "invalid";
  if (error.includes("reach")) return "network";
  return "failed";
}

export function useProbe() {
  const setEngine = useMain((s) => s.setEngine);
  const [state, setState] = useState<ProbeState>({ phase: "idle" });

  /** With `key`, saves it first. The key stays saved even when the probe fails. */
  const check = useCallback(
    async (key?: string) => {
      setState({ phase: "checking" });
      try {
        if (key !== undefined) setEngine(await api.saveKey(key));
        const probe = await api.probe();
        const phase = classify(probe);
        setState(phase === "ok" ? { phase, probe } : { phase, probe, reason: probe.error });
      } catch (e) {
        setState({ phase: "failed", reason: reasonOf(e, "Could not check the key") });
      }
    },
    [setEngine],
  );

  const removeKey = useCallback(async () => {
    try {
      setEngine(await api.deleteKey());
      setState({ phase: "idle" });
    } catch (e) {
      setState({ phase: "failed", reason: reasonOf(e, "Could not remove the key") });
    }
  }, [setEngine]);

  const reset = useCallback(() => setState({ phase: "idle" }), []);

  return { state, check, removeKey, reset };
}

export function sealFor(phase: ProbePhase): SealState {
  if (phase === "checking") return "working";
  if (phase === "ok") return "signed";
  return "rest";
}

/** "0.8 s" from milliseconds. */
export function seconds(ms: number): string {
  return `${(ms / 1000).toFixed(1)} s`;
}

/** The probe's state in words. Renders nothing while idle. */
export function ProbeLine({ state }: { state: ProbeState }) {
  const { phase, probe, reason } = state;
  if (phase === "idle") return null;
  if (phase === "checking") {
    return (
      <p className="m-probe" role="status">
        <span className="badge" data-tone="info">
          checking
        </span>{" "}
        Asking Muse to answer...
      </p>
    );
  }
  if (phase === "ok") {
    return (
      <p className="m-probe" role="status">
        <span className="badge" data-tone="success">
          connected
        </span>{" "}
        Muse answered in {seconds(probe?.latency_ms ?? 0)}
        {probe?.model && <span className="m-probe__model"> · {probe.model}</span>}
      </p>
    );
  }
  const head =
    phase === "invalid"
      ? "Meta refused the key."
      : phase === "network"
        ? "Could not reach Meta."
        : (reason ?? "The check did not finish.");
  const remedy =
    phase === "invalid"
      ? "Check that you copied the whole key, or create a new one on Meta's developer page."
      : phase === "network"
        ? "Check your internet connection and try again."
        : "Try again in a moment.";
  return (
    <div className="m-probe m-probe--bad" role="alert">
      <span className="badge" data-tone="error">
        {phase === "invalid" ? "key refused" : phase === "network" ? "no answer" : "problem"}
      </span>
      <p className="m-probe__head">{head}</p>
      <p className="m-probe__remedy">{remedy}</p>
    </div>
  );
}
