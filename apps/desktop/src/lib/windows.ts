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

/** The event that carries the surface's ask to her window (ADR 0016). */
export const ASK_EVENT = "athena://ask";

/**
 * Hand words to her window, the way "Talk to Athena" opens it: her window is shown and focused, and
 * she takes the words as the person's next turn. Outside Tauri there is no window to hand them to,
 * and the answer is `false`.
 */
export async function handToAthena(text: string): Promise<boolean> {
  if (!isTauri()) return false;
  const { Window } = await import("@tauri-apps/api/window");
  const { emitTo } = await import("@tauri-apps/api/event");
  const her = await Window.getByLabel("athena");
  if (her) {
    await her.show();
    await her.setFocus();
  }
  await emitTo("athena", ASK_EVENT, { text });
  return true;
}

/** Her window's side: called with the words the surface handed over. Resolves to the unlisten. */
export async function onHanded(fn: (text: string) => void): Promise<() => void> {
  if (!isTauri()) return () => undefined;
  const { getCurrentWindow } = await import("@tauri-apps/api/window");
  return getCurrentWindow().listen<{ text: string }>(ASK_EVENT, (e) => fn(e.payload.text));
}
