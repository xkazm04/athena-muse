// Rehearsal - the props: the interactive part a frame names (connect, samples, dials, pages,
// chores, autonomy, memory), shown on the stage beside the script. Her suggestion is pencil until
// you touch it; what you choose is ink.
(function () {
  const { D, R, esc, icon, clock, dateShort } = window.U;
  const S = D.setup;

  const card = (cls, eyebrow, title, body, foot = "") =>
    `<section class="prop plane ${cls}"><header class="prop-head"><span class="eyebrow">${eyebrow}</span><h2>${title}</h2></header><div class="prop-body">${body}</div>${foot ? `<footer class="prop-foot">${foot}</footer>` : ""}</section>`;

  // A choice: your value if you touched it, else her suggestion (pencil).
  const pick = (su, kind, id, suggested) => {
    const mine = su.picks[kind][id];
    return mine === undefined ? { v: suggested, by: "her" } : { v: mine, by: "you" };
  };
  const tick = (p) => `<span class="tick ${p.v ? (p.by === "you" ? "on" : "her") : ""}">${p.v ? icon("check") : ""}</span>`;

  // ---------- connect ----------
  function gmailHTML(su) {
    const c = S.connect.gmail;
    const st = su.gmail;
    let state;
    if (st === "idle") state = `<button type="button" class="btn btn-primary wide" data-act="gmail-signin">${icon("mail")}${esc(c.states.idle)}</button><p class="faint small">Google opens in your browser. Nothing is kept until you finish there.</p>`;
    if (st === "waiting")
      state = `<div class="conn-state waiting"><span class="spin-ring" aria-hidden="true"></span><div><b>${esc(c.states.waiting)}</b><span class="faint small"><span data-tick="gmail">${clock(su.gmailShown || 0)}</span> so far. It gives up after ${c.timeout_s / 60} minutes.</span></div></div>
        <button type="button" class="btn btn-quiet" data-act="gmail-cancel">Cancel</button>`;
    if (st === "connected") state = `<div class="conn-state ok arrive">${icon("check")}<b>${esc(c.states.connected)}</b></div>${su.f === 1 ? `<button type="button" class="btn btn-primary" data-act="continue">Continue${icon("arrow")}</button>` : ""}`;
    if (st === "failed") state = `<div class="conn-state bad">${icon("warn")}<b>${esc(c.states.failed)}</b></div><button type="button" class="btn" data-act="gmail-signin">${icon("retry")}Try again</button>`;
    const body = `<div class="conn">
        <div class="conn-who">${icon("mail")}<div><b>Gmail</b><span class="faint small">Sign in with Google</span></div></div>
        <div class="asks"><div><span class="eyebrow">It asks Google for</span><ul>${c.asks_for.map((a) => `<li class="yes">${icon("check")}${esc(a)}</li>`).join("")}</ul></div>
        <div><span class="eyebrow">It never asks for</span><ul>${c.never_asks_for.map((a) => `<li class="no">${icon("x")}${esc(a)}</li>`).join("")}</ul></div></div>
        <div class="conn-do">${state}</div></div>`;
    return card("p-connect", "Where it speaks", "Your mailbox", body, `<span class="faint">Plays: beat 1, its first message, and every reply after it.</span>`);
  }

  function notionHTML(su) {
    const c = S.connect.notion;
    const st = su.notion;
    const where = su.where
      ? `<ol class="where arrive">${c.where_to_find.map((w) => `<li>${esc(w)}</li>`).join("")}</ol>`
      : "";
    let state = "";
    if (st === "checking") state = `<div class="conn-state waiting"><span class="spin-ring" aria-hidden="true"></span><b>${esc(c.states.checking)}</b></div>`;
    if (st === "connected") state = `<div class="conn-state ok arrive">${icon("check")}<b>${esc(c.states.connected)}</b></div>${su.f === 4 ? `<button type="button" class="btn btn-primary" data-act="continue">Continue${icon("arrow")}</button>` : ""}`;
    if (st === "rejected") state = `<div class="conn-state bad">${icon("warn")}<b>${esc(c.states.rejected)}</b></div>`;
    const field = st === "connected" ? "" : `<label class="small faint" for="nkey">${esc(c.states.idle)}</label>
      <div class="keyrow"><input class="field" id="nkey" data-keep="nkey" type="password" autocomplete="off" placeholder="Starts with ntn_" value="${esc(su.notionKey)}" ${st === "checking" ? "disabled" : ""}/>
      <button type="button" class="btn btn-primary" data-act="notion-check" ${st === "checking" ? "disabled" : ""}>Check it</button></div>`;
    const body = `<div class="conn">
      <div class="conn-who">${icon("notion")}<div><b>Notion</b><span class="faint small">Your Notion key, pasted once</span></div></div>
      ${field}<div class="conn-do">${state}</div>
      <button type="button" class="linkish" data-act="notion-where" aria-expanded="${su.where}">${icon(su.where ? "chevDown" : "chev")}Where to find it</button>${where}</div>`;
    return card("p-connect", "What it knows", "Your Notion", body, `<span class="faint">Plays: beat 3, knowing your offer, and beat 6, filing the outcome.</span>`);
  }

  // ---------- samples ----------
  function samplesHTML(su) {
    let kept = 0, words = 0;
    const rows = S.samples
      .map((s) => {
        const p = pick(su, "samples", s.id, s.mark);
        if (p.v) (kept++, (words += s.words));
        return `<li><button type="button" class="row-btn" data-act="pick" data-kind="samples" data-id="${s.id}" aria-pressed="${p.v}">
          ${tick(p)}<span class="r-main"><span class="r-top"><b>${esc(s.to)}</b><span class="faint">${esc(s.subject)}</span><span class="r-meta faint">${dateShort(s.date)}, ${s.words} words</span></span>
          <span class="r-sub">${s.why_not ? `<span class="why">${esc(s.why_not)}</span>` : esc(s.excerpt)}</span></span></button></li>`;
      })
      .join("");
    return card("p-list", "How it sounds", "Mail you sent yourself", `<ul class="rows">${rows}</ul>`, `<span><b>${kept}</b> kept, ${words} words to learn from</span><span class="faint">Only words you wrote</span>`);
  }

  // ---------- style dials ----------
  function styleHTML(su, m) {
    const frameDials = m.fr.dials;
    const presets = S.style.presets
      .map((p) => `<button type="button" class="seg ${su.picks.preset === p ? "on" : ""}" data-act="preset" data-name="${esc(p)}">${esc(p)}</button>`)
      .join("");
    const rows = frameDials
      .map((d) => {
        const mine = su.picks.dials[d.id];
        let v = d.value, src = d.source;
        if (mine) (v = mine.v), (src = mine.src);
        const dots = [1, 2, 3, 4, 5]
          .map((n) => `<button type="button" class="dial-dot ${n === v ? "cur" : ""} ${n < v ? "under" : ""}" data-act="dial" data-id="${d.id}" data-v="${n}" aria-label="${esc(d.label)} ${n} of 5"></button>`)
          .join("");
        const tag = src === "you" ? `<span class="src you">you</span>` : src === "learned" ? `<span class="src her">your mail</span>` : `<span class="src">preset</span>`;
        return `<li class="dial src-${src}"><span class="d-label">${esc(d.label)}</span><span class="d-end faint">${esc(d.low)}</span><span class="d-dots">${dots}</span><span class="d-end faint">${esc(d.high)}</span>${tag}</li>`;
      })
      .join("");
    return card("p-style", "How it sounds", "Its style, and where each value came from", `<div class="segs" role="group" aria-label="Presets">${presets}</div><ul class="dials">${rows}</ul>`, `<span class="faint">A preset changes only the dials you have not set yourself.</span>`);
  }

  // ---------- pages ----------
  function pagesHTML(su) {
    const rows = S.pages
      .map((pg) => {
        const p = pick(su, "pages", pg.id, pg.suggest);
        return `<li><button type="button" class="row-btn" data-act="pick" data-kind="pages" data-id="${pg.id}" aria-pressed="${p.v}">${tick(p)}
          <span class="r-main"><span class="r-top"><b>${esc(pg.title)}</b><span class="tag">${pg.kind === "database" ? "database" : "page"}</span></span>${pg.why_not ? `<span class="r-sub why">I'd leave it out: ${esc(pg.why_not.toLowerCase())}</span>` : ""}</span></button></li>`;
      })
      .join("");
    return card("p-list", "What it knows", "Pages it may answer from", `<ul class="rows">${rows}</ul>`, `<span class="faint">It never quotes a page you did not share.</span>`);
  }

  // ---------- chores ----------
  function choresHTML(su) {
    const on = S.chorePresets.filter((c) => !c.coming);
    const coming = S.chorePresets.filter((c) => c.coming);
    const row = (c) => {
      const p = c.later ? { v: false } : pick(su, "chores", c.id, c.suggest);
      const dis = c.later || c.coming;
      return `<li><button type="button" class="row-btn ${dis ? "off" : ""}" ${dis ? "disabled" : `data-act="pick" data-kind="chores" data-id="${c.id}"`} aria-pressed="${!!p.v}">${dis ? `<span class="tick"></span>` : tick(p)}
        <span class="r-main"><span class="r-top"><b>${esc(c.name)}</b>${c.later ? `<span class="tag">later</span>` : ""}${c.coming ? `<span class="tag">coming</span>` : ""}${c.id === "file-outcome" ? `<span class="tag beat-tag">beat 6</span>` : ""}${c.id === "practice-page" ? `<span class="tag beat-tag">the rehearsal</span>` : ""}</span><span class="r-sub">${esc(c.does)}</span></span></button></li>`;
    };
    const body = `<span class="group">${icon("notion")}Notion</span><ul class="rows">${on.map(row).join("")}</ul>
      <span class="group faint">${icon("calendar")}Calendar and ${icon("slack")}Slack: not connected in this app yet</span><ul class="rows">${coming.map(row).join("")}</ul>`;
    return card("p-list p-chores", "What it does there", "Ready-made chores", body, `<span class="faint">More tools arrive later; each one brings its chores.</span>`);
  }

  // ---------- autonomy ----------
  function levelSeg(su, key, proposed, label) {
    const mine = su.picks.auto[key];
    const v = mine || proposed;
    const segs = D.autonomyLevels
      .map((l) => {
        const cls = l.id === v ? (mine ? "on" : "her") : "";
        return `<button type="button" class="seg ${cls}" data-act="auto" data-key="${key}" data-v="${l.id}" title="${esc(l.says)}">${esc(l.label)}</button>`;
      })
      .join("");
    const says = D.autonomyLevels.find((l) => l.id === v).says;
    return `<div class="lvl"><span class="lvl-name">${label}</span><div class="segs">${segs}</div><span class="lvl-says faint">${esc(says)}</span></div>`;
  }
  function barRow(su, key, val) {
    const v = su.picks.auto[key] ?? val;
    return `<div class="barrow"><span>Sends alone at</span><button type="button" class="btn btn-icon" data-act="bar" data-key="${key}" data-d="-5" aria-label="Lower">-</button><b class="${su.picks.auto[key] != null ? "you" : "her"}">${v}</b><button type="button" class="btn btn-icon" data-act="bar" data-key="${key}" data-d="5" aria-label="Higher">+</button><span class="faint">sure or more, and only with an empty risk list</span></div>`;
  }
  function autonomyHTML(su) {
    const [g, n] = S.autonomy.channels;
    const repliesAuto = (su.picks.auto.gmail_replies || g.split.replies) === "auto";
    const notionAuto = (su.picks.auto.notion || n.proposed) === "auto";
    const body = `<div class="chan"><div class="chan-head">${icon("mail")}<b>Gmail</b></div>
        ${levelSeg(su, "gmail_first", g.split.first_message, "First message")}
        ${levelSeg(su, "gmail_replies", g.split.replies, "Replies")}
        ${repliesAuto ? barRow(su, "gmail_bar", g.bar) : ""}</div>
      <div class="chan"><div class="chan-head">${icon("notion")}<b>Notion</b><span class="tag">${esc(n.scope)}</span></div>
        ${levelSeg(su, "notion", n.proposed, "Practice page")}${notionAuto ? barRow(su, "notion_bar", n.bar) : ""}</div>
      <p class="rule">${icon("lock")}<span>${esc(S.autonomy.rule)}</span></p>`;
    return card("p-auto", "What it may send alone", "Review, Assist or Auto, per channel", body, `<span class="faint">Plays: beat 1 waits for you; beats 3 and 5 may go alone.</span>`);
  }

  // ---------- memory ----------
  function memoryHTML(su) {
    const rows = S.memory
      .map((f) => {
        const mine = su.picks.memory[f.id];
        const v = mine || f.suggest;
        const seg = (val, lbl) => `<button type="button" class="seg ${v === val ? (mine ? "on" : "her") : ""}" data-act="mem" data-id="${f.id}" data-v="${val}">${lbl}</button>`;
        return `<li class="fact ${v}"><div class="f-main"><b>${esc(f.fact)}</b><span class="faint small">${esc(f.from)}</span>${f.reason ? `<span class="why small">${esc(f.reason)}</span>` : ""}</div><div class="segs">${seg("keep", "Keep")}${seg("drop", "Drop")}</div></li>`;
      })
      .join("");
    return card("p-mem", "What it remembers about you", "Facts she noticed in your mail", `<ul class="facts">${rows}</ul>`, `<span class="faint">It only uses the ones you keep. Plays: beat 5 needs when you publish.</span>`);
  }

  // ---------- the frames without a named panel ----------
  function castHTML() {
    const rows = R.cast.map((c, i) => `<li class="${i === 2 ? "you" : ""}"><b>${esc(c.who)}</b><span class="role">${esc(c.role)}</span><span class="faint small">${esc(c.does)}</span></li>`).join("");
    return card("p-cast", "Who it speaks as", "The cast", `<ul class="cast">${rows}</ul><div class="sig pencil"><span class="faint small">Every line it writes ends with</span><span>cheers, <span class="blank">your signature</span></span></div>`, `<span class="faint">Your answer below names who signs.</span>`);
  }
  function neverHTML(m) {
    const rows = m.pieces
      .filter((p) => p.place === "never")
      .map((p) => {
        const beat = p.id === "p_n2" ? "beat 3" : p.id === "p_n1" ? "beat 3 if they ask for money" : "every beat";
        return p.confirmed
          ? `<li class="ink"><span>${esc(p.label)}</span><span class="faint small">${beat}</span></li>`
          : `<li class="pencil"><span>${esc(p.label)}</span><span class="faint small">${beat}</span><button type="button" class="btn btn-quiet small-btn" data-act="ink" data-id="${p.id}">${icon("pen")}Ink</button></li>`;
      })
      .join("");
    return card("p-never", "What it must never do", "Lines it never crosses", `<ul class="nevers">${rows}</ul>`, `<span class="faint">If a line comes near one of these, it goes on its risk list and waits for you.</span>`);
  }
  function missionHTML(su) {
    const sug = S.frames[10].ask.suggestions;
    const rows = R.missionChoices
      .map((c, i) => `<li><button type="button" class="row-btn" data-act="answer" data-i="${i}"><span class="k">${i + 1}</span><span class="r-main"><b>${esc(sug[i])}</b><span class="r-sub faint">${esc(c.why)}</span></span></button></li>`)
      .join("");
    return card("p-list", "Its first mission", "One goal, on one conversation", `<ul class="rows">${rows}</ul>`, `<span class="faint">It drafts each turn toward the goal, says when it's resolved, and hands back to you when unsure.</span>`);
  }
  function startHTML() {
    const rh = S.rehearsal;
    return card("p-start", "Dress rehearsal", "Rehearse it before anyone real", `<ul class="how"><li>${icon("notion")}<span>${esc(rh.where)}</span></li><li>${icon("eye")}<span>${esc(rh.played_by)}</span></li><li>${icon("pen")}<span>Mark each draft "that's me" or "not me". Anything you change teaches it.</span></li></ul>
      <button type="button" class="btn btn-primary wide" data-act="start-rehearsal">${icon("play")}Start the rehearsal</button>`);
  }
  function howHTML() {
    return card("p-how", "Set up a twin", "How this goes", `<ol class="steps"><li><b>Say what it's for.</b><span class="faint">One sentence is enough.</span></li><li><b>She writes its first conversation as a script.</b><span class="faint">Each answer you give fills a beat: its voice, what it knows, what it must never do.</span></li><li><b>Rehearse it on a Notion practice page.</b><span class="faint">Athena plays the other side. Then it goes live.</span></li></ol>`);
  }

  function render(su, m) {
    if (su.f < 0) return howHTML();
    const panel = m.fr.panel;
    if (!panel) return su.f === 0 ? castHTML() : su.f === 7 ? neverHTML(m) : missionHTML(su);
    switch (panel.kind) {
      case "connect":
        return panel.channel === "gmail" ? gmailHTML(su) : notionHTML(su);
      case "samples":
        return samplesHTML(su);
      case "style":
        return styleHTML(su, m);
      case "pages":
        return pagesHTML(su);
      case "chores":
        return choresHTML(su);
      case "autonomy":
        return autonomyHTML(su);
      case "memory":
        return memoryHTML(su);
      case "rehearsal":
        return startHTML();
    }
    return "";
  }

  window.Panels = { render };
})();
