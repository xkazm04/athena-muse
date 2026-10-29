// Rehearsal - the setup page: the stage (script, prop, wings), Athena's panel along the bottom, and
// the controller that plays the example: answers, her thinking, connecting, inking, the rehearsal.
(function () {
  const { D, R, esc, icon, secs, clock, mark } = window.U;
  const FR = D.setup.frames;
  const FACTOR = 3; // her replies play three times faster than real; the seconds shown are real
  const placeLabel = (id) => (D.places.find((p) => p.id === id) || {}).label || "";

  function fresh() {
    return {
      f: -1, phase: "idle", target: null, need: 0, shown: 0, picked: null, note: "",
      inked: new Set(), open: null,
      gmail: "idle", gmailShown: 0, notion: "idle", notionKey: "", where: false,
      picks: { samples: {}, pages: {}, chores: {}, memory: {}, dials: {}, auto: {}, preset: null },
      rh: null, golive: false,
    };
  }

  // ---------- Athena's panel ----------
  function talk(su, m) {
    if (su.rh || su.golive) return window.Rehearsal.talk(su);
    if (su.f < 0) return R.describe;
    return { line: m.fr.line, ask: m.fr.ask || R.f11ask };
  }

  function stillNeeds(m) {
    if (m.f < 0) return `She needs to know what it's for.`;
    const miss = D.places.filter((p) => m.coverage[p.id] < p.required).map((p) => p.label.toLowerCase());
    if (miss.length) return `She still needs: <b>${esc(miss.join(", "))}</b>.`;
    const opt = D.places.filter((p) => p.required === 0 && m.coverage[p.id] === 0).map((p) => p.label.toLowerCase());
    return opt.length ? `Enough to rehearse. Still open: <b>${esc(opt.join(", "))}</b>.` : "Enough to rehearse. Everything is in place.";
  }

  function herPanel(su, m) {
    const { line, ask } = talk(su, m);
    const busy = su.phase !== "idle";
    let lineHTML;
    if (su.phase === "thinking")
      lineHTML = `<p class="hp-say thinking"><span class="dots">Thinking</span> <b data-tick="think">${secs(su.shown)}</b><span class="faint"> Her replies take 3 to 8 seconds; this example plays faster and shows the real time.</span></p>`;
    else if (su.phase === "slow")
      lineHTML = `<p class="hp-say slow">${icon("clock")}<span>Still thinking, <b data-tick="think">${secs(su.shown)}</b>. Longer than usual.</span><button type="button" class="btn btn-quiet small-btn" data-act="stop">${icon("stop")}Stop</button></p>`;
    else if (su.phase === "failed")
      lineHTML = `<p class="hp-say failed">${icon("warn")}<span>Nothing usable came back, so nothing was changed.</span><button type="button" class="btn small-btn" data-act="retry">${icon("retry")}Try again</button></p>`;
    else lineHTML = `<p class="hp-say ${App.isNew("say:" + line) ? "arrive" : ""}">${esc(line)}</p>`;

    const sugg = ask.suggestions
      .map((s, i) => {
        const picked = su.picked === i ? "picked" : "";
        return `<button type="button" class="sugg ${picked}" data-act="answer" data-i="${i}" ${busy ? "disabled" : ""}><span class="k">${i + 1}</span><span>${esc(s)}</span></button>`;
      })
      .join("");
    const own = typeof su.picked === "string" ? `<span class="own-said">${esc(su.picked)}</span>` : "";
    const inRh = su.rh && !su.golive;
    const canGo = inRh && (su.rh.alt || su.rh.step === "resolved");
    const exit = su.golive
      ? `<button type="button" class="btn btn-primary exit" data-act="to-overview-after">Open your twins page</button><p class="small faint">Partnerships is live.</p>`
      : inRh
      ? `<button type="button" class="btn btn-primary exit" data-act="golive" ${canGo ? "" : "disabled"}>${icon("play")}Go live</button><p class="small faint">${canGo ? "The rehearsal is done." : "Go live once the rehearsal ends."}</p>`
      : `<button type="button" class="btn ${m.ready ? "btn-primary ready" : ""} exit" data-act="enough" ${m.ready && !busy ? "" : "disabled"}>That's enough, rehearse it</button><p class="small needs-line">${stillNeeds(m)}</p>`;
    const place = ask.place ? `<span class="about">${icon("spark")}About ${esc(placeLabel(ask.place).toLowerCase())}</span>` : "";
    return `<section class="her-panel coat" aria-label="Athena">
      <div class="hp-main">
        <div class="hp-line">${mark(28)}${lineHTML}${su.note ? `<span class="note">${esc(su.note)}</span>` : ""}</div>
        <div class="hp-ask">${place}<h2>${esc(ask.text)}</h2></div>
        <div class="hp-row">${sugg}
          <form class="own" data-form="own"><input class="field" name="own" data-keep="own" placeholder="Or say it your own way" autocomplete="off" ${busy ? "disabled" : ""}/>${own}<button class="btn btn-icon" type="submit" aria-label="Send" ${busy ? "disabled" : ""}>${icon("send")}</button></form>
        </div>
      </div>
      <div class="hp-exit">${exit}</div>
    </section>`;
  }

  function render(S) {
    const su = S.su;
    const m = window.Script.model(su);
    const prop = su.rh ? window.Rehearsal.deskHTML(su) : window.Panels.render(su, m);
    const propKey = su.rh ? "desk" : su.f + ":" + (m.fr && m.fr.panel ? m.fr.panel.kind : "none");
    return `<div class="setup ${su.rh ? "in-rehearsal" : ""}">
      <div class="stage">
        ${window.Script.columnHTML(su, m)}
        <div class="prop-col ${App.isNew("prop:" + propKey) ? "arrive" : ""}">${prop}</div>
        ${window.Script.wingsHTML(su, m)}
        ${su.golive ? window.Rehearsal.goliveHTML() : ""}
      </div>
      ${herPanel(su, m)}
    </div>`;
  }

  // ---------- the controller ----------
  const su = () => App.S.su;

  function think(n, opts = {}) {
    const s = su();
    App.clearTimers();
    s.phase = opts.slow ? "slow" : "thinking";
    s.target = n;
    s.need = opts.need ?? FR[n].elapsed_s;
    s.shown = opts.from ?? 0;
    const from = s.shown, t0 = performance.now();
    App.render();
    App.every(() => {
      s.shown = from + ((performance.now() - t0) / 1000) * FACTOR;
      App.setTick("think", secs(s.shown));
      if (s.phase === "thinking" && s.shown >= 8) {
        s.phase = "slow";
        App.render();
      }
      if (s.shown >= s.need) land(n);
    }, 100);
  }

  function land(n) {
    const s = su();
    App.clearTimers();
    s.f = n;
    s.phase = "idle";
    s.open = null;
    s.picked = null;
    s.where = false;
    if (n === 1 && s.gmail !== "connected") s.gmail = "idle";
    if (n === 4 && s.notion !== "connected") s.notion = "idle";
    App.render();
  }

  function offPath(i, text, f) {
    const next = FR[f + 1];
    if (!next || !next.user) return "";
    if (text) return "This example follows one path, so she answers as if you'd picked \"" + FR[f].ask.suggestions[next.user.choice] + "\".";
    if (i !== next.user.choice) return "This example follows one path, so she answers as if you'd picked \"" + FR[f].ask.suggestions[next.user.choice] + "\".";
    return "";
  }

  function answer(i, text) {
    const s = su();
    if (s.phase !== "idle") return;
    s.note = "";
    if (s.golive) {
      if (i === 0 || text) App.go("overview-after-golive");
      else if (i === 1) App.go("setup-describe");
      else (s.note = "She'll be in her window when you need her."), App.render();
      return;
    }
    if (s.rh) return rehearsalAnswer(i, text);
    s.picked = text ? text : i;
    if (s.f < 0) {
      if (text || i !== 0) s.note = "This example follows one path: a twin for creator outreach.";
      return think(0);
    }
    if (s.f === 1) {
      if (i === 2 || text) s.note = "This example follows one path: it signs in with Google.";
      return s.gmail === "connected" ? think(2) : startGmail();
    }
    if (s.f === 4) {
      if (i === 1 && !text) {
        s.where = true;
        s.picked = null;
        return App.render();
      }
      if (i === 2 || text) s.note = "This example follows one path: it connects Notion.";
      return s.notion === "connected" ? think(5) : checkNotion();
    }
    if (s.f === 11) {
      s.picked = null;
      if (i === 0 || text) return startRehearsal();
      s.note = i === 1 ? "This example rehearses the Lumen Vale mission." : "It waits here until you start it.";
      return App.render();
    }
    s.note = offPath(i, text, s.f);
    think(s.f + 1);
  }

  function startGmail() {
    const s = su();
    App.clearTimers();
    s.gmail = "waiting";
    s.gmailShown = s.gmailShown || 0;
    const from = s.gmailShown, t0 = performance.now();
    App.render();
    App.every(() => {
      s.gmailShown = from + ((performance.now() - t0) / 1000) * 6;
      App.setTick("gmail", clock(s.gmailShown));
      if (s.gmailShown >= D.setup.connect.gmail.waiting_s) {
        App.clearTimers();
        s.gmail = "connected";
        s.gmailShown = 0;
        App.render();
        App.later(() => s.f === 1 && think(2), 900);
      }
    }, 200);
  }

  function checkNotion() {
    const s = su();
    const el = document.getElementById("nkey");
    if (el) s.notionKey = el.value.trim();
    if (!s.notionKey) s.notionKey = "ntn_4f2a8c1e9b7d3a60c5e1";
    App.clearTimers();
    s.notion = "checking";
    App.render();
    App.later(() => {
      s.notion = s.notionKey.length < 16 ? "rejected" : "connected";
      App.render();
      if (s.notion === "connected") App.later(() => s.f === 4 && think(5), 900);
    }, D.setup.connect.notion.checking_s * 1000);
  }

  // ---------- the rehearsal ----------
  const RH = () => su().rh;
  function startRehearsal(opts = {}) {
    const s = su();
    App.clearTimers();
    if (s.f < 11) s.f = 11;
    s.rh = window.Rehearsal.fresh();
    s.open = null;
    draft("waits", window.Rehearsal.T.t1.elapsed_s, opts.from || 0);
  }
  function draft(next, elapsed, from = 0) {
    const rh = RH();
    rh.shown = from;
    const t0 = performance.now();
    App.render();
    App.every(() => {
      rh.shown = from + ((performance.now() - t0) / 1000) * window.Rehearsal.FACTOR;
      App.setTick("rdraft", secs(rh.shown));
      App.setTick("rdesk", secs(rh.shown));
      if (rh.shown >= elapsed) {
        App.clearTimers();
        rh.step = next;
        App.render();
      }
    }, 100);
  }
  function cue(step, then) {
    RH().step = step;
    App.render();
    App.later(then, 1300);
  }
  const toHeld = () => cue("cue2", () => ((RH().step = "drafting3"), draft("held", window.Rehearsal.T.t3.elapsed_s)));
  const toSent = () => cue("cue4", () => ((RH().step = "drafting5"), draft("sent", window.Rehearsal.T.t5.elapsed_s)));
  const toResolved = () => {
    RH().step = "filing";
    App.render();
    App.later(() => ((RH().step = "resolved"), App.render()), 1400);
  };

  function rMe() {
    const rh = RH();
    App.clearTimers();
    if (rh.step === "waits") (rh.marks.t1 = "me"), toHeld();
    else if (rh.step === "held") (rh.marks.t3 = "me"), toSent();
    else if (rh.step === "sent") (rh.marks.t5 = "me"), toResolved();
  }
  function rEdit(id) {
    const rh = RH();
    App.clearTimers();
    rh.prev = rh.step;
    rh.editing = id;
    rh.draft = null;
    rh.step = "editing";
    App.render();
    const ta = document.getElementById("redit");
    if (ta) ta.focus();
  }
  function rSave() {
    const s = su(), rh = RH();
    const id = rh.editing;
    const t = window.Rehearsal.T[id];
    const ta = document.getElementById("redit");
    let text = (ta ? ta.value : rh.draft || t.text).trim();
    if (id === "t3" && text === t.text.trim()) {
      text = t.edited_text;
      s.note = "Nothing was changed, so the example uses its own edit.";
    }
    rh.texts[id] = text;
    rh.marks[id] = "edited";
    rh.editing = null;
    rh.draft = null;
    if (id === "t3") {
      rh.learned = true;
      rh.step = "edited";
      s.open = new Set(["voice"]);
      return App.render();
    }
    if (id === "t1") return toHeld();
    return toResolved();
  }
  function rAlt() {
    const rh = RH();
    App.clearTimers();
    rh.alt = true;
    rh.marks.t1 = rh.marks.t1 || "me";
    if (rh.step === "running") rh.step = "waits";
    App.render();
  }

  function rehearsalAnswer(i, text) {
    const s = su(), rh = RH();
    if (text) s.note = "This example follows one path, so your words play it the staged way.";
    const step = rh.alt ? "handed" : rh.step;
    const k = text ? 0 : i;
    const quiet = (n) => ((s.note = n), App.render());
    switch (step) {
      case "waits":
        return k === 0 ? rMe() : rEdit("t1");
      case "held":
        return k === 1 ? rMe() : rEdit("t3");
      case "editing":
        return k === 0 ? rSave() : k === 1 ? App.act("r-example") : App.act("r-cancel");
      case "edited":
        if (k === 0) return toSent();
        if (k === 1) return (s.open = new Set(["voice"])), quiet("It sits in the wings, under how it sounds, in your ink.");
        return rAlt();
      case "sent":
        if (k === 0) return rMe();
        if (k === 1) return rEdit("t5");
        return quiet("This example keeps the bar at 80; you set it per channel in the autonomy step.");
      case "resolved":
        return k === 0 ? App.act("golive") : k === 1 ? startRehearsal() : rAlt();
      case "handed":
        if (k === 0) return App.act("r-yes");
        if (k === 1) return App.act("r-self");
        return App.act("golive");
      default:
        if (k === 1) return rAlt();
        return quiet(k === 0 ? "It plays on." : "This example plays Lumen one way.");
    }
  }

  // ---------- actions ----------
  App.on({
    answer: (el) => answer(Number(el.dataset.i)),
    own: (text) => answer(0, text),
    ink: (el) => {
      su().inked.add(el.dataset.id);
      App.render();
    },
    "ink-all": () => {
      const m = window.Script.model(su());
      m.pieces.filter((p) => !p.confirmed).forEach((p) => su().inked.add(p.id));
      App.render();
    },
    place: (el) => {
      const s = su();
      const id = el.dataset.place;
      if (!s.open) s.open = new Set(document.querySelectorAll(".place.open .pl-head").length ? [...document.querySelectorAll(".place.open .pl-head")].map((b) => b.dataset.place) : []);
      s.open.has(id) ? s.open.delete(id) : s.open.add(id);
      App.render();
    },
    pick: (el) => {
      const s = su();
      const { kind, id } = el.dataset;
      const pressed = el.getAttribute("aria-pressed") === "true";
      s.picks[kind][id] = !pressed;
      App.render();
    },
    dial: (el) => {
      su().picks.dials[el.dataset.id] = { v: Number(el.dataset.v), src: "you" };
      App.render();
    },
    preset: (el) => {
      const s = su();
      const vals = R.presetValues[el.dataset.name];
      s.picks.preset = el.dataset.name;
      for (const [id, v] of Object.entries(vals)) if (!(s.picks.dials[id] && s.picks.dials[id].src === "you")) s.picks.dials[id] = { v, src: "preset" };
      App.render();
    },
    auto: (el) => {
      su().picks.auto[el.dataset.key] = el.dataset.v;
      App.render();
    },
    bar: (el) => {
      const s = su(), k = el.dataset.key;
      const base = s.picks.auto[k] ?? (k === "gmail_bar" ? 80 : 60);
      s.picks.auto[k] = Math.max(50, Math.min(95, base + Number(el.dataset.d)));
      App.render();
    },
    mem: (el) => {
      su().picks.memory[el.dataset.id] = el.dataset.v;
      App.render();
    },
    "gmail-signin": () => startGmail(),
    "gmail-cancel": () => {
      App.clearTimers();
      su().gmail = "failed";
      su().gmailShown = 0;
      App.render();
    },
    "notion-check": () => checkNotion(),
    "notion-where": () => {
      su().where = !su().where;
      App.render();
    },
    continue: () => (su().f === 1 ? think(2) : think(5)),
    stop: () => {
      App.clearTimers();
      const s = su();
      s.phase = "idle";
      s.picked = null;
      s.note = "You stopped her reply. Nothing was changed; answer again when you like.";
      App.render();
    },
    retry: () => {
      const s = su();
      s.note = "";
      think(s.target ?? Math.max(0, s.f + 1));
    },
    enough: () => {
      const s = su();
      if (s.f < 11) s.note = "She set the first mission to her proposal: Lumen Vale and 'Glass Harbor'.";
      startRehearsal();
    },
    "start-rehearsal": () => startRehearsal(),
    "r-me": rMe,
    "r-edit": (el) => rEdit(el.dataset.id),
    "r-save": rSave,
    "r-example": () => {
      RH().draft = window.Rehearsal.T.t3.edited_text;
      App.render();
    },
    "r-cancel": () => {
      const rh = RH();
      rh.step = rh.prev || "held";
      rh.editing = null;
      App.render();
    },
    "r-on": () => toSent(),
    "r-alt": rAlt,
    "r-yes": () => {
      const rh = RH();
      rh.alt = false;
      su().note = "";
      toHeld();
    },
    "r-self": () => {
      su().note = "In a real conversation you'd answer Lumen yourself, and the twin stays out of it.";
      App.render();
    },
    "r-again": () => startRehearsal(),
    golive: () => {
      App.clearTimers();
      su().golive = true;
      App.render();
    },
    "to-overview-after": () => App.go("overview-after-golive"),
  });

  window.Setup = { fresh, render, think, land, startGmail, checkNotion, startRehearsal, draft, FACTOR };
})();
