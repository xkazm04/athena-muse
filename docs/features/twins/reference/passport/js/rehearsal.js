// The dress rehearsal: the practice-page conversation beside the document, a stamp on every twin turn.
(function () {
  const { D, esc, icons, portrait, stamp, sure } = TP;
  const R = D.setup.rehearsal;
  const T = (id) => R.turns.find((t) => t.id === id);
  const para = (s) => esc(s).replace(/\n\n/g, "<br><br>").replace(/\n/g, "<br>");
  const at = (s) => TP.clock(s);

  function writing(label, total) {
    return `<li class="turn turn--twin turn--writing">
      <div class="turn__who">${portrait("P", { size: 26 })}<b>Partnerships</b><span>as Alex</span></div>
      <div class="ghost" aria-hidden="true"><i></i><i></i><i></i></div>
      <p class="turn__status"><span class="spin" aria-hidden="true"></span>${label} <span data-clock="reh">${TP.clockText("reh")}</span> <span class="muted">of about ${total.toFixed(1)} s</span></p>
    </li>`;
  }
  function typing() {
    return `<li class="turn turn--creator turn--typing"><div class="turn__who"><span class="av">LV</span><b>Lumen Vale</b><span class="tag">played by Athena</span></div><p class="dots" aria-label="Lumen Vale is typing"><i></i><i></i><i></i></p></li>`;
  }
  function creator(text, s, fresh) {
    return `<li class="turn turn--creator ${fresh ? "is-new" : ""}"><div class="turn__who"><span class="av">LV</span><b>Lumen Vale</b><span class="tag">played by Athena</span><span class="turn__at">${at(s)}</span></div><p class="turn__text">${para(text)}</p></li>`;
  }

  function twin(t, step, current) {
    const r = TP.S.su.reh;
    const past = !current;
    let st = "";
    let body = `<p class="turn__text">${para(t.text)}</p>`;
    let actions = "";
    let extra = "";
    if (t.id === "t1") {
      st = stamp("Waits for your signature", "human", { fresh: current && step === "waits" });
      extra = `<div class="turn__why">${sure(t.confidence, null, { compact: true })}<span>${esc(t.decision_why)}.</span></div>`;
      if (current) actions = `<div class="turn__act"><button class="btn btn-primary" data-act="reh-mark" data-v="me">${icons.check}That's me</button><button class="btn" data-act="reh-mark" data-v="not">Not me</button></div>`;
      else extra = `<span class="mark" data-v="me">${icons.check}You: that's me, signed</span>`;
    }
    if (t.id === "t3") {
      const editedNow = ["edited", "c4", "w5", "sent", "resolved", "golive"].includes(step);
      st = stamp("Held", "warning", { sub: "waits for you", fresh: current && step === "held" });
      const risks = `<ul class="risks" aria-label="Its risk list">${t.risks.map((x) => `<li>${icons.risk}${esc(x)}</li>`).join("")}</ul>`;
      const why = `<div class="turn__why">${sure(t.confidence, 80, { compact: true })}<span>${esc(t.decision_why)}.</span></div>`;
      if (step === "editing") {
        body = `<label class="sr" for="edit-box">Your version</label><textarea id="edit-box" class="field editbox" rows="5">${esc(r.mine || t.text)}</textarea>`;
        actions = `<div class="turn__act"><button class="btn btn-primary" data-act="reh-save">Save my version</button><button class="btn btn-quiet" data-act="reh-use-example">Use the example's edit</button></div>`;
        extra = risks;
      } else if (editedNow) {
        body = `<p class="turn__text turn__text--mine">${para(r.mine || t.edited_text)}</p>${current ? `<p class="turn__was"><span>It wrote:</span> ${esc(t.text.split("\n")[0])}</p>` : ""}`;
        st = stamp("You edited", "human", { sub: "and signed", fresh: current && step === "edited" });
        extra = `<p class="learned">${icons.layers}<span><b>It learned:</b> ${esc(t.learned)}</span></p>`;
        if (current) actions = `<div class="turn__act"><button class="btn btn-primary" data-act="reh-send">${icons.send}Send it</button><button class="btn btn-quiet" data-act="reh-edit">Edit again</button></div>`;
      } else {
        extra = `${why}${risks}`;
        if (current) actions = `<div class="turn__act"><button class="btn btn-primary" data-act="reh-edit">${icons.pencil}Edit it</button><button class="btn" data-act="reh-send">Send it as it is</button><button class="btn btn-quiet" data-act="reh-mark" data-v="not">Not me</button></div>`;
      }
    }
    if (t.id === "t5") {
      st = stamp("Sent on its own", "success", { fresh: current && step === "sent" });
      extra = `<div class="turn__why">${sure(t.confidence, 80, { compact: true })}<span>${esc(t.decision_why)}.</span></div>`;
      if (current && step === "sent") actions = `<div class="turn__act"><button class="btn" data-act="reh-mark" data-v="me">${icons.check}That's me</button><button class="btn btn-quiet" data-act="reh-outcome">See the outcome${icons.arrow}</button></div>`;
    }
    return `<li class="turn turn--twin ${past ? "turn--past" : "is-current"} ${current ? "is-new" : ""}" data-turn="${t.id}">
      <div class="turn__who">${portrait("P", { size: 26 })}<b>Partnerships</b><span>as Alex</span><span class="turn__at">${at(t.at_s)}</span>${st}</div>
      ${body}${extra}${actions}
    </li>`;
  }

  function outcome() {
    const o = R.outcome;
    const row = o.filed.row;
    const chore = D.setup.chorePresets.find((c) => c.id === o.filed.chore);
    return `<div class="outcome is-new" data-state="resolved">
      <div class="outcome__h">${stamp("Resolved", "success", { fresh: true })}<b>Lumen Vale said yes.</b></div>
      <p class="outcome__s">${icons.notion}The "${esc(chore.name)}" chore added a row to <b>${esc(o.filed.where)}</b></p>
      <table class="filed"><thead><tr>${Object.keys(row).map((k) => `<th>${esc(k)}</th>`).join("")}</tr></thead><tbody><tr>${Object.values(row).map((v) => `<td>${esc(v)}</td>`).join("")}</tr></tbody></table>
      <div class="turn__act"><button class="btn btn-primary" data-act="golive">Go live: issue the document${icons.arrow}</button><button class="btn btn-quiet" data-act="reh-alt">Try it another way</button></div>
    </div>`;
  }
  function handed() {
    const a = R.stuck_alternative;
    return `<div class="outcome is-new" data-state="handed">
      <div class="outcome__h">${stamp("Handed back to you", "human", { fresh: true })}<b>It stopped instead of answering.</b></div>
      <p class="outcome__s">${esc(a.why)}</p>
      <div class="turn__act"><button class="btn btn-primary" data-act="golive">Good. Go live${icons.arrow}</button><button class="btn" data-act="reh-replay">${icons.retry}Replay the usual path</button></div>
    </div>`;
  }

  TP.renderPractice = function () {
    const r = TP.S.su.reh;
    const step = r.step;
    const seen = TP.stepTurns[step] || [];
    const lastTwin = [...seen].reverse().find((id) => T(id).side === "twin");
    const focusTwin = ["waits", "held", "editing", "edited", "sent"].includes(step) ? lastTwin : null;
    const items = [];
    for (const id of seen) {
      const t = T(id);
      if (t.side === "creator") {
        if (r.alt && id === "t2") items.push(creator(R.stuck_alternative.creator_text, t.at_s, step === "handed"));
        else items.push(creator(t.text, t.at_s, step === "w3" && id === "t2"));
      } else items.push(twin(t, step, id === focusTwin));
    }
    if (step === "w1") items.push(writing("Writing its first message", T("t1").elapsed_s));
    if (step === "w3") items.push(writing("Writing a reply", T("t3").elapsed_s));
    if (step === "w5") items.push(writing("Writing a reply", T("t5").elapsed_s));
    if (step === "c2" || step === "c4") items.push(typing());
    const lastAt = seen.length ? T(seen[seen.length - 1]).at_s : 0;
    const mission = D.setup.frames[11].pieces.find((p) => p.id === "p_ms");
    return `<section class="practice" aria-label="Practice page">
      <header class="practice__h">
        <span class="practice__icon">${icons.notion}</span>
        <div><b>Practice: Lumen Vale</b><span>Notion practice page · ${esc(R.played_by)} · ${at(lastAt)} in</span></div>
        <span class="practice__m"><span>Mission</span>${esc(mission.label)}</span>
      </header>
      <ol class="turns" id="turns">${items.join("")}</ol>
      ${step === "resolved" ? outcome() : ""}${step === "handed" ? handed() : ""}
    </section>`;
  };
  // keep the newest turn in view inside the practice page (the page itself never scrolls)
  TP.afterPractice = function () {
    const list = document.getElementById("turns");
    if (!list) return;
    const cur = list.querySelector(".is-current") || list.lastElementChild;
    if (!cur) return;
    // .turns is position: relative, so offsetTop is measured inside the list
    const top = cur.offsetTop - 8;
    const bottom = cur.offsetTop + cur.offsetHeight - list.clientHeight + 12;
    list.scrollTop = Math.max(0, Math.min(top, bottom));
  };
})();
