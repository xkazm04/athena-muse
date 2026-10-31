/**
 * Her hands in a page of her browser (ADR 0013). Ported from athena-portable's hands.js and
 * extended where YouTube Studio needs it: every walk goes through open shadow roots and
 * same-origin frames, and a file input can be given a file (`page_upload`).
 *
 * Injected by the shell into the top document of every tab, with the tab's nonce baked in. The
 * shell calls `run(id, hand, input)` with `eval`; the answer goes back through the one command a
 * page may call, `browser_reply`, tagged with the nonce. Three rules:
 *
 * - A ref is minted here and nowhere else. A model never sees a selector; a ref belongs to one
 *   document and is refused once that document is left.
 * - Nothing throws. Every hand answers `{ok, output, reason?}`; a refusal is a result.
 * - Athena never makes anything public: an acting hand refuses a control that reads "Public" or
 *   "Unlisted".
 */
(() => {
  "use strict";
  if (window.top !== window) return; // frames are reached from the top, never answer for it
  if (window.__athenaHands) return;

  const NONCE = "__ATHENA_NONCE__";
  const PACKET_CAP = 1500;
  const FIND_CAP = 20;
  const LABEL_CAP = 120;
  const SNAPSHOT_TEXT_CAP = 200000;
  const NOT_TEXT = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE", "SVG", "HEAD"]);
  const FIELD = new Set(["SELECT", "INPUT", "TEXTAREA"]);
  const OPERABLE =
    "a[href],button,input,select,textarea,summary,[role=button],[role=link],[role=radio]," +
    "[role=checkbox],[role=tab],[role=menuitem],[role=option],[contenteditable=true],[contenteditable='']";
  const NEVER = /^(public|unlisted)\b/i; // privacy is private, always

  const doc = Math.random().toString(16).slice(2, 8); // this document's ref prefix
  let refs = new Map();
  let seq = 0;
  const snapshots = new Map();
  let snapSeq = 0;
  const staged = new Map(); // upload id -> base64 parts

  const squash = (t) => String(t ?? "").replace(/\s+/g, " ").trim();
  const ok = (output, extra) => ({ ok: true, output: String(output ?? ""), ...extra });
  const no = (reason, detail) => ({ ok: false, reason, output: detail || reason });

  // ---- the deep walk: documents, open shadow roots, same-origin frames ---------------------------

  /** Every element under `root`, descending into open shadow roots and same-origin frames. */
  function* deep(root) {
    for (const el of Array.from(root.children || [])) {
      yield el;
      if (el.shadowRoot) yield* deep(el.shadowRoot);
      if (el.tagName === "IFRAME" || el.tagName === "FRAME") {
        let inner = null;
        try {
          inner = el.contentDocument; // null, or a throw, for a cross-origin frame: not ours
        } catch {
          inner = null;
        }
        if (inner && inner.documentElement) yield* deep(inner.documentElement);
        continue;
      }
      yield* deep(el);
    }
  }

  function viewOf(el) {
    return (el.ownerDocument && el.ownerDocument.defaultView) || window;
  }

  function shown(el) {
    if (!el.isConnected) return false;
    if (el.closest("[hidden],[aria-hidden=true]")) return false;
    const style = viewOf(el).getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
    const box = el.getBoundingClientRect();
    return box.width > 0 && box.height > 0;
  }

  /** A file input is operable even hidden: pages hide it behind their own button. */
  const isFile = (el) => el.tagName === "INPUT" && (el.type || "").toLowerCase() === "file";

  function textOf(root) {
    const parts = [];
    const visit = (node) => {
      for (const child of Array.from(node.childNodes || [])) {
        if (child.nodeType === 3) {
          const t = squash(child.nodeValue);
          if (t) parts.push(t);
        } else if (child.nodeType === 1) {
          if (NOT_TEXT.has(child.tagName)) continue;
          if (child.hidden || child.getAttribute("aria-hidden") === "true") continue;
          if (child.shadowRoot) visit(child.shadowRoot);
          if (child.tagName === "IFRAME" || child.tagName === "FRAME") {
            try {
              if (child.contentDocument && child.contentDocument.body) visit(child.contentDocument.body);
            } catch {
              /* cross-origin: not ours */
            }
            continue;
          }
          visit(child);
        }
      }
    };
    if (root) visit(root);
    return parts.join(" ");
  }

  function labelOf(el) {
    const byId = (id) => (id ? el.getRootNode().getElementById?.(id) : null);
    const candidates = [
      el.getAttribute("aria-label"),
      byId(el.getAttribute("aria-labelledby"))?.textContent,
      el.labels?.[0]?.textContent,
      el.getAttribute("placeholder"),
      el.getAttribute("title"),
      el.tagName === "INPUT" && ["submit", "button"].includes(el.type) ? el.value : "",
      FIELD.has(el.tagName) ? "" : textOf(el),
      el.getAttribute("name"),
      el.getAttribute("id"),
    ];
    const found = candidates.map(squash).find(Boolean) ?? "";
    return found.length > LABEL_CAP ? `${found.slice(0, LABEL_CAP)}…` : found;
  }

  function roleOf(el) {
    const explicit = el.getAttribute("role");
    if (explicit) return explicit;
    const tag = el.tagName.toLowerCase();
    if (tag === "a") return "link";
    if (tag === "select") return "select";
    if (tag === "textarea") return "textbox";
    if (tag === "input") return (el.type || "text") === "text" ? "textbox" : el.type;
    if (el.isContentEditable) return "textbox";
    return tag;
  }

  const inert = (el) => Boolean(el.disabled) || Boolean(el.matches?.(":disabled"));

  function mint(el) {
    for (const [token, held] of refs) if (held === el) return token;
    seq += 1;
    const token = `ref_${doc}_${seq}`;
    refs.set(token, el);
    return token;
  }

  function resolve(ref) {
    if (typeof ref !== "string" || !ref.startsWith("ref_")) {
      return { error: "unknown_ref", detail: "a ref comes from page_find" };
    }
    if (!ref.startsWith(`ref_${doc}_`)) {
      return { error: "unknown_ref", detail: "that ref belongs to a page that has been left; find it again" };
    }
    const el = refs.get(ref);
    if (!el) return { error: "unknown_ref", detail: `no element is held under ${ref}` };
    if (!el.isConnected) return { error: "unknown_ref", detail: "that element is no longer on the page; find it again" };
    return { el };
  }

  /** The label check every acting hand makes, and the one rule no signature lifts. */
  function refuseToAct(el, input) {
    const seen = labelOf(el);
    const value = squash(el.value);
    if (NEVER.test(seen) || (el.type === "radio" && NEVER.test(value))) {
      return no("refused", `Athena never makes anything public; "${seen || value}" is yours to press`);
    }
    if (input.expect === undefined || input.expect === null || input.expect === "") return null;
    if (squash(input.expect).toLowerCase() === squash(seen).toLowerCase()) return null;
    return no("moved", `expected "${squash(input.expect)}" but that element now reads "${seen || roleOf(el)}"; nothing was done`);
  }

  function setValue(el, value) {
    const proto = Object.getPrototypeOf(el);
    const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
    if (setter) setter.call(el, value);
    else el.value = value;
  }

  function fire(el, type) {
    const View = viewOf(el);
    el.dispatchEvent(new View.Event(type, { bubbles: true, composed: true }));
  }

  // ---- reads in packets ----------------------------------------------------------------------

  function packet(id, text, total, start) {
    const room = PACKET_CAP - 160;
    let end = Math.min(text.length, start + room);
    if (end < text.length) {
      const space = text.lastIndexOf(" ", end);
      if (space > start + room - 80) end = space;
    }
    const body = text.slice(start, end);
    const head =
      end < text.length
        ? `cursor: cur_${doc}_${id}_${end} (chars ${start + 1}-${end} of ${total}; pass it as cursor for the next part)`
        : `chars ${start + 1}-${end} of ${total}, the end`;
    return [head, body, `(showing ${body.length} of ${total})`].join("\n");
  }

  const here = () => ({ title: document.title, url: location.href });

  const HANDS = {
    page_info() {
      return ok(`${document.title}\n${location.href}`, here());
    },

    page_read(input) {
      if (input.cursor) {
        const m = /^cur_([0-9a-f]+)_(\d+)_(\d+)$/.exec(String(input.cursor));
        if (!m || m[1] !== doc) return no("unknown_ref", "that cursor belongs to a page that has been left; read again");
        const held = snapshots.get(Number(m[2]));
        if (!held) return no("unknown_ref", "that cursor has expired; read again");
        return ok(packet(Number(m[2]), held.text, held.total, Number(m[3])), here());
      }
      let root = document.body;
      if (input.ref) {
        const found = resolve(input.ref);
        if (found.error) return no(found.error, found.detail);
        root = found.el;
      }
      if (!root) return no("unknown_ref", "this page has no body yet");
      const text = textOf(root);
      if (text.length <= PACKET_CAP) return ok(text, here());
      snapSeq += 1;
      snapshots.set(snapSeq, { text: text.slice(0, SNAPSHOT_TEXT_CAP), total: text.length });
      if (snapshots.size > 4) snapshots.delete(snapshots.keys().next().value);
      return ok(packet(snapSeq, text.slice(0, SNAPSHOT_TEXT_CAP), text.length, 0), here());
    },

    page_find(input) {
      const query = squash(input.query).toLowerCase();
      const wanted = squash(input.role).toLowerCase();
      const rows = [];
      let total = 0;
      for (const el of deep(document.documentElement)) {
        if (!el.matches || !el.matches(OPERABLE)) continue;
        if (!isFile(el) && !shown(el)) continue;
        if (wanted && roleOf(el).toLowerCase() !== wanted) continue;
        const label = labelOf(el);
        if (query && !label.toLowerCase().includes(query)) continue;
        total += 1;
        if (rows.length < FIND_CAP) rows.push(`${mint(el)}  ${roleOf(el)}  ${label}${inert(el) ? "  (disabled)" : ""}`);
      }
      if (!rows.length) return ok("nothing matched", { shown: 0, total: 0 });
      return ok([...rows, `(showing ${rows.length} of ${total})`].join("\n"), { shown: rows.length, total });
    },

    page_click(input) {
      const found = resolve(input.ref);
      if (found.error) return no(found.error, found.detail);
      const refused = refuseToAct(found.el, input);
      if (refused) return refused;
      if (inert(found.el)) return no("refused", "that control is switched off");
      found.el.scrollIntoView?.({ block: "center", behavior: "instant" });
      found.el.click();
      return ok(`clicked ${labelOf(found.el) || roleOf(found.el)}`);
    },

    page_fill(input) {
      const found = resolve(input.ref);
      if (found.error) return no(found.error, found.detail);
      const el = found.el;
      const refused = refuseToAct(el, input);
      if (refused) return refused;
      const value = String(input.value ?? "");
      if (inert(el) || el.readOnly) return no("refused", "that field cannot be typed in");
      if (el.tagName === "SELECT") return no("refused", "that is a select; use page_select");
      if (isFile(el)) return no("refused", "that is a file input; use page_upload");
      if (el.isContentEditable) el.textContent = value;
      else if ("value" in el) setValue(el, value);
      else return no("refused", "that element is not a field");
      fire(el, "input");
      fire(el, "change");
      return ok(`filled ${labelOf(el) || "the field"}`);
    },

    page_select(input) {
      const found = resolve(input.ref);
      if (found.error) return no(found.error, found.detail);
      const el = found.el;
      const refused = refuseToAct(el, input);
      if (refused) return refused;
      if (el.tagName !== "SELECT") return no("refused", "that element is not a select");
      const wanted = squash(input.value).toLowerCase();
      const options = Array.from(el.options);
      const match =
        options.find((o) => squash(o.textContent).toLowerCase() === wanted) ??
        options.find((o) => String(o.value).toLowerCase() === wanted);
      if (!match) return no("refused", `no such option; it offers: ${options.map((o) => squash(o.textContent)).join(", ")}`);
      if (NEVER.test(squash(match.textContent))) return no("refused", "Athena never makes anything public");
      el.value = match.value;
      fire(el, "input");
      fire(el, "change");
      return ok(`selected ${squash(match.textContent)}`);
    },

    page_submit(input) {
      const found = resolve(input.ref);
      if (found.error) return no(found.error, found.detail);
      const refused = refuseToAct(found.el, input);
      if (refused) return refused;
      const form = found.el.tagName === "FORM" ? found.el : found.el.closest("form");
      if (!form) return no("refused", "that element is not inside a form");
      if (typeof form.requestSubmit === "function") form.requestSubmit();
      else form.submit();
      return ok("submitted the form");
    },

    page_scroll(input) {
      if (input.ref) {
        const found = resolve(input.ref);
        if (found.error) return no(found.error, found.detail);
        found.el.scrollIntoView?.({ block: "center", behavior: "instant" });
        return ok(`scrolled to ${labelOf(found.el) || roleOf(found.el)}`);
      }
      const up = squash(input.direction).toLowerCase() === "up";
      window.scrollBy({ top: (up ? -1 : 1) * window.innerHeight * 0.9, behavior: "instant" });
      return ok(`scrolled ${up ? "up" : "down"} one screen`);
    },

    async page_wait(input) {
      const wanted = squash(input.text).toLowerCase();
      if (!wanted) return no("refused", "page_wait needs the text to wait for");
      const budget = Math.min(Math.max(Number(input.timeout_ms) || 5000, 100), 15000);
      const deadline = Date.now() + budget;
      for (;;) {
        if (textOf(document.body).toLowerCase().includes(wanted)) return ok(`"${squash(input.text)}" is on the page`);
        if (Date.now() >= deadline) return no("timeout", `"${squash(input.text)}" did not appear within ${budget} ms`);
        await new Promise((done) => setTimeout(done, 100));
      }
    },

    /** Give a file input the file the shell staged in parts, built in the input's own realm. */
    page_upload(input) {
      const found = resolve(input.ref);
      if (found.error) return no(found.error, found.detail);
      const el = found.el;
      const refused = refuseToAct(el, input);
      if (refused) return refused;
      if (!isFile(el)) return no("refused", "that element is not a file input");
      const parts = staged.get(String(input.stage));
      staged.delete(String(input.stage));
      // A sparse array: `some` would skip the holes, so every index is asked.
      const whole = parts && Array.from({ length: parts.length }, (_, i) => parts[i]).every((p) => typeof p === "string");
      if (!whole) return no("refused", "the file did not arrive whole; nothing was given to the page");
      const View = viewOf(el);
      const chunks = parts.map((b64) => {
        const bin = atob(b64);
        const bytes = new View.Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
        return bytes;
      });
      const file = new View.File(chunks, String(input.name || "file"), { type: String(input.mime || "") });
      if (Number(input.size) !== file.size) return no("refused", `the file arrived as ${file.size} bytes, not ${input.size}; nothing was given to the page`);
      const transfer = new View.DataTransfer();
      transfer.items.add(file);
      el.files = transfer.files;
      fire(el, "input");
      fire(el, "change");
      return ok(`gave the page ${file.name} (${file.size} bytes)`);
    },
  };

  function reply(id, payload) {
    const invoke = window.__TAURI_INTERNALS__ && window.__TAURI_INTERNALS__.invoke;
    if (typeof invoke !== "function") return;
    Promise.resolve(invoke("browser_reply", { nonce: NONCE, id, payload })).catch(() => {});
  }

  const api = {
    run(id, name, input) {
      const hand = HANDS[name];
      if (!hand) {
        reply(id, no("refused", `there is no hand called ${name}`));
        return;
      }
      Promise.resolve()
        .then(() => hand(input || {}))
        .then(
          (out) => reply(id, out),
          (e) => reply(id, no("failed", `the page threw: ${squash(e && e.message).slice(0, 200)}`)),
        );
    },
    stage(id, index, b64, count) {
      let parts = staged.get(id);
      if (!parts) {
        parts = new Array(count);
        staged.set(id, parts);
      }
      parts[index] = b64;
    },
  };
  Object.defineProperty(window, "__athenaHands", { value: Object.freeze(api), configurable: false });
})();
