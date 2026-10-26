// Loop Tide: what the windows import. `applyTheme()` is called once by each entry.
import "./tokens.css";
import "./base.css";
import "./coat.css";
import "./seal.css";

export { Backdrop, type BackdropProps } from "./Backdrop";
export { Seal, SETTLE_MS, type SealProps, type SealState } from "./Seal";
export { SPEED_REST, SPEED_WORKING } from "./current";

export type ThemeChoice = "dark" | "light" | "auto";

/** Pin the theme (`dark` / `light`) or let the system decide (`auto`, the default). */
export function applyTheme(choice: ThemeChoice = "auto"): void {
  const root = document.documentElement;
  if (choice === "auto") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", choice);
}
