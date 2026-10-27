"""Paper sheets as pictures: lay a sheet out as HTML and screenshot it with a headless browser.

The layout is fixed (860 x 1100 px, one absolutely placed row per field), so the box a field was
printed in is known by construction: `layout()` gives it, and a reader that returns no box is
cited at the printed row. PNGs land in `senses/render/` beside media.json and are never committed.
"""

from __future__ import annotations

import html
import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from athena.senses.contract import Box, Media
from athena.senses.normalise import is_money_field, iso_date, money

WIDTH, HEIGHT = 860, 1100
LEFT, RIGHT = 90, 774
ROW_TOP = 210
LINE_H = 26
CHARS = 72  # monospace characters per printed line between the margins
CHROME_ENV = "ATHENA_CHROME"

LABELS = {
    "biller": "From",
    "bill_id": "Statement number",
    "dos": "Date of service",
    "amount_due_usd": "Amount due",
    "due_date": "Please pay by",
    "payments_received_usd": "Payments received",
    "claim_id": "Claim number",
    "provider": "Provider",
    "patient_owes_usd": "You may owe",
    "notice_date": "Date of notice",
    "appeal_deadline": "Appeal by",
}


@dataclass(frozen=True)
class Row:
    field: str
    label: str  # "" for a block printed without a label (an instruction printed on the sheet)
    text: str
    box: Box


def label(name: str) -> str:
    if name in LABELS:
        return LABELS[name]
    words = name.removesuffix("_usd").replace("_", " ").strip()
    return words[:1].upper() + words[1:]


def printed(name: str, value: Any) -> str:
    """How a value is printed on paper: money with `$` and commas, a date written out."""
    if is_money_field(name):
        amount = money(value)
        if amount is not None:
            return f"${amount:,.2f}"
    day = iso_date(value) if isinstance(value, str) and len(value) == 10 else None
    if day is not None:
        y, m, d = (int(p) for p in day.split("-"))
        months = ["January", "February", "March", "April", "May", "June", "July", "August"]
        months += ["September", "October", "November", "December"]
        return f"{months[m - 1]} {d}, {y}"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def source_row(item: Media, tables: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """The world row a `render:<table>/<key>` source names (the first row holding that key)."""
    if not item.source.startswith("render:") or "/" not in item.source:
        return {}
    table, key = item.source[len("render:") :].split("/", 1)
    for row in tables.get(table, []):
        if key in (str(v) for v in row.values()):
            return row
    return {}


def values(item: Media, tables: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """What is printed for each field: the item's own values, else its source row, else its inject."""
    out: dict[str, Any] = {}
    own = item.params.get("values") or {}
    row = source_row(item, tables)
    for name in item.params.get("fields") or []:
        if name in own:
            out[name] = own[name]
        elif name in row:
            out[name] = row[name]
        elif name == "printed_instruction" and item.params.get("inject"):
            out[name] = item.params["inject"]
    return out


def layout(item: Media, tables: dict[str, list[dict[str, Any]]]) -> list[Row]:
    """One row per printed field, top to bottom, each with its normalised box."""
    rows: list[Row] = []
    y = ROW_TOP
    for name, value in values(item, tables).items():
        is_block = name == "printed_instruction"
        text = printed(name, value)
        lab = "" if is_block else label(name)
        chars = len(text) + (len(lab) + 2 if lab else 0)
        lines = max(1, math.ceil(chars / CHARS))
        height = lines * LINE_H
        box = (
            round(LEFT / WIDTH, 4),
            round(y / HEIGHT, 4),
            round(RIGHT / WIDTH, 4),
            round((y + height) / HEIGHT, 4),
        )
        rows.append(Row(name, lab, text, box))
        y += height + 8
    return rows


def hint(item: Media, tables: dict[str, list[dict[str, Any]]]) -> str:
    """The field list a reader gets: each name with the label it is printed under."""
    labelled = {r.field: r.label for r in layout(item, tables)}
    lines = []
    for name in item.params.get("fields") or []:
        where = labelled.get(name)
        if where:
            lines.append(f"- {name}: printed after '{where}:'")
        elif name in labelled:
            lines.append(f"- {name}: a paragraph printed on the sheet, copied whole")
        else:
            lines.append(f"- {name}: somewhere in the printed text")
    return "\n".join(lines)


def page(item: Media, tables: dict[str, list[dict[str, Any]]]) -> str:
    p = item.params
    rows = layout(item, tables)
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'><style>",
        f"html,body{{margin:0;width:{WIDTH}px;height:{HEIGHT}px;background:#fbfaf6;color:#1d1d1b}}",
        "body{position:relative;font-family:'Courier New',monospace;font-size:15px}",
        f".r{{position:absolute;left:{LEFT}px;width:{RIGHT - LEFT}px;line-height:{LINE_H}px;"
        "white-space:pre-wrap;word-break:break-word;overflow:hidden}",
        ".lh{font-family:Georgia,serif;font-size:24px;font-weight:bold}",
        ".k{font-weight:bold}",
        "</style></head><body>",
    ]
    if p.get("letterhead"):
        parts.append(f"<div class='r lh' style='top:48px'>{html.escape(str(p['letterhead']))}</div>")
    if p.get("to"):
        parts.append(f"<div class='r' style='top:110px'>To: {html.escape(str(p['to']))}</div>")
    kind = str(p.get("doc_type") or "").upper()
    parts.append(f"<div class='r k' style='top:150px'>{html.escape(kind)}</div>")
    for r in rows:
        top = round(r.box[1] * HEIGHT)
        height = round((r.box[3] - r.box[1]) * HEIGHT)
        head = f"<span class='k'>{html.escape(r.label)}:</span> " if r.label else ""
        parts.append(
            f"<div class='r' style='top:{top}px;height:{height}px'>{head}{html.escape(r.text)}</div>"
        )
    y = (round(rows[-1].box[3] * HEIGHT) + 24) if rows else ROW_TOP
    for line in p.get("lines") or []:
        n = max(1, math.ceil(len(str(line)) / CHARS))
        parts.append(f"<div class='r' style='top:{y}px'>{html.escape(str(line))}</div>")
        y += n * LINE_H + 6
    parts.append("</body></html>")
    return "".join(parts)


def find_browser() -> str | None:
    """`ATHENA_CHROME`, then Chrome, Chromium or Edge on PATH, then their usual install paths."""
    env = os.environ.get(CHROME_ENV, "").strip()
    if env:
        return env if Path(env).is_file() else None
    for name in ("chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    roots = [os.environ.get(k, "") for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    candidates = [
        Path(r) / sub
        for r in roots
        if r
        for sub in ("Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe")
    ]
    candidates += [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    ]
    return next((str(c) for c in candidates if c.is_file()), None)


def screenshot(browser: str, page_html: str, png: Path) -> bool:
    with tempfile.TemporaryDirectory(prefix="athena-render-") as tmp:
        src = Path(tmp) / "sheet.html"
        src.write_text(page_html, encoding="utf-8")
        cmd = [
            browser, "--headless=new", f"--screenshot={png.resolve()}", f"--window-size={WIDTH},{HEIGHT}",
            "--hide-scrollbars", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
            f"--user-data-dir={Path(tmp) / 'profile'}", src.resolve().as_uri(),
        ]  # fmt: skip
        try:
            subprocess.run(cmd, capture_output=True, timeout=60, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return False
    return png.is_file()


def render_sheets(
    senses_dir: Path, media: tuple[Media, ...], tables: dict[str, list[dict[str, Any]]]
) -> tuple[list[Path], str]:
    """Render every paper sheet. (PNGs written, a plain-words note when a browser is missing.)"""
    browser = find_browser()
    if browser is None:
        return [], "No Chrome or Edge found (set ATHENA_CHROME); nothing rendered."
    out_dir = senses_dir / "render"
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for item in media:
        if item.kind != "paper":
            continue
        png = out_dir / f"{item.id}.png"
        png.unlink(missing_ok=True)
        if screenshot(browser, page(item, tables), png):
            written.append(png)
    return written, ""
