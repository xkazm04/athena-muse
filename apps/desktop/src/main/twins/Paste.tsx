// "Your own messages" (business Phase 2): a web channel has no sent mail to learn from, so its voice
// comes from messages the person pastes - one at a time, for the channel they sent it on. Keeping one
// answers the whole twin; the kept ones are listed under the field, newest last.

import { useEffect, useRef, useState } from "react";
import { PASTE_MAX, type ChannelKind, type TwinDetail } from "../../lib/contract";
import { day } from "./format";
import { Icon } from "./marks";
import { pastedChannel, pastedOf } from "./select";
import { CHANNEL_ICON, CHANNEL_LABEL, WEB_CHANNELS, WEB_WORDS as w } from "./words";

export interface PastePanelProps {
  twin: TwinDetail | null;
  /** The web channels it speaks on; every web channel when it names none yet. */
  channels: readonly ChannelKind[];
  busy: boolean;
  onPaste: (text: string, channel: ChannelKind) => void;
  /** Its own heading, when it sits under other things on the slip (the slip names it otherwise). */
  headed?: boolean;
}

export function PastePanel({ twin, channels, busy, onPaste, headed = true }: PastePanelProps) {
  const choices = channels.length ? channels : WEB_CHANNELS;
  const [text, setText] = useState("");
  const [channel, setChannel] = useState<ChannelKind>(choices[0]!);
  const kept = pastedOf(twin);
  const seen = useRef(kept.length);

  // A message the daemon kept clears the field; a refusal leaves the words where they were.
  useEffect(() => {
    if (kept.length > seen.current) setText("");
    seen.current = kept.length;
  }, [kept.length]);

  const clean = text.trim();
  return (
    <div className="paste" data-role="paste">
      {headed && (
        <>
          <span className="rows__k">{w.pasteTitle}</span>
          <p className="slip__quiet">{w.pasteSub}</p>
        </>
      )}
      <form
        className="paste__f"
        onSubmit={(e) => {
          e.preventDefault();
          if (clean && !busy) onPaste(clean, channel);
        }}
      >
        <label htmlFor="paste-channel">{w.pasteChannel}</label>
        <select id="paste-channel" className="field" value={channel} disabled={busy} onChange={(e) => setChannel(e.target.value as ChannelKind)}>
          {choices.map((k) => (
            <option key={k} value={k}>
              {CHANNEL_LABEL[k]}
            </option>
          ))}
        </select>
        <label htmlFor="paste-text">{w.pasteText}</label>
        <textarea
          id="paste-text"
          className="field"
          rows={4}
          maxLength={PASTE_MAX}
          placeholder={w.pastePlaceholder}
          value={text}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
        />
        <div className="paste__row">
          <span className="slip__count">
            {text.length}/{PASTE_MAX}
          </span>
          <button type="submit" className="btn btn-primary" data-role="paste-keep" disabled={busy || !clean}>
            {busy ? w.pasteKeeping : w.pasteKeep}
          </button>
        </div>
      </form>
      <span className="rows__k">{kept.length ? w.pasteKept(kept.length) : w.pasteNone}</span>
      {kept.length > 0 && (
        <ul className="paste__list">
          {kept.map((x) => {
            const k = pastedChannel(x);
            return (
              <li key={x.id} className="paste__item" data-role="pasted" data-channel={k}>
                <span className="paste__k">
                  {k && <Icon name={CHANNEL_ICON[k]} />}
                  {k ? CHANNEL_LABEL[k] : x.to}
                  <span>
                    {x.date ? `${day(x.date)} · ` : ""}
                    {x.words} words
                  </span>
                </span>
                <span className="paste__x">{x.excerpt}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
