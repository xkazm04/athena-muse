// Mirror - the panels a frame names (connect, samples, style, pages, chores, autonomy, memory).
// They open on the "you" side of the mirror; the reflection stays in view beside them.
// Her suggestions show as pencil ticks; anything the person touches becomes ink.
(function () {
  const TP = window.TP, D = TP.D, esc = TP.esc, SU = D.setup;
  const su = () => TP.S.su;

  const PRESETS = {
    "Friendly pro": { formality: 3, warmth: 4, humor: 2, energy: 3, length: 3, directness: 3, expressiveness: 3, detail: 3 },
    "Brief and direct": { formality: 3, warmth: 2, humor: 1, energy: 3, length: 1, directness: 5, expressiveness: 2, detail: 2 },
    "Warm storyteller": { formality: 2, warmth: 5, humor: 3, energy: 4, length: 4, directness: 2, expressiveness: 4, detail: 3 },
  };

  // a pick: pencil when it is her suggestion untouched, ink once the person chose
  const pick = (group, id, on, touched, label, sub, extra = "") => `<label class="pick ${on ? "on" : ""} ${touched ? "inked" : "pencil"}">
      <input type="checkbox" data-change="pick" data-group="${group}" data-id="${id}" ${on ? "checked" : ""} />
      <span class="tick" aria-hidden="true">${on ? TP.icon("check") : ""}</span>
      <span class="pick-txt"><span class="pick-l">${label}</span>${sub ? `<span class="pick-s">${sub}</span>` : ""}</span>${extra}</label>`;
  const head = (title, sub, right = "") => `<div class="pn-head"><div><h3>${title}</h3>${sub ? `<p>${sub}</p>` : ""}</div>${right}</div>`;
  const legend = "";

  const picks = (group, items, suggest) => {
    const s = su();
    s.picks[group] = s.picks[group] || Object.fromEntries(items.map((x) => [x.id, { on: !!suggest(x), touched: false }]));
    return s.picks[group];
  };
  TP.act.pick = (el) => {
    const g = su().picks[el.dataset.group];
    g[el.dataset.id] = { on: el.checked, touched: true };
    TP.renderSetup();
  };

  // ---- connect: Gmail ----
  const gmail = () => {
    const s = su(), c = SU.connect.gmail;
    const lists = `<div class="asks"><div><p class="a-h">It asks to</p><ul>${c.asks_for.map((x) => `<li class="yes">${TP.icon("check")}${esc(x)}</li>`).join("")}</ul></div>
      <div><p class="a-h">It never asks for</p><ul>${c.never_asks_for.map((x) => `<li class="no">${TP.icon("x")}${esc(x)}</li>`).join("")}</ul></div></div>`;
    let body;
    if (s.gmail === "waiting") {
      const t = Math.floor(s.gmailT || 0);
      body = `<div class="conn conn-wait" role="status"><span class="pulse"></span><div><p>${esc(c.states.waiting)}</p><p class="sub"><span id="gm-t">0:${String(t).padStart(2, "0")}</span> · it gives up after ${c.timeout_s / 60} min</p></div></div>
        <div class="pn-act"><button class="btn" data-act="gm-reopen">Open the browser again</button><button class="btn btn-quiet" data-act="gm-cancel">Cancel</button></div>`;
    } else if (s.gmail === "connected") {
      body = `<div class="conn conn-ok" role="status">${TP.icon("check")}<p>${esc(c.states.connected)}</p></div>${s.auto ? "" : `<div class="pn-act"><button class="btn btn-primary" data-act="gm-continue">Continue</button></div>`}`;
    } else if (s.gmail === "failed") {
      body = `<div class="conn conn-bad" role="alert">${TP.icon("risk")}<p>${esc(c.states.failed)}</p></div><div class="pn-act"><button class="btn btn-primary" data-act="gm-signin">Try again</button></div>`;
    } else {
      body = `<div class="pn-act"><button class="btn btn-primary btn-google" data-act="gm-signin">${TP.icon("mail")}${esc(c.states.idle)}</button></div><p class="pn-note">Google's sign-in page opens in your browser. Nothing is read until you finish there.</p>`;
    }
    return head("Gmail", "Where it speaks. Sign in with the account it writes from.") + lists + body;
  };

  // ---- connect: Notion ----
  const notion = () => {
    const s = su(), c = SU.connect.notion;
    const where = `<ol class="where">${c.where_to_find.map((x) => `<li>${esc(x)}</li>`).join("")}</ol>`;
    let state = "";
    if (s.notion === "checking") state = `<div class="conn conn-wait" role="status"><span class="pulse"></span><p>${esc(c.states.checking)}</p></div>`;
    else if (s.notion === "connected") state = `<div class="conn conn-ok" role="status">${TP.icon("check")}<p>${esc(c.states.connected)}</p></div>${s.auto ? "" : `<div class="pn-act"><button class="btn btn-primary" data-act="nt-continue">Choose its pages</button></div>`}`;
    else if (s.notion === "rejected") state = `<div class="conn conn-bad" role="alert">${TP.icon("risk")}<p>${esc(c.states.rejected)}</p></div>`;
    const done = s.notion === "connected";
    return head("Notion", "What it may know. Your Notion key lets it read only the pages you share with it.") +
      (done ? "" : `<div class="key-row"><label class="sr" for="nt-key">${esc(c.states.idle)}</label><input id="nt-key" class="field" type="password" autocomplete="off" placeholder="${esc(c.states.idle)}" value="${esc(s.notionKey)}" data-input="nt-key" ${s.notion === "checking" ? "disabled" : ""}/><button class="btn btn-primary" data-act="nt-check" ${s.notion === "checking" ? "disabled" : ""}>Check key</button></div>`) +
      state +
      (done ? "" : `<button class="btn btn-quiet where-btn" data-act="nt-where" aria-expanded="${!!s.whereOpen}">${TP.icon(s.whereOpen ? "down" : "chev")}Where to find it</button>${s.whereOpen ? where : ""}`);
  };

  // ---- samples ----
  const samples = () => {
    const g = picks("samples", SU.samples, (x) => x.mark);
    const n = Object.values(g).filter((x) => x.on).length;
    return head("Your sent mail", "It learns your voice only from mail you wrote yourself, never from examples it makes up.", legend) +
      `<div class="pn-list">${SU.samples.map((x) => pick("samples", x.id, g[x.id].on, g[x.id].touched,
        `${esc(x.to)} <em>· ${esc(x.subject)}</em>`,
        x.why_not ? `<span class="why-not">Not this one: ${esc(x.why_not)}</span>` : esc(x.excerpt),
        `<span class="pick-meta">${TP.day(x.date)}<br>${x.words} words</span>`)).join("")}</div>
      <div class="pn-act"><button class="btn btn-primary" data-act="pn-done" data-i="0">Learn from these ${n}</button></div>`;
  };

  // ---- style dials ----
  const style = () => {
    const s = su(), k = Math.max(s.frame, 3);
    const SRC = { learned: "from your mail", preset: "preset", you: "you set it" };
    const rows = SU.style.dials.map((d) => {
      const v = TP.dialValue(d.id, k);
      const src = s.dialSrc[d.id] || F(k).dials.find((x) => x.id === d.id).source;
      return `<div class="dial" role="group" aria-label="${esc(d.label)}">
        <p class="dl-l"><span>${esc(d.label)}</span><span class="src src-${src}">${SRC[src]}</span></p>
        <div class="dl-c"><span class="dl-end">${esc(d.low)}</span><span class="dl-steps">${[1, 2, 3, 4, 5].map((i) => `<button class="step ${i <= v ? "fill" : ""} ${i === v ? "cur" : ""} src-${src}" data-act="dial" data-id="${d.id}" data-v="${i}" aria-label="${esc(d.label)} ${i} of 5" aria-pressed="${i === v}"></button>`).join("")}</span><span class="dl-end">${esc(d.high)}</span></div></div>`;
    }).join("");
    return head("How it sounds", "Eight dials, each showing where its value came from. Move one and watch the reply change.",
      `<button class="btn btn-quiet btn-mini" data-act="dial-reset" ${Object.keys(s.dials).length ? "" : "disabled"}>Reset</button>`) +
      `<div class="presets" role="group" aria-label="Presets">${SU.style.presets.map((p) => `<button class="chip-btn ${s.preset === p ? "on" : ""}" data-act="preset" data-p="${esc(p)}">${esc(p)}</button>`).join("")}</div>
      <div class="dials">${rows}</div>`;
  };
  const F = (k) => SU.frames[k];
  TP.act.dial = (el) => {
    const s = su();
    s.dials[el.dataset.id] = Number(el.dataset.v);
    s.dialSrc[el.dataset.id] = "you";
    s.preset = null;
    TP.renderSetup();
  };
  TP.act.preset = (el) => {
    const s = su(), p = PRESETS[el.dataset.p];
    s.preset = el.dataset.p;
    for (const [id, v] of Object.entries(p)) { s.dials[id] = v; s.dialSrc[id] = "preset"; }
    TP.renderSetup();
  };
  TP.act["dial-reset"] = () => { const s = su(); s.dials = {}; s.dialSrc = {}; s.preset = null; TP.renderSetup(); };

  // ---- pages ----
  const pages = () => {
    const g = picks("pages", SU.pages, (x) => x.suggest);
    const n = Object.values(g).filter((x) => x.on).length;
    return head("Notion pages it can see", "It answers only from the pages you tick. It reads them fresh each time.", legend) +
      `<div class="pn-list">${SU.pages.map((x) => pick("pages", x.id, g[x.id].on, g[x.id].touched, esc(x.title), x.why_not ? `<span class="why-not">I'd leave it out: ${esc(x.why_not)}</span>` : x.kind === "database" ? "Notion database" : "Notion page")).join("")}</div>
      <div class="pn-act"><button class="btn btn-primary" data-act="pn-done" data-i="0">Answer from these ${n}</button></div>`;
  };

  // ---- chores ----
  const chores = () => {
    const live = SU.chorePresets.filter((c) => !c.coming);
    const g = picks("chores", live, (x) => x.suggest);
    const n = Object.values(g).filter((x) => x.on).length;
    const coming = SU.chorePresets.filter((c) => c.coming);
    return head("Ready-made chores", "Things it can do in Notion beyond answering. More tools arrive later.", legend) +
      `<p class="pn-group">Notion</p><div class="pn-list">${live.map((x) => pick("chores", x.id, g[x.id].on, g[x.id].touched, esc(x.name) + (x.later ? ` <span class="badge">later</span>` : ""), esc(x.does))).join("")}</div>
      <p class="pn-group">Coming: tools not connected in this app yet</p><div class="coming-row">${coming.map((x) => `<span class="coming-chip" aria-disabled="true" title="${esc(x.does)}">${x.tool === "calendar" ? "Calendar" : "Slack"}: ${esc(x.name)}</span>`).join("")}</div>
      <div class="pn-act"><button class="btn btn-primary" data-act="pn-done" data-i="1">Run these ${n}</button></div>`;
  };

  // ---- autonomy ----
  const LV = D.autonomyLevels;
  const levelRow = (key, label, val, touched) => `<div class="lv-row"><p>${label}</p><div class="seg ${touched ? "inked" : "pencil"}" role="radiogroup" aria-label="${esc(label)}">${LV.map((l) => `<button role="radio" aria-checked="${val === l.id}" class="${val === l.id ? "on" : ""}" data-act="lv" data-k="${key}" data-v="${l.id}">${l.label}</button>`).join("")}</div></div>`;
  const autonomy = () => {
    const s = su();
    const a = (s.auto2 = s.auto2 || { gf: "assist", gr: "auto", gbar: 80, n: "auto", nbar: 60, touched: {} });
    const says = (v) => LV.find((l) => l.id === v).says;
    return head("What it may send alone", "Per channel. Auto never sends past its risk list.", legend) +
      `<div class="auto-card"><p class="ac-h">${TP.icon("mail")}Gmail</p>
        ${levelRow("gf", "First message", a.gf, a.touched.gf)}<p class="says">${esc(says(a.gf))}</p>
        ${levelRow("gr", "Replies", a.gr, a.touched.gr)}<p class="says">${esc(says(a.gr))}</p>
        <label class="bar-row ${a.touched.gbar ? "inked" : "pencil"}"><span>Its bar: at least <strong>${a.gbar}</strong> sure</span><input type="range" min="50" max="95" value="${a.gbar}" data-change="bar" data-k="gbar" aria-label="Gmail bar" /></label></div>
      <div class="auto-card"><p class="ac-h">${TP.icon("page")}Notion <em>practice page only</em></p>
        ${levelRow("n", "Practice page", a.n, a.touched.n)}
        <label class="bar-row ${a.touched.nbar ? "inked" : "pencil"}"><span>Its bar: at least <strong>${a.nbar}</strong> sure</span><input type="range" min="50" max="95" value="${a.nbar}" data-change="bar" data-k="nbar" aria-label="Notion bar" /></label></div>
      <p class="rule">${esc(SU.autonomy.rule)}</p>
      <div class="pn-act"><button class="btn btn-primary" data-act="pn-done" data-i="1">Set it this way</button></div>`;
  };
  TP.act.lv = (el) => { const a = su().auto2; a[el.dataset.k] = el.dataset.v; a.touched[el.dataset.k] = true; TP.renderSetup(); };
  TP.act.bar = (el) => { const a = su().auto2; a[el.dataset.k] = Number(el.value); a.touched[el.dataset.k] = true; TP.renderSetup(); };

  // ---- memory ----
  const memory = () => {
    const s = su();
    const m = (s.mem = s.mem || Object.fromEntries(SU.memory.map((f) => [f.id, { v: f.suggest, touched: false }])));
    return head("What it noticed about you", "It only uses what you keep.", legend) +
      `<div class="pn-list">${SU.memory.map((f) => `<div class="fact ${m[f.id].touched ? "inked" : "pencil"}"><div class="f-txt"><p>${esc(f.fact)}</p><p class="pick-s">${esc(f.from)}${f.reason ? `<span class="why-not"> · I'd drop it: ${esc(f.reason)}</span>` : ""}</p></div>
        <div class="seg seg-sm ${m[f.id].touched ? "inked" : "pencil"}" role="radiogroup" aria-label="Keep or drop">${["keep", "drop"].map((v) => `<button role="radio" aria-checked="${m[f.id].v === v}" class="${m[f.id].v === v ? "on" : ""}" data-act="mem" data-id="${f.id}" data-v="${v}">${v === "keep" ? "Keep" : "Drop"}</button>`).join("")}</div></div>`).join("")}</div>
      <div class="pn-act"><button class="btn btn-primary" data-act="pn-done" data-i="0">Keep ${Object.values(m).filter((x) => x.v === "keep").length}, forget the rest</button></div>`;
  };
  TP.act.mem = (el) => { su().mem[el.dataset.id] = { v: el.dataset.v, touched: true }; TP.renderSetup(); };

  TP.act["pn-done"] = (el) => TP.answer(Number(el.dataset.i), { via: el.textContent.trim() });

  // ---- connect flows ----
  TP.gmailSignIn = (auto) => {
    const s = su(), c = SU.connect.gmail;
    s.gmail = "waiting"; s.gmailT = 0; s.auto = auto;
    const speed = 6, t0 = performance.now();
    TP.renderSetup();
    TP.every(() => {
      s.gmailT = ((performance.now() - t0) * speed) / 1000;
      const el = TP.$("#gm-t");
      if (el) el.textContent = `0:${String(Math.floor(s.gmailT)).padStart(2, "0")}`;
    }, 200);
    TP.later(() => {
      TP.clearTimers();
      s.gmail = "connected";
      TP.renderSetup();
      if (auto) TP.later(() => TP.startThinking(2), 900);
    }, (c.waiting_s * 1000) / speed);
  };
  TP.act["gm-signin"] = () => TP.gmailSignIn(true);
  TP.act["gm-cancel"] = () => { TP.clearTimers(); su().gmail = "failed"; TP.renderSetup(); };
  TP.act["gm-reopen"] = () => {};
  TP.act["gm-continue"] = () => TP.startThinking(2);

  TP.notionCheck = (auto) => {
    const s = su();
    s.notion = "checking"; s.auto = auto;
    TP.renderSetup();
    TP.later(() => {
      const ok = /^\S{16,}$/.test(s.notionKey || "");
      s.notion = ok ? "connected" : "rejected";
      if (!ok) s.whereOpen = true;
      TP.renderSetup();
      if (ok && auto) TP.later(() => TP.startThinking(5), 900);
    }, 1500);
  };
  TP.act["nt-key"] = (el) => { su().notionKey = el.value; };
  TP.act["nt-check"] = () => { su().notionKey = TP.$("#nt-key")?.value || ""; TP.notionCheck(true); };
  TP.act["nt-where"] = () => { su().whereOpen = !su().whereOpen; TP.renderSetup(); };
  TP.act["nt-continue"] = () => TP.startThinking(5);

  TP.panelTitle = { connect: "Connect", samples: "Pick your mail", style: "Dials", pages: "Pages", chores: "Chores", autonomy: "Sending", memory: "Memory" };
  TP.panelHTML = (panel) => {
    if (!panel) return "";
    const fn = { samples, style, pages, chores, autonomy, memory }[panel.kind];
    if (panel.kind === "connect") return panel.channel === "gmail" ? gmail() : notion();
    return fn ? fn() : "";
  };
})();
