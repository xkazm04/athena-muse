import { useEffect, useId, useRef, useState } from "react";
import { CORE, type SpaceSummary } from "../lib/contract";
import "./ui.css";

export interface ProjectPillProps {
  spaces: SpaceSummary[];
  activeId: string;
  /** Called with a space id, or CORE for "Back to core". The window decides when it applies. */
  onSelect: (spaceId: string) => void;
  /** A switch asked for while a turn runs: shown as "switches after this reply". */
  pendingId?: string;
  compact?: boolean;
}

export const hueColor = (hue: number): string => `hsl(${hue} 80% 62%)`;

/** Where Athena works: a project, or core. Click opens the switch menu. */
export function ProjectPill({ spaces, activeId, onSelect, pendingId, compact = false }: ProjectPillProps) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const root = useRef<HTMLDivElement>(null);
  const active = spaces.find((s) => s.id === activeId);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const pick = (id: string) => {
    setOpen(false);
    if (id !== activeId) onSelect(id);
  };
  const pending = pendingId !== undefined && pendingId !== activeId;

  return (
    <div className={`pill${compact ? " pill--compact" : ""}`} ref={root}>
      <button
        type="button"
        className="pill-button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((v) => !v)}
        title={active ? `Athena is working in ${active.name}` : "Athena is working in core"}
      >
        <i className="pill-dot" style={{ background: active ? hueColor(active.hue) : "var(--accent)" }} aria-hidden />
        <span className="pill-name">{active ? active.name : "Core"}</span>
        {pending && <span className="pill-pending">switches after this reply</span>}
      </button>
      {open && (
        <ul className="pill-menu plane" role="menu" id={menuId}>
          {spaces.map((s) => (
            <li key={s.id} role="none">
              <button type="button" role="menuitemradio" aria-checked={s.id === activeId} onClick={() => pick(s.id)}>
                <i className="pill-dot" style={{ background: hueColor(s.hue) }} aria-hidden />
                {s.name}
              </button>
            </li>
          ))}
          {spaces.length === 0 && <li className="pill-empty">No projects yet</li>}
          <li role="none" className="pill-sep">
            <button type="button" role="menuitemradio" aria-checked={activeId === CORE} onClick={() => pick(CORE)}>
              <i className="pill-dot" style={{ background: "var(--accent)" }} aria-hidden />
              Back to core
            </button>
          </li>
        </ul>
      )}
    </div>
  );
}
