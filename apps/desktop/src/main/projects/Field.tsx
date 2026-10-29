import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { NAME_MAX, SPACES_MAX, type SpaceSummary } from "../../lib/contract";
import { Seal } from "../../theme";
import { hueColor } from "../../ui";
import { reasonOf, useMain } from "../store";
import { DescribeDoor } from "../stage/door";
import { layoutOrbits } from "./orbits";

const FALLBACK = { width: 960, height: 520 };

/** The stage is laid out in real pixels (no viewBox scaling) so moon letters stay at true type size. */
function useStageSize() {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState(FALLBACK);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = (w: number, h: number) => {
      if (w > 0 && h > 0) setSize({ width: Math.round(w), height: Math.round(h) });
    };
    const box = el.getBoundingClientRect();
    measure(box.width, box.height);
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([entry]) => entry && measure(entry.contentRect.width, entry.contentRect.height));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return { ref, size };
}

export function useReducedMotion(): boolean {
  const query = "(prefers-reduced-motion: reduce)";
  const get = () => typeof window.matchMedia === "function" && window.matchMedia(query).matches;
  const [reduced, setReduced] = useState(get);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(query);
    const on = () => setReduced(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return reduced;
}

const firstLine = (text: string) => text.split(/\r?\n/).find((l) => l.trim())?.trim() ?? "";

export function Field() {
  const spaces = useMain((s) => s.spaces);
  const load = useMain((s) => s.spacesLoad);
  const problem = useMain((s) => s.spacesProblem);
  const active = useMain((s) => s.active);
  const loadSpaces = useMain((s) => s.loadSpaces);
  const navigate = useMain((s) => s.navigate);
  const setActive = useMain((s) => s.setActive);
  const reduced = useReducedMotion();
  const { ref, size } = useStageSize();
  const [focused, setFocused] = useState<string | null>(null);

  const shown = spaces.slice(0, SPACES_MAX);
  const orbits = layoutOrbits(shown, size.width, size.height);
  const marquee = shown.find((s) => s.id === focused) ?? shown.find((s) => s.id === active);

  const enter = (s: SpaceSummary) => {
    navigate({ view: "project", id: s.id });
    void setActive(s.id);
  };

  return (
    <div className="m-field">
      <div className="m-field__head">
        <h1 className="m-title">Projects</h1>
        {load === "reading" && (
          <span className="badge" data-tone="info">
            reading
          </span>
        )}
        <NewProject />
        <DescribeDoor />
      </div>
      {load === "problem" && (
        <div className="plane m-problem" role="alert">
          <p>{problem}</p>
          <button type="button" className="btn" onClick={() => void loadSpaces()}>
            Try again
          </button>
        </div>
      )}
      <div className="m-field__body">
        <div className="m-stage" ref={ref} data-reduced={reduced ? "true" : undefined}>
          <svg className="m-stage__svg" width={size.width} height={size.height} aria-hidden="true" focusable="false">
            {orbits.map((o) => {
              const s = shown.find((x) => x.id === o.id)!;
              const color = hueColor(s.hue);
              const lit = o.id === active || o.id === focused;
              return (
                <g key={o.id} className={`m-orbit${lit ? " m-orbit--lit" : ""}`} style={{ color }}>
                  <path className="m-orbit__halo" d={o.path} style={{ opacity: 0.06 + o.halo * 0.34 }} />
                  <path className="m-orbit__ring" d={o.path} />
                  {o.moons.map((m) => (
                    <g
                      key={m.origin}
                      className="m-moon"
                      transform={reduced ? `translate(${m.x} ${m.y})` : undefined}
                    >
                      {!reduced && (
                        <animateMotion
                          path={o.path}
                          dur={`${o.period}s`}
                          begin={`${-m.phase * o.period}s`}
                          repeatCount="indefinite"
                        />
                      )}
                      <circle r="11" />
                      <text textAnchor="middle" dominantBaseline="central">
                        {m.letter}
                      </text>
                    </g>
                  ))}
                </g>
              );
            })}
          </svg>
          <button
            type="button"
            className="m-sun"
            style={{ left: size.width / 2, top: size.height / 2 }}
            onClick={() => navigate({ view: "core" })}
            aria-label="Core: what Athena knows everywhere"
          >
            <Seal state="rest" size={84} label="" />
            <span className="m-sun__label">Core</span>
          </button>
          {orbits.map((o) => {
            const s = shown.find((x) => x.id === o.id)!;
            return (
              <button
                key={o.id}
                type="button"
                className={`m-planet${o.id === active ? " m-planet--active" : ""}`}
                style={{ left: o.label.x, top: o.label.y, ["--hue" as string]: hueColor(s.hue) }}
                onMouseEnter={() => setFocused(s.id)}
                onMouseLeave={() => setFocused((f) => (f === s.id ? null : f))}
                onFocus={() => setFocused(s.id)}
                onBlur={() => setFocused((f) => (f === s.id ? null : f))}
                onClick={() => enter(s)}
              >
                <i className="m-planet__dot" aria-hidden="true" />
                {s.name}
              </button>
            );
          })}
        </div>
        <aside className="plane m-marquee" aria-live="polite">
          {marquee ? (
            <>
              <p className="m-eyebrow">{marquee.id === active ? "Athena is working here" : "Project"}</p>
              <h2 className="m-marquee__name" style={{ color: hueColor(marquee.hue) }}>
                {marquee.name}
              </h2>
              <p className="m-marquee__brief">{firstLine(marquee.brief) || "No brief yet."}</p>
              <dl className="m-facts">
                <div>
                  <dt>Apps</dt>
                  <dd>{marquee.apps.length}</dd>
                </div>
                <div>
                  <dt>Episodes</dt>
                  <dd>{marquee.counts.episodes}</dd>
                </div>
                <div>
                  <dt>Facts</dt>
                  <dd>{marquee.counts.facts}</dd>
                </div>
              </dl>
              <button type="button" className="btn btn-primary" onClick={() => enter(marquee)}>
                Enter
              </button>
            </>
          ) : shown.length === 0 && load === "ready" ? (
            <p className="m-lead">
              Projects keep Athena&apos;s memory for one piece of your work apart from the rest.
            </p>
          ) : (
            <p className="m-muted">Point at a project to see it here.</p>
          )}
        </aside>
      </div>
    </div>
  );
}

function NewProject() {
  const createSpace = useMain((s) => s.createSpace);
  const navigate = useMain((s) => s.navigate);
  const setActive = useMain((s) => s.setActive);
  const full = useMain((s) => s.spaces.length >= SPACES_MAX);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const clean = name.trim();

  const submit = async () => {
    if (!clean || clean.length > NAME_MAX) return;
    setBusy(true);
    setProblem("");
    try {
      const created = await createSpace(clean);
      setOpen(false);
      setName("");
      navigate({ view: "project", id: created.id });
      void setActive(created.id);
    } catch (e) {
      setProblem(reasonOf(e, "Could not create the project"));
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        className="btn btn-primary m-push"
        disabled={full}
        title={full ? `You have ${SPACES_MAX} projects, the most there can be` : undefined}
        onClick={() => setOpen(true)}
      >
        New project
      </button>
    );
  }
  return (
    <form
      className="m-row m-push"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <label className="m-sr" htmlFor="new-project">
        Project name
      </label>
      <input
        id="new-project"
        className="field m-new"
        autoFocus
        maxLength={NAME_MAX}
        placeholder="Name the project"
        value={name}
        disabled={busy}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
      />
      <button type="submit" className="btn btn-primary" disabled={!clean || busy}>
        {busy ? "Creating..." : "Create"}
      </button>
      <button type="button" className="btn btn-quiet" onClick={() => setOpen(false)}>
        Cancel
      </button>
      {problem && (
        <p className="m-error" role="alert">
          {problem}
        </p>
      )}
    </form>
  );
}
