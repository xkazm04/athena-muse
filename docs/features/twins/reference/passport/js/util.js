// Shared helpers: escaping, time words, icons, the seal and the twin's monogram portrait, stamps.
(function () {
  const D = window.TWIN_DATA;
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  const NOW = new Date(D.now);
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const day = (iso) => {
    const d = new Date(iso);
    return `${d.getDate()} ${MONTHS[d.getMonth()]}`;
  };
  // relative words against the prototype's "now"
  function rel(iso) {
    if (!iso) return "-";
    const d = new Date(iso);
    const min = Math.round((NOW - d) / 60000);
    if (min < 1) return "just now";
    if (min < 60) return `${min} min ago`;
    const sameDay = d.toDateString() === NOW.toDateString();
    if (sameDay) return `${Math.round(min / 60)} h ago`;
    const y = new Date(NOW);
    y.setDate(y.getDate() - 1);
    if (d.toDateString() === y.toDateString()) return "yesterday";
    return day(iso);
  }
  const money = (v) => (v === null || v === undefined ? "-" : `$${v.toFixed(2)}`);
  const num = (v) => (v === null || v === undefined ? "-" : String(v));
  const secs = (s) => `${s.toFixed(1)} s`;
  const clock = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

  const P = (d, extra = "") => `<path d="${d}" ${extra}/>`;
  const svg = (inner, cls = "ic") =>
    `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${inner}</svg>`;
  const icons = {
    gmail: svg(P("M3 6.5h18v11H3z") + P("M3.5 7l8.5 6.5L20.5 7")),
    notion: svg(P("M5 4.5h11l3 3v12H5z") + P("M9 16V9l6 7V9")),
    calendar: svg(P("M4 6h16v14H4z") + P("M4 10h16M8 3.5v4M16 3.5v4")),
    slack: svg(P("M9 4v9M15 11v9M4 15h9M11 9h9")),
    pencil: svg(P("M4 20l1-4.5L15.5 5a2 2 0 0 1 3 3L8 18.5z") + P("M13.5 7l3 3")),
    nib: svg(P("M12 21l-6-8 3-8h6l3 8z") + P("M12 13v8M10.5 11a1.5 1.5 0 1 0 3 0a1.5 1.5 0 1 0 -3 0")),
    check: svg(P("M5 12.5l4.5 4.5L19 7.5")),
    x: svg(P("M6 6l12 12M18 6L6 18")),
    never: svg(P("M12 3.5a8.5 8.5 0 1 0 0 17a8.5 8.5 0 1 0 0-17") + P("M6 6l12 12")),
    risk: svg(P("M12 4l9 16H3z") + P("M12 10v4.5M12 17.2v.3")),
    send: svg(P("M4 12l16-8-6 16-2.5-6.5z")),
    hand: svg(P("M8 12V6a1.5 1.5 0 0 1 3 0v5M11 11V4.5a1.5 1.5 0 0 1 3 0V11M14 11V6a1.5 1.5 0 0 1 3 0v7c0 4-2.5 7-6 7s-5-2-6.5-5L3 11.5a1.4 1.4 0 0 1 2.3-1.6L8 13")),
    clock: svg(P("M12 3.5a8.5 8.5 0 1 0 0 17a8.5 8.5 0 1 0 0-17") + P("M12 7.5V12l3 2")),
    book: svg(P("M4 5.5c3-1.5 5.5-1.5 8 0v14c-2.5-1.5-5-1.5-8 0z") + P("M20 5.5c-3-1.5-5.5-1.5-8 0v14c2.5-1.5 5-1.5 8 0z")),
    sun: svg(P("M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8") + P("M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4")),
    moon: svg(P("M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10z")),
    chat: svg(P("M4 5h16v11H9l-5 4z")),
    layers: svg(P("M12 4l8.5 4.5L12 13 3.5 8.5z") + P("M3.5 12.5L12 17l8.5-4.5") + P("M3.5 16.5L12 21l8.5-4.5")),
    arrow: svg(P("M5 12h14M13 6l6 6-6 6")),
    back: svg(P("M19 12H5M11 6l-6 6 6 6")),
    close: svg(P("M6 6l12 12M18 6L6 18")),
    retry: svg(P("M4.5 12a7.5 7.5 0 1 0 2.2-5.3") + P("M4.5 4.5v4h4")),
    key: svg(P("M8.5 15.5a4 4 0 1 1 3-3l8 8M16.5 16.5l2-2M14.5 14.5l1.5-1.5")),
    mail: svg(P("M3 6.5h18v11H3z") + P("M3.5 7l8.5 6.5L20.5 7")),
    file: svg(P("M6 3.5h8l4 4v13H6z") + P("M14 3.5v4h4M9 13h6M9 16.5h6")),
    plus: svg(P("M12 5v14M5 12h14")),
    eye: svg(P("M2.5 12s3.5-6.5 9.5-6.5S21.5 12 21.5 12s-3.5 6.5-9.5 6.5S2.5 12 2.5 12z") + P("M12 9.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5")),
  };

  // Her seal, the app's mark: a small dome with an orb and the A (geometry from the app's Seal).
  let uid = 0;
  const DOME = "M8 50 C8 25 21 10 38 10 C55 10 68 25 68 50 q-5 6 -10 0 q-5 6 -10 0 q-5 6 -10 0 q-5 6 -10 0 q-5 6 -10 0 q-5 6 -10 0 Z";
  const TENT = ["M22 54 q-3 7 0 14", "M33 55 q3 8 0 15", "M44 55 q-3 8 0 15", "M55 54 q3 7 0 14"];
  function seal(size = 36) {
    const id = "sl" + uid++;
    return `<svg class="seal" viewBox="0 0 76 76" width="${size}" height="${size}" aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id="${id}d" cx="35%" cy="25%" r="85%"><stop offset="0" stop-color="var(--seal-dome-a)"/><stop offset="1" stop-color="var(--seal-dome-b)"/></radialGradient>
        <radialGradient id="${id}o" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="var(--seal-orb-core)"/><stop offset="1" stop-color="var(--seal-orb-edge)"/></radialGradient>
      </defs>
      <g fill="none" stroke="var(--seal-dome-a)" stroke-width="2.4" stroke-linecap="round" opacity=".8">${TENT.map((d) => `<path d="${d}"/>`).join("")}</g>
      <path d="${DOME}" fill="url(#${id}d)"/>
      <path d="M17 36 C19 25 27 17 37 15.5" fill="none" stroke="var(--seal-gleam)" stroke-width="2.4" stroke-linecap="round"/>
      <circle cx="38" cy="33" r="16" fill="url(#${id}o)"/>
      <path d="M31.5 41 L38 24 L44.5 41 M34 35.5 L42 35.5" fill="none" stroke="var(--seal-mark)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`;
  }

  // The twin's portrait: the same dome, its own letter on the orb. `pencil` draws it as her sketch.
  function portrait(letter, { size = 72, pencil = false, blank = false } = {}) {
    const id = "pt" + uid++;
    if (blank)
      return `<svg class="portrait portrait--blank" viewBox="0 0 76 76" width="${size}" height="${size}" aria-hidden="true" focusable="false">
        <path d="${DOME}" fill="none" stroke="var(--border-emphasis)" stroke-width="1.6" stroke-dasharray="4 4"/>
        <circle cx="38" cy="33" r="14" fill="none" stroke="var(--border-default)" stroke-width="1.6" stroke-dasharray="3 4"/></svg>`;
    if (pencil)
      return `<svg class="portrait portrait--pencil" viewBox="0 0 76 76" width="${size}" height="${size}" aria-hidden="true" focusable="false">
        <g fill="none" stroke="var(--role-agent)" stroke-width="1.6" stroke-dasharray="4 3" stroke-linecap="round">${TENT.map((d) => `<path d="${d}"/>`).join("")}<path d="${DOME}"/><circle cx="38" cy="33" r="16"/></g>
        <text x="38" y="39.5" text-anchor="middle" font-size="18" font-weight="600" fill="var(--role-agent)">${esc(letter)}</text></svg>`;
    return `<svg class="portrait" viewBox="0 0 76 76" width="${size}" height="${size}" aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id="${id}d" cx="35%" cy="25%" r="85%"><stop offset="0" stop-color="var(--seal-dome-a)"/><stop offset="1" stop-color="var(--seal-dome-b)"/></radialGradient>
        <radialGradient id="${id}o" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="var(--seal-orb-core)"/><stop offset="1" stop-color="var(--seal-orb-edge)"/></radialGradient>
      </defs>
      <g fill="none" stroke="var(--seal-dome-a)" stroke-width="2.4" stroke-linecap="round" opacity=".75">${TENT.map((d) => `<path d="${d}"/>`).join("")}</g>
      <path d="${DOME}" fill="url(#${id}d)"/>
      <path d="M17 36 C19 25 27 17 37 15.5" fill="none" stroke="var(--seal-gleam)" stroke-width="2.4" stroke-linecap="round"/>
      <circle cx="38" cy="33" r="16" fill="url(#${id}o)"/>
      <text x="38" y="39.5" text-anchor="middle" font-size="18" font-weight="600" fill="var(--seal-mark)">${esc(letter)}</text>
    </svg>`;
  }

  // A rubber stamp. tone: human (waits for you), warning (held), success (went / connected), error.
  const stamp = (text, tone, { sub = "", fresh = false, cls = "" } = {}) =>
    `<span class="stamp ${fresh ? "stamp--fresh" : ""} ${cls}" data-tone="${tone}"><span class="stamp__t">${esc(text)}</span>${sub ? `<span class="stamp__s">${esc(sub)}</span>` : ""}</span>`;

  // How sure it was against the channel's bar.
  function sure(value, bar, { compact = false } = {}) {
    const ok = bar === null || value >= bar;
    return `<div class="sure ${compact ? "sure--compact" : ""}" data-ok="${ok}">
      <div class="sure__track" role="img" aria-label="How sure it was: ${value}. Your bar: ${bar ?? "none"}.">
        <span class="sure__fill" style="width:${value}%"></span>
        ${bar !== null ? `<span class="sure__bar" style="left:${bar}%"></span>` : ""}
      </div>
      <span class="sure__words">How sure it was: <b>${value}</b>${bar !== null ? ` · your bar ${bar}` : ""}</span>
    </div>`;
  }

  const levelLabel = (id) => (D.autonomyLevels.find((l) => l.id === id) || {}).label || "-";
  // one channel's autonomy in plain words
  function clearance(c) {
    if (c.split) return `first message ${levelLabel(c.split.first_message)}, replies ${levelLabel(c.split.replies)}${c.bar !== null ? ` at ${c.bar}` : ""}`;
    return `${levelLabel(c.autonomy)}${c.autonomy === "auto" && c.bar !== null ? ` at ${c.bar}` : ""}${c.scope ? `, ${c.scope}` : ""}`;
  }

  function clearanceShort(c) {
    if (c.split) return `${levelLabel(c.split.first_message)} first, then ${levelLabel(c.split.replies)}${c.bar !== null ? ` at ${c.bar}` : ""}`;
    return `${levelLabel(c.autonomy)}${c.autonomy === "auto" && c.bar !== null ? ` at ${c.bar}` : ""}`;
  }

  window.TP = window.TP || {};
  Object.assign(window.TP, { D, V: window.TWIN_VARIANT, esc, rel, day, money, num, secs, clock, icons, seal, portrait, stamp, sure, levelLabel, clearance, clearanceShort });
})();
