// Mirror - the setup page. The main area is a mirror: you on one side (your own sent mail or your
// inked words), your twin's reply to Wren on the other, converging as you answer. The twin's parts
// sit in the margin and point at the words they shape. Athena's panel is at the bottom (chat.js).
(function () {
  const TP = window.TP, D = TP.D, V = TP.V, esc = TP.esc, F = D.setup.frames;
  const su = () => TP.S.su;

  TP.suInit = () => ({
    phase: "describe", frame: -1, inked: new Set(), gmail: "idle", gmailT: 0, notion: "idle", notionKey: "", whereOpen: false,
    picks: {}, dials: {}, dialSrc: {}, preset: null, auto2: null, mem: null, note: null, history: [], youTab: "panel",
    youSample: "s1", reh: null, pending: null, fresh: false, popPlace: null, hover: null, replay: null, readyFlash: false, auto: false, showDials: false,
  });

  const said = (i) => (i === 0 ? D.setup.need : F[i - 1].ask.suggestions[F[i].user.choice]);
  TP.suAt = (n, extra = {}) => {
    const s = TP.suInit();
    s.frame = n;
    s.phase = n === 11 ? "rehearsal" : "frame";
    for (let i = 0; i <= n; i++) s.history.push({ who: "you", text: said(i) }, { who: "her", text: F[i].line });
    if (n >= 2) s.gmail = "connected";
    if (n >= 5) { s.notion = "connected"; s.notionKey = "ntn_4f1c9a77e2b04d6c8a1b"; }
    if (extra.dials) for (const id of Object.keys(extra.dials)) s.dialSrc[id] = "you";
    Object.assign(s, extra);
    return s;
  };

  // coverage from what is on screen (an early ink counts)
  TP.coverageNow = (k) => {
    const pcs = TP.piecesAt(k), out = {};
    for (const p of D.places) { const m = pcs.filter((x) => x.place === p.id); out[p.id] = m.some((x) => x.ink) ? 1 : m.length ? 0.5 : 0; }
    return out;
  };

  // ---- the mirror ----
  const likeness = (k) => (k < 0 ? 0 : F[k].readiness);
  const plaque = (k) => {
    const v = likeness(k);
    const s = su();
    const label = s.replay !== null ? `after answer ${s.replay + 1}` : k < 0 ? "no twin yet" : "sounds like you";
    return `<div class="plaque" id="plaque" title="How much of what it needs to sound like you it has so far">
      <span class="pl-k">Likeness</span><span class="pl-bar" aria-hidden="true"><i style="width:${v}%;--mix:${v}%"></i></span><strong>${v}%</strong><span class="pl-s">${label}</span>
      ${k >= 3 ? `<button class="btn btn-quiet btn-mini" data-act="replay" ${s.replay !== null ? "disabled" : ""}>${TP.icon("replay")}Replay</button>` : ""}</div>`;
  };

  const youPane = (k) => {
    const s = su(), f = F[k];
    const panel = s.showDials && k >= 3 ? { kind: "style" } : f?.panel && f.panel.kind !== "rehearsal" ? f.panel : null;
    const tabs = panel ? `<div class="you-tabs" role="tablist"><button role="tab" aria-selected="${s.youTab === "panel"}" data-act="you-tab" data-t="panel">${esc(panel.kind === "connect" ? (panel.channel === "gmail" ? "Sign in" : "Notion key") : TP.panelTitle[panel.kind])}</button><button role="tab" aria-selected="${s.youTab === "you"}" data-act="you-tab" data-t="you">${s.gmail === "connected" && k >= 2 ? "Your mail" : "Your words"}</button>${s.showDials ? `<button class="btn btn-quiet icon-btn" data-act="dials" aria-label="Close the dials">${TP.icon("x")}</button>` : ""}</div>` : "";
    const body = panel && s.youTab === "panel" ? `<div class="panel pn-${panel.kind}">${TP.panelHTML(panel)}</div>` : youWords(k);
    return `<section class="m-you" aria-label="You">${tabs}<div class="you-body">${body}</div></section>`;
  };

  const youWords = (k) => {
    const s = su();
    if (k < 0) return `<div class="you-empty"><p class="ye-h">You</p><p>What you tell Athena shows here in your own colour. Once you sign in with Google, a mail you wrote yourself stands here, and your twin learns your voice from it.</p></div>`;
    const mine = TP.piecesAt(k).filter((p) => p.origin === "you" && ["who", "voice", "never"].includes(p.place));
    const words = `<div class="your-words"><p class="yw-h">In your words</p>${mine.map((p) => `<span class="yw ${TP.changedAt(k).has(p.id) ? "chg" : ""}" data-ev="${p.id}">${esc(p.label)}</span>`).join("")}</div>`;
    if (s.gmail !== "connected" || k < 2) {
      return `<div class="you-need"><p class="yw-h">You said</p><blockquote>${esc(D.setup.need)}</blockquote></div>${words}
        <div class="you-ghost">${TP.icon("mail")}<p>A mail you wrote yourself will stand here once you sign in with Google. It learns your voice only from your own sent mail.</p></div>`;
    }
    const g = s.picks.samples;
    const kept = D.setup.samples.filter((x) => (g ? g[x.id].on : x.mark) && V.samplesFull[x.id]);
    if (!kept.some((x) => x.id === s.youSample)) s.youSample = kept[0]?.id || "s1";
    return `<div class="sample-tabs" role="tablist" aria-label="Your sent mail">${kept.map((x) => `<button role="tab" aria-selected="${x.id === s.youSample}" data-act="you-sample" data-id="${x.id}">${esc(x.to)}</button>`).join("")}</div>
      ${TP.sampleHTML(s.youSample, k)}${mine.length > 2 ? words : ""}`;
  };

  const twinPane = (k) => {
    const s = su(), x = V.inbound;
    const changed = TP.changedAt(k);
    const pcs = TP.piecesAt(k).filter((p) => changed.has(p.id));
    let caption = "";
    if (k >= 0 && s.replay === null) {
      const inDraft = pcs.filter((p) => V.drafts[k].includes(`{${p.id}|`) || V.drafts[k].includes(`{-${p.id}|`) || ["p_gmail", "p_a1", "p_c1"].includes(p.id) || ["knowledge", "never"].includes(p.place));
      caption = inDraft.length
        ? `<p class="caption"><span class="cap-k">Your last answer changed</span>${inDraft.slice(0, 4).map((p) => `<span class="cap ${p.ink ? "ink" : "pencil"}">${esc(p.label)}</span>`).join("")}${inDraft.length > 4 ? `<span class="cap-more">and ${inDraft.length - 4} more</span>` : ""}</p>`
        : `<p class="caption"><span class="cap-k">No change to the words.</span> This answer shaped ${esc(TP.placeLabel(F[k].ask?.place || "who").toLowerCase())}.</p>`;
      if (Object.keys(s.dials).length && k >= 3) caption += `<p class="caption cap-dials"><span class="cap ink">Your dials</span> rewrote the words underlined in your colour.</p>`;
    }
    return `<section class="m-twin ${s.phase === "thinking" || s.phase === "slow" ? "rewriting" : ""}" aria-label="Your twin">
      <div class="inbound"><p class="ib-who"><strong>${esc(x.from)}</strong> wrote · ${TP.rel(x.at)}</p><p class="ib-text">${esc(x.text)}</p></div>
      <div id="twin-draft">${TP.draftHTML(s.replay !== null ? s.replay : k, s.replay !== null ? { noGone: true } : {})}</div>${caption}
    </section>`;
  };

  const marginalia = (k) => {
    const s = su();
    const pcs = TP.piecesAt(k), changed = TP.changedAt(k), cov = TP.coverageNow(k);
    const pencil = pcs.filter((p) => !p.ink);
    return `<aside class="m-margin" aria-label="What your twin is made of">
      <ol class="mrows">${D.places.map((pl) => {
        const mine = pcs.filter((p) => p.place === pl.id);
        const last = mine[mine.length - 1];
        const c = cov[pl.id];
        const chg = mine.some((p) => changed.has(p.id));
        const pen = mine.filter((p) => !p.ink).length;
        return `<li><button class="mrow cov-${String(c).replace(".", "")}${chg ? " chg" : ""}${s.popPlace === pl.id ? " pop" : ""}" data-act="place" data-place="${pl.id}" aria-expanded="${s.popPlace === pl.id}">
          <span class="m-glyph" aria-hidden="true"></span>
          <span class="m-l">${esc(pl.label)}${mine.length ? ` <em>${mine.length}</em>` : ""}${pl.required === 0 ? ` <i>optional</i>` : ""}</span>
          <span class="m-p ${last ? (last.ink ? "ink" : "pencil") : "none"}">${last ? esc(last.label) : "Not yet"}</span>
          ${pen ? `<span class="m-pen" title="${pen} of her proposals still in pencil">${TP.icon("pen")}${pen}</span>` : ""}
        </button></li>`;
      }).join("")}</ol>
      <div class="m-foot">${pencil.length ? `<button class="btn btn-mini ink-all" data-act="ink-all">${TP.icon("pen")}Ink all her pencil (${pencil.length})</button>` : k >= 0 ? `<p class="m-done">${TP.icon("check")}Nothing left in pencil</p>` : ""}</div>
    </aside>`;
  };

  const popover = (k) => {
    const s = su();
    if (!s.popPlace) return "";
    const pcs = TP.piecesAt(k).filter((p) => p.place === s.popPlace);
    const who = (p) => (p.origin === "you" ? "in your words" : p.ink ? "her proposal, inked by you" : "her proposal, in pencil");
    return `<div class="popover" role="dialog" aria-label="${esc(TP.placeLabel(s.popPlace))}" id="popover">
      <p class="po-h">${esc(TP.placeLabel(s.popPlace))}<button class="btn btn-quiet icon-btn" data-act="place" data-place="${s.popPlace}" aria-label="Close">${TP.icon("x")}</button></p>
      ${pcs.length ? pcs.map((p) => `<div class="pc ${p.ink ? "ink" : "pencil"}"><p class="pc-l">${esc(p.label)}</p>
        <p class="pc-s">${p.detail ? esc(p.detail) + " · " : ""}${who(p)}</p>
        ${p.evidence ? `<p class="pc-s">From your mail to ${p.evidence.map((e) => esc(TP.sampleById(e).to)).join(", ")}</p>` : ""}
        ${p.ink ? "" : `<button class="btn btn-mini" data-act="ink" data-id="${p.id}">${TP.icon("pen")}Ink it</button>`}</div>`).join("") : `<p class="pc-s">Nothing here yet. She will ask about it.</p>`}
    </div>`;
  };

  const mirrorHTML = () => {
    const s = su(), k = s.frame;
    const name = TP.piecesAt(k).find((p) => p.id === "p_name");
    return `<div class="m-head">
        <p class="mh-you"><i class="dot-you"></i>You</p>
        ${plaque(s.replay !== null ? s.replay : k)}
        <p class="mh-twin">Your twin${name ? ` <span class="tw-name ${name.ink ? "ink" : "pencil"}">${esc(name.label)}</span>` : ""}${k >= 3 && !s.showDials ? `<button class="btn btn-quiet btn-mini" data-act="dials">${TP.icon("dial")}Dials</button>` : ""}<i class="dot-twin"></i></p>
      </div>
      <div class="m-body">${youPane(k)}<div class="m-seam" aria-hidden="true"></div>${twinPane(k)}${marginalia(k)}</div>
      ${s.readyFlash || (k === D.setup.first_ready_frame && s.phase === "frame" && s.fresh) ? `<p class="ready-ribbon" role="status">${TP.icon("check")}It has what it needs. Rehearse it now, or keep going.</p>` : ""}
      ${popover(k)}`;
  };

  TP.renderSetup = (el = TP.$("#page-setup")) => {
    const s = su();
    const reh = s.phase === "rehearsal";
    const keepFocus = document.activeElement?.id;
    el.innerHTML = `<div class="setup">
      <div class="mirror coat-lite ${reh ? "is-reh" : ""} ${s.fresh ? "arrive" : ""}" id="mirror">${reh ? TP.rehearsalHTML() : mirrorHTML()}<svg class="leaders" id="leaders" aria-hidden="true"></svg></div>
      ${TP.chatHTML()}</div>`;
    s.fresh = false;
    if (keepFocus) { const f = document.getElementById(keepFocus); if (f && f.tagName !== "BUTTON") f.focus(); }
    requestAnimationFrame(() => TP.redrawLeaders());
    const thread = TP.$(".thread");
    if (thread) thread.scrollTop = thread.scrollHeight;
  };

  // ---- leaders: the margin points at the words it shapes; your mail points at what it taught ----
  TP.redrawLeaders = () => {
    const svg = TP.$("#leaders"), m = TP.$("#mirror");
    if (!svg || !m || TP.S.page !== "setup") return;
    const s = su();
    svg.innerHTML = "";
    if (s.phase === "rehearsal" || s.replay !== null || s.frame < 0) return;
    const mr = m.getBoundingClientRect();
    svg.setAttribute("viewBox", `0 0 ${mr.width} ${mr.height}`);
    const pcs = TP.piecesAt(s.frame);
    let lead;
    if (s.hover) lead = pcs.filter((p) => (s.hover.place ? p.place === s.hover.place : p.id === s.hover.id));
    else { const c = TP.changedAt(s.frame); lead = pcs.filter((p) => c.has(p.id)); }
    const draft = TP.$("#twin-draft .draft");
    if (!draft) return;
    const dr = draft.getBoundingClientRect();
    let out = "", n = 0;
    const seen = new Set();
    for (const p of lead) {
      const row = TP.$(`.mrow[data-place="${p.place}"]`);
      let tgt = TP.$(`#twin-draft [data-piece="${p.id}"]:not(.sp-gone)`) || TP.$(`#twin-draft [data-place="${p.place}"]`);
      if (!row || !tgt) continue;
      const rects = [...tgt.getClientRects()];
      if (!rects.length) continue;
      const top = Math.min(...rects.map((r) => r.top)) - mr.top, bot = Math.max(...rects.map((r) => r.bottom)) - mr.top;
      const key = `${Math.round(top)}-${p.place}`;
      const cls = p.ink ? "ld-ink" : "ld-pencil";
      if (!seen.has(key)) {
        seen.add(key);
        const bx = dr.right - mr.left + 6 + (n++ % 3) * 4;
        const rr = row.getBoundingClientRect();
        const rx = rr.left - mr.left - 2, ry = rr.top - mr.top + rr.height / 2, my = (top + bot) / 2;
        out += `<path class="${cls} br" d="M${bx - 3} ${top + 1} h3 V${bot - 1} h-3"/>`;
        out += `<path class="${cls}" d="M${bx} ${my} C ${bx + (rx - bx) * 0.55} ${my}, ${rx - (rx - bx) * 0.45} ${ry}, ${rx} ${ry}"/><circle class="${cls} dot" cx="${rx}" cy="${ry}" r="2.5"/>`;
      }
      // reflection lines: from the phrase in your mail to the words it shaped
      const ev = TP.$(`.m-you [data-ev="${p.id}"]`);
      const sp = TP.$(`#twin-draft [data-piece="${p.id}"]:not(.sp-gone)`);
      if (ev && sp) {
        const er = ev.getClientRects()[0], sr = sp.getClientRects()[0];
        if (er && sr) {
          const ex = ev.getBoundingClientRect().right - mr.left, ey = er.top - mr.top + er.height / 2;
          const sx = sr.left - mr.left - 2, sy = sr.top - mr.top + sr.height / 2;
          out += `<path class="${cls} refl" d="M${ex} ${ey} C ${ex + 40} ${ey}, ${sx - 40} ${sy}, ${sx} ${sy}"/>`;
        }
      }
    }
    svg.innerHTML = out;
  };

  // hover: a part of the twin lights its leaders
  document.addEventListener("mouseover", (e) => {
    if (TP.S.page !== "setup") return;
    const s = su();
    const row = e.target.closest(".mrow"), sp = e.target.closest("#twin-draft [data-piece], .m-you [data-ev]");
    const h = row ? { place: row.dataset.place } : sp ? { id: sp.dataset.piece || sp.dataset.ev } : null;
    if (JSON.stringify(h) !== JSON.stringify(s.hover)) { s.hover = h; TP.redrawLeaders(); }
  });

  // ---- actions ----
  TP.act.place = (el) => { const s = su(); s.popPlace = s.popPlace === el.dataset.place ? null : el.dataset.place; TP.renderSetup(); };
  TP.closePopover = () => { const s = su(); if (!s.popPlace) return false; s.popPlace = null; TP.renderSetup(); return true; };
  TP.act.ink = (el) => { su().inked.add(el.dataset.id); TP.renderSetup(); };
  TP.act["ink-all"] = () => { const s = su(); TP.piecesAt(s.frame).filter((p) => !p.ink).forEach((p) => s.inked.add(p.id)); s.popPlace = null; TP.renderSetup(); };
  TP.act["you-tab"] = (el) => { su().youTab = el.dataset.t; TP.renderSetup(); };
  TP.act["you-sample"] = (el) => { su().youSample = el.dataset.id; TP.renderSetup(); };
  TP.act.dials = () => { const s = su(); s.showDials = !s.showDials; s.youTab = "panel"; TP.renderSetup(); };

  // Replay: the reflection runs through every version up to now, a stranger turning into you.
  TP.act.replay = () => {
    const s = su(), end = s.frame;
    s.replay = 0;
    TP.renderSetup();
    const step = () => {
      const d = TP.$("#twin-draft"), pl = TP.$("#plaque");
      if (!d) return;
      d.innerHTML = TP.draftHTML(s.replay, { noGone: true });
      d.firstElementChild.classList.add("morph");
      if (pl) pl.outerHTML = plaque(s.replay);
      if (s.replay >= end) { TP.later(() => { s.replay = null; TP.renderSetup(); }, 700); return; }
      s.replay++;
      TP.later(step, TP.reduced() ? 600 : 260);
    };
    TP.later(step, 120);
  };
})();
