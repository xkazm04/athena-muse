// Mirror - the reflection: the twin's draft reply to Wren at any frame, tuned by the dials, and the
// person's own sent mail with the phrases it learned from.
(function () {
  const TP = window.TP, D = TP.D, V = TP.V, esc = TP.esc;
  const F = D.setup.frames;

  // Pieces after frame k, with ink = confirmed by the frame or inked early by the person.
  TP.piecesAt = (k) => {
    const su = TP.S.su;
    if (k < 0) return [];
    return F[k].pieces.map((p) => ({ ...p, ink: p.confirmed || su.inked.has(p.id) }));
  };
  TP.changedAt = (k) => {
    if (k < 0) return new Set();
    const f = F[k];
    return new Set([...f.ops.filter((o) => o.piece).map((o) => o.piece.id), ...f.confirm]);
  };

  // ---- dial tuning: the person's dials rewrite the reflection, in their colour ----
  const sentenceAfter = (re, t, dial) => ({ re, add: { t, kind: "tuned", dial } });
  const RULES = {
    formality: (v) => v >= 4 ? { rep: [[/^Hi /, "Dear "], [/cheers, Alex/, "Kind regards, Alex"], [/Thanks for writing!|Thank you for writing\./, "Thank you for your message."]] }
      : v <= 1 ? { rep: [[/Thank you for writing\./, "Thanks for writing!"], [/Would you be open to me featuring it/, "Up for a feature"]] } : null,
    warmth: (v) => v <= 2 ? { rep: [[/Thank you for writing\.|Thanks for writing!/, ""]] }
      : v >= 5 ? { rep: [[/Thank you for writing\.|Thanks for writing!/, "Thank you so much for writing; it made my day."]] } : null,
    humor: (v) => v >= 4 ? { ins: sentenceAfter(/before the last chorus/, "(Fair warning: it has been stuck in my head all day.)", "humor") } : v <= 1 ? { rep: [[/ is something else/, " is striking"]] } : null,
    energy: (v) => v >= 4 ? { rep: [[/is beautiful\./, "is beautiful!"], [/this Friday\?$/, "this Friday? I really hope so!"]] } : v <= 2 ? { rep: [[/!/g, "."]] } : null,
    length: (v) => v >= 4 ? { ins: sentenceAfter(/free visualizer/, "Happy to send a rough cut first so you can see the style.", "length") }
      : v <= 1 ? { rep: [[/^I make visualizers.*$/, ""], [/Thank you for writing\.|Thanks for writing!/, ""]] } : null,
    directness: (v) => v >= 5 ? { rep: [[/Would you be open to me featuring it/, "Can I feature it"]] }
      : v <= 2 ? { rep: [[/Would you be open to me featuring it/, "No rush at all, but would you maybe be open to me featuring it"]] } : null,
    expressiveness: (v) => v >= 4 ? { rep: [[/is beautiful/, "gives me goosebumps every time"], [/is something else/, "gives me goosebumps"]] }
      : v <= 2 ? { rep: [[/is beautiful|is something else/, "is good"]] } : null,
    detail: (v) => v >= 4 ? { ins: sentenceAfter(/free visualizer/, "It would be a 1080p visualizer, about three minutes long, out at 9 am.", "detail") } : null,
  };
  TP.dialValue = (id, k) => {
    const o = TP.S.su.dials[id];
    return o !== undefined ? o : (F[Math.max(k, 0)].dials.find((d) => d.id === id) || D.setup.style.dials.find((d) => d.id === id)).value;
  };
  const tune = (paras, k) => {
    if (k < 3) return paras; // nothing to tune until it has your voice
    for (const [id, v] of Object.entries(TP.S.su.dials)) {
      const base = F[k].dials.find((d) => d.id === id).value;
      if (v === base) continue;
      const rule = RULES[id]?.(v);
      if (!rule) continue;
      for (const lines of paras) for (const spans of lines) {
        for (let i = 0; i < spans.length; i++) {
          const s = spans[i];
          if (s.kind !== "piece" && s.kind !== "stock" && s.kind !== "tuned") continue;
          for (const [re, to] of rule.rep || []) {
            re.lastIndex = 0;
            if (re.test(s.t)) {
              re.lastIndex = 0;
              const nt = s.t.replace(re, to);
              if (nt !== s.t) {
                if (!nt.trim()) { spans[i] = { ...s, kind: "dialgone", dial: id }; }
                else { s.t = nt; s.tuned = id; }
              }
            }
          }
          if (rule.ins && rule.ins.re.test(s.t) && !spans.some((x) => x.dial === rule.ins.add.dial && x.kind === "tuned")) {
            spans.splice(i + 1, 0, { t: " " }, { ...rule.ins.add });
            i += 2;
          }
        }
      }
    }
    return paras;
  };

  // ---- rendering ----
  const spanHTML = (s, pm, changed) => {
    if (s.kind === "plain" || !s.kind) return esc(s.t);
    if (s.kind === "stock") return `<span class="sp sp-stock${s.tuned ? " sp-tuned" : ""}" title="Stock phrasing: not you yet">${esc(s.t)}</span>`;
    if (s.kind === "gone") return `<span class="sp sp-gone" data-piece="${s.id}" title="Taken out by this answer">${esc(s.t)}</span>`;
    if (s.kind === "dialgone") return `<span class="sp sp-gone sp-dialgone" title="Your dial took this out">${esc(s.t)}</span>`;
    if (s.kind === "tuned") return `<span class="sp sp-tuned" data-dial="${s.dial}" title="Your dial: ${esc(dialLabel(s.dial))}">${esc(s.t)}</span>`;
    const p = pm.get(s.id);
    const st = p ? (p.ink ? "ink" : "pencil") : "ink";
    const tuned = s.tuned ? ` sp-tuned" data-dial="${s.tuned}` : "";
    return `<span class="sp sp-${st}${changed.has(s.id) ? " chg" : ""}${tuned}" data-piece="${s.id}">${esc(s.t)}</span>`;
  };
  const dialLabel = (id) => D.setup.style.dials.find((d) => d.id === id)?.label ?? id;

  const footHTML = (pieces, pm, changed) => {
    const by = (place) => pieces.filter((p) => p.place === place);
    const st = (p) => (p.ink ? "ink" : "pencil") + (changed.has(p.id) ? " chg" : "");
    const out = [];
    const k = by("knowledge");
    out.push(k.length ? `<span class="meta sp-${st(k[0])}" data-place="knowledge">Answers from ${k.map((x) => esc(x.label)).join(", ")}</span>` : `<span class="meta meta-empty" data-place="knowledge">Knows nothing beyond this mail yet</span>`);
    const n = by("never");
    out.push(n.length ? `<span class="meta sp-${n.every((x) => x.ink) ? "ink" : "pencil"}${n.some((x) => changed.has(x.id)) ? " chg" : ""}" data-place="never">Checked against ${n.length} line${n.length > 1 ? "s" : ""} it must never cross: clear</span>` : `<span class="meta meta-empty" data-place="never">No lines it must never cross yet</span>`);
    const a1 = pm.get("p_a1");
    out.push(a1 ? `<span class="meta sp-${st(a1)}" data-piece="p_a1">Waits for your signature: first messages are Assist</span>` : `<span class="meta meta-empty" data-place="autonomy">Who sends it: not decided yet</span>`);
    const c1 = pm.get("p_c1");
    if (c1) out.push(`<span class="meta sp-${st(c1)}" data-piece="p_c1">If Wren says yes, it files the outcome in Notion: Partnerships</span>`);
    return out.join("");
  };

  TP.draftHTML = (k, opts = {}) => {
    const x = V.inbound;
    if (k < 0) return `<article class="draft draft-none"><p class="d-none">${TP.icon("pen")}No twin yet. Tell Athena what it is for, and its first reply to Wren appears here.</p></article>`;
    const pieces = TP.piecesAt(k);
    const pm = new Map(pieces.map((p) => [p.id, p]));
    const changed = opts.noChange ? new Set() : TP.changedAt(k);
    let src = V.drafts[Math.min(k, V.drafts.length - 1)];
    if (opts.noGone) src = src.replace(/\{-[^}]*\}\s?/g, "");
    const paras = tune(TP.parseTagged(src), k);
    const g = pm.get("p_gmail");
    const from = !g ? `<span class="meta-empty" data-place="channels">no mailbox yet</span>`
      : `<span class="sp sp-${g.ink ? "ink" : "pencil"}${changed.has("p_gmail") ? " chg" : ""}" data-piece="p_gmail">${g.ink ? esc(g.detail) : "Gmail, waiting for you to sign in"}</span>`;
    return `<article class="draft" aria-label="Your twin's draft reply to ${esc(x.from)}">
      <header class="d-head"><span><b>From</b> ${from}</span><span><b>To</b> ${esc(x.from)}</span><span><b>Re</b> ${esc(x.subject)}</span></header>
      <div class="d-body">${paras.map((lines) => `<p>${lines.map((spans) => spans.map((s) => spanHTML(s, pm, changed)).join("")).join("<br>")}</p>`).join("")}</div>
      <footer class="d-foot">${footHTML(pieces, pm, changed)}</footer>
    </article>`;
  };

  // The person's own sent mail, with the phrases each piece learned from.
  TP.sampleHTML = (sid, k) => {
    const s = TP.sampleById(sid);
    const pm = new Map(TP.piecesAt(k).map((p) => [p.id, p]));
    const changed = TP.changedAt(k);
    const paras = TP.parseTagged(V.samplesFull[sid]);
    const body = paras.map((lines) => `<p>${lines.map((spans) => spans.map((x) => {
      if (x.kind !== "piece") return esc(x.t);
      const p = pm.get(x.id);
      if (!p || !(p.evidence || []).includes(sid)) return esc(x.t);
      return `<span class="ev ev-${p.ink ? "ink" : "pencil"}${changed.has(x.id) ? " chg" : ""}" data-ev="${x.id}" title="It learned: ${esc(p.label)}">${esc(x.t)}</span>`;
    }).join("")).join("<br>")}</p>`).join("");
    return `<div class="you-mail"><p class="ym-head"><span>You wrote to <strong>${esc(s.to)}</strong></span><span>${esc(s.subject)} · ${TP.day(s.date)}</span></p><div class="ym-body">${body}</div></div>`;
  };
})();
