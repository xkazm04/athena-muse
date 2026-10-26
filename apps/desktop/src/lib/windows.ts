// Window helpers for the Tauri shell. Outside Tauri (a plain browser tab, the preview page, tests)
// every one of them quietly does nothing, so a page never needs to ask where it is running.

export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

/** Show or hide her window (same as Ctrl+Shift+Space). */
export async function toggleAthena(): Promise<void> {
  if (!isTauri()) return;
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("toggle_athena");
}

/** Put the window this code runs in away. Her window is hidden, never destroyed. */
export async function hideThisWindow(): Promise<void> {
  if (!isTauri()) return;
  const { getCurrentWindow } = await import("@tauri-apps/api/window");
  await getCurrentWindow().hide();
}

/** Begin dragging the window; call from a pointerdown on the drag handle (her window has no frame). */
export async function startDrag(): Promise<void> {
  if (!isTauri()) return;
  const { getCurrentWindow } = await import("@tauri-apps/api/window");
  await getCurrentWindow().startDragging();
}

/** Open a web page in the person's browser. Outside Tauri, a new tab. */
export async function openExternal(url: string): Promise<void> {
  if (!isTauri()) {
    window.open(url, "_blank", "noopener");
    return;
  }
  const { openUrl } = await import("@tauri-apps/plugin-opener");
  await openUrl(url);
}
