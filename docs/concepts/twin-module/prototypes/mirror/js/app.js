// Mirror - the app shell: one page, two places (#overview, #setup), the States menu, her window,
// the theme and the test contract window.TwinProto.
(function () {
  const TP = window.TP, D = TP.D, $ = TP.$;
  const S = (TP.S = { page: "overview", ov: TP.ovInit("today"), su: TP.suInit(), herOpen: false, statesOpen: false });

  // ---- render ----
  TP.render = () => {
    const ov = $("#page-overview"), su = $("#page-setup");
    ov.hidden = S.page !== "overview";
    su.hidden = S.page !== "setup";
    if (S.page === "overview") TP.renderOverview(ov);
    else TP.renderSetup(su);
    TP.renderHer();
  };

  TP.goPage = (page) => {
    S.page = page;
    const want = "#" + page;
    if (location.hash !== want) history.replaceState(null, "", want);
    TP.render();
  };
  addEventListener("hashchange", () => {
    const p = location.hash === "#setup" ? "setup" : "overview";
    if (p !== S.page) { TP.clearTimers(); S.page = p; TP.render(); }
  });

  // ---- her window: the past lives here ----
  TP.renderHer = () => {
    const w = $("#her-window");
    $("#her-btn").setAttribute("aria-expanded", String(S.herOpen));
    w.hidden = !S.herOpen;
    if (!S.herOpen) return;
    const h = S.su.history;
    w.innerHTML = `<div class="her-head">${TP.seal(30)}<div><strong>Athena</strong><span>Setting up Partnerships</span></div>
      <button class="btn btn-quiet icon-btn" data-act="her-window" aria-label="Close her window">${TP.icon("x")}</button></div>
      <p class="her-sim">Simulated: this example follows one staged path.</p>
      <ol class="her-log">${h.length ? h.map((m) => `<li class="her-${m.who}"><span>${m.who === "you" ? "You" : "Athena"}</span><p>${TP.esc(m.text)}</p></li>`).join("") : `<li class="her-empty">Nothing said yet. What you and she say during setup stays here.</li>`}</ol>`;
    const log = w.querySelector(".her-log");
    log.scrollTop = log.scrollHeight;
  };
  TP.act["her-window"] = () => { S.herOpen = !S.herOpen; TP.renderHer(); };

  // ---- theme ----
  const theme = () => document.documentElement.getAttribute("data-theme") || "dark";
  const paintTheme = () => {
    const t = theme();
    $("#theme-btn").innerHTML = TP.icon(t === "dark" ? "sun" : "moon");
    $("#theme-btn").setAttribute("aria-label", t === "dark" ? "Switch to light" : "Switch to dark");
  };
  TP.act.theme = () => {
    document.documentElement.setAttribute("data-theme", theme() === "dark" ? "light" : "dark");
    paintTheme();
    TP.redrawLeaders?.();
  };

  // ---- the states ----
  const ovState = (mode, extra) => () => { S.page = "overview"; S.ov = TP.ovInit(mode, extra); };
  const suFrame = (n, extra) => () => { S.page = "setup"; S.su = TP.suAt(n, extra); };
  const STATES = [
    ["Overview", [
      ["overview-loading", "Loading", ovState("loading")],
      ["overview-first-run", "First run: no twins yet", ovState("first")],
      ["overview-today", "Today", ovState("today")],
      ["overview-row-open", "A row opened", ovState("today", { open: "tw_desk" })],
      ["overview-held-draft", "A held draft", ovState("today", { open: "tw_desk", draft: "dr_1" })],
      ["overview-below-bar", "A draft below the bar", ovState("today", { open: "tw_desk", draft: "dr_2" })],
      ["overview-handed-back", "Handed back: Pine & Co", ovState("today", { open: "tw_desk", mission: "ms_3" })],
      ["overview-needs-sign-in", "Needs sign-in: Family admin", ovState("today", { open: "tw_family" })],
      ["overview-setting-up", "Partnerships, being set up", ovState("today", { open: "tw_partners" })],
      ["overview-after-golive", "After go-live", ovState("after", { open: "tw_partners" })],
      ["overview-error", "Could not load", ovState("error")],
    ]],
    ["Setup: talking", [
      ["setup-describe", "Describe: nothing said yet", () => { S.page = "setup"; S.su = TP.suInit(); }],
      ["setup-thinking", "Thinking (3-8 s)", () => { S.page = "setup"; S.su = TP.suAt(2); TP.startThinking(3, { from: 0 }); }],
      ["setup-slow", "Slow: still thinking after 8 s", () => { S.page = "setup"; S.su = TP.suAt(5); TP.startThinking(6, { from: 8.2, slow: 14 }); }],
      ["setup-failed", "Failed reply", () => { S.page = "setup"; S.su = TP.suAt(6); TP.failThinking(7, 8); }],
    ]],
    ["Setup: each answer", D.setup.frames.map((f) => [`setup-f${f.index}`, `Frame ${f.index}: ${f.panel ? f.panel.kind + (f.panel.channel ? " " + f.panel.channel : "") : f.ask ? TP.placeLabel(f.ask.place).toLowerCase() : "rehearsal"}`, suFrame(f.index)])
      .concat([["setup-pencil-waiting", "A proposal waiting (pencil)", suFrame(3, { pencilFocus: true })], ["setup-dials-tuned", "Dials tuned by you", suFrame(4, { dials: { warmth: 5, humor: 4, length: 4 }, showDials: true })], ["setup-ready", "Ready: rehearse it", suFrame(9, { readyFlash: true })]])],
    ["Connect", [
      ["gmail-idle", "Gmail: idle", suFrame(1, { gmail: "idle" })],
      ["gmail-waiting", "Gmail: waiting for the browser", () => { S.page = "setup"; S.su = TP.suAt(1); TP.gmailSignIn(false); }],
      ["gmail-connected", "Gmail: connected", suFrame(1, { gmail: "connected" })],
      ["gmail-failed", "Gmail: failed", suFrame(1, { gmail: "failed" })],
      ["notion-idle", "Notion: idle", suFrame(4, { notion: "idle" })],
      ["notion-checking", "Notion: checking", () => { S.page = "setup"; S.su = TP.suAt(4, { notionKey: "ntn_4f1c9a77e2b04d6c8a1b" }); TP.notionCheck(false); }],
      ["notion-connected", "Notion: connected", suFrame(4, { notion: "connected", notionKey: "ntn_4f1c9a77e2b04d6c8a1b" })],
      ["notion-rejected", "Notion: rejected", suFrame(4, { notion: "rejected", notionKey: "ntn_4f1c", whereOpen: true })],
    ]],
    ["Rehearsal", [
      ["rehearsal-running", "Running: a draft being written", () => { S.page = "setup"; S.su = TP.suAt(11); }],
      ["rehearsal-waits", "Waits: first message", () => { S.page = "setup"; S.su = TP.suAt(11); TP.rehAt("waits"); }],
      ["rehearsal-held", "Held: below the bar, one risk", () => { S.page = "setup"; S.su = TP.suAt(11); TP.rehAt("held"); }],
      ["rehearsal-edited", "Edited: what it learned", () => { S.page = "setup"; S.su = TP.suAt(11); TP.rehAt("edited"); }],
      ["rehearsal-sent-alone", "Sent alone", () => { S.page = "setup"; S.su = TP.suAt(11); TP.rehAt("sent"); }],
      ["rehearsal-resolved", "Resolved and filed", () => { S.page = "setup"; S.su = TP.suAt(11); TP.rehAt("resolved"); }],
      ["rehearsal-handed-back", "Handed back: asked for money", () => { S.page = "setup"; S.su = TP.suAt(11); TP.rehAt("handed"); }],
      ["golive", "Go live", () => { S.page = "setup"; S.su = TP.suAt(11); TP.rehAt("golive"); }],
    ]],
  ];
  const ALL = STATES.flatMap(([, list]) => list);

  const go = (id) => {
    const s = ALL.find((x) => x[0] === id);
    if (!s) throw new Error("unknown state " + id);
    TP.clearTimers();
    S.statesOpen = false;
    S.herOpen = false;
    s[2]();
    if (S.page === "setup" && S.su.phase === "rehearsal" && !S.su.reh) TP.rehAt("running");
    S.current = id;
    const want = "#" + S.page;
    if (location.hash !== want) history.replaceState(null, "", want);
    TP.render();
    paintStates();
  };

  window.TwinProto = { states: ALL.map(([id, label]) => ({ id, label })), go };

  // ---- States menu ----
  const paintStates = () => {
    const pop = $("#states-pop");
    $("#states-btn").setAttribute("aria-expanded", String(S.statesOpen));
    pop.hidden = !S.statesOpen;
    if (!S.statesOpen) return;
    pop.innerHTML = STATES.map(([group, list]) => `<div class="sg"><p>${TP.esc(group)}</p>${list.map(([id, label]) => `<button role="menuitem" data-act="state" data-id="${id}" class="${S.current === id ? "on" : ""}">${TP.esc(label)}</button>`).join("")}</div>`).join("");
  };
  TP.act["states-menu"] = () => { S.statesOpen = !S.statesOpen; paintStates(); };
  TP.act.state = (el) => go(el.dataset.id);

  // ---- events ----
  document.addEventListener("click", (e) => {
    const el = e.target.closest("[data-act]");
    if (S.statesOpen && !e.target.closest(".states-wrap")) { S.statesOpen = false; paintStates(); }
    if (!el || el.disabled || el.getAttribute("aria-disabled") === "true") return;
    const fn = TP.act[el.dataset.act];
    if (fn) { e.preventDefault(); fn(el, e); }
  });
  document.addEventListener("change", (e) => {
    const el = e.target.closest("[data-change]");
    if (el && TP.act[el.dataset.change]) TP.act[el.dataset.change](el, e);
  });
  document.addEventListener("input", (e) => {
    const el = e.target.closest("[data-input]");
    if (el && TP.act[el.dataset.input]) TP.act[el.dataset.input](el, e);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (S.statesOpen) { S.statesOpen = false; paintStates(); return; }
      if (TP.closePopover?.()) return;
      if (S.herOpen) { S.herOpen = false; TP.renderHer(); return; }
    }
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName);
    if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
    if (S.page === "setup" && /^[123]$/.test(e.key)) {
      const b = document.querySelector(`.chat [data-act="suggest"][data-i="${Number(e.key) - 1}"]`);
      if (b && !b.disabled) { e.preventDefault(); b.click(); }
    }
  });
  addEventListener("resize", () => TP.redrawLeaders?.());

  // the honesty line on hover / focus
  const inv = $("#invented"), tip = $("#invented-tip");
  tip.textContent = D.invented;
  const showTip = (on) => () => { tip.hidden = !on; };
  inv.addEventListener("mouseenter", showTip(true));
  inv.addEventListener("mouseleave", showTip(false));
  inv.addEventListener("focus", showTip(true));
  inv.addEventListener("blur", showTip(false));

  // ---- boot ----
  if (!document.documentElement.hasAttribute("data-theme")) document.documentElement.setAttribute("data-theme", "dark");
  $("#brand-seal").innerHTML = TP.seal(34);
  paintTheme();
  S.page = location.hash === "#setup" ? "setup" : "overview";
  if (!location.hash) history.replaceState(null, "", "#overview");
  TP.render();
})();
