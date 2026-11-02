// A Project's open draft, as a small badge wherever the Project is listed (onboarding-jobs): what her
// background job is doing, or that the draft waits on the person. A click opens the stage on it.
import type { DraftBadge as DraftBadgeWire, DraftStep } from "../../lib/contract";
import { useMain } from "../store";

export interface DraftBadgeLook {
  label: string;
  tone: "info" | "human" | "warning" | undefined;
  /** A job is running: the badge carries a live dot. */
  live: boolean;
}

const RUNNING: Partial<Record<DraftStep, string>> = {
  author: "Writing",
  preview: "Preparing cards",
  rehearse: "Testing",
};

/** The badge's words and tone. The summary carries only the job's state, so a running job is named by the step. */
export function draftBadgeLook(d: DraftBadgeWire): DraftBadgeLook {
  switch (d.job) {
    case "running":
      return { label: RUNNING[d.step] ?? "Working", tone: "info", live: true };
    case "done":
      return { label: "Ready to check", tone: "human", live: false };
    case "failed":
    case "stopped":
      return { label: "Needs you", tone: "warning", live: false };
    default:
      return { label: "Draft", tone: undefined, live: false };
  }
}

/** The badge; renders nothing for a Project with no open draft. */
export function DraftBadge({ draft }: { draft: DraftBadgeWire | undefined }) {
  const navigate = useMain((s) => s.navigate);
  if (!draft) return null;
  const look = draftBadgeLook(draft);
  return (
    <button
      type="button"
      className="badge m-draft-badge"
      data-tone={look.tone}
      data-live={look.live ? "true" : undefined}
      aria-label={`${look.label}: open the draft`}
      title="Open the draft"
      onClick={(e) => {
        e.stopPropagation();
        navigate({ view: "stage", id: draft.id });
      }}
    >
      {look.live && <i className="m-draft-badge__dot" aria-hidden="true" />}
      {look.label}
    </button>
  );
}
