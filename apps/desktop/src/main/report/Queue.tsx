// Tracks waiting for the person's verdict. Each has a player (YouTube only, loaded one at a time on a
// click so the page never opens a row of players at once; any other address is a link out), its title
// and creator, Keep / Pass / Later, a genre with suggestions from the project's own tracks, and a note.
// A verdict takes the track out in place: the list keeps its height until the report is read again,
// so nothing else on the page moves.

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { RecordItem, TrackVerdict, TrackVerdictBody } from "../../lib/contract";
import { openExternal } from "../../lib/windows";
import { reasonOf } from "../store";
import { VERDICT_ACT, creatorName, embedUrl, rel, str, youtubeId } from "./format";

const VERDICTS: TrackVerdict[] = ["keep", "pass", "later"];

export interface QueueProps {
  blockId: string;
  items: RecordItem[];
  genres: string[];
  now: Date;
  onVerdict: (recordId: string, body: TrackVerdictBody) => Promise<unknown>;
}

export function Queue({ blockId, items, genres, now, onVerdict }: QueueProps) {
  const [gone, setGone] = useState<ReadonlySet<string>>(new Set());
  const [playing, setPlaying] = useState<string | null>(null);
  const [lock, setLock] = useState<number | null>(null);
  const list = useRef<HTMLUListElement>(null);
  const listId = `rp-genres-${blockId}`;

  // A new reading of the report is the next load: what was taken out is gone from it, and the height
  // may follow the list again.
  useLayoutEffect(() => {
    setGone(new Set());
    setLock(null);
  }, [items]);

  const done = (id: string) => {
    if (lock === null && list.current) setLock(list.current.offsetHeight);
    setGone((g) => new Set(g).add(id));
    if (playing === id) setPlaying(null);
  };

  const left = items.filter((t) => !gone.has(t.id));
  return (
    <div className="rp-queue" style={lock === null ? undefined : { minHeight: lock }}>
      <datalist id={listId}>
        {genres.map((g) => (
          <option key={g} value={g} />
        ))}
      </datalist>
      {left.length ? (
        <ul className="rp-queue__list" ref={list}>
          {left.map((t) => (
            <QueueItem
              key={t.id}
              track={t}
              now={now}
              listId={listId}
              playing={playing === t.id}
              onPlay={() => setPlaying(t.id)}
              onVerdict={onVerdict}
              onDone={() => done(t.id)}
            />
          ))}
        </ul>
      ) : (
        <p className="rp-empty">Nothing else waits for you here.</p>
      )}
    </div>
  );
}

function QueueItem({
  track,
  now,
  listId,
  playing,
  onPlay,
  onVerdict,
  onDone,
}: {
  track: RecordItem;
  now: Date;
  listId: string;
  playing: boolean;
  onPlay: () => void;
  onVerdict: QueueProps["onVerdict"];
  onDone: () => void;
}) {
  const url = str(track, "url") ?? track.key;
  const title = str(track, "title") ?? "A track with no title";
  const vid = youtubeId(url);
  const [genre, setGenre] = useState(str(track, "genre") ?? "");
  const [note, setNote] = useState(str(track, "note") ?? "");
  const [busy, setBusy] = useState<TrackVerdict | null>(null);
  const [problem, setProblem] = useState("");
  const alive = useRef(true);
  useEffect(
    () => () => {
      alive.current = false;
    },
    [],
  );

  const send = async (verdict: TrackVerdict) => {
    setBusy(verdict);
    setProblem("");
    const body: TrackVerdictBody = { verdict };
    if (genre.trim()) body.genre = genre.trim();
    if (note.trim()) body.note = note.trim();
    try {
      await onVerdict(track.id, body);
      if (alive.current) onDone();
    } catch (e) {
      if (!alive.current) return;
      setProblem(reasonOf(e, "Could not keep your answer; try again"));
      setBusy(null);
    }
  };

  const gid = `rp-g-${track.id}`;
  const nid = `rp-n-${track.id}`;
  return (
    <li className="rp-track" data-role="queue-item" data-id={track.id}>
      <div className="rp-track__media">
        {vid ? (
          playing ? (
            <iframe
              className="rp-track__player"
              src={embedUrl(vid)}
              title={`Player: ${title}`}
              allow="autoplay; encrypted-media; picture-in-picture"
              referrerPolicy="strict-origin-when-cross-origin"
              allowFullScreen
            />
          ) : (
            <button type="button" className="rp-track__play" aria-label={`Play ${title}`} onClick={onPlay}>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M8 5.5v13l10.5-6.5z" />
              </svg>
            </button>
          )
        ) : (
          <a
            className="rp-track__out"
            href={url}
            onClick={(e) => {
              e.preventDefault();
              void openExternal(url);
            }}
          >
            Open the track
          </a>
        )}
      </div>
      <div className="rp-track__body">
        <p className="rp-track__head">
          {vid && !playing ? (
            <button type="button" className="rp-track__title rp-track__title--btn" onClick={onPlay}>
              {title}
            </button>
          ) : (
            <b className="rp-track__title">{title}</b>
          )}
          <span className="rp-track__by">
            {creatorName(str(track, "creator_key"))} · found {rel(str(track, "found_at"), now)}
          </span>
        </p>
        <div className="rp-track__fields">
          <label className="m-sr" htmlFor={gid}>
            Genre for {title}
          </label>
          <input
            id={gid}
            className="field rp-track__genre"
            list={listId}
            placeholder="Genre"
            maxLength={40}
            value={genre}
            disabled={busy !== null}
            onChange={(e) => setGenre(e.target.value)}
          />
          <label className="m-sr" htmlFor={nid}>
            Note on {title}
          </label>
          <input
            id={nid}
            className="field rp-track__note"
            placeholder="A note, if you like"
            maxLength={280}
            value={note}
            disabled={busy !== null}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>
        <div className="rp-track__acts" role="group" aria-label={`Your answer on ${title}`}>
          {VERDICTS.map((v) => (
            <button
              key={v}
              type="button"
              className={v === "keep" ? "btn btn-primary rp-verdict" : "btn rp-verdict"}
              data-role="verdict"
              data-verdict={v}
              disabled={busy !== null}
              onClick={() => void send(v)}
            >
              {busy === v ? "Sending..." : VERDICT_ACT[v]}
            </button>
          ))}
        </div>
        {problem && (
          <p className="m-error" role="alert">
            {problem}
          </p>
        )}
      </div>
    </li>
  );
}
