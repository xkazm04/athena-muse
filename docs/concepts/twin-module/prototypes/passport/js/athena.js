// Athena's bottom panel: her one line, the one question, three suggestions, your own words,
// the "That's enough" exit from the first ready frame, and what she still needs.
(function () {
  const { D, V, esc, icons, seal } = TP;
  const F = D.setup.frames;

  // what the panel asks now: {line, place, ask, suggestions, picked}
  function current(m) {
    const su = TP.S.su;
    if (su.reh) {
      const key = { w1: "running", c2: "running", w3: "running", c4: "running", w5: "running" }[su.reh.step] || su.reh.step;
      const c = V.rehearsal[key];
      const line = key === "golive" ? D.setup.golive.line : c.line;
      return { line, place: null, ask: c.ask, suggestions: c.suggestions };
    }
    if (m.f < 0) return { line: V.describe.line, place: "who", ask: V.describe.ask, suggestions: V.describe.suggestions };
    const fr = m.fr;
    if (!fr.ask) {
      const c = V.rehearsal.intro;
      return { line: fr.line, place: "mission", ask: c.ask, suggestions: c.suggestions };
    }
    return { line: fr.line, place: fr.ask.place, ask: fr.ask.text, suggestions: fr.ask.suggestions };
  }

  function lineRow(m, c) {
    const su = TP.S.su;
    const r = su.reply;
    const you = r ? (su.frame < 0 ? su.need : F[r.target].user.choice !== undefined && su.frame >= 0 ? F[su.frame].ask.suggestions[F[r.target].user.choice] : "") : "";
    if (r && r.kind === "thinking")
      return `<div class="ath__line" data-state="thinking">${seal(30)}<p>${you ? `<span class="you">You: ${esc(you)}</span>` : ""}<span class="dots" aria-hidden="true"><i></i><i></i><i></i></span>Thinking <b data-clock="reply">${TP.secs(r.secs)}</b></p></div>`;
    if (r && r.kind === "slow")
      return `<div class="ath__line" data-state="slow">${seal(30)}<p><span class="dots" aria-hidden="true"><i></i><i></i><i></i></span>Still thinking: <b data-clock="reply">${TP.secs(r.secs)}</b>. Slower than usual; nothing is lost.</p>
        <span class="ath__lineact"><button class="btn btn-quiet" data-act="keep-waiting">Keep waiting</button><button class="btn btn-quiet" data-act="stop-reply">Stop</button></span></div>`;
    if (r && r.kind === "failed")
      return `<div class="ath__line" data-state="failed">${seal(30)}<p><span class="err">${icons.risk}</span>Nothing usable came back after ${TP.secs(r.secs)}. Nothing was changed on the document.</p>
        <span class="ath__lineact"><button class="btn" data-act="retry">${icons.retry}Try again</button></span></div>`;
    return `<div class="ath__line">${seal(30)}<p>${esc(c.line)}</p></div>`;
  }

  function side(m) {
    const su = TP.S.su;
    if (su.reh) {
      const step = su.reh.step;
      if (step === "golive") return `<div class="ath__side"><button class="btn btn-primary ath__exit" data-act="to-overview">Back to your twins${icons.arrow}</button><p class="needs">Issued. Nothing more is needed.</p></div>`;
      const can = step === "resolved" || step === "handed";
      return `<div class="ath__side"><button class="btn btn-primary ath__exit" data-act="golive" ${can ? "" : "disabled"}>Go live${icons.arrow}</button><p class="needs">${can ? "The rehearsal is done. Go live when you are happy." : "Go live opens when the rehearsal ends: resolved, or handed back to you."}</p></div>`;
    }
    const ready = m.ready && m.f >= D.setup.first_ready_frame;
    const pencil = m.pieces.filter((p) => !p.confirmed).length;
    const inkAll = pencil ? `<button class="btn ath__inkall" data-act="ink-all">${icons.nib}Ink all her pencil (${pencil})</button>` : "";
    const needs = m.needs.length ? `<p class="needs">She still needs: <b>${m.needs.join(", ")}</b></p>` : `<p class="needs">Everything it needs is filled in. Memory and a first mission are up to you.</p>`;
    if (!ready) return `<div class="ath__side ath__side--needs"><span class="ath__ready"><span class="meter" aria-hidden="true"><i style="width:${m.readiness}%"></i></span>${m.readiness}% filled</span>${needs}${inkAll}</div>`;
    return `<div class="ath__side"><button class="btn btn-primary ath__exit ${su.readyCallout ? "is-callout" : ""}" data-act="enough" ${su.reply ? "disabled" : ""}>That's enough, rehearse it</button>${needs}${inkAll}</div>`;
  }

  TP.renderAthena = function (m) {
    const su = TP.S.su;
    const c = current(m);
    const busy = su.reply && su.reply.kind !== "failed";
    const r = su.reply;
    const pickedI = r && su.frame >= 0 ? F[r.target].user.choice : r && su.frame < 0 ? 0 : -1;
    const about = c.place
      ? `<span class="about" data-place="${c.place}">${icons.arrow}${esc(V.sections[c.place])}</span>`
      : su.reh && su.reh.step === "golive"
        ? `<span class="about">${icons.check}Issued</span>`
        : `<span class="about">${icons.notion}Practice page</span>`;
    const sugg = c.suggestions
      .map((s, i) => `<button class="sugg ${busy && i === pickedI ? "is-picked" : ""}" data-act="pick" data-i="${i}" ${busy ? "disabled" : ""}><kbd>${i + 1}</kbd><span>${esc(s)}</span></button>`)
      .join("");
    return `<section class="athena" aria-label="Athena">
      <div class="ath__main">
        ${lineRow(m, c)}
        <div class="ath__ask">${about}<h2>${esc(c.ask)}</h2></div>
        <div class="ath__answers">${sugg}
          <form id="own-words" class="own" autocomplete="off"><label class="sr" for="own-input">In your own words</label><input id="own-input" class="field" placeholder="Or in your own words" ${busy ? "disabled" : ""}><button class="btn own__send" type="submit" aria-label="Send" ${busy ? "disabled" : ""}>${icons.send}</button></form>
        </div>
        ${su.note ? `<p class="ath__note">${esc(su.note)}</p>` : ""}
      </div>
      ${side(m)}
    </section>`;
  };
})();
