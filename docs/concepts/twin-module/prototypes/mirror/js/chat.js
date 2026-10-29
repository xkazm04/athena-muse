// Mirror - Athena's bottom panel: her one line, the one question, three suggestions, your own
// words, the "That's enough" exit and what she still needs. Also the timed thinking states.
(function () {
  const TP = window.TP, D = TP.D, V = TP.V, esc = TP.esc, F = D.setup.frames;
  const su = () => TP.S.su;
  const ONE_PATH = "This example follows one path, so she answers as the staged conversation does.";

  const needsText = (k) => {
    if (k < 0) return `She still needs: <strong>what the twin is for</strong>.`;
    const cov = TP.coverageNow(k);
    const need = D.places.filter((p) => p.required > 0 && cov[p.id] < p.required);
    const opt = D.places.filter((p) => p.required === 0 && cov[p.id] < 1);
    if (!need.length) return `She has the basics.${opt.length ? ` Optional: ${opt.map((p) => p.label.toLowerCase()).join(", ")}.` : ""}`;
    return `She still needs: ${need.map((p) => `<strong>${esc(p.label.toLowerCase())}</strong>${cov[p.id] === 0.5 ? " (your ink on her pencil)" : ""}`).join(", ")}.`;
  };

  TP.chatHTML = () => {
    const s = su(), k = s.frame;
    let line, ask, disabled = false, status = "", exit = "", needs, place;
    if (s.phase === "rehearsal") {
      const r = TP.rehChat();
      line = r.line; ask = r.ask; disabled = r.disabled; needs = r.needs; place = "Rehearsal";
      exit = `<button class="btn btn-primary exit" data-act="${r.exitAct}" ${r.exitOn ? "" : "disabled"}>${esc(r.exitLabel)}</button>`;
    } else {
      const cur = k < 0 ? V.describe : { line: F[k].line, ask: F[k].ask };
      line = cur.line; ask = cur.ask;
      place = TP.placeLabel(ask.place);
      needs = needsText(k);
      const ready = k >= D.setup.first_ready_frame;
      exit = ready ? `<button class="btn btn-primary exit ${s.readyFlash ? "glow" : ""}" data-act="enough" ${s.phase === "frame" ? "" : "disabled"}>That's enough, rehearse it</button>` : `<p class="exit-later">You can rehearse it once she has the basics.</p>`;
      if (s.phase === "thinking" || s.phase === "slow" || s.phase === "failed") {
        disabled = true;
        const shown = s.pending?.shown ?? 0;
        if (s.phase === "thinking") status = `<p class="c-status" role="status"><span class="pulse"></span><span>Thinking about your answer · <span id="think-t">${TP.secs(shown)}</span></span></p>`;
        if (s.phase === "slow") status = `<p class="c-status slow" role="status"><span class="pulse"></span><span>Still thinking · <span id="think-t">${TP.secs(shown)}</span>. Slower than usual; replies take 3 to 8 s.</span><button class="btn btn-mini" data-act="keep-waiting">Keep waiting</button><button class="btn btn-mini btn-quiet" data-act="retry">Try again</button></p>`;
        if (s.phase === "failed") status = `<p class="c-status failed" role="alert">${TP.icon("risk")}<span>Nothing usable came back after ${TP.secs(s.pending.at)}. Your answer is kept and nothing changed.</span><button class="btn btn-mini btn-primary" data-act="retry">Try again</button></p>`;
      }
    }
    const sayLast = s.history.filter((m) => m.who === "you").pop();
    return `<section class="chat plane" aria-label="Athena">
      <div class="c-main">
        <div class="c-line">${TP.seal(30)}<div class="c-said">${status || `<p class="her-line">${esc(line)}</p>`}${sayLast && !status ? `<p class="you-said" title="What you said last"><span>You:</span> ${esc(sayLast.text)}</p>` : ""}</div></div>
        <div class="c-ask"><span class="c-place">${esc(place)}</span><h2>${esc(ask.text)}</h2>${s.note ? `<p class="c-note">${esc(s.note)}</p>` : ""}</div>
        <div class="c-answers">${ask.suggestions.map((t, i) => `<button class="sugg" data-act="suggest" data-i="${i}" ${disabled ? "disabled" : ""}><kbd>${i + 1}</kbd><span>${esc(t)}</span></button>`).join("")}
          <div class="own"><label class="sr" for="own">Or say it in your own words</label><input id="own" class="field" placeholder="Your own words" autocomplete="off" ${disabled ? "disabled" : ""}/><button class="btn btn-primary icon-btn" data-act="own-send" aria-label="Send" ${disabled ? "disabled" : ""}>${TP.icon("send")}</button></div>
        </div>
      </div>
      <div class="c-side">${exit}<p class="needs">${needs}</p></div>
    </section>`;
  };

  // ---- answering ----
  TP.answer = (i, opts = {}) => {
    const s = su();
    if (s.phase === "rehearsal") return TP.rehAnswer(i, opts);
    if (s.phase !== "describe" && s.phase !== "frame") return;
    const k = s.frame;
    const ask = k < 0 ? V.describe.ask : F[k].ask;
    const text = opts.text ?? opts.via ?? ask.suggestions[i];
    const to = k + 1;
    const staged = to === 0 ? 0 : F[to].user.choice;
    s.note = opts.text || (i !== staged && !opts.via) ? ONE_PATH : null;
    s.popPlace = null; s.showDials = false;
    if (k === 1 && s.gmail !== "connected") { s.history.push({ who: "you", text }); return TP.gmailSignIn(true); }
    if (k === 4 && s.notion !== "connected") {
      if (i === 1 && !opts.text) { s.whereOpen = true; s.note = null; return TP.renderSetup(); }
      s.history.push({ who: "you", text });
      if (!/^\S{16,}$/.test(s.notionKey || "")) s.notionKey = "ntn_4f1c9a77e2b04d6c8a1b";
      return TP.notionCheck(true);
    }
    s.history.push({ who: "you", text });
    TP.startThinking(to);
  };
  TP.act.suggest = (el) => TP.answer(Number(el.dataset.i));
  TP.act["own-send"] = () => {
    const v = TP.$("#own")?.value.trim();
    if (!v) return TP.$("#own")?.focus();
    TP.answer(-1, { text: v });
  };
  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && document.activeElement?.id === "own") { e.preventDefault(); TP.act["own-send"](); }
    if (e.key === "Enter" && document.activeElement?.id === "nt-key") { e.preventDefault(); TP.act["nt-check"](); }
  });

  // ---- thinking: a real timed state, played faster, showing real seconds ----
  TP.startThinking = (to, o = {}) => {
    const s = su();
    TP.clearTimers();
    s.phase = "thinking";
    const target = o.slow ?? F[to].elapsed_s;
    s.pending = { to, shown: o.from || 0 };
    if (s.pending.shown > 8) s.phase = "slow";
    const t0 = performance.now() - ((o.from || 0) * 1000) / TP.speed;
    TP.renderSetup();
    TP.every(() => {
      const shown = ((performance.now() - t0) * TP.speed) / 1000;
      s.pending.shown = shown;
      if (shown >= target) return TP.arrive(to);
      if (shown > 8 && s.phase === "thinking") { s.phase = "slow"; return TP.renderSetup(); }
      const el = TP.$("#think-t");
      if (el) el.textContent = TP.secs(shown);
    }, 100);
  };
  TP.failThinking = (to, at) => { const s = su(); s.phase = "failed"; s.pending = { to, at, shown: at }; s.history.push({ who: "you", text: F[to].user.choice !== undefined ? F[to - 1].ask.suggestions[F[to].user.choice] : "" }); };
  TP.arrive = (to) => {
    const s = su();
    TP.clearTimers();
    s.frame = to;
    s.phase = to === 11 ? "rehearsal" : "frame";
    s.pending = null; s.fresh = true; s.youTab = "panel"; s.hover = null; s.auto = false;
    s.history.push({ who: "her", text: F[to].line });
    if (to === 11) return TP.rehAt("running", true);
    TP.render();
  };
  TP.act.retry = () => TP.startThinking(su().pending.to);
  TP.act["keep-waiting"] = () => {};
  TP.act.enough = () => {
    const s = su();
    s.note = s.frame < 10 ? "She takes the first mission she suggested: Lumen Vale and 'Glass Harbor'." : null;
    s.history.push({ who: "you", text: "That's enough, rehearse it" });
    TP.startThinking(11);
  };
})();
