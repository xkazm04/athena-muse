// The slip: the one working leaf clipped beside the document (sign in, samples, dials, pages,
// permits, clearance, endorsements). It says which section of the document the answer lands in.
(function () {
  const { D, V, esc, icons, stamp } = TP;
  const F = D.setup.frames;
  const C = D.setup.connect;

  const shell = (kind, lands, title, sub, body, foot = "") =>
    `<aside class="slip" data-kind="${kind}" aria-label="${esc(title)}">
      <header class="slip__h">${lands ? `<span class="slip__k">${icons.arrow}Lands in <b>${esc(lands)}</b></span>` : ""}<h2>${esc(title)}</h2>${sub ? `<p>${sub}</p>` : ""}</header>
      <div class="slip__b">${body}</div>
      ${foot ? `<footer class="slip__f">${foot}</footer>` : ""}
    </aside>`;
  const lands = (place) => V.sections[place];
  const tick = (m) => `<span class="tick" data-on="${m.on}" data-by="${m.by}" aria-hidden="true">${m.on ? icons.check : ""}</span>`;

  function intro() {
    const step = (n, t, s) => `<li><span class="num">${n}</span><div><b>${t}</b><span>${s}</span></div></li>`;
    return shell("intro", null, "How a twin gets its document", "", `<ol class="howto">
      ${step(1, "You say what it is for", "Athena fills in each section in pencil while you talk. You ink what is right.")}
      ${step(2, "It takes a first trip", "A dress rehearsal on a Notion practice page, with Athena playing the other side.")}
      ${step(3, "Go live", "The document is issued. Drafts you must sign wait for you on your twins page.")}
    </ol><p class="slip__quiet">Nothing is sent to anyone while you set it up.</p>`);
  }

  function pencil(m) {
    const list = m.pieces.filter((p) => !p.confirmed);
    const place = m.fr && m.fr.ask ? m.fr.ask.place : null;
    const body = list.length
      ? `<ul class="pcs pcs--lines pcs--slip">${list.map((p) => TP.pc(p, { ev: false })).join("")}</ul>`
      : `<p class="slip__quiet">Nothing in her pencil. Everything on the document is inked.</p>`;
    return shell("pencil", place ? lands(place) : null, list.length ? `Her pencil: ${list.length} to ink` : "All inked", list.length ? "Her proposals are dashed. Ink one, or all of them, to make them yours. Answer her question below either way." : "", body,
      list.length ? `<button class="btn" data-act="ink-all">${icons.nib}Ink all ${list.length}</button>` : "");
  }

  function gmail() {
    const su = TP.S.su;
    const st = su.gmail;
    const g = C.gmail;
    const lists = `<div class="perm"><div><span class="perm__k">It asks Google for</span>${g.asks_for.map((x) => `<span class="perm__i" data-ok="true">${icons.check}${esc(x)}</span>`).join("")}</div>
      <div><span class="perm__k">It never asks for</span>${g.never_asks_for.map((x) => `<span class="perm__i" data-ok="false">${icons.x}${esc(x)}</span>`).join("")}</div></div>`;
    let state = "";
    let foot = `<button class="btn btn-primary" data-act="gmail-signin">${icons.gmail}Sign in with Google</button>`;
    if (st === "waiting") {
      state = `<div class="cstate" data-state="waiting"><span class="spin" aria-hidden="true"></span><div><b>${esc(g.states.waiting)}</b><span>Waiting <span data-clock="gmail">${TP.clockText("gmail")}</span>. It stops waiting after 10 minutes.</span></div></div>`;
      foot = `<button class="btn" data-act="gmail-cancel">Cancel</button>`;
    } else if (st === "connected") {
      state = `<div class="cstate" data-state="connected">${stamp("Stamped", "success", { fresh: su.fresh === "gmail" })}<div><b>${esc(g.states.connected)}</b><span>The visa is on the document.</span></div></div>`;
      foot = "";
    } else if (st === "failed") {
      state = `<div class="cstate" data-state="failed">${icons.risk}<div><b>${esc(g.states.failed)}</b><span>Try again, or use a different account.</span></div></div>`;
      foot = `<button class="btn btn-primary" data-act="gmail-signin">${icons.retry}Try again</button>`;
    }
    return shell("gmail", lands("channels"), "Gmail visa", "Sign in with the Google account it should write from.", `${lists}${state}`, foot);
  }

  function notion() {
    const su = TP.S.su;
    const st = su.notion;
    const n = C.notion;
    const where = su.where || st === "rejected"
      ? `<ol class="where">${n.where_to_find.map((x, i) => `<li><span class="num">${i + 1}</span>${esc(x)}</li>`).join("")}</ol>`
      : `<button class="btn btn-quiet where__btn" data-act="notion-where">${icons.eye}Where to find it</button>`;
    let state = "";
    if (st === "checking") state = `<div class="cstate" data-state="waiting"><span class="spin" aria-hidden="true"></span><div><b>${esc(n.states.checking)}</b><span><span data-clock="notion">${TP.clockText("notion")}</span></span></div></div>`;
    if (st === "connected") state = `<div class="cstate" data-state="connected">${stamp("Stamped", "success", { fresh: su.fresh === "notion" })}<div><b>${esc(n.states.connected)}</b><span>The visa is on the document.</span></div></div>`;
    if (st === "rejected") state = `<div class="cstate" data-state="failed">${icons.risk}<div><b>${esc(n.states.rejected)}</b><span>The key is long; it is easy to miss the end.</span></div></div>`;
    const form = st === "connected" ? "" : `<form id="notion-form" class="keyform" autocomplete="off">
      <label for="notion-key">Your Notion key</label>
      <div class="keyform__row"><input id="notion-key" class="field" type="password" value="${esc(su.notionKey)}" placeholder="Paste it here" ${st === "checking" ? "disabled" : ""}>
      <button class="btn btn-primary" type="submit" ${st === "checking" ? "disabled" : ""}>${icons.key}Check</button></div></form>`;
    return shell("notion", lands("channels"), "Notion visa", "It reads only the pages you share with it.", `${form}${state}${st === "connected" ? "" : where}`);
  }

  function samples() {
    const marks = TP.S.su.marks.samples;
    const on = Object.values(marks).filter((m) => m.on).length;
    const rows = D.setup.samples.map((s) => {
      const m = marks[s.id];
      return `<button class="row" data-act="mark" data-group="samples" data-id="${s.id}" aria-pressed="${m.on}">
        ${tick(m)}<span class="row__m"><span class="row__t"><b>${esc(s.to)}</b><span>${esc(s.subject)}</span></span>
        <span class="row__d">${TP.day(s.date)} · ${s.words} words</span>
        ${s.why_not ? `<span class="row__why">Not suggested: ${esc(s.why_not)}</span>` : `<span class="row__x">${esc(s.excerpt)}</span>`}</span></button>`;
    });
    return shell("samples", lands("voice"), "Six mails you sent", "Its voice comes only from mail you wrote yourself. Dashed ticks are her pencil.", `<div class="rows">${rows.join("")}</div>`,
      `<span class="slip__count">${on} kept</span><button class="btn btn-primary" data-act="panel-go" ${on ? "" : "disabled"}>Learn from these ${on}</button>`);
  }

  function style(m) {
    const su = TP.S.su;
    const SRC = { learned: "your mail", preset: "preset", you: "you" };
    const presets = D.setup.style.presets.map((p) => `<button class="chip" data-act="preset" data-name="${esc(p)}" aria-pressed="${su.preset === p}">${esc(p)}</button>`).join("");
    const dials = m.dials.map((d) => `<div class="dialrow" data-src="${d.source}">
      <span class="dialrow__l">${esc(d.label)}</span>
      <span class="dialrow__lo">${esc(d.low)} to ${esc(d.high)}</span>
      <span class="dialrow__p" role="group" aria-label="${esc(d.label)}">${[1, 2, 3, 4, 5].map((v) => `<button data-act="dial" data-id="${d.id}" data-v="${v}" data-on="${v <= d.value}" aria-label="${v}" aria-pressed="${v === d.value}"></button>`).join("")}</span>
      <span class="dialrow__s">${SRC[d.source]}</span></div>`).join("");
    return shell("style", lands("voice"), "Its particulars", "Eight dials, set from your four mails. Each says where its value came from. Change any; or swap to a preset.",
      `<div class="presets"><span>Swap to</span>${presets}</div><div class="dials">${dials}</div>`,
      `<button class="btn btn-primary" data-act="panel-go">Keep this style</button>`);
  }

  function pages() {
    const marks = TP.S.su.marks.pages;
    const on = Object.values(marks).filter((m) => m.on).length;
    const rows = D.setup.pages.map((p) => {
      const m = marks[p.id];
      return `<button class="row row--1" data-act="mark" data-group="pages" data-id="${p.id}" aria-pressed="${m.on}">${tick(m)}<span class="row__m"><span class="row__t"><b>${esc(p.title)}</b><span>${p.kind === "database" ? "Notion database" : "Notion page"}</span></span>${p.why_not ? `<span class="row__why">Not suggested: ${esc(p.why_not)}</span>` : ""}</span></button>`;
    });
    return shell("pages", lands("knowledge"), "Pages it can see", "It answers only from the pages you tick, and nothing else.", `<div class="rows">${rows.join("")}</div>`,
      `<span class="slip__count">${on} chosen</span><button class="btn btn-primary" data-act="panel-go">Read from these ${on}</button>`);
  }

  function chores() {
    const marks = TP.S.su.marks.chores;
    const on = Object.values(marks).filter((m) => m.on).length;
    const ready = D.setup.chorePresets.filter((c) => !c.coming);
    const coming = D.setup.chorePresets.filter((c) => c.coming);
    const row = (c) => {
      const m = marks[c.id];
      return `<button class="row permit-row" data-act="mark" data-group="chores" data-id="${c.id}" aria-pressed="${m.on}">${tick(m)}<span class="row__m"><span class="row__t"><b>${esc(c.name)}</b>${c.later ? `<span class="tag">for later</span>` : ""}</span><span class="row__x row__x--wrap">${esc(c.does)}</span></span></button>`;
    };
    const blank = (c) => `<div class="row permit-row permit-row--blank" aria-disabled="true"><span class="tick" data-on="false" aria-hidden="true"></span><span class="row__m"><span class="row__t"><b>${esc(c.name)}</b><span class="tag">coming</span></span><span class="row__x">${c.tool === "calendar" ? "Calendar" : "Slack"} is not connected in this app yet</span></span></div>`;
    return shell("chores", lands("chores"), "Permits: ready-made chores", "Things it can do in Notion besides answering. More tools arrive later.",
      `<div class="rows"><span class="rows__k">${icons.notion}Notion</span>${ready.map(row).join("")}<span class="rows__k">Coming</span>${coming.map(blank).join("")}</div>`,
      `<span class="slip__count">${on} to issue</span><button class="btn btn-primary" data-act="panel-go">Issue ${on} permit${on === 1 ? "" : "s"}</button>`);
  }

  function seg(which, value) {
    return `<span class="seg" role="group">${D.autonomyLevels.map((l) => `<button data-act="level" data-which="${which}" data-v="${l.id}" aria-pressed="${value === l.id}">${l.label}</button>`).join("")}</span>`;
  }
  function autonomy() {
    const a = TP.S.su.auto;
    const says = (id) => D.autonomyLevels.find((l) => l.id === id).says;
    const by = a.touched ? "you" : "athena";
    const anyAuto = a.first === "auto" || (a.split && a.replies === "auto");
    const gm = `<div class="clr" data-by="${by}">
      <div class="clr__h">${icons.gmail}<b>Gmail</b><label class="switch"><input type="checkbox" data-act="split" ${a.split ? "checked" : ""}> Different for replies</label></div>
      <div class="clr__r"><span>${a.split ? "First message" : "Every send"}</span>${seg("first", a.first)}</div>
      ${a.split ? `<div class="clr__r"><span>Replies</span>${seg("replies", a.replies)}</div>` : ""}
      <p class="clr__says">${esc(says(a.split && a.replies === "auto" ? "auto" : a.first))}</p>
      ${anyAuto ? `<div class="clr__bar"><span>Sends alone at</span><button class="btn" data-act="bar" data-d="-5" aria-label="Lower the bar">-</button><b>${a.bar}</b><button class="btn" data-act="bar" data-d="5" aria-label="Raise the bar">+</button><span>or more sure, risk list empty</span></div>` : ""}
    </div>`;
    const no = `<div class="clr" data-by="athena"><div class="clr__h">${icons.notion}<b>Notion</b><span class="clr__scope">practice page only</span></div>
      <div class="clr__r"><span>Practice page</span>${seg("notion", a.notion)}</div><p class="clr__says">Nothing leaves Notion; it sends alone at ${a.notionBar} or more.</p></div>`;
    return shell("autonomy", lands("autonomy"), "Clearance per channel", "", `${gm}${no}<p class="rule">${esc(D.setup.autonomy.rule)}</p>`,
      `<button class="btn btn-primary" data-act="panel-go">Set clearance</button>`);
  }

  function memory() {
    const marks = TP.S.su.marks.memory;
    const rows = D.setup.memory.map((x) => {
      const m = marks[x.id];
      return `<div class="fact" data-by="${m.by}" data-on="${m.on}">
        <b class="fact__f">${esc(x.fact)}</b>
        <div class="fact__row"><span>${esc(x.from)}</span><span class="seg seg--sm" role="group" aria-label="Keep or drop"><button data-act="mark" data-group="memory" data-id="${x.id}" aria-pressed="${m.on}" ${m.on ? "disabled" : ""}>Keep</button><button data-act="mark" data-group="memory" data-id="${x.id}" aria-pressed="${!m.on}" ${!m.on ? "disabled" : ""}>Drop</button></span></div>
        ${x.reason ? `<span class="row__why">She'd drop it: ${esc(x.reason)}</span>` : ""}
      </div>`;
    });
    const on = Object.values(marks).filter((m) => m.on).length;
    return shell("memory", lands("memory"), "What she noticed about you", "It only uses the facts you keep. Dashed: her suggestion.", `<div class="facts">${rows.join("")}</div>`,
      `<span class="slip__count">${on} kept</span><button class="btn btn-primary" data-act="panel-go">Keep ${on}, drop ${4 - on}</button>`);
  }

  function rehearsal() {
    const R = D.setup.rehearsal;
    return shell("rehearsal", null, "Dress rehearsal", "", `<div class="practice-card">${icons.notion}<div><b>${esc(R.where)}</b><span>${esc(R.played_by)}. Nothing reaches a real person.</span></div></div>
      <ol class="howto howto--tight">
        <li><span class="num">1</span><div><b>It writes as you</b><span>Each draft gets a stamp: waits for you, held with its risk list, or sent on its own.</span></div></li>
        <li><span class="num">2</span><div><b>You mark each draft</b><span>"That's me" or "not me". Anything you change teaches it.</span></div></li>
        <li><span class="num">3</span><div><b>Then go live</b><span>The document is sealed and issued.</span></div></li>
      </ol>`, `<button class="btn btn-primary" data-act="reh-start">Start the rehearsal${icons.arrow}</button>`);
  }

  function golive() {
    const g = D.setup.golive;
    return shell("golive", null, "Issued", g.line, `<span class="rows__k">What stays as you set it</span><ul class="stays">${g.stays.map((s) => `<li>${icons.check}${esc(s)}</li>`).join("")}</ul>
      <p class="slip__quiet">Standing rules, like how much it may ever give, come in a later step.</p>`,
      `<button class="btn btn-primary" data-act="to-overview">Back to your twins${icons.arrow}</button>`);
  }

  TP.renderSlip = function (m) {
    const su = TP.S.su;
    if (su.sealed) return golive();
    if (m.f < 0) return intro();
    const p = m.fr.panel;
    if (!p) return pencil(m);
    if (p.kind === "connect") return p.channel === "gmail" ? gmail() : notion();
    return { samples, style, pages, chores, autonomy, memory, rehearsal }[p.kind](m);
  };
})();
