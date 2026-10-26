import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { applyTheme } from "../theme";
import { Preview } from "./Preview";
import "./preview.css";

// Opens at /preview.html with no daemon: this is where the theme is judged.
applyTheme();
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Preview />
  </StrictMode>,
);
