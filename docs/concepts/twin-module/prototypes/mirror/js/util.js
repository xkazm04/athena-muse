// Mirror - small helpers shared by every script. Classic scripts so the page opens from disk.
(function () {
  const TP = (window.TP = window.TP || {});
  TP.D = window.TWIN_DATA;
  TP.V = window.TWIN_VARIANT;
  TP.act = {}; // click handlers by data-act name
  TP.speed = 4; // play faster than real; on-screen seconds stay real

  TP.esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  TP.$ = (sel, root = document) => root.querySelector(sel);
  TP.$$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  // Timers that belong to the current state; go() clears them all.
  const live = new Set();
  TP.later = (fn, ms) => {
    const id = setTimeout(() => { live.delete(id); fn(); }, ms);
    live.add(id);
    return id;
  };
  TP.every = (fn, ms) => {
    const id = setInterval(fn, ms);
    live.add(-id - 1);
    return id;
  };
  TP.clearTimers = () => {
    for (const id of live) id < 0 ? clearInterval(-id - 1) : clearTimeout(id);
    live.clear();
  };

  TP.reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Relative time against the example's "now".
  const NOW = new Date(TP.D.now);
  const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  TP.day = (iso) => { const d = new Date(iso); return `${d.getDate()} ${MON[d.getMonth()]}`; };
  TP.rel = (iso) => {
    if (!iso) return "-";
    const d = new Date(iso);
    const min = Math.round((NOW - d) / 60000);
    if (min < 1) return "just now";
    if (min < 60) return `${min} min ago`;
    if (min < 60 * 12 && d.getDate() === NOW.getDate()) return `${Math.round(min / 60)} h ago`;
    const days = Math.round((new Date(NOW.toDateString()) - new Date(d.toDateString())) / 864e5);
    if (days === 0) return `today ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    if (days === 1) return "yesterday";
    if (days < 7) return `${days} days ago`;
    return TP.day(iso);
  };
  TP.clock = (iso) => { const d = new Date(iso); return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };
  TP.secs = (s) => `${s.toFixed(1)} s`;
  TP.money = (v) => (v === null || v === undefined ? "-" : `$${v.toFixed(2)}`);
  TP.num = (v) => (v === null || v === undefined ? "-" : String(v));

  // Tagged text -> paragraphs of spans. {id|words}, {~|words}, {-id|words}; "\n\n" splits paragraphs.
  TP.parseTagged = (str) =>
    str.split(/\n\n/).map((para) =>
      para.split(/\n/).map((line) => {
        const out = [];
        const re = /\{(-?)([~\w]+)\|([^}]*)\}/g;
        let last = 0, m;
        while ((m = re.exec(line))) {
          if (m.index > last) out.push({ t: line.slice(last, m.index), kind: "plain" });
          if (m[2] === "~") out.push({ t: m[3], kind: "stock" });
          else out.push({ t: m[3], id: m[2], kind: m[1] ? "gone" : "piece" });
          last = re.lastIndex;
        }
        if (last < line.length) out.push({ t: line.slice(last), kind: "plain" });
        return out;
      })
    );
  TP.plainOf = (str) => str.replace(/\{-[^}]*\}\s?/g, "").replace(/\{[~\w]+\|([^}]*)\}/g, "$1");

  // Word diff (LCS) for "a reflection correcting itself".
  TP.diffWords = (a, b) => {
    const A = a.split(/(\s+)/), B = b.split(/(\s+)/);
    const n = A.length, m = B.length;
    const L = Array.from({ length: n + 1 }, () => new Int16Array(m + 1));
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) L[i][j] = A[i] === B[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    const out = [];
    let i = 0, j = 0;
    while (i < n && j < m) {
      if (A[i] === B[j]) { out.push({ t: A[i], op: "same" }); i++; j++; }
      else if (L[i + 1][j] >= L[i][j + 1]) out.push({ t: A[i++], op: "del" });
      else out.push({ t: B[j++], op: "add" });
    }
    while (i < n) out.push({ t: A[i++], op: "del" });
    while (j < m) out.push({ t: B[j++], op: "add" });
    return out;
  };

  TP.placeLabel = (id) => TP.D.places.find((p) => p.id === id)?.label ?? id;
  TP.sampleById = (id) => TP.D.setup.samples.find((s) => s.id === id);

  // Icons, drawn inline.
  const P = {
    check: '<path d="M4 8.5l2.6 2.6L12 5.6"/>',
    pen: '<path d="M10.8 2.8l2.4 2.4-7.6 7.6-3 .6.6-3z"/>',
    mail: '<rect x="2" y="3.5" width="12" height="9" rx="1.5"/><path d="M2.5 4.5l5.5 4.2 5.5-4.2"/>',
    page: '<path d="M4 2h5.5L12 4.5V14H4z"/><path d="M6 7h4M6 9.5h4"/>',
    chev: '<path d="M6 4l4 4-4 4"/>',
    down: '<path d="M4 6l4 4 4-4"/>',
    back: '<path d="M10 4L6 8l4 4"/>',
    send: '<path d="M3 8h9M8.5 4.5L12 8l-3.5 3.5"/>',
    x: '<path d="M4.5 4.5l7 7M11.5 4.5l-7 7"/>',
    sun: '<circle cx="8" cy="8" r="2.8"/><path d="M8 1.5v1.6M8 12.9v1.6M1.5 8h1.6M12.9 8h1.6M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M3.4 12.6l1.1-1.1M11.5 4.5l1.1-1.1"/>',
    moon: '<path d="M12.8 9.6A5.2 5.2 0 016.4 3.2a5.2 5.2 0 106.4 6.4z"/>',
    risk: '<path d="M8 2.2l6 10.6H2z"/><path d="M8 6.5v3M8 11.2v.1"/>',
    replay: '<path d="M3 8a5 5 0 109-3"/><path d="M12.4 2v3.2H9.2"/>',
    lock: '<rect x="3.5" y="7" width="9" height="6.5" rx="1.2"/><path d="M5.5 7V5a2.5 2.5 0 015 0v2"/>',
    dial: '<path d="M2.5 5h11M2.5 11h11"/><circle cx="6" cy="5" r="1.6"/><circle cx="10.5" cy="11" r="1.6"/>',
    history: '<path d="M2.5 8a5.5 5.5 0 101.6-3.9"/><path d="M2.4 2.6v2.6H5"/><path d="M8 5v3.2l2 1.3"/>',
    layers: '<path d="M8 2l6 3.2-6 3.2-6-3.2z"/><path d="M2 8.4l6 3.2 6-3.2"/>',
    spark: '<path d="M8 2v3M8 11v3M2 8h3M11 8h3"/>',
  };
  TP.icon = (name, cls = "") =>
    `<svg class="ico ${cls}" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[name] || ""}</svg>`;

  // Athena's seal: a small jellyfish-like dome with her letter.
  TP.seal = (size = 32) => `<svg class="seal" width="${size}" height="${size}" viewBox="0 0 40 40" aria-hidden="true">
    <defs><radialGradient id="sg${size}" cx="40%" cy="30%" r="70%"><stop offset="0" stop-color="var(--seal-orb-core)"/><stop offset=".55" stop-color="var(--seal-dome-a)"/><stop offset="1" stop-color="var(--seal-dome-b)"/></radialGradient></defs>
    <path d="M7 21a13 13 0 0126 0c0 1.4-1 2-2.2 2H9.2C8 23 7 22.4 7 21z" fill="url(#sg${size})"/>
    <path d="M13 25c0 4-2 6-2 9M20 25v10M27 25c0 4 2 6 2 9" stroke="var(--seal-orb-core)" stroke-width="1.6" fill="none" stroke-linecap="round" opacity=".8"/>
    <text x="20" y="20" text-anchor="middle" font-family="Outfit, sans-serif" font-weight="600" font-size="11" fill="var(--seal-mark)">A</text>
  </svg>`;
})();
