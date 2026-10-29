// Rehearsal - the app: state, one render, the two pages on #overview and #setup, timers, the
// States menu, her window, the theme, keys 1-3, and the test contract window.TwinProto.
(function () {
  const { D, R, esc, icon, mark } = window.U;
  const FR = D.setup.frames;
  const main = document.getElementById("main");

  const S = { page: "overview", ov: window.Overview.fresh(), su: window.Setup.fresh() };
  App.S = S;

  // ---------- timers (every state change clears them) ----------
  let timers = [];
  App.later = (fn, ms) => timers.push(setTimeout(fn, ms));
  App.every = (fn, ms) => timers.push(setInterval(fn, ms));
  App.clearTimers = () => {
    timers.forEach((t) => (clearTimeout(t), clearInterval(t)));
    timers = [];
  };
  App.setTick = (name, text) => document.querySelectorAll(`[data-tick="${name}"]`).forEach((el) => (el.textContent = text));

  // ---------- render, keeping what the person is typing ----------
  App.render = () => {
    const kept = {};
    let focusKey = null, sel = null;
    document.querySelectorAll("[data-keep]").forEach((el) => {
      kept[el.dataset.keep] = el.value;
      if (el === document.activeElement) (focusKey = el.dataset.keep), (sel = [el.selectionStart, el.selectionEnd]);
    });
    main.innerHTML = S.page === "overview" ? window.Overview.render(S) : window.Setup.render(S);
    main.dataset.page = S.page;
    // keep the beats this answer moved in view (the script never scrolls the page)
    const beats = main.querySelector(".beats");
    const focus = beats ? beats.querySelectorAll(".beat.focus") : [];
    if (focus.length) {
      const first = focus[0], last = focus[focus.length - 1];
      const bottom = last.offsetTop + last.offsetHeight;
      if (bottom > beats.clientHeight) beats.scrollTop = Math.max(0, Math.min(first.offsetTop - 4, bottom - beats.clientHeight + 4));
    }
    if (beats) {
      const mark = () => beats.classList.toggle("more", beats.scrollTop + beats.clientHeight < beats.scrollHeight - 2);
      mark();
      beats.addEventListener("scroll", mark, { passive: true });
    }
    document.querySelectorAll("[data-keep]").forEach((el) => {
      const k = el.dataset.keep;
      if (kept[k] !== undefined && !el.dataset.fresh && el.tagName !== "TEXTAREA") el.value = kept[k];
      if (k === focusKey) {
        el.focus();
        try {
          el.setSelectionRange(sel[0], sel[1]);
        } catch (e) {}
      }
    });
    renderHer();
    syncHeader();
  };

  App.toast = (text) => {
    const host = document.getElementById("toast-host");
    host.innerHTML = `<div class="toast" role="status">${icon("check")}${esc(text)}</div>`;
    clearTimeout(App._toast);
    App._toast = setTimeout(() => (host.innerHTML = ""), 3200);
  };

  // ---------- pages on the hash ----------
  function setPage(p) {
    S.page = p;
    if (location.hash !== "#" + p) history.replaceState(null, "", "#" + p);
  }
  window.addEventListener("hashchange", () => {
    const p = location.hash === "#setup" ? "setup" : "overview";
    if (p !== S.page) {
      App.clearTimers();
      S.page = p;
      App.render();
    }
  });

  // ---------- the states ----------
  const ovState = (patch) => () => {
    setPage("overview");
    S.ov = Object.assign(window.Overview.fresh(), patch);
  };
  // Put the setup at frame f, with every earlier choice taken the staged way.
  function atFrame(f, patch = {}) {
    setPage("setup");
    const su = window.Setup.fresh();
    su.f = f;
    if (f >= 2) su.gmail = "connected";
    if (f >= 5) su.notion = "connected";
    Object.assign(su, patch);
    S.su = su;
    return su;
  }
  const rhState = (step, extra = {}) => () => {
    const su = atFrame(11);
    su.rh = Object.assign(window.Rehearsal.fresh(), { step }, JSON.parse(JSON.stringify(extra)));
  };
  const BEFORE_HELD = { marks: { t1: "me" } };
  const AFTER_EDIT = { marks: { t1: "me", t3: "edited" }, texts: { t3: window.Rehearsal.T.t3.edited_text }, learned: true };

  const STATES = [
    ["Overview", "overview-loading", "Loading", () => (ovState({ mode: "loading" })(), App.later(() => ((S.ov.mode = "today"), App.render()), 1600))],
    ["Overview", "overview-first-run", "First run, no twins", ovState({ mode: "first" })],
    ["Overview", "overview-today", "Today", ovState({})],
    ["Overview", "overview-row-open", "A row opened", ovState({ open: "tw_desk" })],
    ["Overview", "overview-held-draft", "A held draft", ovState({ open: "tw_desk", draft: "dr_1" })],
    ["Overview", "overview-handed-back", "Handed back", ovState({ open: "tw_desk", mission: "ms_3" })],
    ["Overview", "overview-needs-sign-in", "Needs sign-in", ovState({ open: "tw_family" })],
    ["Overview", "overview-after-golive", "After go-live", () => (ovState({ mode: "after", open: "tw_partners" })(), App.toast("Partnerships is live."))],
    ["Overview", "overview-error", "Could not load", ovState({ mode: "error" })],
    ["Setup", "setup-describe", "Describe", () => atFrame(-1)],
    ["Setup", "setup-thinking", "Thinking", () => (atFrame(-1, { picked: 0 }), "think0")],
    ["Setup", "setup-slow", "Slow", () => (atFrame(-1, { picked: 0 }), "slow0")],
    ["Setup", "setup-failed", "Failed reply", () => atFrame(-1, { picked: 0, phase: "failed", target: 0 })],
    ...FR.map((fr, i) => ["Frames", "setup-f" + i, `Frame ${i}${i === 3 ? ": the wow" : ""}${i === D.setup.first_ready_frame ? ": ready" : ""}`, () => atFrame(i)]),
    ["Setup", "setup-ready", "Ready to rehearse", () => atFrame(D.setup.first_ready_frame)],
    ["Connect", "gmail-idle", "Gmail: idle", () => atFrame(1)],
    ["Connect", "gmail-waiting", "Gmail: waiting for the browser", () => (atFrame(1, { picked: 0, gmailShown: 4 }), "gmail")],
    ["Connect", "gmail-connected", "Gmail: connected", () => atFrame(1, { gmail: "connected" })],
    ["Connect", "gmail-failed", "Gmail: failed", () => atFrame(1, { gmail: "failed" })],
    ["Connect", "notion-idle", "Notion: idle", () => atFrame(4)],
    ["Connect", "notion-checking", "Notion: checking", () => (atFrame(4, { notion: "checking", notionKey: "ntn_4f2a8c1e9b7d3a60c5e1" }), "notion")],
    ["Connect", "notion-connected", "Notion: connected", () => atFrame(4, { notion: "connected", notionKey: "ntn_4f2a8c1e9b7d3a60c5e1" })],
    ["Connect", "notion-rejected", "Notion: rejected", () => atFrame(4, { notion: "rejected", notionKey: "ntn_4f2a", where: true })],
    ["Rehearsal", "rehearsal-running", "Running", () => "rehearse"],
    ["Rehearsal", "rehearsal-waits", "Waits for your signature", rhState("waits")],
    ["Rehearsal", "rehearsal-held", "Held: risk list and the bar", rhState("held", BEFORE_HELD)],
    ["Rehearsal", "rehearsal-editing", "Editing in your words", rhState("editing", { ...BEFORE_HELD, editing: "t3", prev: "held" })],
    ["Rehearsal", "rehearsal-edited", "Edited: what it learned", rhState("edited", AFTER_EDIT)],
    ["Rehearsal", "rehearsal-sent-alone", "Sent on its own", rhState("sent", AFTER_EDIT)],
    ["Rehearsal", "rehearsal-resolved", "Resolved and filed", rhState("resolved", { ...AFTER_EDIT, marks: { t1: "me", t3: "edited", t5: "me" } })],
    ["Rehearsal", "rehearsal-handed-back", "Handed back: they ask for money", rhState("waits", { marks: { t1: "me" }, alt: true })],
    ["Rehearsal", "golive", "Go live", () => (rhState("resolved", { ...AFTER_EDIT, marks: { t1: "me", t3: "edited", t5: "me" } })(), (S.su.golive = true))],
  ];
  // a few start a real timed run after rendering
  const RUNS = {
    think0: () => window.Setup.think(0, { from: 1.2 }),
    slow0: () => window.Setup.think(0, { from: 8.6, need: 14.2, slow: true }),
    gmail: () => window.Setup.startGmail(),
    notion: () => {
      S.su.notion = "idle";
      window.Setup.checkNotion();
    },
    rehearse: () => {
      atFrame(11);
      window.Setup.startRehearsal({ from: 1.4 });
    },
  };

  function go(id) {
    const st = STATES.find((s) => s[1] === id);
    if (!st) return;
    App.clearTimers();
    closeMenus();
    document.getElementById("toast-host").innerHTML = "";
    const run = st[3]();
    App.seen.clear();
    App.quiet = true;
    if (run && RUNS[run]) RUNS[run]();
    else App.render();
    App.quiet = false;
    App.current = id;
    renderMenu();
  }
  App.go = go;

  // ---------- header, menus, her window, theme ----------
  document.getElementById("brand-mark").innerHTML = mark(30);
  document.getElementById("her-ic").innerHTML = icon("chat");
  document.getElementById("states-ic").innerHTML = icon("layers");
  const menu = document.getElementById("states-menu");
  const her = document.getElementById("herwin");

  function renderMenu() {
    let html = "", group = "";
    for (const [g, id, label] of STATES) {
      if (g !== group) (html += `<h4>${g}</h4>`), (group = g);
      html += `<button type="button" role="menuitem" data-state="${id}" aria-current="${App.current === id}">${esc(label)}</button>`;
    }
    menu.innerHTML = html;
  }
  function closeMenus() {
    menu.classList.remove("open");
    document.getElementById("states-btn").setAttribute("aria-expanded", "false");
    her.classList.remove("open");
    document.getElementById("her-btn").setAttribute("aria-expanded", "false");
  }
  document.getElementById("states-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    const open = !menu.classList.contains("open");
    closeMenus();
    if (open) {
      renderMenu();
      menu.classList.add("open");
      e.currentTarget.setAttribute("aria-expanded", "true");
      const cur = menu.querySelector('[aria-current="true"]');
      if (cur) cur.scrollIntoView({ block: "nearest" });
    }
  });
  menu.addEventListener("click", (e) => {
    const b = e.target.closest("[data-state]");
    if (b) go(b.dataset.state);
  });
  document.getElementById("her-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    const open = !her.classList.contains("open");
    closeMenus();
    if (open) {
      her.classList.add("open");
      e.currentTarget.setAttribute("aria-expanded", "true");
      renderHer();
    }
  });
  her.addEventListener("click", (e) => {
    e.stopPropagation();
    if (e.target.closest("[data-close]")) closeMenus();
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".menu")) closeMenus();
  });

  function renderHer() {
    if (!her.classList.contains("open")) return;
    const su = S.su;
    const items = [];
    for (let i = 0; i <= su.f && i < FR.length; i++) {
      const fr = FR[i];
      const said = fr.user.text || (i > 0 && FR[i - 1].ask ? FR[i - 1].ask.suggestions[fr.user.choice] : "");
      if (said) items.push(`<div class="you">${esc(said)}</div>`);
      items.push(`<div class="her">${esc(fr.line)}</div>`);
    }
    her.innerHTML = `<header>${mark(32)}<div><b>Athena</b><small>Setting up Partnerships</small></div><button type="button" class="btn btn-quiet btn-icon" data-close aria-label="Close">${icon("x")}</button></header>
      <div class="past">${items.length ? items.join("") : `<p class="empty">Your setup conversation with Athena will gather here.</p>`}</div>`;
    const past = her.querySelector(".past");
    past.scrollTop = past.scrollHeight;
  }

  function syncHeader() {
    document.querySelector('[data-nav="overview"]').setAttribute("aria-current", "page");
  }
  document.querySelector('[data-nav="overview"]').addEventListener("click", () => {
    App.clearTimers();
    setPage("overview");
    App.render();
  });

  const themeBtn = document.getElementById("theme-btn");
  function paintTheme() {
    const light = document.documentElement.dataset.theme === "light";
    themeBtn.innerHTML = icon(light ? "moon" : "sun");
    themeBtn.setAttribute("aria-label", light ? "Switch to dark" : "Switch to light");
  }
  themeBtn.addEventListener("click", () => {
    const light = document.documentElement.dataset.theme === "light";
    document.documentElement.dataset.theme = light ? "dark" : "light";
    try {
      localStorage.setItem("twin-rehearsal-theme", document.documentElement.dataset.theme);
    } catch (e) {}
    paintTheme();
  });
  try {
    document.documentElement.dataset.theme = localStorage.getItem("twin-rehearsal-theme") || "dark";
  } catch (e) {
    document.documentElement.dataset.theme = "dark";
  }
  paintTheme();

  // ---------- one click handler for every action ----------
  main.addEventListener("click", (e) => {
    const el = e.target.closest("[data-act]");
    if (!el || el.disabled) return;
    App.act(el.dataset.act, el);
  });
  main.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && e.target.matches(".lg-row")) {
      e.preventDefault();
      App.act("ov-row", e.target);
    }
  });
  main.addEventListener("submit", (e) => {
    e.preventDefault();
    const input = e.target.querySelector("input");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    App.act("own", text);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeMenus();
    if (S.page !== "setup" || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.target.matches("input, textarea")) return;
    if (["1", "2", "3"].includes(e.key)) {
      const b = main.querySelector(`.sugg[data-i="${Number(e.key) - 1}"]`);
      if (b && !b.disabled) App.act("answer", b);
    }
  });

  // ---------- the test contract ----------
  window.TwinProto = {
    states: STATES.map(([, id, label]) => ({ id, label })),
    go,
  };

  // start where the hash says
  go(location.hash === "#setup" ? "setup-describe" : "overview-today");
})();
