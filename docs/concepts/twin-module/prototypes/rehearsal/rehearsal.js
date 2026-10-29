// Rehearsal - the dress rehearsal: the same script played for real on the Notion practice page.
// Beats turn into turns: it waits, it is held (risk list, the edit, what it learned), it sends alone,
// the outcome is filed; or they ask for money and it hands the conversation back.
(function () {
  const { D, R, esc, icon, clock, secs, fillLine } = window.U;
  const RH = D.setup.rehearsal;
  const T = Object.fromEntries(RH.turns.map((t) => [t.id, t]));
  const ORDER = ["running", "waits", "cue2", "drafting3", "held", "editing", "edited", "cue4", "drafting5", "sent", "filing", "resolved"];
  const at = (rh, step) => ORDER.indexOf(rh.step) >= ORDER.indexOf(step);
  const FACTOR = 3; // plays three times faster than real; the seconds shown are real

  function fresh() {
    return { step: "running", marks: {}, texts: {}, learned: false, alt: false, editing: null, shown: 0, note: "" };
  }

  // What the practice page shows for a turn: "hidden" | "typing" | "drafting" | "shown".
  function turnState(rh, id) {
    if (rh.alt) {
      if (id === "t1") return "shown";
      if (id === "t2") return "shown";
      return "hidden";
    }
    switch (id) {
      case "t1":
        return rh.step === "running" ? "drafting" : "shown";
      case "t2":
        return rh.step === "cue2" ? "typing" : at(rh, "drafting3") ? "shown" : "hidden";
      case "t3":
        return rh.step === "drafting3" ? "drafting" : at(rh, "held") ? "shown" : "hidden";
      case "t4":
        return rh.step === "cue4" ? "typing" : at(rh, "drafting5") ? "shown" : "hidden";
      case "t5":
        return rh.step === "drafting5" ? "drafting" : at(rh, "sent") ? "shown" : "hidden";
      case "outcome":
        return rh.step === "filing" ? "drafting" : rh.step === "resolved" ? "shown" : "hidden";
    }
  }
  // The turn the person acts on now.
  function current(rh) {
    if (rh.alt) return "t2";
    return { running: "t1", waits: "t1", cue2: "t2", drafting3: "t3", held: "t3", editing: rh.editing || "t3", edited: "t3", cue4: "t4", drafting5: "t5", sent: "t5", filing: "outcome", resolved: "outcome" }[rh.step];
  }
  const clockAt = (rh) => {
    if (rh.alt) return 16;
    const vis = RH.turns.filter((t) => turnState(rh, t.id) === "shown");
    const last = vis[vis.length - 1];
    return last ? last.at_s + (last.elapsed_s || 2) : rh.shown;
  };

  // ---------- the practice page (script column) ----------
  function columnHTML(su, m) {
    const rh = su.rh;
    return `<section class="script-col rehearsing" aria-label="The practice page">
      <header class="script-head">
        <div><span class="eyebrow">${icon("notion")}Practice page, in Notion</span><span class="mission ink">${esc(m.pieces.find((p) => p.id === "p_ms").label)}</span></div>
        <div class="tally"><span>${esc(RH.played_by)}</span><span class="clock">${icon("clock")}<b data-tick="rclock">${clock(clockAt(rh))}</b></span></div>
      </header>
      <ol class="beats">${R.beats.map((b, i) => beatHTML(b, i, m, su)).join("")}</ol>
    </section>`;
  }

  function badgeFor(t, rh) {
    if (t.decision === "sent_alone") return `<span class="badge" data-tone="success">${icon("send")}Sent on its own</span>`;
    if (t.risks.length) return `<span class="badge" data-tone="warning">${icon("warn")}Held: waits for your signature</span>`;
    return `<span class="badge" data-tone="human">${icon("pen")}Waits for your signature</span>`;
  }
  function markFor(rh, id) {
    const mk = rh.marks[id];
    if (mk === "me") return `<span class="badge solid" data-tone="human">${icon("check")}That's me</span>`;
    if (mk === "edited") return `<span class="badge solid" data-tone="human">${icon("pen")}You edited it</span>`;
    return "";
  }

  function beatHTML(b, i, m, su) {
    const rh = su.rh;
    const id = b.turn;
    const st = turnState(rh, id);
    const cur = current(rh) === id;
    const no = `<span class="beat-no lit ${st === "shown" ? "done" : ""}">${i + 1}</span>`;
    const cls = `beat ${b.side} ${st} ${cur ? "focus current" : ""}`;
    if (st === "hidden") {
      // still the script: what comes next, in pencil
      const l = window.Script.lineOf(b.id, m.f);
      const body = b.side === "creator" ? `<div class="cue"><span class="who">${esc(R.names.artist)}</span><span class="cue-t">${esc(b.cue)}</span></div>` : b.side === "chore" ? `<div class="cue"><span class="cue-t">${esc(b.title)}: a row in Notion: Partnerships</span></div>` : `<header><h3>${esc(b.title)}</h3><span class="faint small">to come</span></header>${l ? `<p class="line pencil clamp1"><span class="txt">${fillLine(l.text, true)}</span></p>` : ""}`;
      return `<li class="${cls} tocome" data-beat="${b.id}">${no}<div class="beat-body">${body}</div></li>`;
    }
    if (b.side === "creator") {
      const text = rh.alt ? RH.stuck_alternative.creator_text : T[id].text;
      const inner = st === "typing" ? `<span class="dots">${esc(R.names.artist)} is writing</span>` : esc(text);
      return `<li class="${cls}" data-beat="${b.id}">${no}<div class="beat-body"><div class="said ${App.isNew("said:" + id + rh.alt) ? "arrive" : ""}"><span class="who">${esc(R.names.artist)} <span class="faint">(Athena playing)</span></span><p class="${cur ? "" : "one"}">${inner}</p></div></div></li>`;
    }
    if (b.side === "chore") {
      const filed = RH.outcome.filed;
      const cells = Object.entries(filed.row)
        .map(([k, v]) => `<span class="cell"><small>${esc(k)}</small>${st === "shown" ? `<b>${esc(v)}</b>` : `<span class="ghost"></span>`}</span>`)
        .join("");
      return `<li class="${cls}" data-beat="${b.id}">${no}<div class="beat-body"><header><h3>${esc(b.title)}</h3>${st === "shown" ? `<span class="badge" data-tone="success">${icon("check")}Filed to ${esc(filed.where)}</span>` : `<span class="faint small dots">Filing</span>`}</header>
        <div class="notion-row ${st === "shown" ? "ink filed" : "pencil"} ${App.isNew("filed" + st) ? "arrive" : ""}">${cells}</div></div></li>`;
    }
    const t = T[id];
    if (st === "drafting") {
      return `<li class="${cls}" data-beat="${b.id}">${no}<div class="beat-body"><header><h3>${esc(b.title)}</h3><span class="faint small"><span class="dots">Writing</span> <span data-tick="rdraft">${secs(rh.shown)}</span></span></header>
        <div class="line drafting"><span class="ghost"></span><span class="ghost"></span><span class="ghost short"></span></div></div></li>`;
    }
    const mk = rh.marks[id];
    const text = rh.texts[id] || t.text;
    const editedBy = mk === "edited";
    const inkCls = mk ? "ink" : "pencil";
    const lineCls = cur ? "full" : "clamp";
    return `<li class="${cls}" data-beat="${b.id}">${no}<div class="beat-body"><header><h3>${esc(b.title)}</h3>${badgeFor(t, rh)}${markFor(rh, id)}</header>
      <p class="line ${inkCls} ${lineCls} ${App.isNew("turn:" + id + ":" + (mk || "")) ? "arrive" : ""}"><span class="txt">${fillLine(text, true)}</span></p>
      ${editedBy && id === "t3" && rh.learned ? `<p class="learned small">${icon("spark")}It learned: ${esc(t.learned)}</p>` : ""}</div></li>`;
  }

  // ---------- the prompt desk (prop column) ----------
  function sureHTML(t, bar) {
    const under = bar != null && t.confidence < bar;
    return `<div class="sure ${under ? "under" : ""}"><span>How sure it is</span><span class="track"><span class="fill" style="width:${t.confidence}%"></span>${bar != null ? `<span class="bar" style="left:${bar}%" title="your bar"></span>` : ""}</span><span><b>${t.confidence}</b>${bar != null ? ` / bar ${bar}` : ""}</span></div>`;
  }
  function risksHTML(t) {
    if (!t.risks.length) return `<p class="risks none">${icon("check")}Its risk list is empty.</p>`;
    return `<div class="risks"><span class="eyebrow">Its risk list</span><ul>${t.risks.map((r) => `<li>${icon("warn")}${esc(r)}</li>`).join("")}</ul></div>`;
  }
  function decisionHTML(id, rh) {
    const t = T[id];
    const bar = t.kind === "first_message" ? null : 80;
    const acts =
      id === "t1"
        ? `<button type="button" class="btn btn-primary" data-act="r-me">${icon("check")}That's me</button><button type="button" class="btn" data-act="r-edit" data-id="t1">Not me</button><button type="button" class="btn btn-quiet" data-act="r-edit" data-id="t1">${icon("pencil")}Edit</button>`
        : id === "t3"
        ? `<button type="button" class="btn btn-primary" data-act="r-edit" data-id="t3">${icon("pencil")}Put it in my words</button><button type="button" class="btn" data-act="r-me">That's me, send it</button><button type="button" class="btn btn-quiet" data-act="r-edit" data-id="t3">Not me</button>`
        : `<button type="button" class="btn btn-primary" data-act="r-me">${icon("check")}That's me</button><button type="button" class="btn" data-act="r-edit" data-id="t5">Not me</button>`;
    return `<div class="decision">${sureHTML(t, bar)}${risksHTML(t)}<p class="why-line">${icon(t.decision === "sent_alone" ? "send" : "pen")}<span>${esc(t.decision_why)}${t.kind === "first_message" ? ". It was " + t.confidence + " sure; first messages have no bar." : ""}</span></p><div class="acts">${acts}</div></div>`;
  }
  function deskBody(su) {
    const rh = su.rh;
    if (rh.alt) {
      const a = RH.stuck_alternative;
      return `<div class="handed arrive"><span class="badge" data-tone="warning">${icon("hand")}Handed back to you</span><p class="said-q">"${esc(a.creator_text)}"</p><p>${esc(a.why)}</p>
        <div class="acts"><button type="button" class="btn btn-primary" data-act="r-yes">${icon("back")}Back to the yes path</button><button type="button" class="btn" data-act="r-self">I'll answer it myself</button></div></div>`;
    }
    switch (rh.step) {
      case "running":
      case "drafting3":
      case "drafting5":
        return `<div class="working"><span class="spin-ring" aria-hidden="true"></span><div><b>${rh.step === "running" ? "Writing its first message" : rh.step === "drafting3" ? "Writing its answer" : "Writing its thanks"}</b><span class="faint small"><span data-tick="rdesk">${secs(rh.shown)}</span> so far. A real reply takes 3 to 8 seconds.</span></div></div>`;
      case "cue2":
      case "cue4":
        return `<div class="working"><span class="spin-ring" aria-hidden="true"></span><div><b>Athena is playing ${esc(R.names.artist)}</b><span class="faint small">Writing their reply on the practice page.</span></div></div>`;
      case "waits":
        return decisionHTML("t1", rh);
      case "held":
        return decisionHTML("t3", rh);
      case "sent":
        return decisionHTML("t5", rh);
      case "editing": {
        const id = rh.editing;
        const t = T[id];
        return `<div class="editing"><label class="eyebrow" for="redit">In your words</label><textarea class="field" id="redit" data-keep="redit" rows="6">${esc(rh.draft ?? t.text)}</textarea>
          <div class="acts"><button type="button" class="btn btn-primary" data-act="r-save">${icon("check")}Save, it learns from this</button>${id === "t3" ? `<button type="button" class="btn" data-act="r-example">Use the example edit</button>` : ""}<button type="button" class="btn btn-quiet" data-act="r-cancel">Cancel</button></div></div>`;
      }
      case "edited": {
        const t = T.t3;
        return `<div class="learnt arrive"><span class="eyebrow">What it learned</span><p class="ink lesson">${icon("spark")}<span>${esc(rh.learned ? t.learned : "Your wording, for this beat")}</span></p><p class="faint small">${rh.learned ? "It joins how it sounds, in your ink, in the wings." : "Only the answer to Lumen's question teaches it something new in this example."}</p>
          <div class="acts"><button type="button" class="btn btn-primary" data-act="r-on">Carry on${icon("arrow")}</button></div></div>`;
      }
      case "filing":
        return `<div class="working"><span class="spin-ring" aria-hidden="true"></span><div><b>Filing the outcome</b><span class="faint small">The "File the outcome" chore adds a row to Notion: Partnerships.</span></div></div>`;
      case "resolved":
        return `<div class="resolved arrive"><span class="badge" data-tone="success">${icon("check")}Mission resolved</span><p>${esc(R.names.artist)} said yes, and the row is filed. Three drafts, one edit, one sent on its own.</p>
          <button type="button" class="btn btn-primary wide" data-act="golive">${icon("play")}Go live</button><button type="button" class="btn btn-quiet" data-act="r-again">Rehearse once more</button></div>`;
    }
    return "";
  }
  function deskHTML(su) {
    const rh = su.rh;
    const tally = Object.values(rh.marks);
    const me = tally.filter((x) => x === "me").length, ed = tally.filter((x) => x === "edited").length;
    const canAlt = !rh.alt && rh.step !== "resolved" && rh.step !== "editing";
    return `<section class="prop plane desk"><header class="prop-head"><span class="eyebrow">Dress rehearsal</span><h2>${rh.alt ? "It stopped" : rh.step === "resolved" ? "It worked" : "Your mark"}</h2></header>
      <div class="prop-body">${deskBody(su)}</div>
      <footer class="prop-foot"><span><b>${me}</b> that's me, <b>${ed}</b> edited, <b>0</b> not me</span>${canAlt ? `<button type="button" class="linkish" data-act="r-alt">${icon("hand")}What if they ask for money?</button>` : ""}</footer></section>`;
  }

  // ---------- go live ----------
  function goliveHTML() {
    const g = D.setup.golive;
    return `<div class="curtain"><section class="golive coat arrive" role="dialog" aria-label="Partnerships is live">
      <span class="badge" data-tone="success">${icon("check")}Live</span><h2>Partnerships is live</h2><p>${esc(g.line)}</p>
      <ul>${g.stays.map((s) => `<li class="ink">${esc(s)}</li>`).join("")}</ul>
      <button type="button" class="btn btn-primary wide" data-act="to-overview-after">Open your twins page${icon("arrow")}</button></section></div>`;
  }

  // ---------- Athena's panel during the rehearsal ----------
  function talk(su) {
    const rh = su.rh;
    if (su.golive) return { line: D.setup.golive.line, ask: { text: "Anything else before you go?", suggestions: ["Open my twins page", "Set up another twin", "Not now"] } };
    if (rh.alt) return R.rehearsal.handed;
    const map = { running: "running", cue2: "running", drafting3: "running", waits: "waits", held: "held", editing: "editing", edited: "edited", cue4: "running", drafting5: "running", sent: "sent", filing: "running", resolved: "resolved" };
    const base = R.rehearsal[map[rh.step]];
    const lines = { cue2: "Your first message is signed. Now I'm Lumen, replying.", drafting3: "Lumen asked what they'd get and whether it's exclusive. It's writing its answer.", cue4: "Your answer is in. I'm writing Lumen's yes.", drafting5: "Lumen said yes. It's writing its thanks.", filing: "That's me, noted. Filing the outcome to Notion." };
    return { line: lines[rh.step] || base.line, ask: base.ask };
  }

  window.Rehearsal = { fresh, columnHTML, beatHTML, deskHTML, goliveHTML, talk, turnState, current, T, ORDER, FACTOR };
})();
