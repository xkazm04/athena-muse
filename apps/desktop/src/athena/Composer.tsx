import { forwardRef, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { TEXT_MAX } from "../lib/contract";
import { useHer } from "./store";

const MAX_LINES = 5;
// The counter shows only near the cap; below it, a number would just be noise.
const COUNT_FROM = TEXT_MAX - 400;

/** Where the person writes. Enter sends, Shift+Enter is a new line; Stop ends a reply early. */
export const Composer = forwardRef<HTMLTextAreaElement>(function Composer(_, outer) {
  const [text, setText] = useState("");
  const streaming = useHer((s) => s.streaming);
  const ready = useHer((s) => s.status === "ready");
  const send = useHer((s) => s.send);
  const stop = useHer((s) => s.stop);
  const inner = useRef<HTMLTextAreaElement | null>(null);

  const setRef = (el: HTMLTextAreaElement | null) => {
    inner.current = el;
    if (typeof outer === "function") outer(el);
    else if (outer) outer.current = el;
  };

  // Grow with the text up to five lines, then scroll inside.
  useLayoutEffect(() => {
    const el = inner.current;
    if (!el) return;
    el.style.height = "auto";
    const cs = getComputedStyle(el);
    const line = parseFloat(cs.lineHeight) || 22;
    const pad = (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0);
    const border = (parseFloat(cs.borderTopWidth) || 0) + (parseFloat(cs.borderBottomWidth) || 0);
    const cap = line * MAX_LINES + pad + border;
    el.style.height = `${Math.min(el.scrollHeight + border, cap)}px`;
    el.style.overflowY = el.scrollHeight + border > cap ? "auto" : "hidden";
  }, [text]);

  const submit = () => {
    const value = text.trim();
    if (!value || streaming || !ready) return;
    setText("");
    void send(value);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <form
      className="her-composer"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <textarea
        ref={setRef}
        className="field her-input"
        rows={1}
        value={text}
        maxLength={TEXT_MAX}
        placeholder={streaming ? "Athena is replying..." : "Message Athena"}
        aria-label="Message Athena"
        disabled={streaming || !ready}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className="her-composer__side">
        {text.length >= COUNT_FROM && (
          <span className="her-count" aria-live="polite">
            {text.length}/{TEXT_MAX}
          </span>
        )}
        {streaming ? (
          <button type="button" className="btn her-send" onClick={stop}>
            Stop
          </button>
        ) : (
          <button type="submit" className="btn btn-primary her-send" disabled={!ready || !text.trim()}>
            Send
          </button>
        )}
      </div>
    </form>
  );
});
