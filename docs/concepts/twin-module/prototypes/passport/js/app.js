// Passport: the state, the play loop, the States menu and the test contract (window.TwinProto).
(function () {
  const { D, V } = TP;
  const F = D.setup.frames;
  const R = D.setup.rehearsal;
  const T = (id) => R.turns.find((t) => t.id === id);

  // ---------- state ----------
  function freshSetup() {
    const m = (list, on) => Object.fromEntries(list.map((x) => [x.id, { on: on(x), by: "athena" }]));
    return {
      frame: -1,
      reply: null, // {kind: thinking|slow|failed, secs, total, target, failAt?}
      need: "",
      gmail: "idle", gSecs: 0,
      notion: "idle", nSecs: 0, notionKey: "", where: false,
      inked: [], arrive: [], justInked: [],
      marks: {
        samples: m(D.setup.samples, (x) => x.mark),
        pages: m(D.setup.pages, (x) => x.suggest),
        chores: m(D.setup.chorePresets.filter((c) => !c.coming), (x) => !!x.suggest),
        memory: m(D.setup.memory, (x) => x.suggest === "keep"),
      },
      dials: {}, preset: null,
      auto: { first: "assist", replies: "assist", split: false, bar: D.setup.autonomy.bar_default, notion: "auto", notionBar: 60, touched: false },
      note: null,
      reh: null, // {step, secs, total, alt, edit, mine}
      sealed: false,
      readyCallout: false,
    };
  }
  function fresh() {
    return {
      page: "overview",
      ov: { mode: "today", open: null, focus: null, signin: "idle", sSecs: 0, done: {}, editing: null, flash: null, live: {} },
      su: freshSetup(),
      her: false,
      menu: false,
      speed: 1,
    };
  }
  let S = (TP.S = fresh());

  // ---------- timers ----------
  let ticker = null;
  let later = [];
  function stopTimers() {
    clearInterval(ticker);
    ticker = null;
    later.forEach(clearTimeout);
    later = [];
  }
  const after = (ms, fn) => later.push(setTimeout(fn, ms / Math.max(1, S.speed / 2)));
  function startTick() {
    if (ticker) return;
    ticker = setInterval(tick, 100);
  }
  function tick() {
    const step = 0.1 * S.speed;
    const su = S.su;
    let busy = false;
    if (su.reply && su.reply.kind !== "failed") {
      busy = true;
      su.reply.secs += step;
      if (su.reply.failAt && su.reply.secs >= su.reply.failAt) {
        su.reply.kind = "failed";
        return render();
      }
      if (su.reply.secs >= 8 && su.reply.kind === "thinking") {
        su.reply.kind = "slow";
        return render();
      }
      if (su.reply.secs >= su.reply.total) return arrive(su.reply.target);
      TP.updateClock();
    }
    if (su.gmail === "waiting") {
      busy = true;
      su.gSecs += step * 2;
      if (su.gSecs >= D.setup.connect.gmail.waiting_s) {
        su.gmail = "connected";
        su.fresh = "gmail";
        render();
        after(1400, () => S.su.frame === 1 && S.su.gmail === "connected" && advance());
        return;
      }
      TP.updateClock();
    }
    if (su.notion === "checking") {
      busy = true;
      su.nSecs += step;
      if (su.nSecs >= D.setup.connect.notion.checking_s) {
        su.notion = su.notionKey.trim().length >= 8 ? "connected" : "rejected";
        if (su.notion === "connected") su.fresh = "notion";
        render();
        if (su.notion === "connected") after(1400, () => S.su.frame === 4 && S.su.notion === "connected" && advance());
        return;
      }
      TP.updateClock();
    }
    if (su.reh && su.reh.total) {
      busy = true;
      su.reh.secs += step;
      if (su.reh.secs >= su.reh.total) return rehNext();
      TP.updateClock();
    }
    if (S.ov.signin === "waiting") {
      busy = true;
      S.ov.sSecs += step * 2;
      if (S.ov.sSecs >= D.setup.connect.gmail.waiting_s) {
        S.ov.signin = "done";
        S.ov.live.tw_family = true;
        S.ov.flash = "Signed in again. Family admin is live and back to its usual work.";
        return render();
      }
      TP.updateClock();
    }
    if (!busy) stopTicker();
  }
  function stopTicker() {
    clearInterval(ticker);
    ticker = null;
  }

  // ---------- setup flow ----------
  const play = () => (S.speed = 4);
  function advance(note) {
    const su = S.su;
    const target = su.frame + 1;
    if (target >= F.length) return;
    su.note = note || null;
    su.reply = { kind: "thinking", secs: 0, total: F[target].elapsed_s, target };
    render();
    startTick();
  }
  function arrive(target) {
    const su = S.su;
    const fr = F[target];
    su.reply = null;
    su.frame = target;
    su.arrive = [];
    for (const o of fr.ops) if (o.op === "add" || o.op === "change") su.arrive.push(o.piece.id);
    su.justInked = fr.confirm.slice();
    if (target === 1) su.gmail = "idle";
    if (target === 4) su.notion = "idle";
    render();
    su.arrive = [];
    su.justInked = [];
  }
  function noteFor(i, ask) {
    const next = F[S.su.frame + 1];
    return next && next.user.choice !== undefined && next.user.choice !== i ? V.notes.staged : null;
  }
  // a suggestion picked (click or keys 1-3)
  function pick(i) {
    play();
    const su = S.su;
    if (su.reply && su.reply.kind !== "failed") return;
    if (su.reh) return rehPick(i);
    if (su.frame === -1) {
      su.need = i === 0 ? D.setup.need : V.describe.suggestions[i];
      return advance(i === 0 ? null : V.notes.staged);
    }
    const fr = F[su.frame];
    if (!fr.ask) return;
    if (fr.panel && fr.panel.kind === "connect" && fr.panel.channel === "gmail") {
      su.note = i === 0 ? null : V.notes.staged;
      return signInGmail();
    }
    if (fr.panel && fr.panel.kind === "connect" && fr.panel.channel === "notion") {
      if (i === 1) {
        su.where = true;
        su.note = null;
        return render();
      }
      su.note = i === 0 ? null : V.notes.staged;
      if (!su.notionKey) su.notionKey = "secret_lowtide_partnerships_7f3a";
      return checkNotion();
    }
    if (fr.panel && fr.panel.kind === "rehearsal") return rehStart(i === 0 ? null : V.notes.staged);
    advance(noteFor(i));
  }
  function say(text) {
    play();
    const su = S.su;
    if (!text.trim()) return;
    if (su.reh) return rehPick(0, V.notes.typed);
    if (su.frame === -1) {
      su.need = text.trim();
      return advance(V.notes.typed);
    }
    const fr = F[su.frame];
    if (fr.panel && fr.panel.kind === "connect") return pick(0), (su.note = V.notes.typed), render();
    if (fr.panel && fr.panel.kind === "rehearsal") return rehStart(V.notes.typed);
    advance(V.notes.typed);
  }
  function signInGmail() {
    const su = S.su;
    su.gmail = "waiting";
    su.gSecs = 0;
    render();
    startTick();
  }
  function checkNotion() {
    const su = S.su;
    su.notion = "checking";
    su.nSecs = 0;
    render();
    startTick();
  }
  function ink(id) {
    const su = S.su;
    if (!su.inked.includes(id)) su.inked.push(id);
    su.justInked = [id];
    render();
    su.justInked = [];
  }
  function inkAll() {
    const ids = TP.pencilPieces().map((p) => p.id);
    S.su.inked.push(...ids);
    S.su.justInked = ids;
    render();
    S.su.justInked = [];
  }

  // ---------- rehearsal ----------
  const STEP_TURNS = {
    w1: [], waits: ["t1"], c2: ["t1"], w3: ["t1", "t2"], held: ["t1", "t2", "t3"], editing: ["t1", "t2", "t3"], edited: ["t1", "t2", "t3"],
    c4: ["t1", "t2", "t3"], w5: ["t1", "t2", "t3", "t4"], sent: ["t1", "t2", "t3", "t4", "t5"], resolved: ["t1", "t2", "t3", "t4", "t5"],
    handed: ["t1", "t2"], golive: ["t1", "t2", "t3", "t4", "t5"],
  };
  TP.stepTurns = STEP_TURNS;
  function rehSet(step, extra = {}) {
    const r = S.su.reh || (S.su.reh = { alt: false, edit: null, mine: null });
    Object.assign(r, { step, secs: 0, total: 0 }, extra);
    if (step === "w1") r.total = T("t1").elapsed_s;
    if (step === "w3") r.total = T("t3").elapsed_s;
    if (step === "w5") r.total = T("t5").elapsed_s;
    if (step === "c2" || step === "c4") r.total = 1.6;
    if (step === "golive") S.su.sealed = true;
    render();
    if (r.total) startTick();
  }
  function rehNext() {
    const r = S.su.reh;
    const next = { w1: "waits", c2: "w3", w3: "held", c4: "w5", w5: "sent" }[r.step];
    rehSet(next);
    if (next === "sent") after(2400, () => S.su.reh && S.su.reh.step === "sent" && rehSet("resolved"));
  }
  function rehStart(note) {
    S.su.note = note || null;
    S.su.reh = null;
    rehSet("w1");
  }
  function rehPick(i, typedNote) {
    const r = S.su.reh;
    const su = S.su;
    su.note = typedNote || null;
    const staged = () => (su.note = su.note || V.notes.staged);
    switch (r.step) {
      case "w1": case "c2": case "w3": case "c4": case "w5":
        if (i === 2) return rehSet("handed", { alt: true });
        return render();
      case "waits":
        if (i !== 0) staged();
        return rehSet("c2");
      case "held":
        if (i !== 0) staged();
        return rehSet("editing");
      case "editing":
        if (i === 1) staged();
        if (i === 2) return (r.mine = null), rehSet("editing");
        return saveEdit();
      case "edited":
        if (i === 1) return rehSet("editing");
        if (i === 2) staged();
        return rehSet("c4");
      case "sent":
        if (i === 1) staged();
        return rehSet("resolved");
      case "resolved":
        if (i === 1) return rehSet("handed", { alt: true });
        if (i === 2) return staged(), render();
        return rehSet("golive");
      case "handed":
        if (i === 1) return rehSet("w1", { alt: false });
        if (i === 2) return staged(), render();
        return rehSet("golive");
      case "golive":
        if (i === 0) return toOverviewAfter();
        if (i === 1) return staged(), render();
        return render();
    }
  }
  function saveEdit() {
    const r = S.su.reh;
    const box = document.getElementById("edit-box");
    const t3 = T("t3");
    const text = box ? box.value.trim() : "";
    if (text && text !== t3.text.trim() && text !== t3.edited_text.trim()) {
      r.mine = text;
      S.su.note = "Saved in your words. What it learned follows the example's edit.";
    } else {
      r.mine = null;
    }
    rehSet("edited");
  }
  function toOverviewAfter() {
    stopTimers();
    S.page = "overview";
    S.ov = { ...fresh().ov, mode: "after", flash: "Partnerships is live. Its document is issued and in your wallet." };
    setHash();
    render();
  }

  // ---------- overview ----------
  function ovRetry() {
    S.ov.mode = "loading";
    render();
    later.push(setTimeout(() => ((S.ov.mode = "today"), render()), 1200));
  }
  function ovSignIn() {
    S.speed = 4;
    S.ov.signin = "waiting";
    S.ov.sSecs = 0;
    render();
    startTick();
  }

  // ---------- go(id): the States menu and the test contract ----------
  const STATES = [
    ["overview-loading", "Overview: loading"],
    ["overview-first-run", "Overview: first run"],
    ["overview-today", "Overview: today"],
    ["overview-row-open", "Overview: a twin opened"],
    ["overview-held-draft", "Overview: a held draft"],
    ["overview-handed-back", "Overview: handed back"],
    ["overview-needs-sign-in", "Overview: needs sign-in"],
    ["overview-after-golive", "Overview: after go-live"],
    ["overview-error", "Overview: could not load"],
    ["setup-describe", "Setup: describe"],
    ["setup-thinking", "Setup: thinking"],
    ["setup-slow", "Setup: slow reply"],
    ["setup-failed", "Setup: failed reply"],
    ...F.map((f, i) => [`setup-f${i}`, `Setup: frame ${i}${f.panel ? ` (${f.panel.kind === "connect" ? f.panel.channel : f.panel.kind})` : f.ask ? ` (${f.ask.place})` : ""}`]),
    ["setup-proposal", "Setup: her pencil waiting"],
    ["gmail-idle", "Gmail: idle"],
    ["gmail-waiting", "Gmail: waiting for the browser"],
    ["gmail-connected", "Gmail: connected"],
    ["gmail-failed", "Gmail: failed"],
    ["notion-idle", "Notion: idle"],
    ["notion-checking", "Notion: checking"],
    ["notion-connected", "Notion: connected"],
    ["notion-rejected", "Notion: rejected"],
    ["setup-ready", "Setup: ready to rehearse"],
    ["rehearsal-running", "Rehearsal: running"],
    ["rehearsal-waits", "Rehearsal: waits for you"],
    ["rehearsal-held", "Rehearsal: held"],
    ["rehearsal-editing", "Rehearsal: you edit"],
    ["rehearsal-edited", "Rehearsal: edited"],
    ["rehearsal-sent-alone", "Rehearsal: sent on its own"],
    ["rehearsal-resolved", "Rehearsal: resolved"],
    ["rehearsal-handed-back", "Rehearsal: handed back"],
    ["golive", "Go live"],
  ];

  function atFrame(n, extra = {}) {
    S.page = "setup";
    S.su.frame = n;
    // everything inked up to n is in the data; keep panel choices as the staged path left them
    if (n >= 2) S.su.gmail = "connected";
    if (n >= 5) S.su.notion = "connected";
    if (n >= 5) S.su.notionKey = "secret_lowtide_partnerships_7f3a";
    if (n >= 9) Object.assign(S.su.auto, { first: "assist", replies: "auto", split: true, touched: true });
    if (n >= 10) S.su.marks.memory = { f1: { on: true, by: "you" }, f2: { on: true, by: "you" }, f3: { on: false, by: "athena" }, f4: { on: false, by: "athena" } };
    if (n >= 7) S.su.marks.chores["task-inbox"] = { on: true, by: "you" };
    Object.assign(S.su, extra);
  }
  function go(id) {
    stopTimers();
    S = TP.S = fresh();
    S.speed = 1;
    const [kind, rest] = [id.split("-")[0], id.slice(id.indexOf("-") + 1)];
    if (kind === "overview") {
      S.page = "overview";
      const ov = S.ov;
      if (rest === "loading") ov.mode = "loading";
      if (rest === "first-run") ov.mode = "first";
      if (rest === "error") ov.mode = "error";
      if (rest === "after-golive") Object.assign(ov, { mode: "after", flash: "Partnerships is live. Its document is issued and in your wallet." });
      if (rest === "row-open") ov.open = "tw_desk";
      if (rest === "held-draft") Object.assign(ov, { open: "tw_desk", focus: "dr_1" });
      if (rest === "handed-back") Object.assign(ov, { open: "tw_desk", focus: "ms_3" });
      if (rest === "needs-sign-in") Object.assign(ov, { open: "tw_family", focus: "signin" });
    } else if (id === "setup-describe") {
      S.page = "setup";
    } else if (id === "setup-thinking" || id === "setup-slow" || id === "setup-failed") {
      S.page = "setup";
      S.su.need = D.setup.need;
      const k = id.slice(6);
      S.su.reply = { kind: k === "failed" ? "failed" : k === "slow" ? "slow" : "thinking", secs: k === "slow" ? 9.2 : k === "failed" ? 6.0 : 2.4, total: k === "slow" ? 14 : F[0].elapsed_s, target: 0 };
    } else if (/^setup-f\d+$/.test(id)) {
      const n = +id.slice(7);
      atFrame(n);
      if (n === 1) S.su.gmail = "idle";
      if (n === 4) S.su.notion = "idle";
      S.su.arrive = [];
      for (const o of F[n].ops) if (o.op === "add" || o.op === "change") S.su.arrive.push(o.piece.id);
    } else if (id === "setup-proposal") {
      atFrame(7);
    } else if (id === "setup-ready") {
      atFrame(9, { readyCallout: true });
    } else if (kind === "gmail") {
      atFrame(1, { gmail: rest, gSecs: rest === "waiting" ? 12 : 0, fresh: rest === "connected" ? "gmail" : null });
    } else if (kind === "notion") {
      atFrame(4, { notion: rest, nSecs: rest === "checking" ? 0.6 : 0, notionKey: rest === "idle" ? "" : rest === "rejected" ? "secret_lowt" : "secret_lowtide_partnerships_7f3a", where: rest === "rejected" });
      if (rest === "rejected") S.su.notionKey = "secret_lo";
      if (rest === "connected") S.su.fresh = "notion";
    } else if (kind === "rehearsal" || id === "golive") {
      atFrame(11);
      const step = { running: "w1", waits: "waits", held: "held", editing: "editing", edited: "edited", "sent-alone": "sent", resolved: "resolved", "handed-back": "handed" }[rest] || "golive";
      S.su.reh = { step, secs: step === "w1" ? 3.4 : 0, total: step === "w1" ? T("t1").elapsed_s : 0, alt: step === "handed", edit: null, mine: null };
      if (step === "golive") S.su.sealed = true;
    }
    setHash();
    render();
    S.su.arrive = [];
    // timed states keep running at real speed, so a person sees them move
    if (S.su.reply && S.su.reply.kind !== "failed") startTick();
    if (S.su.gmail === "waiting" || S.su.notion === "checking" || (S.su.reh && S.su.reh.total)) startTick();
  }

  function setHash() {
    const h = "#" + S.page;
    if (location.hash !== h) history.replaceState(null, "", h);
  }

  // ---------- render ----------
  function render() {
    const app = document.getElementById("app");
    const keep = TP.keepFocus();
    document.getElementById("view-overview").hidden = S.page !== "overview";
    document.getElementById("view-setup").hidden = S.page !== "setup";
    document.querySelectorAll("[data-nav]").forEach((a) => a.setAttribute("aria-current", a.dataset.nav === "twins" ? "page" : "false"));
    if (S.page === "overview") {
      TP.renderOverview(document.getElementById("view-overview"));
      if (S.ov.flash && !S.ov.flashTimer) {
        const ov = S.ov;
        ov.flashTimer = setTimeout(() => {
          if (TP.S.ov === ov && ov.flash) ((ov.flash = null), render());
        }, 6000);
      }
      // keep the person's next move in view inside the opened document (the page never scrolls)
      const f = document.querySelector(".dr.is-open .dr__act, .ms[data-focus='true'] .ms__act, .dr.is-open, .ms[data-focus='true']");
      if (f) f.scrollIntoView({ block: "nearest" });
    }
    else TP.renderSetup(document.getElementById("view-setup"));
    TP.renderMenu();
    TP.renderHer();
    app.dataset.page = S.page;
    TP.restoreFocus(keep);
    // one-shot animations play once, on the render that brought them
    S.su.arrive = [];
    S.su.justInked = [];
    S.su.fresh = null;
  }
  TP.render = render;
  TP.keepFocus = () => {
    const a = document.activeElement;
    if (!a || !a.id || !/^(INPUT|TEXTAREA)$/.test(a.tagName)) return null;
    return { id: a.id, v: a.value, s: a.selectionStart, e: a.selectionEnd };
  };
  TP.restoreFocus = (k) => {
    if (!k) return;
    const el = document.getElementById(k.id);
    if (!el) return;
    el.value = k.v;
    el.focus();
    try { el.setSelectionRange(k.s, k.e); } catch (e) { /* number inputs */ }
  };
  // update only the ticking numbers, never rebuild the page for a clock
  TP.updateClock = () => {
    document.querySelectorAll("[data-clock]").forEach((el) => {
      el.textContent = TP.clockText(el.dataset.clock);
    });
    document.querySelectorAll("[data-clockbar]").forEach((el) => {
      el.style.transform = `scaleX(${TP.clockFrac(el.dataset.clockbar)})`;
    });
  };
  TP.clockText = (k) => {
    const su = S.su;
    if (k === "reply") return TP.secs(su.reply ? su.reply.secs : 0);
    if (k === "gmail") return `${TP.clock(su.gSecs)} of ${TP.clock(D.setup.connect.gmail.timeout_s)}`;
    if (k === "notion") return TP.secs(su.nSecs);
    if (k === "reh") return TP.secs(su.reh ? su.reh.secs : 0);
    if (k === "signin") return `${TP.clock(S.ov.sSecs)} of ${TP.clock(D.setup.connect.gmail.timeout_s)}`;
    return "";
  };
  TP.clockFrac = (k) => {
    const su = S.su;
    if (k === "reply" && su.reply) return Math.min(1, su.reply.secs / Math.max(su.reply.total, 8));
    if (k === "reh" && su.reh && su.reh.total) return Math.min(1, su.reh.secs / su.reh.total);
    return 0;
  };

  // ---------- events ----------
  const actions = {
    nav: (el) => {
      stopTimers();
      if (el.dataset.to === "overview") {
        S.page = "overview";
        S.ov = fresh().ov;
      } else {
        S.page = "setup";
        S.su = freshSetup();
      }
      setHash();
      render();
    },
    pick: (el) => pick(+el.dataset.i),
    ink: (el) => ink(el.dataset.id),
    "ink-all": () => inkAll(),
    retry: () => {
      play();
      const r = S.su.reply;
      S.su.reply = { kind: "thinking", secs: 0, total: r ? F[r.target].elapsed_s : 4, target: r ? r.target : 0 };
      S.su.note = null;
      render();
      startTick();
    },
    "keep-waiting": () => render(),
    "stop-reply": () => {
      S.su.reply = null;
      S.su.note = "Stopped. Nothing was changed; ask again when you like.";
      render();
    },
    enough: () => {
      play();
      const skipped = S.su.frame < 10;
      const noMission = S.su.frame < 11;
      if (noMission) {
        S.su.frame = 11;
        if (skipped) S.su.marks.memory = { f1: { on: true, by: "athena" }, f2: { on: true, by: "athena" }, f3: { on: false, by: "athena" }, f4: { on: false, by: "athena" } };
      }
      rehStart(noMission ? "She took the first mission she suggested: Lumen Vale's yes to feature 'Glass Harbor'. You can change it before going live." : null);
    },
    "gmail-signin": () => (play(), (S.su.note = null), signInGmail()),
    "gmail-cancel": () => ((S.su.gmail = "failed"), render()),
    "gmail-fail": () => ((S.su.gmail = "failed"), render()),
    "notion-check": () => {
      play();
      const f = document.getElementById("notion-key");
      S.su.notionKey = f ? f.value : S.su.notionKey;
      checkNotion();
    },
    "notion-where": () => ((S.su.where = !S.su.where), render()),
    "panel-go": () => {
      play();
      const su = S.su;
      const kind = F[su.frame].panel && F[su.frame].panel.kind;
      let changed = false;
      if (kind === "samples") changed = Object.entries(su.marks.samples).some(([id, m]) => m.on !== D.setup.samples.find((s) => s.id === id).mark);
      if (kind === "pages") changed = Object.entries(su.marks.pages).some(([id, m]) => m.on !== D.setup.pages.find((s) => s.id === id).suggest);
      if (kind === "chores") changed = Object.values(su.marks.chores).filter((m) => m.on).length !== 3;
      if (kind === "memory") changed = Object.entries(su.marks.memory).some(([id, m]) => m.on !== (D.setup.memory.find((s) => s.id === id).suggest === "keep"));
      if (kind === "autonomy") changed = !(su.auto.split && su.auto.first === "assist" && su.auto.replies === "auto");
      if (kind === "style") changed = false;
      advance(changed ? V.notes.staged : null);
    },
    mark: (el) => {
      const g = S.su.marks[el.dataset.group];
      const m = g[el.dataset.id];
      g[el.dataset.id] = { on: !m.on, by: "you" };
      render();
    },
    dial: (el) => {
      S.su.dials[el.dataset.id] = { value: +el.dataset.v, source: "you" };
      render();
    },
    preset: (el) => {
      const name = el.dataset.name;
      if (S.su.preset === name) {
        S.su.preset = null;
        S.su.dials = {};
      } else {
        S.su.preset = name;
        S.su.dials = Object.fromEntries(Object.entries(V.presetValues[name]).map(([k, v]) => [k, { value: v, source: "preset" }]));
      }
      render();
    },
    level: (el) => {
      const a = S.su.auto;
      a[el.dataset.which] = el.dataset.v;
      a.touched = true;
      render();
    },
    bar: (el) => {
      const a = S.su.auto;
      a.bar = Math.max(50, Math.min(95, a.bar + +el.dataset.d));
      a.touched = true;
      render();
    },
    split: () => {
      const a = S.su.auto;
      a.split = !a.split;
      if (!a.split) a.replies = a.first;
      a.touched = true;
      render();
    },
    "reh-start": () => (play(), rehStart(null)),
    "reh-mark": (el) => rehPick(el.dataset.v === "me" ? 0 : 1),
    "reh-edit": () => (play(), rehSet("editing")),
    "reh-use-example": () => {
      const box = document.getElementById("edit-box");
      if (box) box.value = T("t3").edited_text;
    },
    "reh-save": () => (play(), saveEdit()),
    "reh-send": () => (play(), rehPick(0)),
    "reh-outcome": () => rehSet("resolved"),
    "reh-alt": () => (play(), rehSet("handed", { alt: true })),
    "reh-replay": () => (play(), rehSet("w1", { alt: false })),
    golive: () => rehSet("golive"),
    "to-overview": () => toOverviewAfter(),
    // overview
    open: (el) => {
      S.ov.open = S.ov.open === el.dataset.id && !el.dataset.focus ? null : el.dataset.id;
      S.ov.focus = el.dataset.focus || null;
      S.ov.editing = null;
      render();
    },
    close: () => ((S.ov.open = null), (S.ov.focus = null), render()),
    focus: (el) => ((S.ov.focus = S.ov.focus === el.dataset.id ? null : el.dataset.id), (S.ov.editing = null), render()),
    sign: (el) => {
      S.ov.done[el.dataset.id] = "signed";
      S.ov.focus = null;
      S.ov.flash = "Signed and sent as you.";
      render();
    },
    decline: (el) => {
      S.ov.done[el.dataset.id] = "declined";
      S.ov.focus = null;
      S.ov.flash = "Declined. It will not send that draft.";
      render();
    },
    "edit-draft": (el) => ((S.ov.editing = el.dataset.id), render()),
    "save-draft": (el) => {
      S.ov.done[el.dataset.id] = "signed";
      S.ov.editing = null;
      S.ov.focus = null;
      S.ov.flash = "Your version was sent. It learns from what you changed.";
      render();
    },
    "take-over": (el) => {
      S.ov.done[el.dataset.id] = "taken";
      S.ov.flash = "It's yours now. The twin stays out of that conversation until you hand it back.";
      render();
    },
    "ov-signin": () => ovSignIn(),
    "ov-retry": () => ovRetry(),
    "new-twin": () => {
      stopTimers();
      S.page = "setup";
      S.su = freshSetup();
      setHash();
      render();
    },
    "flash-off": () => ((S.ov.flash = null), (S.ov.flashTimer = null), render()),
    // chrome
    menu: () => ((S.menu = !S.menu), render()),
    go: (el) => go(el.dataset.id),
    her: () => ((S.her = !S.her), render()),
    theme: () => {
      const root = document.documentElement;
      root.dataset.theme = root.dataset.theme === "light" ? "dark" : "light";
      try { localStorage.setItem("twin-passport-theme", root.dataset.theme); } catch (e) { /* private window */ }
      render();
    },
  };

  document.addEventListener("click", (e) => {
    const el = e.target.closest("[data-act]");
    if (!el || el.disabled) {
      if (S.menu && !e.target.closest(".menu")) ((S.menu = false), render());
      return;
    }
    const fn = actions[el.dataset.act];
    if (fn) {
      e.preventDefault();
      if (el.dataset.act !== "menu" && el.dataset.act !== "go") S.menu = false;
      fn(el);
    }
  });
  document.addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    if (f.id === "own-words") {
      const input = f.querySelector("input");
      const v = input.value;
      input.value = "";
      say(v);
    }
    if (f.id === "notion-form") actions["notion-check"]();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (S.menu || S.her) ((S.menu = false), (S.her = false), render());
      return;
    }
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) return;
    if (S.page === "setup" && /^[123]$/.test(e.key) && !e.metaKey && !e.ctrlKey) {
      const btn = document.querySelector(`.athena [data-act="pick"][data-i="${+e.key - 1}"]`);
      if (btn && !btn.disabled) btn.click();
    }
  });
  window.addEventListener("hashchange", () => {
    const p = location.hash === "#setup" ? "setup" : "overview";
    if (p !== S.page) {
      stopTimers();
      S.page = p;
      render();
    }
  });

  TP.go = go;
  TP.STATES = STATES;
  window.TwinProto = { states: STATES.map(([id, label]) => ({ id, label })), go };

  // boot
  document.documentElement.dataset.theme = "dark"; // dark is the app's default
  try {
    const t = localStorage.getItem("twin-passport-theme");
    if (t) document.documentElement.dataset.theme = t;
  } catch (e) { /* private window */ }
  if (location.hash === "#setup") go("setup-describe");
  else go("overview-today");
})();
