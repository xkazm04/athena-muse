// Rehearsal - the twins page: a stat strip, then a ledger of twins. Each open mission reads as a
// script in progress (which beat it is on, what it waits for); a row opens in place.
(function () {
  const { D, R, esc, icon, rel, num, usd } = window.U;
  const KIND = { gmail: "Gmail", notion: "Notion" };
  const LEVEL = { review: "Review", assist: "Assist", auto: "Auto" };

  function fresh() {
    return { mode: "today", open: null, draft: null, mission: null, signin: "idle", done: {}, editing: null, answering: null };
  }

  // Rows with what the person did here (signed drafts, signed in again) applied.
  function rowsOf(ov) {
    const src = ov.mode === "after" ? D.overview_after_golive : D.overview;
    return src.rows.map((r) => {
      const row = { ...r, waiting: r.waiting.filter((w) => !ov.done[w.id]), missions: r.missions.map((x) => (ov.done[x.id] ? { ...x, state: "resolved", note: "You answered it yourself." } : x)) };
      if (r.id === "tw_family" && ov.signin === "done") {
        row.state = "live";
        row.paused_because = null;
        row.channels = r.channels.map((c) => ({ ...c, status: "connected", health: "active" }));
      }
      return row;
    });
  }
  function statsOf(rows) {
    const sum = (f) => {
      const v = rows.map(f).filter((x) => x !== null && x !== undefined);
      return v.length ? Math.round(v.reduce((a, b) => a + b, 0) * 100) / 100 : null;
    };
    return {
      live: rows.filter((r) => r.state === "live").length,
      waiting_for_you: sum((r) => r.waiting.length + r.missions.filter((m) => m.state === "handed_back").length),
      missions_open: sum((r) => r.missions.filter((m) => m.state === "open" || m.state === "handed_back").length),
      sent_week: sum((r) => r.week.sent),
      sent_alone_week: sum((r) => r.week.sent_alone),
      held_by_risk_week: sum((r) => r.week.held_by_risk),
      cost_usd_week: sum((r) => r.week.cost_usd),
      drafts: sum((r) => r.waiting.length),
      handed: sum((r) => r.missions.filter((m) => m.state === "handed_back").length),
    };
  }

  // ---------- stat strip ----------
  function tile(label, figure, unit, drawn = "", tone = "", delta = "") {
    return `<div class="tile ${tone}"><span class="t-label">${label}</span><span class="t-fig"><b>${figure}</b>${delta}</span><span class="t-unit">${unit}</span>${drawn}</div>`;
  }
  function stripHTML(rows, st, before) {
    const d = (k) => (before && before[k] !== st[k] && st[k] !== null ? `<span class="delta arrive">${st[k] > before[k] ? "+" : ""}${k === "cost_usd_week" ? usd(st[k] - before[k]) : st[k] - before[k]}</span>` : "");
    const dots = `<span class="drawn twins">${rows.map((r) => `<i class="${r.state === "live" ? "on" : ""}"></i>`).join("")}</span>`;
    const wait = `<span class="drawn sq">${Array.from({ length: st.waiting_for_you || 0 }, () => "<i></i>").join("")}</span>`;
    const split = st.sent_week ? `<span class="drawn split" title="${st.sent_alone_week} of ${st.sent_week} on its own"><i style="width:${(100 * st.sent_alone_week) / st.sent_week}%"></i></span>` : `<span class="drawn split none"></span>`;
    return `<section class="strip" aria-label="This week">
      ${tile("Live twins", num(st.live), `of ${rows.length} twins`, dots, "", d("live"))}
      ${tile("Waiting for you", num(st.waiting_for_you), `${st.drafts} ${st.drafts === 1 ? "draft" : "drafts"}, ${st.handed} handed back`, wait, st.waiting_for_you ? "human" : "")}
      ${tile("Missions open", num(st.missions_open), "conversations in progress")}
      ${tile("Sent this week", num(st.sent_week), `${num(st.sent_alone_week)} on its own`, split)}
      ${tile("Held by its risk list", num(st.held_by_risk_week), "this week")}
      ${tile("Cost this week", usd(st.cost_usd_week), "est.", "", "", d("cost_usd_week"))}
    </section>`;
  }
  function stripLoading() {
    return `<section class="strip loading" aria-label="Loading">${["Live twins", "Waiting for you", "Missions open", "Sent this week", "Held by its risk list", "Cost this week"].map((l) => `<div class="tile"><span class="t-label">${l}</span><span class="ghost fig"></span><span class="ghost"></span></div>`).join("")}</section>`;
  }

  // ---------- a mission as a script in progress ----------
  function stripOf(ms) {
    const sc = R.missionScripts[ms.id];
    if (!sc) return "";
    return `<span class="beatstrip" aria-hidden="true">${sc.beats
      .map((b, i) => {
        const n = i + 1;
        let c = n < sc.at ? "done" : n === sc.at ? (ms.state === "handed_back" ? "stuck" : "cur") : "next";
        if (ms.state === "resolved") c = "done";
        return `<i class="${c}" title="${esc(b)}"></i>`;
      })
      .join("")}</span>`;
  }
  function whereOn(ms) {
    const sc = R.missionScripts[ms.id];
    if (ms.state === "resolved") return `resolved in ${ms.turns} turns`;
    if (!sc) return ms.note;
    const beat = sc.beats[sc.at - 1];
    if (ms.state === "handed_back") return `stopped at beat ${sc.at} of ${sc.beats.length}, "${beat}": handed back to you`;
    return `beat ${sc.at} of ${sc.beats.length}, "${beat}": waits for ${sc.waiting}`;
  }

  function chanChip(c) {
    if (c.status === "needs_sign_in") return `<span class="chan-chip warn">${icon(c.kind === "gmail" ? "mail" : "notion")}Sign in again</span>`;
    let lvl = LEVEL[c.autonomy];
    if (c.split) lvl = `${LEVEL[c.split.first_message]} first, ${LEVEL[c.split.replies]} ${c.bar}`;
    else if (c.autonomy === "auto" && c.bar) lvl += " " + c.bar;
    return `<span class="chan-chip" title="${esc(KIND[c.kind] + ": " + c.account + (c.scope ? ", " + c.scope : ""))}">${icon(c.kind === "gmail" ? "mail" : "notion")}${esc(lvl)}</span>`;
  }
  const STATE = { live: ["success", "Live"], paused: ["warning", "Paused"], setting_up: ["info", "Setting up"] };

  function scriptsCell(r) {
    const open = r.missions.filter((m) => m.state !== "resolved");
    if (r.state === "setting_up") return `<span class="sc-line"><span class="beatstrip ghost">${"<i></i>".repeat(6)}</span><span class="faint">First mission still being written</span></span>`;
    if (!open.length) {
      const res = r.missions.filter((m) => m.state === "resolved").length;
      return `<span class="faint">No open missions${res ? `, ${res} resolved` : ""}</span>`;
    }
    return open
      .slice(0, 2)
      .map((m) => {
        const sc = R.missionScripts[m.id];
        const tail = m.state === "handed_back" ? `<span class="hb">handed back</span>` : `<span class="wt">beat ${sc.at} of ${sc.beats.length}</span>`;
        return `<span class="sc-line">${stripOf(m)}<b>${esc(m.with)}</b>${tail}</span>`;
      })
      .join("");
  }

  function rowHTML(r, ov, isNewLive) {
    const waits = r.waiting.length + r.missions.filter((m) => m.state === "handed_back").length;
    const [tone, label] = STATE[r.state];
    const open = ov.open === r.id;
    return `<div class="lg-row ${open ? "open" : ""} ${isNewLive ? "fresh" : ""}" role="row" data-act="ov-row" data-id="${r.id}" tabindex="0" aria-expanded="${open}">
      <span class="c-twin" role="cell"><b>${esc(r.name)}</b><span class="faint">${esc(r.purpose)}</span></span>
      <span role="cell"><span class="badge" data-tone="${tone}">${label}</span></span>
      <span class="c-chan" role="cell">${r.channels.length ? r.channels.map(chanChip).join("") : `<span class="faint">None yet</span>`}</span>
      <span class="c-scripts" role="cell">${scriptsCell(r)}</span>
      <span class="num" role="cell">${waits ? `<span class="badge solid" data-tone="human">${waits}</span>` : `<span class="faint">0</span>`}</span>
      <span class="num c-ready" role="cell"><b>${r.readiness}%</b><span class="ready-bar"><i style="width:${r.readiness}%"></i></span></span>
      <span class="num" role="cell"><b>${num(r.week.sent)}</b><span class="faint">${r.week.sent_alone === null ? "-" : r.week.sent_alone + " alone"}</span></span>
      <span class="num" role="cell">${usd(r.week.cost_usd)}</span>
      <span class="chev" role="cell">${icon(open ? "chevDown" : "chev")}</span>
    </div>`;
  }

  // ---------- the opened row ----------
  function draftHTML(w, r, ov) {
    const ch = r.channels.find((c) => c.kind === w.channel) || {};
    const bar = ch.bar ?? 80;
    const under = w.confidence < bar;
    const open = ov.draft === w.id;
    const why = w.why === "held" ? `${w.risks.length} on its risk list` : `under the bar of ${bar}`;
    const head = `<button type="button" class="d-head" data-act="ov-draft" data-id="${w.id}" aria-expanded="${open}">${icon("mail")}<span class="d-sub"><b>${esc(w.subject)}</b><span class="faint">to ${esc(w.to)}</span></span><span class="badge" data-tone="warning">${w.why === "held" ? icon("warn") : ""}${why}</span>${icon(open ? "chevDown" : "chev")}</button>`;
    if (!open) return `<li class="draft">${head}</li>`;
    const editing = ov.editing === w.id;
    const body = editing
      ? `<textarea class="field" id="ov-edit" data-keep="ov-edit" rows="3">${esc(w.excerpt)}</textarea>`
      : `<p class="d-text pencil">${esc(w.excerpt)}</p>`;
    return `<li class="draft open">${head}<div class="d-body arrive">${body}
      <div class="sure ${under ? "under" : ""}"><span>How sure it was</span><span class="track"><span class="fill" style="width:${w.confidence}%"></span><span class="bar" style="left:${bar}%"></span></span><span><b>${w.confidence}</b> / bar ${bar}</span></div>
      ${w.risks.length ? `<ul class="risk-list">${w.risks.map((x) => `<li>${icon("warn")}${esc(x)}</li>`).join("")}</ul>` : `<p class="faint small">${icon("check")} Its risk list is empty; it waits only because ${w.confidence} is under your bar of ${bar}.</p>`}
      <div class="acts">${editing ? `<button type="button" class="btn btn-primary" data-act="ov-sign" data-id="${w.id}">${icon("send")}Sign and send my version</button><button type="button" class="btn btn-quiet" data-act="ov-edit" data-id="">Cancel</button>` : `<button type="button" class="btn btn-primary" data-act="ov-sign" data-id="${w.id}">${icon("send")}Sign and send</button><button type="button" class="btn" data-act="ov-edit" data-id="${w.id}">${icon("pencil")}Edit</button><button type="button" class="btn btn-quiet" data-act="ov-decline" data-id="${w.id}">Decline</button>`}</div></div></li>`;
  }

  function missionHTML(m, ov, few) {
    const open = ov.mission === m.id;
    const tone = m.state === "handed_back" ? "warning" : m.state === "open" ? "human" : "success";
    const lbl = m.state === "handed_back" ? "Handed back" : m.state === "open" ? "Open" : "Resolved";
    const sc = R.missionScripts[m.id];
    const beats = sc
      ? `<ol class="beat-names">${sc.beats.map((b, i) => `<li class="${m.state === "resolved" || i + 1 < sc.at ? "done" : i + 1 === sc.at ? (m.state === "handed_back" ? "stuck" : "cur") : "next"}">${esc(b)}</li>`).join("")}</ol>`
      : "";
    const extra = open && m.state === "handed_back"
      ? `<div class="hb-box arrive"><p>${icon("hand")}<span>${esc(m.note)}</span></p>${
          ov.answering === m.id
            ? `<textarea class="field" id="ov-answer" data-keep="ov-answer" rows="2" placeholder="Your reply to ${esc(m.with)}, in your words"></textarea><div class="acts"><button type="button" class="btn btn-primary" data-act="ov-answer-send" data-id="${m.id}">${icon("send")}Send my reply</button><button type="button" class="btn btn-quiet" data-act="ov-answer" data-id="">Cancel</button></div>`
            : `<div class="acts"><button type="button" class="btn btn-primary" data-act="ov-answer" data-id="${m.id}">${icon("pen")}Answer it yourself</button><span class="faint small">Later: a standing rule for discounts.</span></div>`
        }</div>`
      : "";
    return `<li class="ms-item st-${m.state} ${open ? "expanded" : ""} ${few ? "few" : ""}"><button type="button" class="m-head" data-act="ov-mission" data-id="${m.id}">
        <span class="m-top"><b>${esc(m.title)}</b><span class="badge" data-tone="${tone}">${lbl}</span><span class="faint">${m.state === "resolved" ? m.turns + " turns, " : ""}${rel(m.last_at)}</span></span>
        ${beats}<span class="m-where">${esc(whereOn(m))}</span></button>${extra}</li>`;
  }

  function detailHTML(r, ov) {
    const order = { handed_back: 0, open: 1, resolved: 2 };
    const ms = [...r.missions].sort((a, b) => order[a.state] - order[b.state]);
    const paused =
      r.paused_because || (r.id === "tw_family" && ov.signin !== "idle")
        ? `<div class="signin ${ov.signin === "done" ? "ok" : ""}">${
            ov.signin === "done"
              ? `${icon("check")}<span>Signed in again as ${esc(r.channels[0].account)}. ${esc(r.name)} is back on Review.</span>`
              : ov.signin === "waiting"
              ? `<span class="spin-ring" aria-hidden="true"></span><span>${esc(D.setup.connect.gmail.states.waiting)}</span>`
              : `${icon("warn")}<span><b>Paused.</b> ${esc(r.paused_because)} Nothing has been sent since.</span><button type="button" class="btn btn-primary" data-act="ov-signin">${icon("mail")}Sign in with Google</button>`
          }</div>`
        : "";
    let left;
    if (r.state === "setting_up")
      left = `<div class="setting"><p>Athena is still writing its first mission as a script with you. It is ${r.readiness}% ready.</p><button type="button" class="btn btn-primary" data-act="ov-continue">${icon("play")}Continue with Athena</button></div>`;
    else left = `<ul class="missions">${ms.map((m) => missionHTML(m, ov, ms.length === 1)).join("")}</ul>`;
    const right = r.waiting.length
      ? `<ul class="drafts">${r.waiting.map((w) => draftHTML(w, r, ov)).join("")}</ul>`
      : `<p class="faint nothing">${icon("check")} Nothing waits for your signature.</p>`;
    return `<div class="lg-detail" role="row"><div class="det-grid">
      ${paused}
      <section><h3 class="eyebrow">Its missions, as scripts</h3>${left}</section>
      <section><h3 class="eyebrow">Waiting for your signature</h3>${right}</section>
    </div></div>`;
  }

  function ledgerHTML(rows, ov, st) {
    const head = `<div class="lg-head" role="row"><span>Twin</span><span>State</span><span>Where it speaks</span><span>Scripts in progress</span><span class="num">Waits on you</span><span class="num">Ready</span><span class="num">Sent, week</span><span class="num">Cost, est.</span><span></span></div>`;
    const body = rows.map((r) => rowHTML(r, ov, ov.mode === "after" && r.id === "tw_partners") + (ov.open === r.id ? detailHTML(r, ov) : "")).join("");
    const totals = `<div class="lg-totals" role="row"><span>${rows.length} twins, ${st.live} live</span><span>${num(st.missions_open)} missions open</span><span class="human">${num(st.waiting_for_you)} waiting for you</span><span>${num(st.sent_week)} sent this week, ${num(st.sent_alone_week)} on its own</span><span>est. ${usd(st.cost_usd_week)}</span></div>`;
    return `<section class="ledger" role="table" aria-label="Your twins">${head}<div class="lg-body">${body}</div>${totals}</section>`;
  }
  function ledgerLoading() {
    return `<section class="ledger loading" aria-label="Loading"><div class="lg-head"><span>Twin</span><span>State</span><span>Where it speaks</span><span>Scripts in progress</span><span class="num">Waits on you</span><span class="num">Ready</span><span class="num">Sent, week</span><span class="num">Cost, est.</span><span></span></div>${[0, 1, 2]
      .map(() => `<div class="lg-row skel"><span class="ghost"></span><span class="ghost"></span><span class="ghost"></span><span class="ghost"></span><span></span><span></span><span></span><span></span><span></span></div>`)
      .join("")}<p class="loading-line faint"><span class="dots">Loading your twins</span></p></section>`;
  }

  // ---------- what waits for you, across twins (shown while no row is open) ----------
  function queueHTML(rows) {
    const items = [];
    for (const r of rows) {
      for (const m of r.missions.filter((x) => x.state === "handed_back")) items.push({ r, m });
      for (const w of r.waiting) items.push({ r, w });
    }
    if (!items.length) return `<section class="queue-wrap"><h3 class="eyebrow">Waiting for you</h3><p class="faint nothing">${icon("check")} Nothing waits for you.</p></section>`;
    const cards = items
      .map(({ r, m, w }) => {
        if (m) {
          const sc = R.missionScripts[m.id];
          return `<button type="button" class="q-card stuck" data-act="ov-jump" data-row="${r.id}" data-mission="${m.id}">
            <span class="q-top"><span class="badge" data-tone="warning">${icon("hand")}Handed back</span><span class="faint">${esc(r.name)}, ${rel(m.last_at)}</span></span>
            <b>${esc(m.title)}</b>${stripOf(m)}<span class="q-why">${esc(m.note)}</span></button>`;
        }
        const ch = r.channels.find((c) => c.kind === w.channel) || {};
        const bar = ch.bar ?? 80;
        const ms = w.mission ? r.missions.find((x) => x.id === w.mission) : null;
        return `<button type="button" class="q-card" data-act="ov-jump" data-row="${r.id}" data-draft="${w.id}">
          <span class="q-top"><span class="badge" data-tone="${w.why === "held" ? "warning" : "human"}">${w.why === "held" ? icon("warn") + "Held by its risk list" : icon("pen") + "Under the bar"}</span><span class="faint">${esc(r.name)}</span></span>
          <b>${esc(w.subject)}</b>
          <div class="sure ${w.confidence < bar ? "under" : ""}"><span>How sure</span><span class="track"><span class="fill" style="width:${w.confidence}%"></span><span class="bar" style="left:${bar}%"></span></span><span><b>${w.confidence}</b> / ${bar}</span></div>
          <span class="q-why">${w.risks.length ? esc(w.risks[0]) + "." : "Nothing on its risk list; it was not sure enough to send alone."}${ms ? ` Beat ${R.missionScripts[ms.id].at} of "${esc(ms.title)}".` : ""}</span></button>`;
      })
      .join("");
    return `<section class="queue-wrap"><div class="q-head"><h3 class="eyebrow">Waiting for you</h3><span class="faint">Open one to sign it, put it in your words, or take the conversation over.</span></div><div class="queue">${cards}</div></section>`;
  }

  function render(S) {
    const ov = S.ov;
    const title = `<div class="ov-title"><div><h1>Twins</h1><p class="faint">Each twin speaks for you in one place, one mission at a time.</p></div><button type="button" class="btn btn-primary" data-act="ov-new">${icon("plus")}Set up a twin</button></div>`;
    if (ov.mode === "loading") return `<div class="overview">${title}${stripLoading()}${ledgerLoading()}</div>`;
    if (ov.mode === "error")
      return `<div class="overview">${title}<section class="problem plane">${icon("warn")}<div><b>Your twins could not be loaded.</b><p class="faint">The app could not read its list of twins just now. Nothing is lost, and nothing was sent while this page was down.</p></div><button type="button" class="btn" data-act="ov-retry">${icon("retry")}Try again</button></section></div>`;
    if (ov.mode === "first")
      return `<div class="overview">${title}<section class="first coat"><div class="first-copy"><span class="eyebrow">No twins yet</span><h2>A twin answers for you, one conversation at a time</h2><p>Tell Athena what it's for. She writes its first conversation as a script with you, it rehearses on a Notion practice page, and only then does it go live.</p>
        <button type="button" class="btn btn-primary" data-act="ov-new">${icon("play")}Set up a first twin with Athena</button></div>
        <ol class="first-script">${["Its first message", "They reply", "Its answer", "They say yes", "Its thanks", "File the outcome"].map((b, i) => `<li class="${i % 2 ? "them" : ""}"><span class="beat-no">${i + 1}</span><span>${b}</span><span class="ghost"></span></li>`).join("")}</ol></section></div>`;
    const rows = rowsOf(ov);
    const st = statsOf(rows);
    const before = ov.mode === "after" ? D.overview.stats : null;
    const q = !ov.open ? queueHTML(rows) : ov.mode === "after" ? queueHTML(rows).replace('class="queue-wrap"', 'class="queue-wrap roomy"') : "";
    return `<div class="overview">${title}${stripHTML(rows, st, before)}${ledgerHTML(rows, ov, st)}${q}</div>`;
  }

  // ---------- actions ----------
  const ov = () => App.S.ov;
  const findDraft = (id) => {
    for (const r of rowsOf(ov())) for (const w of r.waiting) if (w.id === id) return w;
    return null;
  };
  App.on({
    "ov-row": (el) => {
      const o = ov();
      o.open = o.open === el.dataset.id ? null : el.dataset.id;
      o.draft = o.mission = o.editing = o.answering = null;
      App.render();
    },
    "ov-jump": (el) => {
      const o = ov();
      o.open = el.dataset.row;
      o.draft = el.dataset.draft || null;
      o.mission = el.dataset.mission || null;
      o.editing = o.answering = null;
      App.render();
    },
    "ov-draft": (el) => {
      const o = ov();
      o.draft = o.draft === el.dataset.id ? null : el.dataset.id;
      o.editing = null;
      if (o.draft) o.mission = null;
      App.render();
    },
    "ov-mission": (el) => {
      const o = ov();
      o.mission = o.mission === el.dataset.id ? null : el.dataset.id;
      if (o.mission) o.draft = null;
      App.render();
    },
    "ov-edit": (el) => {
      ov().editing = el.dataset.id || null;
      App.render();
    },
    "ov-sign": (el) => {
      const o = ov(), w = findDraft(el.dataset.id);
      o.done[el.dataset.id] = "sent";
      o.draft = o.editing = null;
      App.render();
      App.toast(`Signed and sent to ${w ? w.to : "them"}.`);
    },
    "ov-decline": (el) => {
      const o = ov();
      o.done[el.dataset.id] = "declined";
      o.draft = null;
      App.render();
      App.toast("Declined. Nothing was sent.");
    },
    "ov-answer": (el) => {
      ov().answering = el.dataset.id || null;
      App.render();
      const ta = document.getElementById("ov-answer");
      if (ta) ta.focus();
    },
    "ov-answer-send": (el) => {
      const o = ov();
      o.done[el.dataset.id] = "answered";
      o.answering = o.mission = null;
      App.render();
      App.toast("Sent in your words. The mission is yours now.");
    },
    "ov-signin": () => {
      const o = ov();
      o.signin = "waiting";
      App.render();
      App.later(() => {
        o.signin = "done";
        App.render();
      }, 1800);
    },
    "ov-retry": () => {
      ov().mode = "loading";
      App.render();
      App.later(() => {
        ov().mode = "today";
        App.render();
      }, 1200);
    },
    "ov-new": () => App.go("setup-describe"),
    "ov-continue": () => App.go("setup-f0"),
  });

  window.Overview = { fresh, render };
})();
