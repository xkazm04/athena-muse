// One system notification when a draft's background job ends while the person is away from the app
// (onboarding-jobs). While the window has focus nothing is shown: the Project's badge and the stage say
// it. Permission is asked once, lazily, at the first ending job, never at start. Outside Tauri (a plain
// browser tab, the preview page, tests) it does nothing.

import type { AppEvent, DraftJob } from "./contract";
import { isTauri } from "./windows";

export const NOTIFY_TITLE = "Athena";

/** The toast's words for a job that ended; `null` while it still runs. */
export function jobEndLine(job: DraftJob): string | null {
  if (job.state === "running") return null;
  if (job.state === "failed" || job.state === "stopped") {
    const reason = job.reason?.trim();
    return reason ? `She stopped: ${reason}` : "She stopped.";
  }
  switch (job.kind) {
    case "write":
      return "Your chore is written - come back to check it.";
    case "preview":
      return "Her cards are ready to mark.";
    case "rehearse":
      return "The test run is done.";
  }
}

type Permission = "unasked" | "granted" | "denied";
let permission: Permission = "unasked";
let asking: Promise<boolean> | null = null;

/** For tests: forget the answer, as a fresh app start would. */
export function resetNotifyForTests(): void {
  permission = "unasked";
  asking = null;
}

const focused = () => typeof document !== "undefined" && document.hasFocus();

async function allowed(): Promise<boolean> {
  if (permission !== "unasked") return permission === "granted";
  asking ??= (async () => {
    try {
      const { isPermissionGranted, requestPermission } = await import("@tauri-apps/plugin-notification");
      const granted = (await isPermissionGranted()) || (await requestPermission()) === "granted";
      permission = granted ? "granted" : "denied";
    } catch {
      permission = "denied";
    }
    return permission === "granted";
  })();
  return asking;
}

/** Called for every app event in the main window; shows a toast only for a `draft_job` that ended unseen. */
export async function notifyDraftJob(e: AppEvent): Promise<void> {
  if (e.type !== "draft_job" || !e.job) return;
  const body = jobEndLine(e.job);
  if (!body || !isTauri() || focused()) return;
  if (!(await allowed())) return;
  try {
    const { sendNotification } = await import("@tauri-apps/plugin-notification");
    sendNotification({ title: NOTIFY_TITLE, body });
  } catch {
    // A notification that cannot be shown is not worth a word: the badge still says it.
  }
}
