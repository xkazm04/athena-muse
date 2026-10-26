import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { applyTheme } from "../theme";
import { App } from "./App";
import "./main.css";

applyTheme();
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
