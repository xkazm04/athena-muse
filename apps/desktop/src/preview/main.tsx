import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { applyTheme } from "../theme";
import { Preview } from "./Preview";
import { SpreadHarness } from "./SpreadHarness";
import "../main/main.css";
import "./preview.css";

// Opens at /preview.html with no daemon: this is where the theme is judged. `?spread=open` or
// `?spread=folded` draws the book alone, at the window's full size, and `?spread=shell` inside the main
// window's frame (ADR 0024).
const spread = new URLSearchParams(window.location.search).get("spread");
applyTheme();
if (spread === "folded") document.body.classList.add("her");
createRoot(document.getElementById("root")!).render(
  <StrictMode>{spread === "open" || spread === "folded" || spread === "shell" ? <SpreadHarness layout={spread} /> : <Preview />}</StrictMode>,
);
