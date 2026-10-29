// Mirror - the twins page: a stat strip, then the ledger. A row opens in place to show its latest
// exchange as a small mirror (their message, its reply), drafts waiting, and missions.
(function () {
  const TP = window.TP, D = TP.D, V = TP.V, esc = TP.esc;
  const clone = (v) => JSON.parse(JSON.stringify(v));

  TP.ovInit = (mode, extra = {}) => {
    const src = mode === "after" ? D.overview_after_golive : D.overview;
    return { mode, rows: clone(src.rows), open: extra.open ?? null, draft: extra.draft ?? null, mission: extra.mission ?? null, signin: "idle", editing: false, flash: null, arrived: mode === "after" ? "tw_partners" : null };
  };

  // Same formulas as shared/src/build.mjs, so a signed draft or a fixed sign-in moves the strip.
  const sumOf = (rows, f) => { const v = rows.map(f).filter((x) => x !== null && x !== undefined); return v.length ? Math.round(v.reduce((a, b) => a + b, 0) * 100) / 100 : null; };
  const statsOf = (rows) => ({
    live: rows.filter((t) => t.state === "live").length,
    waiting_for_you: sumOf(rows, (t) => t.waiting.length + t.missions.filter((m) => m.state === "handed_back").length),
    missions_open: sumOf(rows, (t) => t.missions.filter((m) => m.state === "open" || m.state === "handed_back").length),
    sent_week: sumOf(rows, (t) => t.week.sent),
    sent_alone_week: sumOf(rows, (t) => t.week.sent_alone),
    held_by_risk_week: sumOf(rows, (t) => t.week.held_by_risk),
    cost_usd_week: sumOf(rows, (t) => t.week.cost_usd),
  });

  const STATE = { live: ["success", "Live"], paused: ["warning", "Paused"], setting_up: ["agent", "Being set up"] };
  const AUTON = Object.fromEntries(D.autonomyLevels.map((a) => [a.id, a.label]));
  const kindLabel = (k) => D.channelKinds[k].label;
  const lastActive = (r) => { const t = r.channels.map((c) => c.last_at).filter(Boolean).sort().pop(); return t ? TP.rel(t) : "-"; };

  const chanChip = (c) => {
    if (c.status === "needs_sign_in") return `<span class="chip chip-warn" title="${esc(c.account)}">${TP.icon(c.kind === "gmail" ? "mail" : "page")}${kindLabel(c.kind)}: sign in again</span>`;
    const lvl = c.split ? `${AUTON[c.split.first_message]} first, ${AUTON[c.split.replies]} replies` : AUTON[c.autonomy];
    const bar = c.bar !== null && c.bar !== undefined ? ` at ${c.bar}` : "";
    return `<span class="chip" title="${esc(c.account)}${c.scope ? ", " + esc(c.scope) : ""}"><i class="health h-${c.health}" aria-label="${c.health}"></i>${TP.icon(c.kind === "gmail" ? "mail" : "page")}${kindLabel(c.kind)} · ${lvl}${bar}</span>`;
  };

  // ---- stat strip ----
  const dots = (n, on, tone) => `<span class="q-dots" aria-hidden="true">${Array.from({ length: n }, (_, i) => `<i class="${i < on ? "on " + tone : ""}"></i>`).join("")}</span>`;
  const delta = (k, s) => {
    const o = TP.S.ov;
    if (o.mode !== "after") return "";
    const before = D.overview.stats[k], now = s[k];
    if (before === null || now === null || before === now) return "";
    const d = Math.round((now - before) * 100) / 100;
    return `<span class="delta">${d > 0 ? "+" : ""}${k === "cost_usd_week" ? "$" + d.toFixed(2) : d}</span>`;
  };
  const tiles = (rows) => {
    const s = statsOf(rows);
    const signed = s.sent_week === null ? null : s.sent_week - (s.sent_alone_week ?? 0);
    const t = [
      ["live", "Live twins", TP.num(s.live), `of ${rows.length}`, dots(rows.length, s.live, "ok")],
      ["waiting_for_you", "Waiting for you", TP.num(s.waiting_for_you), "drafts and hand-backs", dots(Math.max(s.waiting_for_you ?? 0, 1), s.waiting_for_you ?? 0, "human"), "human"],
      ["missions_open", "Missions open", TP.num(s.missions_open), "conversations", ""],
      ["sent_week", "Sent this week", TP.num(s.sent_week), s.sent_alone_week === null ? "" : `${s.sent_alone_week} on its own`,
        s.sent_week ? `<span class="q-split" aria-hidden="true"><i style="flex:${s.sent_alone_week}"></i><b style="flex:${signed}"></b></span><span class="q-legend">${s.sent_alone_week} alone · ${signed} signed by you</span>` : ""],
      ["held_by_risk_week", "Held by its risk list", TP.num(s.held_by_risk_week), "this week", ""],
      ["cost_usd_week", "Cost this week", TP.money(s.cost_usd_week), "est.", ""],
    ];
    return `<div class="stats" role="list">${t.map(([k, label, fig, unit, q, tone]) => `<div class="tile${tone ? " t-" + tone : ""}" role="listitem"><p class="t-label">${label}</p><p class="t-fig"><strong>${fig}</strong><span>${unit}</span>${delta(k, s)}</p>${q ? `<div class="t-q">${q}</div>` : ""}</div>`).join("")}</div>`;
  };

  // ---- ledger ----
  const HEAD = `<div class="lg-head" role="row"><span>Twin</span><span>State</span><span>Channels</span><span>Ready</span><span class="num">Missions</span><span class="num">Waiting</span><span class="num">This week</span><span class="c-last">Last active</span><span></span></div>`;

  const rowHTML = (r) => {
    const o = TP.S.ov, isOpen = o.open === r.id;
    const [tone, word] = STATE[r.state];
    const handed = r.missions.filter((m) => m.state === "handed_back").length;
    const sent = r.week.sent === null ? "-" : `${r.week.sent}${r.week.sent ? `<small> · ${r.week.sent_alone} alone</small>` : ""}`;
    let last = `<span class="c-last">${lastActive(r)}</span>`;
    if (r.state === "paused" && r.channels.some((c) => c.status === "needs_sign_in")) last = `<span class="c-last"><button class="btn btn-mini" data-act="ov-signin" data-id="${r.id}">Sign in again</button></span>`;
    if (r.state === "setting_up") last = `<span class="c-last"><button class="btn btn-mini" data-act="new-twin">Continue setup</button></span>`;
    return `<div class="lg-row${isOpen ? " open" : ""}${o.arrived === r.id ? " arrived" : ""}" role="row" data-act="ov-open" data-id="${r.id}" tabindex="0" aria-expanded="${isOpen}">
      <span class="c-twin"><strong>${esc(r.name)}</strong><small>${esc(r.purpose)}</small></span>
      <span><span class="badge" data-tone="${tone}">${word}</span></span>
      <span class="c-chan">${r.channels.length ? r.channels.map(chanChip).join("") : `<span class="muted">None yet</span>`}</span>
      <span class="c-ready"><span class="rbar" aria-hidden="true"><i style="width:${r.readiness}%"></i></span>${r.readiness}%</span>
      <span class="num">${r.open_missions}${handed ? `<small class="hb"> · ${handed} handed back</small>` : ""}</span>
      <span class="num ${r.waiting.length ? "wait-on" : ""}">${r.waiting.length}</span>
      <span class="num">${sent}</span>
      ${last}
      <span class="chev" aria-hidden="true">${TP.icon(isOpen ? "down" : "chev")}</span>
    </div>${isOpen ? openHTML(r) : ""}`;
  };

  // the small mirror: their message on one side, its reply on the other
  const exchangeHTML = (r) => {
    const x = TP.S.ov.mode === "after" && r.id === "tw_partners" ? V.exchanges.tw_partners_live : V.exchanges[r.id];
    if (!x) return `<div class="mini-empty">${TP.icon("layers")}<p>No conversations yet. It starts talking once you go live.</p></div>`;
    let reply, state, cls;
    if (x.reply_from) {
      const d = r.waiting.find((w) => w.id === x.reply_from);
      if (d) { reply = d.excerpt; state = "Waits for your signature"; cls = "pencil"; }
      else { reply = TP.S.ov.sentText || D.overview.rows.find((t) => t.id === r.id).waiting.find((w) => w.id === x.reply_from).excerpt; state = "Sent, signed by you"; cls = "ink"; }
    } else { reply = x.reply; state = x.reply_state === "alone" ? "Sent on its own" : "Sent, signed by you"; cls = "ink"; }
    return `<div class="mini-mirror">
      <div class="mm-theirs"><p class="mm-who">${esc(x.with)} <span>${TP.rel(x.their_at)}</span></p><p>${esc(x.theirs)}</p></div>
      <div class="mm-seam" aria-hidden="true"></div>
      <div class="mm-mine ${cls}"><p class="mm-who">${esc(r.name)} replied <span>${esc(state)}</span></p><p>${esc(reply).replace(/\n\n/g, " ")}</p></div>
    </div>`;
  };

  const meter = (conf, bar) => `<div class="sure" role="img" aria-label="How sure it was: ${conf}. The bar is ${bar}.">
    <div class="sure-track"><i class="sure-fill ${conf >= bar ? "over" : "under"}" style="width:${conf}%"></i><b class="sure-bar" style="left:${bar}%"><span>bar ${bar}</span></b></div>
    <p><strong>${conf}</strong> sure · the bar is ${bar}</p></div>`;

  const draftsHTML = (r) => {
    const o = TP.S.ov;
    const gmail = r.channels.find((c) => c.kind === "gmail");
    const bar = gmail?.bar ?? D.setup.autonomy.bar_default;
    if (o.draft) {
      const d = r.waiting.find((w) => w.id === o.draft);
      if (d) {
        const why = d.why === "held" ? `Held: ${d.risks.length} thing${d.risks.length > 1 ? "s" : ""} on its risk list, so it waits even though it was sure enough.` : `Below the bar: it was ${d.confidence} sure and your bar is ${bar}, so it waits for you.`;
        return `<div class="draft-focus"><div class="df-l">
          <button class="btn btn-quiet back-link" data-act="ov-draft" data-id="">${TP.icon("back")}All waiting</button>
          <p class="df-to">To ${esc(d.to)} · ${esc(d.subject)}</p>
          ${o.editing ? `<textarea class="field df-edit" id="df-edit" rows="3" aria-label="Your edit">${esc(d.excerpt)}</textarea>` : `<p class="df-text">${esc(d.excerpt)}</p>`}
          ${meter(d.confidence, bar)}</div><div class="df-r">
          <div class="risks">${d.risks.length ? `<p class="r-h">${TP.icon("risk")}Its risk list</p><ul>${d.risks.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : `<p class="r-h r-empty">Its risk list is empty</p>`}</div>
          <p class="df-why">${why}</p>
          <div class="df-act">${o.editing ? `<button class="btn btn-primary" data-act="ov-sign" data-id="${d.id}" data-edited="1">Sign and send your edit</button><button class="btn btn-quiet" data-act="ov-edit">Cancel</button>` : `<button class="btn btn-primary" data-act="ov-sign" data-id="${d.id}">Sign and send</button><button class="btn" data-act="ov-edit">Edit</button><button class="btn btn-quiet" data-act="ov-decline" data-id="${d.id}">Decline</button>`}</div>
        </div></div>`;
      }
    }
    if (!r.waiting.length) return `<p class="col-empty">${o.flash ? esc(o.flash) : "Nothing waits for your signature."}</p>`;
    return `<ul class="wait-list">${r.waiting.map((d) => `<li><button class="wait-card" data-act="ov-draft" data-id="${d.id}">
        <span class="wc-top"><span>${esc(d.to)}</span><span class="badge" data-tone="${d.why === "held" ? "warning" : "human"}">${d.why === "held" ? `${d.risks.length} risk` : "below the bar"}</span></span>
        <span class="wc-text">${esc(d.excerpt)}</span>
        <span class="wc-sure"><span class="mini-sure"><i style="width:${d.confidence}%"></i><b style="left:${bar}%"></b></span>${d.confidence} sure, bar ${bar}</span>
      </button></li>`).join("")}</ul>${o.flash ? `<p class="flash">${esc(o.flash)}</p>` : ""}`;
  };

  const MSTATE = { open: ["info", "Open"], resolved: ["success", "Resolved"], handed_back: ["human", "Handed back to you"] };
  const missionsHTML = (r) => {
    const o = TP.S.ov;
    if (!r.missions.length) return `<p class="col-empty">No missions yet. Its first one is chosen at the end of setup.</p>`;
    return `<ul class="mission-list">${r.missions.map((m) => {
      const [tone, word] = MSTATE[m.state];
      const focus = o.mission === m.id;
      return `<li class="${focus ? "focus" : ""} ms-${m.state}"><button class="ms-row" data-act="ov-mission" data-id="${focus ? "" : m.id}" aria-expanded="${focus}">
          <span class="ms-title">${esc(m.title)}</span><span class="badge" data-tone="${tone}">${word}</span>
          <span class="ms-meta">${m.turns} turns · ${TP.rel(m.last_at)}</span></button>
        ${focus ? `<div class="ms-note"><p>${esc(m.note)}</p>${m.state === "handed_back" ? `<div class="df-act"><button class="btn btn-primary" data-act="ov-takeover" data-id="${m.id}">Answer ${esc(m.with)} yourself</button><button class="btn" data-act="ov-carry" data-id="${m.id}">No discount: let it carry on</button></div>` : ""}</div>` : ""}</li>`;
    }).join("")}</ul>`;
  };

  const pausedHTML = (r) => {
    const o = TP.S.ov;
    const c = r.channels.find((x) => x.status === "needs_sign_in");
    if (o.signin === "waiting") return `<div class="paused"><p class="p-h"><span class="pulse"></span>Waiting for you in the browser. Google's sign-in page opened there.</p><button class="btn btn-quiet" data-act="ov-signin-cancel">Cancel</button></div>`;
    if (!c) return `<div class="paused ok"><p class="p-h">${TP.icon("check")}Signed in again as ${esc(r.channels[0].account)}. Family admin is live.</p></div>`;
    return `<div class="paused"><p class="p-h">${TP.icon("lock")}Paused. ${esc(r.paused_because)}</p><p class="p-sub">Nothing was read or sent while it was paused. Sign in as ${esc(c.account)} and it picks up where it stopped.</p>
      <button class="btn btn-primary" data-act="ov-signin" data-id="${r.id}">Sign in with Google again</button></div>`;
  };

  const setupHTML = (r) => `<div class="setting-up"><p>Being set up with Athena. It is ${r.readiness}% ready.</p>
    <ul class="cov">${D.places.map((p) => `<li class="cov-${String(r.filled[p.id]).replace(".", "")}"><i></i>${esc(p.label)}</li>`).join("")}</ul>
    <button class="btn btn-primary" data-act="new-twin">Continue setup with Athena</button></div>`;

  const openHTML = (r) => {
    const chans = r.channels.map((c) => `<span>${kindLabel(c.kind)}: ${esc(c.account)}${c.scope ? " (" + esc(c.scope) + ")" : ""} · last ${TP.rel(c.last_at)}</span>`).join("");
    const median = r.week.median_reply_min === null ? "-" : `${r.week.median_reply_min} min`;
    const colB = r.state === "paused" ? pausedHTML(r) : r.state === "setting_up" ? setupHTML(r) : draftsHTML(r);
    const bTitle = r.state === "paused" ? "Why it is paused" : r.state === "setting_up" ? "Setup" : `Waiting for your signature <em>${r.waiting.length}</em>`;
    const focus = TP.S.ov.draft && r.waiting.some((w) => w.id === TP.S.ov.draft);
    return `<div class="lg-open" role="region" aria-label="${esc(r.name)}">
      <p class="lo-chan">${chans || "No channels yet."}<span>Median reply this week: ${median}</span>${r.since ? `<span>Live since ${TP.day(r.since)}</span>` : ""}</p>
      <div class="lo-cols">
        <section class="lo-col"><h3>Latest exchange</h3>${exchangeHTML(r)}</section>
        <section class="lo-col${focus ? " span2" : ""}"><h3>${bTitle}</h3>${colB}</section>
        ${focus ? "" : `<section class="lo-col"><h3>Missions <em>${r.missions.length}</em></h3>${missionsHTML(r)}</section>`}
      </div></div>`;
  };

  // ---- waiting for you: each item as a small mirror, the one thing to do now ----
  const queueHTML = (rows) => {
    const items = [];
    for (const r of rows) {
      const gmail = r.channels.find((c) => c.kind === "gmail");
      for (const d of r.waiting) {
        const x = V.exchanges[r.id];
        items.push(`<button class="q-card" data-act="ov-jump" data-row="${r.id}" data-draft="${d.id}">
          <span class="q-top"><strong>${esc(r.name)}</strong><span>to ${esc(d.to)}</span><span class="badge" data-tone="${d.why === "held" ? "warning" : "human"}">${d.why === "held" ? `${d.risks.length} risk` : "below the bar"}</span></span>
          <span class="q-mirror">${x && x.reply_from === d.id ? `<span class="q-theirs">${esc(x.theirs)}</span>` : `<span class="q-theirs q-subj">${esc(d.subject)}</span>`}<span class="q-mine">${esc(d.excerpt)}</span></span>
          <span class="q-foot">${d.confidence} sure, bar ${gmail?.bar ?? "-"}${d.risks.length ? ` · ${esc(d.risks[0])}` : " · its risk list is empty"}</span></button>`);
      }
      for (const m of r.missions.filter((m) => m.state === "handed_back")) {
        items.push(`<button class="q-card q-hand" data-act="ov-jump" data-row="${r.id}" data-mission="${m.id}">
          <span class="q-top"><strong>${esc(r.name)}</strong><span>with ${esc(m.with)}</span><span class="badge" data-tone="human">Handed back to you</span></span>
          <span class="q-mirror"><span class="q-theirs q-subj">${esc(m.title)}</span><span class="q-mine q-stop">${esc(m.note)}</span></span>
          <span class="q-foot">${m.turns} turns · stopped ${TP.rel(m.last_at)}</span></button>`);
      }
    }
    const paused = rows.find((r) => r.state === "paused" && r.channels.some((c) => c.status === "needs_sign_in"));
    if (!items.length && !paused) return "";
    return `<section class="queue" aria-label="Waiting for you"><div class="q-head"><h2>Waiting for you <em>${items.length}</em></h2>
      ${paused ? `<p class="q-paused">${TP.icon("lock")}${esc(paused.name)} is paused: ${esc(paused.paused_because)}<button class="btn btn-mini" data-act="ov-signin" data-id="${paused.id}">Sign in again</button></p>` : ""}</div>
      <div class="q-cards">${items.join("") || `<p class="col-empty">Nothing waits for you.</p>`}</div></section>`;
  };
  TP.act["ov-jump"] = (el) => {
    const o = S().ov;
    o.open = el.dataset.row; o.draft = el.dataset.draft || null; o.mission = el.dataset.mission || null; o.editing = false; o.flash = null; o.arrived = null;
    TP.render();
  };

  // ---- the page ----
  TP.renderOverview = (el) => {
    const o = TP.S.ov;
    const head = `<div class="ov-head"><div><h1>Twins</h1><p>Each twin answers for you on your channels, in your own voice, and waits for you when it is unsure.</p></div>
      ${o.mode === "first" ? "" : `<button class="btn btn-primary" data-act="new-twin">Set up a twin with Athena</button>`}</div>`;
    if (o.mode === "loading") {
      el.innerHTML = `<div class="ov">${head}<div class="stats loading" aria-busy="true">${["Live twins", "Waiting for you", "Missions open", "Sent this week", "Held by its risk list", "Cost this week"].map((l) => `<div class="tile"><p class="t-label">${l}</p><p class="ph ph-fig"></p><p class="ph ph-unit"></p></div>`).join("")}</div>
        <div class="ledger plane">${HEAD}<div class="lg-rows">${[1, 2, 3].map(() => `<div class="lg-row ph-row"><span class="ph"></span><span class="ph"></span><span class="ph"></span><span class="ph"></span></div>`).join("")}</div><p class="lg-total muted">Loading your twins</p></div></div>`;
      TP.later(() => { TP.S.ov = TP.ovInit("today"); TP.render(); }, 1600);
      return;
    }
    if (o.mode === "error") {
      el.innerHTML = `<div class="ov">${head}<div class="ov-problem plane" role="alert">${TP.icon("risk")}<div><h2>Could not load your twins.</h2><p>The list did not arrive from the app just now. Your twins are not affected: live ones keep working and keep waiting for you as usual.</p></div><button class="btn btn-primary" data-act="ov-retry">Try again</button></div></div>`;
      return;
    }
    if (o.mode === "first") {
      const v = V.drafts;
      el.innerHTML = `<div class="ov">${head}<div class="first plane">
        <div class="first-copy"><p class="eyebrow">No twins yet</p><h2>A twin answers like you, so you don't have to.</h2>
          <p>Athena sets one up with you in a short conversation: where it speaks, how you sound (only from mail you wrote yourself), what it must never do, and what it may send on its own. It rehearses on a practice page before it ever writes to a real person.</p>
          <button class="btn btn-primary btn-lg" data-act="new-twin">Set up your first twin with Athena</button></div>
        <div class="first-mirror" aria-hidden="true">
          <div class="fm-side"><p class="mm-who">Before</p><p class="fm-stiff">${esc(TP.plainOf(v[0]).split("\n\n").slice(1, 2).join(" "))}</p></div>
          <div class="mm-seam"></div>
          <div class="fm-side fm-you"><p class="mm-who">After it learns you</p><p>${esc(TP.plainOf(v[11]).split("\n\n").slice(1, 2).join(" "))}</p></div>
        </div></div></div>`;
      return;
    }
    const rows = o.rows;
    const s = statsOf(rows);
    const counts = Object.keys(STATE).map((k) => [k, rows.filter((r) => r.state === k).length]).filter(([, n]) => n).map(([k, n]) => `${n} ${STATE[k][1].toLowerCase()}`).join(", ");
    const banner = o.mode === "after" ? `<div class="golive-banner" role="status">${TP.icon("check")}<span><strong>Partnerships is live.</strong> ${esc(D.setup.golive.stays.join(" · "))}</span></div>` : "";
    el.innerHTML = `<div class="ov">${head}${banner}${tiles(rows)}
      <div class="ledger plane" role="table" aria-label="Your twins">${HEAD}<div class="lg-rows">${rows.map(rowHTML).join("")}</div>
      <p class="lg-total" role="row"><span>${rows.length} twins: ${counts}</span><span>${s.missions_open} missions open</span><span class="wait-on">${s.waiting_for_you} waiting for you</span><span>${TP.num(s.sent_week)} sent this week</span><span>est. ${TP.money(s.cost_usd_week)} this week</span></p></div>
      ${o.open ? "" : queueHTML(rows)}</div>`;
  };

  // ---- actions ----
  const S = () => TP.S;
  const rowById = (id) => S().ov.rows.find((r) => r.id === id);
  TP.act["ov-open"] = (el, e) => {
    if (e.target.closest("button")) return;
    const o = S().ov;
    o.open = o.open === el.dataset.id ? null : el.dataset.id;
    o.draft = null; o.mission = null; o.editing = false; o.flash = null; o.arrived = null;
    TP.render();
  };
  TP.act["ov-draft"] = (el) => { const o = S().ov; o.draft = el.dataset.id || null; o.editing = false; o.flash = null; TP.render(); };
  TP.act["ov-edit"] = () => { S().ov.editing = !S().ov.editing; TP.render(); TP.$("#df-edit")?.focus(); };
  TP.act["ov-sign"] = (el) => {
    const o = S().ov, r = rowById(o.open);
    const d = r.waiting.find((w) => w.id === el.dataset.id);
    if (el.dataset.edited) o.sentText = TP.$("#df-edit")?.value || d.excerpt;
    r.waiting = r.waiting.filter((w) => w.id !== d.id);
    r.week.sent += 1;
    r.waiting_count = r.waiting.length;
    o.draft = null; o.editing = false;
    o.flash = `Sent to ${d.to}, signed by you${el.dataset.edited ? ", with your edit. Your edit teaches it." : "."}`;
    TP.render();
  };
  TP.act["ov-decline"] = (el) => {
    const o = S().ov, r = rowById(o.open);
    const d = r.waiting.find((w) => w.id === el.dataset.id);
    r.waiting = r.waiting.filter((w) => w.id !== d.id);
    o.draft = null;
    o.flash = `Declined. Nothing was sent to ${d.to}; the conversation is yours.`;
    TP.render();
  };
  TP.act["ov-mission"] = (el) => { S().ov.mission = el.dataset.id || null; TP.render(); };
  TP.act["ov-takeover"] = (el) => {
    const r = rowById(S().ov.open), m = r.missions.find((x) => x.id === el.dataset.id);
    m.state = "resolved"; m.note = "You took this one over. It will not write to Pine & Co again on this mission.";
    S().ov.mission = m.id; TP.render();
  };
  TP.act["ov-carry"] = (el) => {
    const r = rowById(S().ov.open), m = r.missions.find((x) => x.id === el.dataset.id);
    m.state = "open"; m.note = "You said no discount. It carries on toward a new deadline and still waits for you if they push back.";
    S().ov.mission = m.id; TP.render();
  };
  TP.act["ov-signin"] = (el) => {
    const o = S().ov;
    o.open = el.dataset.id; o.signin = "waiting";
    TP.render();
    TP.later(() => {
      const r = rowById(el.dataset.id);
      r.channels.forEach((c) => { c.status = "connected"; c.health = "active"; c.last_at = D.now; });
      r.state = "live"; delete r.paused_because;
      o.signin = "done";
      TP.render();
    }, 2200);
  };
  TP.act["ov-signin-cancel"] = () => { TP.clearTimers(); S().ov.signin = "idle"; TP.render(); };
  TP.act["ov-retry"] = () => { TP.S.ov = TP.ovInit("loading"); TP.render(); };
  TP.act["new-twin"] = () => {
    TP.clearTimers();
    // go back to where setup stopped; a fresh setup starts at "describe"
    TP.goPage("setup");
  };
})();
