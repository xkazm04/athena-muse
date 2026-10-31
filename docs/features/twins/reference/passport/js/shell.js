// The setup page's composition, the States menu and her own window (where the past lives).
(function () {
  const { D, V, esc, icons, seal } = TP;
  const F = D.setup.frames;

  TP.renderSetup = function (root) {
    const su = TP.S.su;
    const m = TP.setupModel();
    let work;
    if (su.reh && su.reh.step !== "golive") work = `<div class="work" data-mode="trip">${TP.renderTrip(m)}${TP.renderPractice()}</div>`;
    else work = `<div class="work" data-mode="${su.sealed ? "sealed" : "doc"}">${TP.renderDoc(m)}${TP.renderSlip(m)}</div>`;
    root.innerHTML = `${work}${TP.renderAthena(m)}`;
    if (su.reh) TP.afterPractice();
  };

  TP.renderMenu = function () {
    const host = document.getElementById("menu-host");
    const btn = document.getElementById("states-btn");
    btn.setAttribute("aria-expanded", TP.S.menu);
    if (!TP.S.menu) return (host.innerHTML = "");
    const groups = [
      ["Overview", (id) => id.startsWith("overview")],
      ["Setup", (id) => id.startsWith("setup")],
      ["Sign in", (id) => id.startsWith("gmail") || id.startsWith("notion")],
      ["Rehearsal and go live", (id) => id.startsWith("rehearsal") || id === "golive"],
    ];
    host.innerHTML = `<div class="menu" role="menu" aria-label="States">${groups
      .map(([g, f]) => `<div class="menu__g"><span class="menu__k">${g}</span>${TP.STATES.filter(([id]) => f(id))
        .map(([id, label]) => `<button role="menuitem" data-act="go" data-id="${id}">${esc(label.replace(/^[^:]+: /, ""))}</button>`)
        .join("")}</div>`)
      .join("")}</div>`;
  };

  // her own window: the conversation so far (the setup page shows only the present)
  TP.renderHer = function () {
    const host = document.getElementById("her-host");
    const S = TP.S;
    document.getElementById("her-btn").setAttribute("aria-pressed", S.her);
    if (!S.her) return (host.innerHTML = "");
    const items = [];
    const last = S.page === "setup" ? S.su.frame : -1;
    for (let i = 0; i <= last; i++) {
      const fr = F[i];
      const you = i === 0 ? S.su.need || fr.user.text : F[i - 1].ask.suggestions[fr.user.choice];
      items.push(`<li class="her__you">${esc(you)}</li><li class="her__she">${esc(fr.line)}</li>`);
    }
    host.innerHTML = `<aside class="her coat" aria-label="Her window">
      <header class="her__h">${seal(34)}<div><b>Athena</b><span>${S.page === "setup" ? "Setting up Partnerships" : "Resting"}</span></div><button class="btn btn-quiet her__x" data-act="her" aria-label="Close her window">${icons.close}</button></header>
      ${items.length ? `<ol class="her__list">${items.join("")}</ol>` : `<p class="her__empty">Nothing yet. What you and Athena say while setting up a twin is kept here.</p>`}
    </aside>`;
    const list = host.querySelector(".her__list");
    if (list) list.scrollTop = list.scrollHeight;
  };
})();
