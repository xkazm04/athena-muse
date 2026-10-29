// The twins page: the stat strip, the wallet of closed documents, what waits for you, and the ledger.
(function () {
  const { D, V, esc, icons, portrait, stamp, sure, rel, day, money, num, clearance, clearanceShort } = TP;
  const KIND = D.channelKinds;

  // ---------- data with the person's actions applied ----------
  function rowsNow() {
    const ov = TP.S.ov;
    const base = ov.mode === "after" ? D.overview_after_golive.rows : D.overview.rows;
    return base.map((r0) => {
      const r = JSON.parse(JSON.stringify(r0));
      r.waiting = r.waiting.filter((w) => !ov.done[w.id]);
      r.missions = r.missions.map((ms) => (ov.done[ms.id] === "taken" ? { ...ms, state: "taken" } : ms));
      if (ov.live[r.id]) {
        r.state = "live";
        r.channels = r.channels.map((c) => ({ ...c, status: "connected", health: "active", last_at: D.now }));
        r.paused_because = null;
      }
      r.waiting_count = r.waiting.length;
      r.open_missions = r.missions.filter((m) => m.state === "open" || m.state === "handed_back").length;
      return r;
    });
  }
  const sumOf = (rows, f) => {
    const v = rows.map(f).filter((x) => x !== null && x !== undefined);
    return v.length ? Math.round(v.reduce((a, b) => a + b, 0) * 100) / 100 : null;
  };
  function statsOf(rows) {
    return {
      live: rows.filter((t) => t.state === "live").length,
      waiting_for_you: sumOf(rows, (t) => t.waiting.length + t.missions.filter((m) => m.state === "handed_back").length),
      missions_open: sumOf(rows, (t) => t.open_missions),
      sent_week: sumOf(rows, (t) => t.week.sent),
      sent_alone_week: sumOf(rows, (t) => t.week.sent_alone),
      held_by_risk_week: sumOf(rows, (t) => t.week.held_by_risk),
      cost_usd_week: sumOf(rows, (t) => t.week.cost_usd),
    };
  }

  const STATE = {
    live: ["Live", "success"],
    paused: ["Paused", "warning"],
    setting_up: ["Being issued", "info"],
  };
  const badge = (state) => `<span class="badge" data-tone="${STATE[state][1]}">${STATE[state][0]}</span>`;
  const MS = { open: ["Open", "info"], resolved: ["Resolved", "success"], handed_back: ["Handed back to you", "human"], taken: ["With you now", ""] };

  function visaMark(c) {
    const ok = c.status === "connected";
    return `<span class="vmark" data-ok="${ok}" title="${esc(KIND[c.kind].label)}: ${ok ? esc(c.account) : "sign in again"}">${icons[c.kind]}${KIND[c.kind].label}${ok ? "" : `<em>sign in again</em>`}</span>`;
  }
  const clrLine = (r, full = false) => (r.channels.length ? r.channels.map((c) => `<span><b>${KIND[c.kind].label}</b> ${esc(full ? clearance(c) : clearanceShort(c))}</span>`).join("") : `<span class="muted">No channels yet</span>`);
  const lastOf = (r) => {
    const all = [...r.channels.map((c) => c.last_at), ...r.missions.map((m) => m.last_at)].filter(Boolean).sort();
    return all.length ? all[all.length - 1] : null;
  };
  const initial = (r) => r.name[0];

  // ---------- stat strip ----------
  function tile(label, value, unit, { tone = "", draw = "" } = {}) {
    return `<div class="tile" ${tone ? `data-tone="${tone}"` : ""}><span class="tile__l">${label}</span><span class="tile__v"><b>${value}</b><span class="tile__u">${unit}</span></span>${draw}</div>`;
  }
  function stats(st, rows, mode) {
    if (mode === "loading") return `<div class="stats" aria-busy="true">${Array.from({ length: 6 }, () => `<div class="tile tile--wait"><span class="sk sk--l"></span><span class="sk sk--v"></span></div>`).join("")}</div>`;
    const dash = mode === "first" || mode === "error";
    const v = (x) => (dash ? "-" : num(x));
    const sentDraw =
      !dash && st.sent_week
        ? `<span class="split" role="img" aria-label="${st.sent_alone_week} of ${st.sent_week} went on their own"><i style="flex:${st.sent_alone_week}"></i><i style="flex:${st.sent_week - st.sent_alone_week}"></i></span>`
        : "";
    const liveDraw = !dash && rows.length ? `<span class="dots-row" aria-hidden="true">${rows.map((r) => `<i data-on="${r.state === "live"}"></i>`).join("")}</span>` : "";
    const prev = D.overview.stats;
    const moved = mode === "after" ? (k) => (st[k] !== prev[k] ? `<span class="moved">was ${k === "cost_usd_week" ? money(prev[k]) : num(prev[k])}</span>` : "") : () => "";
    return `<div class="stats">
      ${tile("Live", v(st.live), dash ? "" : `of ${rows.length} twins${moved("live")}`, { draw: liveDraw, tone: mode === "after" ? "moved" : "" })}
      ${tile("Waiting for you", v(st.waiting_for_you), dash ? "" : "drafts and hand-backs", { tone: !dash && st.waiting_for_you ? "human" : "" })}
      ${tile("Missions open", v(st.missions_open), dash ? "" : "conversations")}
      ${tile("Sent this week", v(st.sent_week), dash ? "" : `${num(st.sent_alone_week)} on their own`, { draw: sentDraw })}
      ${tile("Held back", v(st.held_by_risk_week), dash ? "" : "by its risk list")}
      ${tile("Cost this week", dash ? "-" : money(st.cost_usd_week), dash ? "" : `est.${moved("cost_usd_week")}`)}
    </div>`;
  }

  // ---------- the wallet ----------
  function booklet(r) {
    const ov = TP.S.ov;
    const isNew = ov.mode === "after" && r.id === "tw_partners";
    const wait = r.waiting.length + r.missions.filter((m) => m.state === "handed_back").length;
    let foot = "";
    if (r.state === "paused") foot = `<button class="btn booklet__act" data-act="open" data-id="${r.id}" data-focus="signin">${icons.gmail}Sign in with Google</button>`;
    else if (r.state === "setting_up") foot = `<button class="btn booklet__act" data-act="new-twin">Continue with Athena${icons.arrow}</button>`;
    else if (wait) foot = `<span class="badge" data-tone="human">${wait} wait${wait === 1 ? "s" : ""} for you</span>`;
    else foot = `<span class="booklet__quiet">Nothing waits for you</span>`;
    return `<article class="booklet" data-state="${r.state}" ${ov.open === r.id ? 'data-open="true"' : ""}>
      <button class="booklet__open" data-act="open" data-id="${r.id}" aria-label="Open ${esc(r.name)}"></button>
      <span class="booklet__top"><span class="booklet__kind">Twin document</span>${badge(r.state)}</span>
      <span class="booklet__pic">${r.state === "setting_up" ? portrait(initial(r), { size: 64, pencil: true }) : portrait(initial(r), { size: 64 })}${isNew ? stamp("Issued today", "success", { fresh: true, cls: "booklet__issued" }) : ""}</span>
      <span class="booklet__name">${esc(r.name)}</span>
      <span class="booklet__purpose">${esc(r.purpose)}</span>
      <span class="booklet__visas">${r.channels.length ? r.channels.map(visaMark).join("") : `<span class="vmark vmark--none">No visas yet</span>`}</span>
      <span class="booklet__clr">${clrLine(r)}</span>
      <span class="booklet__ready"><span class="meter" aria-hidden="true"><i style="width:${r.readiness}%"></i></span>Readiness ${r.readiness}%</span>
      <span class="booklet__foot">${r.state === "paused" ? `<span class="booklet__why">${esc(r.paused_because)}</span>` : ""}${foot}</span>
    </article>`;
  }

  // ---------- an opened document ----------
  function mission(ms, r) {
    const ov = TP.S.ov;
    const focus = ov.focus === ms.id;
    const [label, tone] = MS[ms.state];
    const acts =
      ms.state === "handed_back"
        ? `<div class="ms__act"><button class="btn btn-primary" data-act="take-over" data-id="${ms.id}">${icons.hand}Take it over</button><span class="ms__later">How much it may ever give is a standing rule, a later step.</span></div>`
        : "";
    return `<li class="ms" data-state="${ms.state}" ${focus ? 'data-focus="true"' : ""}>
      <div class="ms__h"><b>${esc(ms.title)}</b><span class="badge" ${tone ? `data-tone="${tone}"` : ""}>${label}</span></div>
      <div class="ms__m">${esc(ms.with)} · ${KIND[ms.channel].label} · ${ms.turns} turns · ${rel(ms.last_at)}</div>
      ${ms.state === "handed_back" ? `<p class="ms__note ms__note--stop">${icons.hand}<span><b>It stopped:</b> ${esc(ms.note)}</span></p>${focus ? acts : ""}` : `<p class="ms__note">${esc(ms.note)}</p>`}
    </li>`;
  }
  function draft(w, r) {
    const ov = TP.S.ov;
    const focus = ov.focus === w.id;
    const ch = r.channels.find((c) => c.kind === w.channel);
    const bar = ch ? ch.bar : null;
    const ms = r.missions.find((m) => m.id === w.mission);
    const st = w.why === "held" ? stamp("Held", "warning", { sub: "risk list" }) : stamp("Not sure enough", "human", { sub: `${w.confidence} of ${bar}` });
    if (!focus)
      return `<li class="dr" data-why="${w.why}"><button class="dr__btn" data-act="focus" data-id="${w.id}"><span class="dr__h"><b>${esc(w.subject)}</b>${st}</span><span class="dr__to">to ${esc(w.to)}${ms ? ` · ${esc(ms.with)}` : ""}</span><span class="dr__x">${esc(w.excerpt)}</span></button></li>`;
    const why =
      w.why === "held"
        ? `It was sure enough (${w.confidence}, your bar ${bar}), but its risk list is not empty, so it waits for your signature.`
        : `Its risk list is empty, but ${w.confidence} is below your bar of ${bar}, so it waits for your signature.`;
    const body =
      ov.editing === w.id
        ? `<label class="sr" for="draft-edit">Your version</label><textarea id="draft-edit" class="field editbox" rows="3">${esc(w.excerpt)}</textarea>
           <div class="dr__act"><button class="btn btn-primary" data-act="save-draft" data-id="${w.id}">${icons.send}Sign and send yours</button><button class="btn btn-quiet" data-act="focus" data-id="${w.id}">Cancel</button></div>`
        : `<p class="dr__full">${esc(w.excerpt)}</p>
           <div class="dr__grid">${sure(w.confidence, bar)}
           ${w.risks.length ? `<ul class="risks" aria-label="Its risk list">${w.risks.map((x) => `<li>${icons.risk}${esc(x)}</li>`).join("")}</ul>` : `<p class="risks risks--none">${icons.check}Its risk list is empty.</p>`}</div>
           <p class="dr__why">${esc(why)}</p>
           <div class="dr__act"><button class="btn btn-primary" data-act="sign" data-id="${w.id}">${icons.send}Sign and send</button><button class="btn" data-act="edit-draft" data-id="${w.id}">${icons.pencil}Edit</button><button class="btn btn-quiet" data-act="decline" data-id="${w.id}">Decline</button></div>`;
    return `<li class="dr is-open" data-why="${w.why}"><div class="dr__h"><b>${esc(w.subject)}</b>${st}<button class="btn btn-quiet dr__x-btn" data-act="focus" data-id="${w.id}" aria-label="Fold the draft">${icons.close}</button></div><span class="dr__to">to ${esc(w.to)}${ms ? ` · ${esc(ms.with)} mission` : " · no mission"}</span>${body}</li>`;
  }
  function pausedCard(r) {
    const ov = TP.S.ov;
    const s = ov.signin;
    let act = `<button class="btn btn-primary btn-big" data-act="ov-signin">${icons.gmail}Sign in with Google</button><span class="muted">One press. It asks for the same things as before: read and send mail.</span>`;
    if (s === "waiting") act = `<div class="cstate" data-state="waiting"><span class="spin" aria-hidden="true"></span><div><b>${esc(D.setup.connect.gmail.states.waiting)}</b><span>Waiting <span data-clock="signin">${TP.clockText("signin")}</span></span></div></div>`;
    if (s === "done") act = `<div class="cstate" data-state="connected">${stamp("Stamped", "success", { fresh: true })}<div><b>Signed in again as ${esc(r.channels[0].account)}</b><span>${esc(r.name)} is live.</span></div></div>`;
    return `<div class="paused" data-state="${s}"><span class="paused__k">${icons.risk}${s === "done" ? "Back to work" : "Paused"}</span><p><b>${esc(r.paused_because || "Google asked you to sign in again on 26 Sep.")}</b> ${s === "done" ? "" : "It sends nothing while paused, and nothing was lost."}</p>${act}</div>`;
  }
  function spread(r) {
    const missions = r.missions.length ? `<ul class="mss">${r.missions.map((m) => mission(m, r)).join("")}</ul>` : `<p class="empty">No missions yet.</p>`;
    const drafts = r.waiting.length ? `<ul class="drs">${r.waiting.map((w) => draft(w, r)).join("")}</ul>` : `<p class="empty">${icons.check}Nothing waits for your signature.</p>`;
    let left = `<section class="ovpage"><h3>Missions <span>${r.missions.length}</span></h3>${missions}</section>`;
    let right = `<section class="ovpage"><h3>Waiting for your signature <span>${r.waiting.length}</span></h3>${drafts}</section>`;
    if (r.state === "paused" || TP.S.ov.signin === "done" && r.id === "tw_family") {
      left = `<section class="ovpage">${pausedCard(r)}</section>`;
      right = `<section class="ovpage"><h3>Missions <span>${r.missions.length}</span></h3>${missions}</section>`;
    }
    if (r.state === "setting_up") {
      left = `<section class="ovpage"><div class="paused" data-tone="info"><span class="paused__k">${icons.pencil}Being issued</span><p><b>Readiness ${r.readiness}%.</b> Only its name is pencilled in. Athena picks up where you left off.</p><button class="btn btn-primary btn-big" data-act="new-twin">Continue with Athena${icons.arrow}</button></div></section>`;
    }
    const isNew = TP.S.ov.mode === "after" && r.id === "tw_partners";
    return `<article class="ovspread" data-id="${r.id}">
      <header class="ovspread__h">${portrait(initial(r), { size: 40, pencil: r.state === "setting_up" })}<div class="ovspread__t"><b>${esc(r.name)}</b><span>${esc(r.purpose)}</span></div>
        ${badge(r.state)}${isNew ? stamp("Issued today", "success", { fresh: true }) : ""}
        <span class="ovspread__clr">${clrLine(r, true)}</span>
        <button class="btn btn-quiet" data-act="close" aria-label="Close the document">${icons.close}Close</button></header>
      <div class="ovspread__pages">${left}${right}</div>
    </article>`;
  }

  // ---------- waiting for you ----------
  function queue(rows) {
    const ov = TP.S.ov;
    const items = [];
    const also = [];
    for (const r of rows) {
      for (const w of r.waiting) {
        const ch = r.channels.find((c) => c.kind === w.channel);
        items.push(`<button class="q" data-act="open" data-id="${r.id}" data-focus="${w.id}" aria-pressed="${ov.focus === w.id}"><span class="q__k">${icons.mail}${esc(r.name)}</span><b>${esc(w.subject)}</b><span class="q__s">${w.why === "held" ? `Held: ${w.risks.length} on its risk list` : `Not sure enough: ${w.confidence} of ${ch ? ch.bar : "-"}`}</span></button>`);
      }
      for (const m of r.missions.filter((x) => x.state === "handed_back"))
        items.push(`<button class="q q--hand" data-act="open" data-id="${r.id}" data-focus="${m.id}" aria-pressed="${ov.focus === m.id}"><span class="q__k">${icons.hand}${esc(r.name)}</span><b>${esc(m.with)}: handed back to you</b><span class="q__s">${esc(m.note.split(".")[0])}.</span></button>`);
      if (r.state === "paused") also.push(`<button class="q q--also" data-act="open" data-id="${r.id}" data-focus="signin" aria-pressed="${ov.focus === "signin"}"><span class="q__k">${icons.risk}${esc(r.name)}: paused</span><b>Sign in with Google again</b></button>`);
    }
    return `<aside class="queue" aria-label="Waiting for you"><h2>Waiting for you <span class="count">${items.length}</span></h2>
      ${items.length ? `<div class="q__list">${items.join("")}</div>` : `<p class="empty">${icons.check}Nothing waits for you.</p>`}
      ${also.length ? `<span class="q__also">Also</span><div class="q__list">${also.join("")}</div>` : ""}</aside>`;
  }

  // ---------- the ledger ----------
  function ledger(rows, st, mode) {
    const ov = TP.S.ov;
    const head = `<div class="lg__row lg__head" role="row"><span role="columnheader">Twin</span><span role="columnheader">State</span><span role="columnheader">Where it speaks</span><span role="columnheader">May send alone</span><span role="columnheader">Readiness</span><span role="columnheader">Waiting</span><span role="columnheader">Missions</span><span role="columnheader">This week</span><span role="columnheader">Last</span></div>`;
    if (mode === "loading") return `<div class="ledger" role="table" aria-busy="true">${head}${[1, 2, 3].map(() => `<div class="lg__row lg__sk" role="row"><span class="sk"></span><span class="sk"></span><span class="sk"></span><span class="sk"></span></div>`).join("")}</div>`;
    if (mode === "first") return `<div class="ledger" role="table">${head}<div class="lg__row lg__empty" role="row"><span>No twins yet. Your first one shows here once Athena has helped you set it up.</span></div></div>`;
    if (mode === "error") return `<div class="ledger" role="table">${head}<div class="lg__row lg__empty" role="row"><span>Not loaded. This is not an empty list.</span></div></div>`;
    const body = rows
      .map((r) => {
        const wait = r.waiting.length;
        const hb = r.missions.filter((m) => m.state === "handed_back").length;
        return `<button class="lg__row" role="row" data-act="open" data-id="${r.id}" aria-expanded="${ov.open === r.id}" ${ov.mode === "after" && r.id === "tw_partners" ? 'data-new="true"' : ""}>
        <span class="lg__twin" role="cell"><b>${esc(r.name)}</b><span>${esc(r.purpose)}</span></span>
        <span role="cell">${badge(r.state)}</span>
        <span class="lg__ch" role="cell">${r.channels.length ? r.channels.map((c) => `<span class="lg__c" data-ok="${c.status === "connected"}" title="${esc(c.account)}">${icons[c.kind]}${KIND[c.kind].label}${c.status === "connected" ? `<i data-health="${c.health}" aria-label="${c.health}"></i>` : `<em>sign in</em>`}</span>`).join("") : `<span class="muted">-</span>`}</span>
        <span class="lg__clr" role="cell">${r.channels.length ? r.channels.map((c) => `<span title="${esc(clearance(c))}">${KIND[c.kind].label}: ${esc(clearanceShort(c))}</span>`).join("") : `<span class="muted">-</span>`}</span>
        <span class="lg__ready" role="cell"><span class="meter" aria-hidden="true"><i style="width:${r.readiness}%"></i></span>${r.readiness}%</span>
        <span role="cell" class="lg__n lg__wait ${wait + hb ? "is-human" : ""}">${wait + hb ? [wait ? `<b>${wait} draft${wait === 1 ? "" : "s"}</b>` : "", hb ? `<b>${hb} handed back</b>` : ""].join("") : "0"}</span>
        <span role="cell" class="lg__n">${r.open_missions}</span>
        <span role="cell" class="lg__wk">${r.week.sent === null ? "-" : `${r.week.sent} sent<span>${r.week.sent_alone} alone</span>`}</span>
        <span role="cell" class="lg__last">${rel(lastOf(r))}</span>
      </button>`;
      })
      .join("");
    const total = `<div class="lg__row lg__total" role="row"><span role="cell"><b>${rows.length} twins</b></span><span role="cell">${st.live} live</span><span role="cell" class="lg__wide">${st.waiting_for_you} waiting for you · ${st.missions_open} missions open · ${num(st.sent_week)} sent this week, ${num(st.sent_alone_week)} on their own · ${num(st.held_by_risk_week)} held back · est. ${money(st.cost_usd_week)}</span></div>`;
    return `<div class="ledger" role="table" aria-label="Twins ledger">${head}${body}${total}</div>`;
  }

  // ---------- the page ----------
  TP.renderOverview = function (root) {
    const ov = TP.S.ov;
    const mode = ov.mode;
    const rows = mode === "first" || mode === "error" || mode === "loading" ? [] : rowsNow();
    const st = statsOf(rows);
    let shelf;
    if (mode === "loading")
      shelf = `<div class="wallet" aria-busy="true">${[1, 2, 3].map(() => `<div class="booklet booklet--sk"><span class="sk sk--pic"></span><span class="sk"></span><span class="sk sk--short"></span></div>`).join("")}</div><aside class="queue queue--sk"><span class="sk"></span><span class="sk"></span><span class="sk"></span></aside>`;
    else if (mode === "first")
      shelf = `<div class="invite"><div class="booklet booklet--blank">${portrait("", { size: 64, blank: true })}<span>Twin document</span><span class="muted">not issued</span></div>
        <div class="invite__t"><h2>No twins yet</h2><p>A twin writes as you in your Gmail and Notion. It learns your voice from mail you sent, sends on its own only when it is sure and its risk list is empty, and hands back to you what it is not sure of.</p>
        <button class="btn btn-primary btn-big" data-act="new-twin">${icons.plus}Set up a first twin with Athena</button><span class="muted">You talk; she fills in its document. Nothing is sent while you set it up.</span></div></div>`;
    else if (mode === "error")
      shelf = `<div class="problem" role="alert">${icons.risk}<div><h2>Your twins could not be loaded</h2><p>Something went wrong reaching them. This is not an empty list, and nothing was changed. Your twins keep working.</p><button class="btn btn-primary" data-act="ov-retry">${icons.retry}Try again</button></div></div>`;
    else {
      const open = rows.find((r) => r.id === ov.open);
      shelf = `${open ? spread(open) : `<div class="wallet">${rows.map(booklet).join("")}</div>`}${queue(rows)}`;
    }
    root.innerHTML = `<div class="ov" data-mode="${mode}">
      <div class="ov__top"><div class="ov__title"><h1>Twins</h1><p>They write as you where you connect them, and hand back what they are not sure of.</p></div>
        ${stats(st, rows, mode)}
        <button class="btn btn-primary ov__new" data-act="new-twin">${icons.plus}New twin</button></div>
      <div class="shelf" data-open="${!!ov.open}">${shelf}</div>${ov.flash ? `<p class="flash" role="status">${icons.check}<span>${esc(ov.flash)}</span><button class="btn btn-quiet" data-act="flash-off" aria-label="Dismiss">${icons.close}</button></p>` : ""}
      ${ledger(rows, st, mode)}
    </div>`;
  };
})();
