// Rehearsal - the model of the twin at a frame, the script of beats it will have to play, and the
// wings where its parts gather by place, in pencil and ink.
(function () {
  const { D, R, esc, icon, fillLine, typeIn } = window.U;
  const FR = D.setup.frames;
  const PLACES = D.places;
  const LEARNED = { id: "p_learn", place: "voice", label: "", origin: "you", confirmed: true };

  // The whole twin at the current frame, with what the person inked ahead of her.
  function model(su, at = su.f) {
    const fr = at >= 0 ? FR[at] : null;
    let pieces = fr ? fr.pieces.map((p) => ({ ...p, confirmed: p.confirmed || su.inked.has(p.id) })) : [];
    if (su.rh && su.rh.learned) pieces = pieces.concat([{ ...LEARNED, label: D.setup.rehearsal.turns[2].learned }]);
    const coverage = {};
    for (const p of PLACES) {
      const mine = pieces.filter((x) => x.place === p.id);
      coverage[p.id] = mine.some((x) => x.confirmed) ? 1 : mine.length ? 0.5 : 0;
    }
    const core = PLACES.filter((p) => p.required > 0);
    const readiness = Math.round((100 * core.reduce((s, p) => s + coverage[p.id], 0)) / core.length);
    const ready = PLACES.every((p) => coverage[p.id] >= p.required);
    const named = pieces.some((p) => p.id === "p_ms");
    return { f: at, fr, pieces, coverage, readiness, ready, named };
  }

  function needState(need, m) {
    const have = m.pieces.filter((p) => need.ids.includes(p.id));
    if (!have.length) return "empty";
    return have.some((p) => p.confirmed) ? "ink" : "pencil";
  }
  function needLabel(need, st, m) {
    if (st === "empty") return need.need;
    if (need.gotInk && m.named) return need.gotInk;
    return need.got;
  }
  function lineOf(beatId, f) {
    const all = R.lines[beatId];
    if (!all) return null;
    let cur = null;
    for (const l of all) if (l.from <= f) cur = l;
    return cur;
  }
  const beatLit = (b, m) => !b.needs || b.needs.every((n) => needState(n, m) !== "empty");

  // Which beats this frame moved: a need changed, or its line was (re)written.
  function moved(su, m) {
    if (m.f < 0) return new Set();
    const prev = model(su, m.f - 1);
    const out = new Set();
    for (const b of R.beats) {
      if (b.needs && b.needs.some((n) => needState(n, m) !== needState(n, prev))) out.add(b.id);
      const a = lineOf(b.id, m.f), z = lineOf(b.id, m.f - 1);
      if (a && a !== z) out.add(b.id);
      if (a && m.named !== prev.named) out.add(b.id);
    }
    if (m.f >= 0 && m.named !== prev.named) ["b2", "b4", "b6"].forEach((id) => out.add(id));
    return out;
  }

  // ---------- one beat, as written so far ----------
  function needsHTML(b, m) {
    if (!b.needs) return "";
    return `<ul class="needs">${b.needs
      .map((n) => {
        const st = needState(n, m);
        const ic = st === "ink" ? icon("check") : st === "pencil" ? icon("pencil") : "";
        const k = `need:${b.id}:${n.place}:${st}`;
        return `<li class="need ${st === "empty" ? "empty-need" : st} ${App.isNew(k) && st !== "empty" ? "arrive" : ""}" data-place="${n.place}" title="${esc(D.places.find((p) => p.id === n.place).label)}">${ic}${esc(needLabel(n, st, m))}</li>`;
      })
      .join("")}</ul>`;
  }

  function lineHTML(b, m, focus) {
    const l = lineOf(b.id, m.f);
    if (!l) {
      return `<div class="line unwritten"><span class="ghost"></span><span class="ghost short"></span><em>Unwritten: it needs your voice to write this line.</em></div>`;
    }
    const key = `line:${b.id}:${l.from}:${m.named}`;
    let html = fillLine(l.text, m.named);
    if (App.isNew(key)) html = typeIn(html, b.id === "b1" ? 0 : b.id === "b3" ? 420 : 840);
    return `<p class="line pencil ${focus ? "full" : "clamp"}" data-key="${key}"><span class="txt">${html}</span></p>`;
  }

  function outcomeHTML(m) {
    const cells = R.outcomeCells
      .map((c) => {
        const known = m.f >= c.from;
        return `<span class="cell"><small>${c.key}</small>${known ? `<b>${esc(R.names[c.blank])}</b>` : `<span class="blank">${c.blank}</span>`}</span>`;
      })
      .join("");
    return `<div class="notion-row pencil">${cells}</div>`;
  }

  function beatHTML(b, i, m, su, focusSet) {
    if (su.rh) return window.Rehearsal.beatHTML(b, i, m, su);
    const lit = beatLit(b, m);
    const focus = focusSet.has(b.id);
    const no = `<span class="beat-no ${lit ? "lit" : ""}">${i + 1}</span>`;
    if (b.side === "creator") {
      const who = m.named ? R.names.artist : "The creator";
      return `<li class="beat creator ${focus ? "focus" : ""}" data-beat="${b.id}">${no}
        <div class="beat-body" title="Athena plays them in the rehearsal"><div class="cue"><span class="who">${esc(who)}</span><span class="cue-t">${esc(b.cue)}</span></div></div></li>`;
    }
    const litBadge = lit ? `<span class="badge lit-badge ${App.isNew("lit:" + b.id) ? "arrive" : ""}" data-tone="info">${icon("spark")}lit</span>` : "";
    const head = `<header><h3>${esc(b.title)}</h3>${needsHTML(b, m)}${litBadge}</header>`;
    const body = b.side === "chore" ? outcomeHTML(m) : lineHTML(b, m, focus);
    return `<li class="beat ${b.side} ${lit ? "lit" : ""} ${focus ? "focus" : ""}" data-beat="${b.id}">${no}
      <div class="beat-body">${head}${body}</div></li>`;
  }

  function columnHTML(su, m) {
    if (su.f < 0) return describeHTML();
    if (su.rh) return window.Rehearsal.columnHTML(su, m);
    const focusSet = moved(su, m);
    const ms = m.pieces.find((p) => p.id === "p_ms");
    const mt = m.pieces.find((p) => p.id === "p_mtype");
    const title = ms
      ? `<span class="mission ink">${esc(ms.label)}</span>`
      : `<span class="mission pencil">${esc(mt ? mt.label : "")}</span>`;
    const lit = R.beats.filter((b) => b.side !== "creator" && beatLit(b, m)).length;
    const written = ["b1", "b3", "b5"].filter((id) => lineOf(id, m.f)).length;
    return `<section class="script-col" aria-label="The script">
      <header class="script-head">
        <div><span class="eyebrow">Its first mission, as a script</span>${title}</div>
        <div class="tally"><span><b>${written}</b> of 3 lines written</span><span><b>${lit}</b> of 4 beats lit</span></div>
      </header>
      <ol class="beats ${["b1", "b3", "b5"].filter((id) => focusSet.has(id)).length >= 2 ? "crowded" : ""}">${R.beats.map((b, i) => beatHTML(b, i, m, su, focusSet)).join("")}</ol>
    </section>`;
  }

  function describeHTML() {
    return `<section class="script-col describe" aria-label="The script">
      <header class="script-head"><div><span class="eyebrow">Its first mission, as a script</span><span class="mission empty-need">Not written yet</span></div></header>
      <ol class="beats ghosts">${[0, 1, 2, 3, 4, 5]
        .map((i) => `<li class="beat ghostbeat ${i % 2 ? "creator" : "twin"}"><span class="beat-no">${i + 1}</span><div class="beat-body"><span class="ghost"></span><span class="ghost short"></span></div></li>`)
        .join("")}</ol>
      <p class="ghost-note">Tell Athena what the twin is for. Its first conversation appears here as a script, one beat per turn, and every answer you give writes part of it.</p>
    </section>`;
  }

  // ---------- the wings ----------
  function wingsHTML(su, m) {
    const touched = new Set();
    if (m.fr) {
      m.fr.ops.forEach((o) => o.piece && touched.add(o.piece.place || (m.pieces.find((p) => p.id === o.piece.id) || {}).place));
      m.fr.confirm.forEach((id) => touched.add((m.pieces.find((p) => p.id === id) || {}).place));
      if (m.fr.ask) touched.add(m.fr.ask.place);
    }
    if (su.rh) {
      touched.clear();
      touched.add(su.rh.learned ? "voice" : "mission");
    }
    const open = su.open || touched;
    const pencil = m.pieces.filter((p) => !p.confirmed);
    const rows = PLACES.map((pl) => {
      const mine = m.pieces.filter((p) => p.place === pl.id);
      const cov = m.coverage[pl.id];
      const isOpen = open.has(pl.id) && mine.length;
      const dots = mine
        .map((p) => `<i class="dot ${p.confirmed ? "on" : "her"}" title="${esc(p.label)}"></i>`)
        .join("");
      const chips = isOpen
        ? `<ul class="pieces">${mine
            .map((p) => {
              const k = `piece:${p.id}:${p.confirmed}`;
              const nw = App.isNew(k) ? "arrive" : "";
              return p.confirmed
                ? `<li class="piece ink ${nw}" title="${esc(p.label + (p.detail ? ", " + p.detail : ""))}"><span>${esc(p.label)}</span></li>`
                : `<li class="piece pencil ${nw}"><button type="button" data-act="ink" data-id="${p.id}" title="Ink it: make it yours"><span>${esc(p.label)}</span><span class="do">${icon("pen")}ink</span></button></li>`;
            })
            .join("")}</ul>`
        : "";
      const req = pl.required === 0 ? `<span class="opt">optional</span>` : "";
      return `<li class="place cov${String(cov).replace(".", "")} ${isOpen ? "open" : ""} ${touched.has(pl.id) ? "now" : ""}">
        <button type="button" class="pl-head" data-act="place" data-place="${pl.id}" aria-expanded="${isOpen ? "true" : "false"}">
          <span class="cov" aria-hidden="true"></span><span class="pl-name">${esc(pl.label)}</span>${req}<span class="pdots">${dots || '<i class="dot none"></i>'}</span>
        </button>${chips}</li>`;
    }).join("");
    return `<aside class="wings" aria-label="In the wings">
      <header class="wings-head">
        <div><span class="eyebrow">In the wings</span><b>${m.f >= 0 ? "Partnerships" : "Your twin"}</b></div>
        <div class="ready" title="How much of what setup needs is in place"><b>${m.f >= 0 ? m.readiness + "%" : "-"}</b><span class="faint">ready</span>
          <span class="ready-bar"><i style="width:${m.f >= 0 ? m.readiness : 0}%"></i></span></div>
      </header>
      <ol class="places">${rows}</ol>
      ${
        pencil.length
          ? `<button type="button" class="btn ink-all" data-act="ink-all">${icon("pen")}Ink all her pencil (${pencil.length})</button>`
          : `<p class="wings-foot faint">${m.f < 0 ? "Its parts gather here as you answer." : "Everything here is in your ink."}</p>`
      }
    </aside>`;
  }

  window.Script = { model, needState, beatLit, lineOf, columnHTML, wingsHTML, needsHTML, outcomeHTML };
})();
