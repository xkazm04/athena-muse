// Rehearsal - small helpers shared by every view: escaping, times, numbers, icons, Athena's mark.
(function () {
  const D = window.TWIN_DATA;
  const R = window.REHEARSAL;
  const NOW = new Date(D.now);
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  const day = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  function rel(iso) {
    if (!iso) return "-";
    const d = new Date(iso);
    const min = Math.round((NOW - d) / 60000);
    if (min < 1) return "just now";
    if (min < 60) return min + " min ago";
    const days = Math.round((day(NOW) - day(d)) / 864e5);
    if (days === 0) return Math.round(min / 60) + " h ago";
    if (days === 1) return "yesterday";
    if (days < 7) return days + " days ago";
    return d.getDate() + " " + MONTHS[d.getMonth()];
  }
  const dateShort = (iso) => {
    const d = new Date(iso);
    return d.getDate() + " " + MONTHS[d.getMonth()];
  };
  const num = (v) => (v === null || v === undefined ? "-" : String(v));
  const usd = (v) => (v === null || v === undefined ? "-" : "$" + Number(v).toFixed(2));
  const secs = (s) => s.toFixed(1) + " s";
  const clock = (s) => Math.floor(s / 60) + ":" + String(Math.floor(s % 60)).padStart(2, "0");

  // Stroke icons, 16 px box, currentColor.
  const P = {
    mail: '<rect x="2" y="3.5" width="12" height="9" rx="1.6"/><path d="M2.6 4.4 8 8.6l5.4-4.2"/>',
    notion: '<rect x="2.5" y="2.5" width="11" height="11" rx="2"/><path d="M6 11V5l4 6V5"/>',
    check: '<path d="m3.5 8.4 2.8 2.8 6.2-6.4"/>',
    x: '<path d="m4.5 4.5 7 7m0-7-7 7"/>',
    pencil: '<path d="m10.6 2.9 2.5 2.5-7.4 7.4-3.1.6.6-3.1z"/><path d="m9.3 4.2 2.5 2.5"/>',
    pen: '<path d="M8 2.2 12.4 7 8 13.8 3.6 7z"/><circle cx="8" cy="7.4" r="1.1"/><path d="M8 8.5v5.3"/>',
    warn: '<path d="M8 2.6 14 13H2z"/><path d="M8 6.6v3.2M8 11.4v.1"/>',
    clock: '<circle cx="8" cy="8" r="5.6"/><path d="M8 4.8V8l2.2 1.4"/>',
    arrow: '<path d="M3 8h9.5M9 4.5 12.5 8 9 11.5"/>',
    back: '<path d="M13 8H3.5M7 4.5 3.5 8 7 11.5"/>',
    chev: '<path d="m6 3.8 4.2 4.2L6 12.2"/>',
    chevDown: '<path d="M3.8 6 8 10.2 12.2 6"/>',
    sun: '<circle cx="8" cy="8" r="2.8"/><path d="M8 1.6v1.6M8 12.8v1.6M1.6 8h1.6M12.8 8h1.6M3.5 3.5l1.1 1.1M11.4 11.4l1.1 1.1M3.5 12.5l1.1-1.1M11.4 4.6l1.1-1.1"/>',
    moon: '<path d="M13 9.6A5.4 5.4 0 0 1 6.4 3a5.4 5.4 0 1 0 6.6 6.6z"/>',
    layers: '<path d="M8 2.5 14 5.6 8 8.7 2 5.6z"/><path d="m2 8.2 6 3.1 6-3.1"/><path d="m2 10.8 6 3.1 6-3.1"/>',
    chat: '<path d="M2.6 4.2c0-.9.7-1.6 1.6-1.6h7.6c.9 0 1.6.7 1.6 1.6v5.2c0 .9-.7 1.6-1.6 1.6H6.6L3.8 13.4V11h0c-.7 0-1.2-.6-1.2-1.4z"/>',
    send: '<path d="M2.6 8 13.4 3 10 13.4 7.6 8.6z"/><path d="M7.6 8.6 13.4 3"/>',
    file: '<path d="M4 2.2h5l3 3v8.6H4z"/><path d="M9 2.2v3h3M6 9h4M6 11.2h4"/>',
    lock: '<rect x="3.4" y="7" width="9.2" height="6.6" rx="1.4"/><path d="M5.4 7V5.2a2.6 2.6 0 0 1 5.2 0V7"/>',
    play: '<path d="M5 3.2v9.6L12.6 8z"/>',
    stop: '<path d="M4.6 4.6 11.4 11.4M11.4 4.6l-6.8 6.8"/><circle cx="8" cy="8" r="5.8"/>',
    retry: '<path d="M12.8 7.4A4.8 4.8 0 1 0 11.4 11"/><path d="M13 3.6v3.8H9.2"/>',
    hand: '<path d="M5.4 8.4V4.2a1 1 0 0 1 2 0v3.4M7.4 7V3.2a1 1 0 0 1 2 0V7M9.4 7V4a1 1 0 0 1 2 0v5.2c0 2.6-1.6 4.6-4 4.6-1.6 0-2.6-.8-3.4-2L2.6 8.8a1 1 0 0 1 1.6-1.2l1.2 1.4"/>',
    spark: '<path d="M8 2v3.2M8 10.8V14M2 8h3.2M10.8 8H14M4 4l2 2M10 10l2 2M4 12l2-2M10 6l2-2"/>',
    plus: '<path d="M8 3v10M3 8h10"/>',
    eye: '<path d="M1.8 8S4 3.8 8 3.8 14.2 8 14.2 8 12 12.2 8 12.2 1.8 8 1.8 8z"/><circle cx="8" cy="8" r="1.9"/>',
    calendar: '<rect x="2.4" y="3.4" width="11.2" height="10" rx="1.6"/><path d="M2.4 6.6h11.2M5.4 2v2.6M10.6 2v2.6"/>',
    slack: '<path d="M6 2.6v5M10 8.4v5M2.6 10h5M8.4 6h5"/>',
  };
  const icon = (n, cls = "") =>
    `<svg class="ic ${cls}" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[n] || ""}</svg>`;

  // Athena's mark: a jellyfish dome with an A, drawn in the seal tokens.
  let markN = 0;
  function mark(size = 30) {
    const id = "mk" + markN++;
    return `<svg class="mark" viewBox="0 0 40 40" width="${size}" height="${size}" aria-hidden="true">
      <defs><radialGradient id="${id}" cx="40%" cy="30%" r="75%"><stop offset="0" stop-color="var(--seal-orb-core)"/><stop offset=".55" stop-color="var(--seal-dome-a)"/><stop offset="1" stop-color="var(--seal-dome-b)"/></radialGradient></defs>
      <path d="M5 21C5 11.6 11.7 5 20 5s15 6.6 15 16c-1.8 1.4-3.4 1.4-5 0-1.6 1.4-3.4 1.4-5 0-1.6 1.4-3.4 1.4-5 0-1.6 1.4-3.4 1.4-5 0-1.6 1.4-3.4 1.4-5 0z" fill="url(#${id})"/>
      <path d="M15.4 17.4 20 9.6l4.6 7.8M16.9 14.8h6.2" fill="none" stroke="var(--seal-mark)" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M13 25c-1.4 3 1.4 5 0 9M20 25.4c-1.4 3 1.4 5 0 9M27 25c-1.4 3 1.4 5 0 9" fill="none" stroke="var(--seal-orb-core)" stroke-width="1.6" stroke-linecap="round" opacity=".8"/>
    </svg>`;
  }

  // The twin's pencil line: [[x]] blanks become names once the mission is set, otherwise a blank.
  function fillLine(text, named) {
    const parts = esc(text).split(/\[\[([^\]]+)\]\]/);
    let out = "";
    parts.forEach((p, i) => {
      if (i % 2 === 0) out += p;
      else if (named && R.names[p]) out += `<span class="filled">${esc(R.names[p])}</span>`;
      else out += `<span class="blank" title="Not known yet">${p}</span>`;
    });
    return out.replace(/\n\n([\s\S]*)$/, ' <span class="signoff">$1</span>');
  }

  // Wrap the words of an HTML line in spans that arrive one after another (the wow).
  function typeIn(html, delay = 0, step = 18) {
    let i = 0;
    return html.replace(/(<[^>]+>)|([^<\s]+)/g, (m, tag, word) => {
      if (tag) return tag;
      return `<span class="w" style="animation-delay:${delay + i++ * step}ms">${word}</span>`;
    });
  }

  window.U = { D, R, NOW, esc, rel, dateShort, num, usd, secs, clock, icon, mark, fillLine, typeIn };

  // The app's action registry and the "only the new piece arrives" memory; app.js adds the rest.
  window.App = {
    acts: {},
    on(map) {
      Object.assign(this.acts, map);
    },
    act(name, el) {
      const f = this.acts[name];
      if (f) f(el || { dataset: {} });
    },
    seen: new Set(),
    quiet: false,
    isNew(key) {
      if (this.seen.has(key)) return false;
      this.seen.add(key);
      return !this.quiet;
    },
  };
})();
