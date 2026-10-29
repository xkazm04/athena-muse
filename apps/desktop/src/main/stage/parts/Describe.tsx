// The describe step's shared part: the person says, in their own words, what they want handed off.

import { useState, type FormEvent } from "react";
import { NEED_MAX } from "../../../lib/contract";
import type { StageWords } from "../words";

export const DESCRIBE_WORDS = {
  title: "What chore would you like to hand off?",
  hint: "Say it the way you would tell a friend. She asks one thing at a time and sketches as you go.",
  label: "Describe the chore in your own words",
} as const;

export interface DescribeProps {
  /** Sending: the need is on its way and the first reply has not come back. */
  sending: boolean;
  /** What was sent, shown while sending and kept after a failure. */
  sent?: string;
  onDescribe: (need: string) => void;
  words: StageWords;
}

export function Describe({ sending, sent = "", onDescribe, words }: DescribeProps) {
  const [text, setText] = useState(sent);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim() && !sending) onDescribe(text);
  };
  return (
    <form className="sp-describe" data-role="describe" data-sending={sending ? "true" : undefined} onSubmit={submit}>
      <h1 className="sp-describe__title">{DESCRIBE_WORDS.title}</h1>
      <p className="sp-describe__hint">{DESCRIBE_WORDS.hint}</p>
      <textarea
        className="field sp-describe__field"
        rows={3}
        maxLength={NEED_MAX}
        value={sending ? sent || text : text}
        readOnly={sending}
        aria-label={DESCRIBE_WORDS.label}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key !== "Enter" || e.shiftKey) return;
          e.preventDefault();
          if (!e.nativeEvent.isComposing) submit(e);
        }}
      />
      <div className="sp-describe__row">
        {sending ? (
          <span className="sp-describe__sending" role="status">
            <span className="sp-dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            {words.sending}
          </span>
        ) : (
          <button type="submit" className="btn btn-primary" disabled={!text.trim()}>
            {words.send}
          </button>
        )}
      </div>
    </form>
  );
}
