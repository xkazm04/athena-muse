// The twin's document: an open spread being filled in. Her proposals in pencil, your words in ink.
(function () {
  const { D, V, esc, icons, portrait, stamp } = TP;
  const F = D.setup.frames;
  const placeLabel = (id) => D.places.find((p) => p.id === id).label;

  // ---------- the derived model of the setup page ----------
  TP.setupModel = function () {
    const su = TP.S.su;
    const f = su.frame;
    const fr = f >= 0 ? F[f] : null;
    const sealed = su.sealed;
    const pieces = fr ? fr.pieces.map((p) => ({ ...p, confirmed: sealed || p.confirmed || su.inked.includes(p.id) })) : [];
    const coverage = {};
    for (const p of D.places) {
      const mine = pieces.filter((x) => x.place === p.id);
      coverage[p.id] = mine.some((x) => x.confirmed) ? 1 : mine.length ? 0.5 : 0;
    }
    const core = D.places.filter((p) => p.required > 0);
    const readiness = Math.round((100 * core.reduce((s, p) => s + coverage[p.id], 0)) / core.length);
    const ready = D.places.every((p) => coverage[p.id] >= p.required);
    const dials = (fr ? fr.dials : D.setup.style.dials).map((d) => (su.dials[d.id] ? { ...d, ...su.dials[d.id] } : d));
    let lit = null;
    if (!su.reh) lit = fr ? (fr.ask ? fr.ask.place : null) : "who";
    const needs = D.places.filter((p) => coverage[p.id] < p.required).map((p) => p.label.toLowerCase());
    return { f, fr, pieces, coverage, readiness, ready, dials, lit, needs, thinking: !!su.reply };
  };
  TP.pencilPieces = () => TP.setupModel().pieces.filter((p) => !p.confirmed);

  // ---------- a piece ----------
  // `opt`: the detail shows only while its section is being asked about (otherwise on hover)
  function pc(p, { tag = "li", cls = "", detail = true, ev = true, opt = false, chip = false } = {}) {
    const su = TP.S.su;
    const pencil = !p.confirmed;
    const isNew = su.arrive.includes(p.id);
    const inked = su.justInked.includes(p.id);
    const evid = ev && p.evidence ? `<span class="pc__ev">from ${p.evidence.length === 1 ? "one" : p.evidence.length} of your mails</span>` : "";
    const tip = [p.detail, p.evidence ? `from ${p.evidence.length} of your mails` : ""].filter(Boolean).join(", ");
    return `<${tag} class="pc ${cls} ${isNew ? "is-new" : ""} ${inked ? "is-inked" : ""}" data-state="${pencil ? "pencil" : "ink"}" data-origin="${p.origin}" data-piece="${p.id}" ${tip ? `title="${esc(tip)}"` : ""}>
      <span class="pc__l">${esc(p.label)}</span>${detail && p.detail ? `<span class="pc__d ${opt ? "pc__d--opt" : ""}">${esc(p.detail)}</span>` : ""}${evid}
      ${pencil ? `<button class="pc__ink ${chip ? "pc__ink--chip" : ""}" data-act="ink" data-id="${p.id}" title="Ink her proposal: make it yours" aria-label="Ink: ${esc(p.label)}">${icons.nib}<span>Ink</span></button>` : ""}
    </${tag}>`;
  }
  TP.pc = pc;

  function sec(place, body, m, { cls = "", empty = "Not filled in yet", aside = "" } = {}) {
    const cov = m.coverage[place] ?? 0;
    const lit = m.lit === place;
    const hasBody = body && body.trim();
    const slot = lit ? `<p class="sec__land">${icons.arrow}<span>${m.thinking ? "She is writing here" : "Your answer lands here"}</span></p>` : `<p class="sec__empty">${empty}</p>`;
    const printed = hasBody && body.includes("<!--blank-->");
    return `<section class="sec sec--${place} ${cls} ${printed ? "sec--printed" : ""}" data-lit="${lit}" data-cov="${cov}" ${lit && m.thinking ? 'data-busy="true"' : ""}>
      <h3 class="sec__h"><span class="cov" data-cov="${cov}" aria-hidden="true"></span><span class="sec__n">${V.sections[place]}</span><span class="sec__p">${esc(placeLabel(place))}</span>${aside}</h3>
      ${printed ? `${lit ? slot : ""}${body}` : hasBody ? body : slot}
    </section>`;
  }

  const of = (m, place) => m.pieces.filter((p) => p.place === place);
  const get = (m, id) => m.pieces.find((p) => p.id === id);

  // ---------- sections ----------
  function identity(m) {
    const name = get(m, "p_name");
    const sign = get(m, "p_sign");
    const purpose = get(m, "p_purpose");
    const pic = name ? portrait(name.label[0], { size: 76, pencil: !name.confirmed }) : portrait("", { size: 76, blank: true });
    const fld = (k, p, cls = "") =>
      `<div class="fld ${cls}"><span class="fld__k">${k}</span>${p ? pc(p, { tag: "div", detail: k !== "Name" }) : `<span class="fld__none">-</span>`}</div>`;
    if (!name && !purpose)
      return `<!--blank--><div class="ident ident--blank"><div class="ident__pic">${pic}</div><div class="ident__f">${fld("Name", null, "fld--name")}${fld("Signs as", null)}${fld("Purpose", null)}</div></div>`;
    return `<div class="ident"><div class="ident__pic">${pic}</div><div class="ident__f">${fld("Name", name, "fld--name")}${fld("Signs as", sign)}${fld("Purpose", purpose)}</div></div>`;
  }

  function visaState(kind, m) {
    const su = TP.S.su;
    if (kind === "gmail") return m.f < 1 ? "empty" : m.f === 1 ? su.gmail : "connected";
    return m.f < 4 ? "empty" : m.f === 4 ? su.notion : "connected";
  }
  function visa(kind, m) {
    const st = visaState(kind, m);
    const c = D.setup.connect[kind];
    const ck = D.channelKinds[kind];
    const p = get(m, kind === "gmail" ? "p_gmail" : "p_notion");
    const allow = kind === "gmail" ? "read and send" : "read chosen pages";
    let body = "";
    if (st === "empty") body = `<span class="visa__w">No visa yet</span>`;
    else if (st === "idle") body = `<span class="visa__w">Not stamped: ${kind === "gmail" ? "sign in with Google" : "paste your Notion key"}</span>`;
    else if (st === "waiting") body = `<span class="visa__w">${icons.clock}Waiting for you in the browser</span>`;
    else if (st === "checking") body = `<span class="visa__w">${icons.clock}Checking the key with Notion</span>`;
    else if (st === "failed") body = `<span class="visa__w">Sign-in did not finish. Nothing was saved.</span>`;
    else if (st === "rejected") body = `<span class="visa__w">Notion did not accept that key</span>`;
    else body = `<span class="visa__v">${esc(kind === "gmail" ? "alex@lowtide-visuals.example" : "Low Tide studio")}</span>`;
    const fresh = TP.S.su.fresh === kind || (p && TP.S.su.arrive.includes(p.id) && st === "connected");
    return `<div class="visa" data-kind="${kind}" data-state="${st}" ${p && !p.confirmed && st !== "connected" ? 'data-pencil="true"' : ""}>
      <div class="visa__k" title="${allow}">${icons[kind]}<b>${ck.label}</b>${st === "connected" ? stamp("Stamped", "success", { fresh, cls: "visa__stamp" }) : ""}</div>
      ${body}
    </div>`;
  }
  function visas(m) {
    if (m.f < 1)
      return `<!--blank--><div class="visas">${["gmail", "notion"].map((k) => `<div class="visa" data-state="empty"><div class="visa__k">${icons[k]}<b>${D.channelKinds[k].label}</b></div><span class="visa__w">No visa yet: ${k === "gmail" ? "sign in with Google" : "your Notion key"}</span></div>`).join("")}</div>`;
    return `<div class="visas">${visa("gmail", m)}${m.f >= 4 ? visa("notion", m) : `<div class="visa" data-state="empty"><div class="visa__k">${icons.notion}<b>Notion</b></div><span class="visa__w">No visa yet</span></div>`}</div>`;
  }

  function particulars(m, blank = false) {
    const pencil = m.f < 4;
    return `<div class="parts" data-state="${blank ? "blank" : pencil ? "pencil" : "ink"}" aria-label="Particulars: its style, and where each value came from">
      <span class="parts__k">Particulars <span>${blank ? "set from your samples" : "from your mail, unless marked"}</span></span>
      ${m.dials
        .map(
          (d) => `<div class="part" data-src="${d.source}" title="${esc(d.label)}: ${esc(d.low)} to ${esc(d.high)}, ${d.value} of 5">
        <span class="part__l">${esc(d.label)}</span>
        <span class="pips" aria-label="${blank ? "not set" : `${d.value} of 5`}">${[1, 2, 3, 4, 5].map((i) => `<i data-on="${!blank && i <= d.value}"></i>`).join("")}</span>
        <span class="part__s">${blank || d.source === "learned" ? "" : d.source === "you" ? "you" : "preset"}</span></div>`,
        )
        .join("")}</div>`;
  }
  function voice(m) {
    const traits = of(m, "voice");
    if (m.f < 3 && !traits.length)
      return `<!--blank--><blockquote class="specimen specimen--blank"><span class="specimen__t">Specimen: a few lines of your own sent mail go here</span></blockquote>${particulars(m, true)}`;
    const s = D.setup.samples.find((x) => x.id === V.specimen.sample);
    const spec = `<blockquote class="specimen" title="Specimen of your writing, from your mail to ${esc(s.to)}, ${TP.day(s.date)}"><span class="specimen__t"><span class="specimen__k">Specimen, your mail to ${esc(s.to)}:</span> ${esc(V.specimen.text)}</span></blockquote>`;
    return `${spec}<ul class="pcs pcs--lines pcs--voice">${traits.map((p) => pc(p)).join("")}</ul>${particulars(m)}`;
  }

  function chips(m, place) {
    const list = of(m, place);
    if (!list.length) return "";
    return `<ul class="pcs pcs--chips">${list.map((p) => pc(p, { opt: true, chip: true })).join("")}</ul>`;
  }
  function permits(m) {
    const list = of(m, "chores");
    const coming = m.f >= 6 ? D.setup.chorePresets.filter((c) => c.coming) : [];
    if (!list.length && !coming.length) return "";
    const blank = coming.length
      ? `<li class="permit permit--blank" title="${esc(coming.map((c) => `${c.name}: ${c.does}`).join(" "))} These tools are not connected in this app yet, so these permits cannot be issued."><span class="pc__l">${coming.map((c) => (c.tool === "calendar" ? "Calendar" : "Slack")).join(", ")}</span><span class="tag">coming</span></li>`
      : "";
    return `<ul class="pcs pcs--permits">${list.map((p) => pc(p, { cls: "permit", opt: true, chip: true })).join("")}${blank}</ul>`;
  }
  function lines(m, place, cls = "", opt = false) {
    const list = of(m, place);
    if (!list.length) return "";
    return `<ul class="pcs pcs--lines ${cls}">${list.map((p) => pc(p, { opt })).join("")}</ul>`;
  }

  TP.renderDoc = function (m) {
    const su = TP.S.su;
    let status = "Blank: say what it is for";
    if (m.f >= 0) status = m.ready ? "Ready to rehearse" : "Being issued";
    if (su.sealed) status = `Issued ${V.issued.date}`;
    const name = get(m, "p_name");
    const left = [
      sec("who", identity(m), m, { empty: "Name, signature and purpose", aside: `<span class="doc__line"><span class="doc__kind">${icons.book}Twin document</span><span class="doc__status" data-state="${su.sealed ? "issued" : m.ready ? "ready" : "draft"}">${status}</span></span>` }),
      sec("channels", visas(m), m, { empty: "Gmail and Notion, once you sign in" }),
      sec("voice", voice(m), m, { empty: "Learned only from mail you sent" }),
    ].join("");
    const right = [
      `<div class="pair">${sec("knowledge", chips(m, "knowledge"), m, { empty: "Notion pages you choose" })}${sec("chores", permits(m), m, { empty: "Ready-made chores you pick" })}</div>`,
      sec("never", lines(m, "never", "pcs--never"), m, { empty: "Lines it must not cross" }),
      sec("autonomy", lines(m, "autonomy"), m, { empty: "Review, Assist or Auto, per channel" }),
      sec("memory", lines(m, "memory"), m, { empty: "Facts about you that you keep" }),
      sec("mission", lines(m, "mission", "", true), m, { empty: "A goal on one conversation" }),
    ].join("");
    return `<article class="doc ${su.sealed ? "doc--sealed" : ""} ${m.f < 0 ? "doc--blank" : ""}" aria-label="The twin's document: ${name ? esc(name.label) : "unnamed"}">
      <div class="spread">
        <div class="page page--l">${left}</div>
        <div class="page page--r">${right}</div>
        ${su.sealed ? issuedSeal(m) : ""}
      </div>
    </article>`;
  };

  function issuedSeal(m) {
    const name = get(m, "p_name");
    return `<div class="issued" aria-label="Issued ${V.issued.date}">
      <svg viewBox="0 0 168 168" width="168" height="168" aria-hidden="true" focusable="false">
        <defs><path id="issued-ring" d="M84 84 m-62 0 a62 62 0 1 1 124 0 a62 62 0 1 1 -124 0"/></defs>
        <circle cx="84" cy="84" r="80" class="issued__r1"/><circle cx="84" cy="84" r="74" class="issued__r2"/><circle cx="84" cy="84" r="50" class="issued__r2"/>
        <text font-size="12" font-weight="600" letter-spacing="2.6" class="issued__t"><textPath href="#issued-ring">ISSUED · ${V.issued.date.toUpperCase()} · ${V.issued.by.toUpperCase()} ·</textPath></text>
      </svg>
      <span class="issued__pic">${portrait(name ? name.label[0] : "P", { size: 70 })}</span>
    </div>`;
  }

  // ---------- the trip page: the document during its dress rehearsal ----------
  TP.renderTrip = function (m) {
    const r = TP.S.su.reh;
    const step = r.step;
    const R = D.setup.rehearsal;
    const lit = step === "held" || step === "editing" || step === "w3";
    const name = get(m, "p_name");
    const ent = [];
    const seen = TP.stepTurns[step] || [];
    const past = (s) => seen.includes(s);
    if (past("t1") && step !== "waits") ent.push(stamp("Waited for you", "human", { sub: "you said: that's me" }));
    if (step === "waits") ent.push(stamp("Waits for you", "human", { sub: "first message", fresh: true }));
    if (past("t3")) ent.push(stamp("Held", "warning", { sub: "77 of 80, one risk", fresh: step === "held" }));
    if (["edited", "c4", "w5", "sent", "resolved", "golive"].includes(step)) ent.push(stamp("You edited", "human", { sub: "it learned", fresh: step === "edited" }));
    if (past("t5")) ent.push(stamp("Sent on its own", "success", { sub: "91 of 80, no risks", fresh: step === "sent" }));
    if (step === "resolved") ent.push(stamp("Resolved", "success", { sub: "filed to Notion", fresh: true }));
    if (step === "handed") ent.push(stamp("Handed back", "human", { sub: "asked for money", fresh: true }));
    const never = of(m, "never");
    return `<article class="doc doc--trip" aria-label="The twin's document, on its first trip">
      <header class="doc__head"><span class="doc__kind">${icons.book}Twin document</span><span class="doc__status">First trip</span><span class="doc__where">on the practice page</span></header>
      <div class="trip">
        <div class="trip__id">${portrait(name ? name.label[0] : "P", { size: 54 })}<div><b>${name ? esc(name.label) : "Partnerships"}</b><span>Signs as Alex from Low Tide Visuals</span></div></div>
        <section class="sec sec--autonomy"><h3 class="sec__h"><span class="cov" data-cov="1"></span><span class="sec__n">Clearance</span><span class="sec__p">what it may send alone</span></h3>
          <ul class="pcs pcs--lines">${of(m, "autonomy").map((p) => pc(p)).join("")}</ul></section>
        <section class="sec sec--never" data-lit="${lit}"><h3 class="sec__h"><span class="cov" data-cov="1"></span><span class="sec__n">Restrictions</span><span class="sec__p">what it must never do</span></h3>
          <ul class="pcs pcs--lines pcs--never">${never.map((p) => pc(p, { cls: (lit && p.id === "p_n2") || (step === "handed" && p.id === "p_n1") ? "is-hit" : "" })).join("")}</ul></section>
        <section class="sec sec--entries"><h3 class="sec__h"><span class="sec__n">Entries</span><span class="sec__p">${esc(R.where.replace("Notion practice page: ", "practice page "))}</span></h3>
          ${ent.length ? `<div class="entries">${ent.join("")}</div>` : `<p class="sec__empty">Each draft gets a stamp here.</p>`}</section>
      </div>
    </article>`;
  };
})();
