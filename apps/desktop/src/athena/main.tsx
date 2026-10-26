import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { applyTheme } from "../theme";
import { App } from "./App";

// Her window entry (athena.html sets `her` on body, which keeps the window transparent).
applyTheme();
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
