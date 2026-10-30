"""What a twin reads and writes through the connected accounts (ADR 0008).

Reads go through the vault's one door (`Vault.request`), which attaches the credential and holds the
hosts; their structure is parsed here with the providers' own helpers. Text a model will read is
fenced by the caller. Writes (the practice page) go through the Notion service, so the writes switch
and the allow-list hold as for every other write.

Sent mail is listed with a short excerpt and a word count; the whole body is read again only for the
one engine call that learns the voice, and never stored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any
from urllib.parse import quote

from athena.connectors.part import Connectors
from athena.connectors.providers import gmail, notion
from athena.connectors.vault import NeedsReauth, VaultError
from athena.contracts import SAMPLES_MAX, ChannelKind

EXCERPT_MAX = 200  # the most of a mail's text the twin keeps: what the samples slip shows
PAGES_MAX = 20
_QUOTED = re.compile(r"^(On .{0,200} wrote:|-{2,} ?Original Message ?-{2,}|>.*)$", re.M)
_FORWARD = re.compile(r"^\s*(fwd?|fw)\s*:", re.I)
_CREATED = re.compile(r"created page ([0-9a-f]{32})")
_PERSONAL = re.compile(r"\b(journal|diary|personal|private)\b", re.I)


class Unreachable(Exception):
    """A read or write that could not be made. The message is plain words, safe to show."""


@dataclass(frozen=True)
class SentMail:
    id: str
    to: str  # the first recipient's name, else their address
    subject: str
    date: str  # ISO date
    words: int
    excerpt: str
    forward: bool
    recipients: int
    outside: bool  # written to someone outside the account's own domain


@dataclass(frozen=True)
class Page:
    id: str
    title: str
    kind: str  # "page" or "database"
    personal: bool


def _request(connectors: Connectors, kind: ChannelKind, method: str, url: str, body: Any = None) -> Any:
    """One read through the vault; anything but an answer is `Unreachable`, in plain words."""
    label = "Gmail" if kind == "gmail" else "Notion"
    if connectors.connection(kind)["status"] != "connected":
        raise Unreachable(f"{label} is not connected.")
    try:
        status, answer = connectors.vault.request(kind, method, url, body)
    except NeedsReauth:
        raise Unreachable(f"{label} needs you to sign in again.") from None
    except VaultError:
        raise Unreachable(f"{label} could not be reached. Try again in a moment.") from None
    if status >= 300:
        raise Unreachable(f"{label} turned the request away (it answered {status}).")
    return answer


def own_words(text: str) -> str:
    """The person's own words in a sent mail: everything above the first quoted line."""
    found = _QUOTED.search(text)
    return (text[: found.start()] if found else text).strip()


def excerpt(text: str, limit: int = EXCERPT_MAX) -> str:
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:.-") + "…"


def _date(raw: str, internal: Any) -> str:
    try:
        return parsedate_to_datetime(raw).date().isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return datetime.fromtimestamp(int(internal) / 1000, UTC).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def _domain(address: str) -> str:
    return address.rsplit("@", 1)[-1].lower() if "@" in address else ""


def _message(connectors: Connectors, message_id: str) -> Any:
    safe = quote(gmail.gmail_id(message_id, "message"), safe="")
    return _request(connectors, "gmail", "GET", f"{gmail.API}/messages/{safe}?format=full")


def sent_mail(connectors: Connectors, limit: int = SAMPLES_MAX) -> list[SentMail]:
    """The person's newest sent mail, up to `limit`, with only what the slip shows."""
    account = connectors.connection("gmail").get("account", "")
    listed = _request(
        connectors, "gmail", "GET", f"{gmail.API}/messages?q={quote('in:sent')}&maxResults={limit}"
    )
    out: list[SentMail] = []
    for message_id in gmail.parse_message_ids(listed)[:limit]:
        try:
            body = _message(connectors, message_id)
        except (Unreachable, ValueError):
            continue
        meta = gmail.parse_metadata(body)
        people = [(name, addr) for name, addr in getaddresses([meta.get("to", "")]) if addr]
        first_name, first_addr = people[0] if people else ("", meta.get("to", ""))
        words = own_words(gmail.extract_text(body))
        out.append(
            SentMail(
                id=message_id,
                to=(first_name or first_addr).strip() or "(no one)",
                subject=meta.get("subject", "(no subject)") or "(no subject)",
                date=_date(
                    meta.get("date", ""), body.get("internalDate") if isinstance(body, dict) else None
                ),
                words=len(words.split()),
                excerpt=excerpt(words),
                forward=bool(_FORWARD.match(meta.get("subject", ""))),
                recipients=len(people),
                outside=all(_domain(a) != _domain(account) for _, a in people) if account else True,
            )
        )
    return out


def mail_text(connectors: Connectors, message_id: str) -> str:
    """One sent mail's own words, whole, for the engine call that learns the voice. Never stored."""
    return own_words(gmail.extract_text(_message(connectors, message_id)))


def pages(connectors: Connectors, limit: int = PAGES_MAX) -> list[Page]:
    """The Notion pages and databases shared with Athena, as Notion lists them."""
    found = _request(connectors, "notion", "POST", f"{notion.API}/search", {"query": "", "page_size": limit})
    out: list[Page] = []
    results = found.get("results", []) if isinstance(found, dict) else []
    for item in results[:limit]:
        if not isinstance(item, dict):
            continue
        try:
            page_id = notion.normalize_id(str(item.get("id", "")))
        except ValueError:
            continue
        title = " ".join(notion.title_of(item).split()) or "(untitled)"
        kind = "database" if item.get("object") == "database" else "page"
        out.append(Page(page_id, title, kind, bool(_PERSONAL.search(title))))
    return out


_LINE_BLOCKS = frozenset({"paragraph", "bulleted_list_item", "numbered_list_item", "to_do"})


def page_lines(connectors: Connectors, page_id: str) -> list[tuple[str, str]]:
    """A Notion page's lines of text, top to bottom, each with its block id: paragraphs, list items and
    to-dos not yet ticked (headings and everything else are not lines a person writes a task on).
    Untrusted text. Notion's first page of blocks is read: the newest lines go on top or are few."""
    safe = quote(notion.normalize_id(page_id), safe="")
    url = f"{notion.API}/blocks/{safe}/children?page_size={notion.CHILDREN_PAGE}"
    found = _request(connectors, "notion", "GET", url)
    out: list[tuple[str, str]] = []
    for block in found.get("results", []) if isinstance(found, dict) else []:
        if not isinstance(block, dict) or block.get("type") not in _LINE_BLOCKS:
            continue
        payload = block.get(block["type"])
        if not isinstance(payload, dict) or (block["type"] == "to_do" and payload.get("checked")):
            continue  # a ticked to-do is done
        text = notion.rich_text(payload.get("rich_text"))
        if " ".join(text.split()):
            out.append((str(block.get("id", "")), " ".join(text.split())))
    return out


# --- the practice page ------------------------------------------------------------------------------


def open_practice(connectors: Connectors, parent: str, title: str) -> str:
    """Creates the practice page under `parent` and answers its id. Turns Notion's writes on and lets
    the two pages onto its allow-list: a practice page is the twin's own scope there."""
    vault = connectors.vault
    allowed = list(vault.record("notion").allowlist)
    vault.set_allowlist("notion", [*allowed, parent])
    connectors.set_writes("notion", True)
    result = connectors.service("notion").call("create_page", {"parent_page_id": parent, "title": title})
    found = _CREATED.search(result.output.replace("-", "")) if result.ok else None
    if found is None:
        raise Unreachable("Notion would not make the practice page.")
    page_id = found.group(1)
    vault.set_allowlist("notion", [*allowed, parent, page_id])
    return page_id


def append(connectors: Connectors, page_id: str, text: str) -> None:
    result = connectors.service("notion").call("append_to_page", {"page_id": page_id, "text": text[:4000]})
    if not result.ok:
        raise Unreachable("Notion would not take the next line of the practice page.")
