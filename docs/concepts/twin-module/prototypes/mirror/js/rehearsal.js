// Mirror - the dress rehearsal. The mirror becomes the conversation on the Notion practice page:
// Athena plays Lumen Vale on one side, your twin speaks on the other. You mark each draft; your
// edit shows as the reflection correcting itself, and what it learned.
(function () {
  const TP = window.TP, D = TP.D, V = TP.V, esc = TP.esc;
  const R = D.setup.rehearsal, T = Object.fromEntries(R.turns.map((t) => [t.id, t]));
  const su = () => TP.S.su;
  const BAR = D.setup.autonomy.bar_default;

  const SNAP = {
    running: { shown: [], writing: "t1", marks: {} },
    waits: { shown: ["t1"], marks: {} },
    held: { shown: ["t1", "t2", "t3"], marks: { t1: "me" }, editOpen: true },
    edited: { shown: ["t1", "t2", "t3"], marks: { t1: "me", t3: "edited" }, learned: true },
    sent: { shown: ["t1", "t2", "t3", "t4", "t5"], marks: { t1: "me", t3: "edited" }, learned: true },
    resolved: { shown: ["t1", "t2", "t3", "t4", "t5"], marks: { t1: "me", t3: "edited", t5: "me" }, learned: true, outcome: true },
    handed: { shown: ["t1", "alt"], marks: { t1: "me" }, handed: true },
    golive: { shown: ["t1", "t2", "t3", "t4", "t5"], marks: { t1: "me", t3: "edited", t5: "me" }, learned: true, outcome: true, golive: true },
  };

  TP.rehAt = (step, play = false) => {
    const s = su();
    TP.clearTimers();
    s.phase = "rehearsal";
    s.reh = { step, ...JSON.parse(JSON.stringify(SNAP[step])), editText: step === "held" ? T.t3.text : null, writingT: 0 };
    if (step === "edited" || step === "sent" || step === "resolved" || step === "golive") s.reh.editText = T.t3.edited_text;
    if (step === "running") write("t1", "waits");
    TP.render();
  };

  // a twin turn being written: real seconds shown, played faster
  const write = (id, next) => {
    const s = su(), r = s.reh, t = T[id], t0 = performance.now();
    r.writing = id; r.writingT = 0;
    TP.every(() => {
      r.writingT = ((performance.now() - t0) * TP.speed) / 1000;
      const el = TP.$("#write-t");
      if (el) el.textContent = TP.secs(Math.min(r.writingT, t.elapsed_s));
    }, 100);
    TP.later(() => {
      TP.clearTimers();
      r.writing = null;
      r.shown.push(id);
      r.step = next;
      if (id === "t3") r.editOpen = true;
      TP.renderSetup();
    }, (t.elapsed_s * 1000) / TP.speed);
  };
  // Athena, as the creator, answers after a beat; then the twin writes
  const creatorThen = (cid, tid, next) => {
    const r = su().reh;
    r.typing = true;
    TP.renderSetup();
    TP.later(() => { r.typing = false; r.shown.push(cid); TP.renderSetup(); TP.later(() => { write(tid, next); TP.renderSetup(); }, 500); }, 1100);
  };

  // ---- rendering ----
  const meter = (conf) => `<span class="sure-mini" role="img" aria-label="How sure it was: ${conf}; the bar is ${BAR}"><span class="sm-track"><i class="${conf >= BAR ? "over" : "under"}" style="width:${conf}%"></i><b style="left:${BAR}%"></b></span><span><strong>${conf}</strong> sure · bar ${BAR}</span></span>`;
  const markBadge = (m) => m === "me" ? `<span class="mark mk-me">${TP.icon("check")}That's me</span>` : m === "edited" ? `<span class="mark mk-ed">${TP.icon("pen")}Edited by you</span>` : m === "not" ? `<span class="mark mk-not">Not me</span>` : "";

  const creatorRow = (text, compact, extra = "") => `<div class="tr tr-creator ${compact ? "compact" : ""}"><div class="bubble"><p class="b-who">Lumen Vale <span>played by Athena</span></p><p class="b-text">${esc(text)}</p>${extra}</div><div></div></div>`;

  const twinCard = (t, r, latest) => {
    const mark = r.marks[t.id];
    const compact = !latest && !!mark;
    const kind = t.kind === "first_message" ? "First message" : "Reply";
    const decision = t.decision === "sent_alone" ? `<span class="badge" data-tone="success">Sent on its own</span>` : mark ? `<span class="badge">Signed by you</span>` : `<span class="badge" data-tone="human">Waits for your signature</span>`;
    let body;
    if (t.id === "t3" && r.editOpen && !mark) {
      body = `<label class="sr" for="t3-edit">Your edit</label><textarea id="t3-edit" class="field ink-field" rows="4">${esc(r.editText || t.text)}</textarea>
        <div class="tt-act"><button class="btn btn-primary" data-act="reh-save">Send my edit</button><button class="btn btn-quiet" data-act="reh-mark" data-id="t3" data-m="me">Sign it as it is</button></div>`;
    } else if (t.id === "t3" && mark === "edited" && !compact) {
      const diff = TP.diffWords(t.text, r.editText || t.edited_text);
      body = `<div class="correct"><div class="c-orig"><p class="c-h">Its draft</p><p>${diff.filter((d) => d.op !== "add").map((d) => d.op === "del" ? `<del>${esc(d.t)}</del>` : esc(d.t)).join("")}</p></div>
        <div class="c-mine"><p class="c-h">Your edit</p><p>${diff.filter((d) => d.op !== "del").map((d) => d.op === "add" ? `<ins>${esc(d.t)}</ins>` : esc(d.t)).join("")}</p></div></div>
        ${r.learned ? `<p class="learned">${TP.icon("spark")}<span>It learned: <strong>${esc(t.learned)}</strong></span></p>` : ""}`;
    } else {
      body = `<p class="tt-text">${esc(mark === "edited" ? r.editText || t.edited_text : t.text).replace(/\n\n/g, "<br>")}</p>`;
    }
    const meta = compact ? "" : `<div class="tt-meta">${meter(t.confidence)}<span class="risk ${t.risks.length ? "has" : ""}">${t.risks.length ? `${TP.icon("risk")}${esc(t.risks[0])}` : "Its risk list is empty"}</span></div>
      <p class="tt-why">${decision}<span>${esc(t.decision_why)}</span></p>`;
    const marks = mark ? "" : t.id === "t3" && r.editOpen ? "" : `<div class="tt-act"><button class="btn btn-primary" data-act="reh-mark" data-id="${t.id}" data-m="me">That's me${t.decision === "waits" ? ", sign it" : ""}</button><button class="btn" data-act="reh-mark" data-id="${t.id}" data-m="not">Not me</button><button class="btn btn-quiet" data-act="reh-edit" data-id="${t.id}">${TP.icon("pen")}Edit</button></div>`;
    return `<div class="tr tr-twin ${compact ? "compact" : ""}"><div></div><div class="tt ${mark ? "marked" : "open"} ${t.risks.length && !mark ? "risky" : ""}">
      <p class="tt-who"><span>Your twin · ${kind}</span><span>written in ${TP.secs(t.elapsed_s)}</span>${markBadge(mark)}</p>${body}${meta}${marks}</div></div>`;
  };

  const writingRow = (id) => `<div class="tr tr-twin"><div></div><div class="tt writing" role="status"><p class="tt-who"><span>Your twin · ${T[id].kind === "first_message" ? "First message" : "Reply"}</span></p>
    <p class="w-lines" aria-hidden="true"><i></i><i></i><i></i></p><p class="w-t"><span class="pulse"></span>Writing · <span id="write-t">${TP.secs(Math.min(su().reh.writingT || 0, T[id].elapsed_s))}</span></p></div></div>`;

  const sideHTML = (r) => {
    const st = r.handed ? ["human", "Handed back to you"] : r.outcome ? ["success", "Resolved"] : ["info", "Open"];
    const rows = R.turns.filter((t) => r.shown.includes(t.id)).map((t) => `<li><span class="tl-s">${t.at_s} s</span><span>${t.side === "creator" ? "Lumen" : t.kind === "first_message" ? "Its first message" : "Its reply"}</span><span class="tl-d">${t.side === "twin" ? (t.decision === "sent_alone" ? "on its own" : r.marks[t.id] === "edited" ? "your edit" : r.marks[t.id] ? "signed" : "waits") : ""}</span></li>`);
    if (r.shown.includes("alt")) rows.push(`<li><span class="tl-s">14 s</span><span>Lumen asks for money</span><span class="tl-d">handed back</span></li>`);
    const row = R.outcome.filed.row;
    return `<aside class="reh-side" aria-label="The rehearsal">
      <div class="rs-card"><p class="rs-h">Mission</p><p class="rs-m">${esc(F11ms())}</p><span class="badge" data-tone="${st[0]}">${st[1]}</span></div>
      <div class="rs-card"><p class="rs-h">On the practice page</p><ol class="timeline">${rows.join("") || `<li class="muted">Starting</li>`}</ol></div>
      ${r.learned ? `<div class="rs-card rs-learned"><p class="rs-h">It learned from your edit</p><p>${esc(T.t3.learned)}</p></div>` : ""}
      ${r.outcome ? `<div class="rs-card rs-filed"><p class="rs-h">${TP.icon("page")}Filed to ${esc(R.outcome.filed.where)}</p><dl>${Object.entries(row).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl></div>` : ""}
      ${r.handed ? `<div class="rs-card rs-hand"><p class="rs-h">Why it stopped</p><p>${esc(R.stuck_alternative.why)}</p></div>` : ""}
    </aside>`;
  };
  const F11ms = () => D.setup.frames[11].pieces.find((p) => p.id === "p_ms").label;

  TP.rehearsalHTML = () => {
    const r = su().reh || { shown: [], marks: {} };
    const ids = r.shown;
    const latestTwin = [...ids].reverse().find((id) => T[id]?.side === "twin");
    let rows = ids.map((id) => {
      if (id === "alt") return creatorRow(R.stuck_alternative.creator_text, false);
      const t = T[id];
      if (t.side === "creator") return creatorRow(t.text, ids.indexOf(id) < ids.length - 2);
      return twinCard(t, r, id === latestTwin);
    }).join("");
    if (r.handed) rows += `<div class="tr tr-twin"><div></div><div class="tt handback" role="status"><p class="tt-who"><span>Your twin</span><span class="badge" data-tone="human">Handed back to you</span></p>
      <p class="tt-text">It wrote nothing. ${esc(R.stuck_alternative.why)}</p><div class="tt-meta"><span class="risk has">${TP.icon("risk")}They asked for money: it must never promise money</span></div></div></div>`;
    if (r.typing) rows += `<div class="tr tr-creator"><div class="bubble typing"><p class="b-who">Lumen Vale <span>played by Athena</span></p><p class="dots" aria-label="Athena is writing as Lumen"><i></i><i></i><i></i></p></div><div></div></div>`;
    if (r.writing) rows += writingRow(r.writing);
    const golive = r.golive ? `<div class="golive" role="dialog" aria-label="Partnerships is live"><div class="gl-card coat">${TP.seal(44)}<h2>Partnerships is live</h2><p>${esc(D.setup.golive.line.replace(/^Partnerships is live\.\s*/, ""))}</p>
      <ul>${D.setup.golive.stays.map((x) => `<li>${TP.icon("check")}${esc(x)}</li>`).join("")}</ul><button class="btn btn-primary" data-act="to-twins">See it on your twins page</button></div></div>` : "";
    return `<div class="m-head">
        <p class="mh-you"><i class="dot-ext"></i>Lumen Vale <span class="muted">· ${esc(R.played_by)}</span></p>
        <div class="plaque reh-plaque">${TP.icon("page")}<span>${esc(R.where)}</span><span class="pl-s">nothing leaves Notion</span></div>
        <p class="mh-twin">Your twin <span class="tw-name ink">Partnerships</span><i class="dot-twin"></i></p>
      </div>
      <div class="m-body reh"><div class="thread" aria-live="polite">${rows || `<p class="thread-empty">Athena is opening the practice page as Lumen Vale.</p>`}</div>${sideHTML(r)}</div>${golive}`;
  };

  // ---- the panel at the bottom during the rehearsal ----
  TP.rehChat = () => {
    const r = su().reh || { step: "running" };
    const c = V.rehearsal[r.step] || V.rehearsal.running;
    const busy = !!(r.writing || r.typing);
    const unmarked = r.shown.filter((id) => T[id]?.side === "twin" && !r.marks[id]).length;
    let needs = r.golive ? "Nothing. It is live." : r.outcome ? "Nothing. Go live when you are ready." : r.handed ? "Your answer to Lumen, or the yes path." : `Your mark on ${unmarked ? "its draft" : "its next draft"}, then the mission resolved.`;
    return {
      line: busy ? (r.typing ? "Lumen is answering. I'm playing them, so it takes a moment." : r.shown.length ? "Your twin is writing its reply." : V.rehearsal.running.line) : c.line || D.setup.golive.line,
      ask: { place: "mission", ...c.ask },
      disabled: busy,
      needs,
      exitLabel: r.golive ? "Back to your twins" : "Go live",
      exitAct: r.golive ? "to-twins" : "reh-golive",
      exitOn: !!r.outcome,
    };
  };

  // ---- actions ----
  TP.act["reh-mark"] = (el) => {
    const r = su().reh, id = el.dataset.id, m = el.dataset.m;
    r.marks[id] = m;
    r.editOpen = false;
    if (m === "not") su().note = "Not me noted: it will ask what was off. This example then carries on the staged path.";
    if (id === "t1") { r.step = "held"; return creatorThen("t2", "t3", "held"); }
    if (id === "t3") { r.step = "sent"; return creatorThen("t4", "t5", "sent"); }
    if (id === "t5") { r.step = "resolved"; r.outcome = true; return TP.renderSetup(); }
  };
  TP.act["reh-edit"] = (el) => {
    const r = su().reh;
    if (el.dataset.id === "t3") { r.editOpen = true; r.editText = T.t3.text; return TP.renderSetup(); }
    su().note = "Your edit is kept. This example teaches it only from the edit on its second reply.";
    TP.act["reh-mark"]({ dataset: { id: el.dataset.id, m: "me" } });
  };
  TP.act["reh-save"] = () => {
    const r = su().reh, v = TP.$("#t3-edit")?.value.trim() || T.t3.text;
    r.editText = v === T.t3.text.trim() ? T.t3.edited_text : v;
    if (v === T.t3.text.trim()) su().note = "You left it unchanged, so this example shows the staged edit.";
    r.marks.t3 = "edited"; r.editOpen = false; r.learned = true; r.step = "edited";
    TP.renderSetup();
  };
  TP.act["reh-golive"] = () => TP.rehAt("golive");
  TP.act["to-twins"] = () => { TP.clearTimers(); TP.S.ov = TP.ovInit("after"); TP.S.ov.open = "tw_partners"; TP.goPage("overview"); };

  TP.rehAnswer = (i, opts = {}) => {
    const s = su(), r = s.reh;
    if (!r || r.writing || r.typing) return;
    s.note = opts.text ? "This example follows one path, so she answers as the staged conversation does." : null;
    const step = r.step;
    if (step === "waits") {
      if (i === 2 || (opts.text && i < 0)) return TP.act["reh-edit"]({ dataset: { id: "t1" } });
      return TP.act["reh-mark"]({ dataset: { id: "t1", m: i === 1 ? "not" : "me" } });
    }
    if (step === "held") {
      if (i === 1) return TP.act["reh-mark"]({ dataset: { id: "t3", m: "me" } });
      if (i === 2) { r.editOpen = true; return TP.renderSetup(); }
      const ta = TP.$("#t3-edit");
      if (ta) ta.value = opts.text || T.t3.edited_text;
      return TP.act["reh-save"]();
    }
    if (step === "edited") {
      if (i === 1) { s.note = `It learned: ${T.t3.learned}. You'll find it under how it sounds.`; return TP.renderSetup(); }
      if (i === 2) { r.marks.t3 = undefined; delete r.marks.t3; r.editOpen = true; r.step = "held"; return TP.renderSetup(); }
      r.step = "sent";
      return creatorThen("t4", "t5", "sent");
    }
    if (step === "sent") return TP.act["reh-mark"]({ dataset: { id: "t5", m: i === 1 ? "not" : "me" } });
    if (step === "resolved") {
      if (i === 0 || opts.text) return TP.rehAt("golive");
      if (i === 1) return TP.rehAt("handed");
      return TP.rehAt("running");
    }
    if (step === "handed") {
      if (i === 0) { s.note = "It's yours now. On a real conversation it stops writing until you hand it back."; return TP.renderSetup(); }
      TP.rehAt("resolved");
      su().note = i === 1 ? "Noted: when money comes up, it says kindly that there is no fee, and still waits for you." : null;
      return TP.renderSetup();
    }
    if (step === "golive") {
      if (i === 2) return TP.rehAt("running");
      return TP.act["to-twins"]();
    }
  };
})();
