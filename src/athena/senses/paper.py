"""The paper sense: a flip-through video and photographed sheets, read twice, to cited tables.

Each track the segmenter follows through the video is one sheet, cited at its best frame (highest
score, earliest on a tie). Each sheet is read twice; a field is `read` only when both reads agree
after normalising, else it is `asked` and `<sheet_id>.<field>` is listed for a person to answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from athena.contracts import ProofRow, SenseName
from athena.senses import render
from athena.senses.contract import Box, Media, Read, ReadField, Segment, SenseContext, SenseOutput, proof
from athena.senses.normalise import agree, comparable, stored

PURITY_BAR = 0.90


@dataclass(frozen=True)
class Track:
    track_id: str
    media_id: str
    best: Segment
    frames: int


def best_segment(segments: list[Segment]) -> Segment:
    """Highest score; the earliest frame on a tie."""
    return min(segments, key=lambda s: (-s.score, s.frame))


def tracks(media_id: str, segments: list[Segment]) -> list[Track]:
    by_id: dict[str, list[Segment]] = {}
    for s in segments:
        if s.track_id:
            by_id.setdefault(s.track_id, []).append(s)
    out = [
        Track(tid, media_id, best_segment(segs), len({s.frame for s in segs})) for tid, segs in by_id.items()
    ]
    return sorted(out, key=lambda t: (t.best.frame, t.track_id))


def box_list(box: Box | None) -> list[float] | None:
    return [round(v, 4) for v in box] if box is not None else None


def merge_reads(
    name: str, first: Read, second: Read, *, layout_box: Box | None = None
) -> tuple[str, ReadField | None, float | None]:
    """(status, the field to cite, the lower confidence) for one field over two reads."""
    a = next((f for f in first.fields if f.name == name), None)
    b = next((f for f in second.fields if f.name == name), None)
    if a is None or b is None or not agree(name, a.value, b.value):
        return "asked", None, None
    confs = [c for c in (a.confidence, b.confidence) if c is not None]
    cited = ReadField(
        name,
        a.value,
        min(confs) if confs else None,
        a.frame if a.frame is not None else b.frame,
        a.box or b.box or layout_box,
    )
    return "read", cited, cited.confidence


def field_rows(
    sheet_id: str, item: Media, fields: list[str], reads: tuple[Read, Read], layout: dict[str, Box]
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    asked: list[str] = []
    for name in fields:
        status, cited, conf = merge_reads(name, reads[0], reads[1], layout_box=layout.get(name))
        row: dict[str, Any] = {"sheet_id": sheet_id, "field": name, "status": status}
        if cited is not None:
            row["value"] = stored(name, cited.value)
            if conf is not None:
                row["confidence"] = round(conf, 4)
        row["media_id"] = item.id
        if cited is not None and cited.frame is not None:
            row["frame"] = cited.frame
        if cited is not None and cited.box is not None:
            row["box"] = box_list(cited.box)
        rows.append(row)
        if status == "asked":
            asked.append(f"{sheet_id}.{name}")
    return rows, asked


def read_twice(ctx: SenseContext, sense: SenseName, item: Media, fields: list[str]) -> tuple[Read, Read]:
    image = ctx.render_png(item)
    hint = render.hint(item, ctx.tables) if item.kind == "paper" else ""
    out: list[Read] = []
    for attempt in (0, 1):
        read, usage = ctx.reader.read(item, fields, attempt, image=image, hint=hint)
        ctx.record(sense, "reader", item.id, usage)
        out.append(read)
    return out[0], out[1]


class PaperSense:
    name: SenseName = "paper"

    def build(self, ctx: SenseContext) -> SenseOutput:
        found: dict[str, Track] = {}
        for video in ctx.items("paper", "video"):
            segments, usage = ctx.segmenter.segment(video, str(video.params.get("prompt") or ""))
            ctx.record("paper", "segmenter", video.id, usage)
            for t in tracks(video.id, segments):
                found.setdefault(t.track_id, t)
        sheets: list[dict[str, Any]] = []
        fields_out: list[dict[str, Any]] = []
        asked: list[str] = []
        papers = ctx.items("paper", "paper")
        named = {str(p.params.get("sheet_id") or p.id) for p in papers}
        for item in papers:
            sheet_id = str(item.params.get("sheet_id") or item.id)
            row: dict[str, Any] = {
                "sheet_id": sheet_id,
                "doc_type": str(item.params.get("doc_type") or "unknown"),
            }
            track = found.get(sheet_id)
            if track is not None:
                row |= {
                    "media_id": track.media_id,
                    "frame": track.best.frame,
                    "box": box_list(track.best.box),
                }
                row |= {"track_id": track.track_id, "frames_seen": track.frames}
            else:
                row |= {"media_id": item.id, "frame": 0}
            sheets.append(row)
            fields = [str(f) for f in item.params.get("fields") or []]
            layout = {r.field: r.box for r in render.layout(item, ctx.tables)} if ctx.render_png(item) else {}
            rows, missing = field_rows(sheet_id, item, fields, read_twice(ctx, "paper", item, fields), layout)
            fields_out += rows
            asked += missing
        for tid, track in found.items():
            if tid not in named:  # a sheet the camera saw that no media item describes: found, unread
                sheets.append(
                    {"sheet_id": tid, "doc_type": "unknown", "media_id": track.media_id}
                    | {"frame": track.best.frame, "box": box_list(track.best.box), "track_id": tid}
                    | {"frames_seen": track.frames}
                )
        return SenseOutput("paper", {"sheets": sheets, "sheet_fields": fields_out}, tuple(asked))

    def prove(self, ctx: SenseContext, out: SenseOutput, key: dict[str, Any]) -> list[ProofRow]:
        k = key.get("paper") or {}
        truth: dict[str, dict[str, Any]] = k.get("sheets") or {}
        piles: dict[str, list[str]] = k.get("piles") or {}
        sheets = out.tables.get("sheets", [])
        fields = out.tables.get("sheet_fields", [])
        rows: list[ProofRow] = []

        # F1: every sheet the key names is found, and every tracked sheet is one sheet of its pile.
        found_ids = {str(s["sheet_id"]) for s in sheets}
        found = sum(1 for sid in truth if sid in found_ids)
        tracked = [s for s in sheets if "track_id" in s]
        pile_of = {sid: p for p, ids in piles.items() for sid in ids}
        pure = sum(1 for s in tracked if str(s["track_id"]) in pile_of)
        found_rate = found / len(truth) if truth else None
        purity = pure / len(tracked) if tracked else None
        measured = min(v for v in (found_rate, purity) if v is not None) if truth else None
        note = f"{found} of {len(truth)} key sheets found"
        note += (
            f"; {pure} of {len(tracked)} tracks are one key sheet of a pile"
            if tracked
            else "; no video tracks"
        )
        rows.append(
            proof(
                "paper",
                "F1",
                "Is every sheet found, each track one sheet?",
                PURITY_BAR,
                ">=",
                len(truth),
                measured,
                note,
            )
        )

        # F2 / F2x: read fields against the key; F3: read fields that cite a place.
        read = [f for f in fields if f["status"] == "read" and str(f["sheet_id"]) in truth]
        right = [f for f in read if _right(f, truth)]
        wrong = len(read) - len(right)
        rows.append(
            proof(
                "paper",
                "F2",
                "Are the fields marked read right?",
                0.95,
                ">=",
                len(read),
                len(right) / len(read) if read else None,
                f"{len(right)} of {len(read)} read fields equal the key after normalising",
            )
        )
        rows.append(
            proof(
                "paper",
                "F2x",
                "How many fields are read but wrong?",
                0.02,
                "<=",
                len(read),
                wrong / len(read) if read else None,
                f"{wrong} of {len(read)} read fields differ from the key",
            )
        )
        located = [f for f in read if "box" in f and "frame" in f]
        rows.append(
            proof(
                "paper",
                "F3",
                "Does every read field cite where it was read?",
                1.0,
                ">=",
                len(read),
                len(located) / len(read) if read else None,
                f"{len(located)} of {len(read)} read fields carry a frame and a box",
            )
        )

        # R2: on a hard sheet (glare, fold, handwriting...) every field is read right or asked.
        hard = {sid: t for sid, t in truth.items() if t.get("hard")}
        if hard:
            hard_rows = [f for f in fields if str(f["sheet_id"]) in hard]
            safe = sum(1 for f in hard_rows if f["status"] == "asked" or _right(f, truth))
            kinds = ", ".join(f"{sid} {t['hard']}" for sid, t in sorted(hard.items()))
            rows.append(
                proof(
                    "paper",
                    "R2",
                    "On a hard sheet, is every field right or asked?",
                    1.0,
                    ">=",
                    len(hard_rows),
                    safe / len(hard_rows) if hard_rows else None,
                    f"{safe} of {len(hard_rows)} fields on hard sheets ({kinds}) right or asked",
                )
            )

        # R3: what reading one pile cost, the dearest pile; an unpriced call fails it.
        if piles:
            media_pile = {m.id: str(m.params.get("pile") or "") for m in ctx.items("paper")}
            media_pile |= {m.id: m.id for m in ctx.items("paper", "video")}
            costs: dict[str, float] = {p: 0.0 for p in piles}
            unpriced = 0
            for c in ctx.calls:
                pile = media_pile.get(c["media_id"], "")
                if c["sense"] != "paper" or pile not in costs:
                    continue
                if "cost_usd" not in c:
                    unpriced += 1
                else:
                    costs[pile] += c["cost_usd"]
            worst = max(costs.values())
            est = any(c.get("cost_estimated") for c in ctx.calls if c["sense"] == "paper")
            note = f"dearest pile ${worst:.4f}{' est.' if est else ''} over {len(piles)} pile(s)"
            if unpriced:
                note += f"; {unpriced} unpriced call(s) fail it"
            rows.append(
                proof(
                    "paper",
                    "R3",
                    "What does reading one pile cost (USD)?",
                    0.50,
                    "<=",
                    len(piles),
                    None if unpriced else worst,
                    note,
                )
            )
        return rows


def _right(f: dict[str, Any], truth: dict[str, dict[str, Any]]) -> bool:
    want = (truth.get(str(f["sheet_id"])) or {}).get("fields", {})
    name = str(f["field"])
    return name in want and comparable(name, f.get("value")) == comparable(name, want[name])
