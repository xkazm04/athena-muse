"""Gmail: four intent-shaped tools over the REST API (ADR 0008; ported from athena-portable).

`search_mail` lists ids then reads each one's metadata; `read_mail` reads one message in full and
takes its `text/plain` part; `read_thread` reads a whole conversation, oldest first, so a twin can
answer it; `send_mail` posts one RFC 2822 message, into a thread when it is given one (`threadId`,
with `In-Reply-To` and `References` naming the message it answers). Outside the tools,
`fetch_threads` lists the newest conversations with each one's headers only, for the slip that gives
a twin a mission. Everything on the wire goes through the `Request` callable, which is the vault's
and holds the credential.

Gmail files a reply into the thread only when the subject matches the thread's too; the caller
keeps the subject ("Re: ..."), this module does not rewrite it.
"""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any
from urllib.parse import quote

from athena.connectors.addresses import one_address

__all__ = [
    "API",
    "TOOLS",
    "Request",
    "SubjectRefused",
    "ThreadMessage",
    "build_send_body",
    "execute",
    "extract_text",
    "fetch_thread",
    "fetch_threads",
    "parse_metadata",
    "parse_thread",
    "render_results",
    "render_thread",
    "sent_ref",
]

API = "https://gmail.googleapis.com/gmail/v1/users/me"
WANTED_HEADERS = ("From", "To", "Subject", "Date")
#: Gmail's message and thread ids are hexadecimal; anything else could carry a path into the URL.
_GMAIL_ID = re.compile(r"[0-9A-Za-z]{1,64}")
#: A Message-ID as it rides in `In-Reply-To`: one angle-bracketed token, no spaces or line breaks.
_MESSAGE_ID = re.compile(r"<[^<>\s]{1,996}>")

#: `(method, url, json_body) -> (status, decoded body)`. The vault's door.
Request = Callable[[str, str, Any], tuple[int, Any]]


def _q(value: str) -> str:
    return quote(value, safe="")


def gmail_id(value: str, what: str) -> str:
    """A Gmail message or thread id, or a refusal before any request is made."""
    if not _GMAIL_ID.fullmatch(value):
        raise ValueError(f"{value!r} is not a Gmail {what} id")
    return value


def parse_message_ids(body: Any) -> list[str]:
    if not isinstance(body, Mapping) or not isinstance(body.get("messages"), list):
        return []
    return [str(m["id"]) for m in body["messages"] if isinstance(m, Mapping) and "id" in m]


def _headers_of(payload: Any) -> dict[str, str]:
    """Every header of a message, by its lower-cased name (Gmail sends `Message-ID` or `Message-Id`)."""
    if not isinstance(payload, Mapping) or not isinstance(payload.get("headers"), list):
        return {}
    out: dict[str, str] = {}
    for header in payload["headers"]:
        if isinstance(header, Mapping) and isinstance(header.get("name"), str):
            out.setdefault(header["name"].lower(), str(header.get("value", "")))
    return out


def parse_metadata(body: Any) -> dict[str, str]:
    if not isinstance(body, Mapping):
        return {}
    headers = _headers_of(body.get("payload"))
    return {
        "id": str(body.get("id", "")),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "date": headers.get("date", ""),
        "subject": headers.get("subject", "(no subject)"),
        "snippet": str(body.get("snippet", "")),
    }


def decode_b64url(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", "replace")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return ""


def _parts(payload: Any) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    found: list[Mapping[str, Any]] = [payload]
    for part in payload.get("parts") or []:
        found.extend(_parts(part))
    return found


def extract_text(body: Any) -> str:
    """The `text/plain` part of a full message, else its snippet."""
    if not isinstance(body, Mapping):
        return ""
    for part in _parts(body.get("payload")):
        if part.get("mimeType") != "text/plain":
            continue
        data = part.get("body")
        if isinstance(data, Mapping) and isinstance(data.get("data"), str):
            text = decode_b64url(data["data"])
            if text.strip():
                return text
    return str(body.get("snippet", ""))


def render_results(rows: Sequence[Mapping[str, str]]) -> str:
    return "\n".join(
        f"- id: {r.get('id', '')}\n  from: {r.get('from', '')}\n  date: {r.get('date', '')}\n"
        f"  subject: {r.get('subject', '')}\n  snippet: {r.get('snippet', '')}"
        for r in rows
    )


@dataclass(frozen=True)
class ThreadMessage:
    """One message of a thread. `text` is the sender's words, untrusted: a model reads it fenced."""

    id: str  # Gmail's own id
    sender: str  # the From header
    to: str
    date: str
    subject: str
    text: str
    message_id: str  # the Message-ID header: what a reply names in In-Reply-To; "" when absent


def parse_thread(body: Any) -> list[ThreadMessage]:
    """A thread's messages in Gmail's order, oldest first."""
    if not isinstance(body, Mapping) or not isinstance(body.get("messages"), list):
        return []
    out: list[ThreadMessage] = []
    for message in body["messages"]:
        if not isinstance(message, Mapping):
            continue
        headers = _headers_of(message.get("payload"))
        out.append(
            ThreadMessage(
                id=str(message.get("id", "")),
                sender=headers.get("from", ""),
                to=headers.get("to", ""),
                date=headers.get("date", ""),
                subject=headers.get("subject", "(no subject)"),
                text=extract_text(message),
                message_id=headers.get("message-id", ""),
            )
        )
    return out


def render_thread(messages: Sequence[ThreadMessage]) -> str:
    return "\n\n".join(
        f"from: {m.sender}\nto: {m.to}\ndate: {m.date}\nsubject: {m.subject}\nmessage id: {m.message_id}"
        f"\n\n{m.text.strip()}"
        for m in messages
    )


def fetch_thread(request: Request, thread_id: str) -> tuple[int, list[ThreadMessage]]:
    """Gmail's status and the thread's messages (none unless it answered 2xx)."""
    status, body = request("GET", f"{API}/threads/{_q(gmail_id(thread_id, 'thread'))}?format=full", None)
    return status, parse_thread(body) if status < 300 else []


def fetch_threads(request: Request, limit: int) -> tuple[int, list[tuple[str, list[ThreadMessage]]]]:
    """Gmail's status and the newest `limit` conversations, Gmail's order (newest first), each as its
    messages with headers only: a message's `text` is Gmail's snippet of it. A conversation whose own
    read fails is left out; the listing's status is the one answered."""
    status, body = request("GET", f"{API}/threads?maxResults={int(limit)}", None)
    if status >= 300:
        return status, []
    found = body.get("threads") if isinstance(body, Mapping) else None
    ids = [str(t["id"]) for t in found or [] if isinstance(t, Mapping) and "id" in t][:limit]
    headers = "".join(f"&metadataHeaders={h}" for h in (*WANTED_HEADERS, "Message-ID"))
    out: list[tuple[str, list[ThreadMessage]]] = []
    for thread_id in ids:
        try:
            safe = _q(gmail_id(thread_id, "thread"))
        except ValueError:
            continue
        got, thread = request("GET", f"{API}/threads/{safe}?format=metadata{headers}", None)
        messages = parse_thread(thread) if got < 300 else []
        if messages:
            out.append((thread_id, messages))
    return status, out


class SubjectRefused(ValueError):
    """A subject or a reply header the message cannot carry. Raised before any request is made."""


def _checked(value: str) -> str:
    """The bare address the egress check allowed; a value that is not one address is a bug."""
    address = one_address(value)
    if address is None:
        raise ValueError(f"{value!r} is not exactly one address")
    return address


def build_send_body(
    *,
    to: Sequence[str],
    subject: str,
    body: str,
    cc: Sequence[str] = (),
    thread_id: str = "",
    in_reply_to: str = "",
) -> dict[str, str]:
    """The `messages/send` body. With `thread_id` the message joins that thread; with `in_reply_to`
    it names the message it answers in `In-Reply-To` and `References`."""
    message = EmailMessage()
    message["To"] = ", ".join(_checked(a) for a in to)
    if cc:
        message["Cc"] = ", ".join(_checked(a) for a in cc)
    message["Subject"] = subject
    if in_reply_to:
        if not _MESSAGE_ID.fullmatch(in_reply_to):
            raise SubjectRefused("in_reply_to is one message id in angle brackets, on one line")
        message["In-Reply-To"] = in_reply_to
        message["References"] = in_reply_to
    message.set_content(body)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")
    payload = {"raw": raw}
    if thread_id:
        payload["threadId"] = gmail_id(thread_id, "thread")
    return payload


def sent_ref(body: Any) -> dict[str, str]:
    """What a send made: Gmail's message id and the thread it is in."""
    if not isinstance(body, Mapping):
        return {}
    ref = {"id": body.get("id"), "thread_id": body.get("threadId")}
    return {k: v for k, v in ref.items() if isinstance(v, str) and v}


def _statuses(failed: Sequence[int]) -> str:
    return ", ".join(str(code) for code in sorted(set(failed)))


Handler = Callable[[Request, Mapping[str, Any]], tuple[bool, str]]


def _search_mail(request: Request, params: Mapping[str, Any]) -> tuple[bool, str]:
    limit = int(params.get("max_results", 5) or 5)
    status, body = request("GET", f"{API}/messages?q={_q(str(params['query']))}&maxResults={limit}", None)
    if status >= 300:
        return False, f"Gmail answered {status} to the search"
    ids = parse_message_ids(body)[:limit]
    rows = []
    failed: list[int] = []
    for message_id in ids:
        headers = "".join(f"&metadataHeaders={h}" for h in WANTED_HEADERS)
        status, detail = request("GET", f"{API}/messages/{_q(message_id)}?format=metadata{headers}", None)
        if status < 300:
            rows.append(parse_metadata(detail))
        else:
            failed.append(status)
    if not ids:
        return True, "No messages matched."
    if not rows:
        return False, (
            f"Gmail found {len(ids)} messages but all {len(ids)} reads failed (answered {_statuses(failed)})"
        )
    text = render_results(rows)
    if failed:
        text += (
            f"\n(showing {len(rows)} of {len(ids)}; {len(failed)} reads failed, answered {_statuses(failed)})"
        )
    return True, text


def _read_mail(request: Request, params: Mapping[str, Any]) -> tuple[bool, str]:
    message_id = gmail_id(str(params["message_id"]), "message")
    status, body = request("GET", f"{API}/messages/{_q(message_id)}?format=full", None)
    if status >= 300:
        return False, f"Gmail answered {status} to the read"
    meta = parse_metadata(body)
    return True, (
        f"from: {meta.get('from', '')}\nto: {meta.get('to', '')}\ndate: {meta.get('date', '')}\n"
        f"subject: {meta.get('subject', '')}\n\n{extract_text(body)}"
    )


def _read_thread(request: Request, params: Mapping[str, Any]) -> tuple[bool, str]:
    status, messages = fetch_thread(request, str(params["thread_id"]))
    if status >= 300:
        return False, f"Gmail answered {status} to the thread read"
    return True, render_thread(messages) or "The thread has no messages."


def _send_mail(request: Request, params: Mapping[str, Any]) -> tuple[bool, str]:
    subject = str(params["subject"])
    if "\r" in subject or "\n" in subject:
        raise SubjectRefused("a subject is one line; remove the line breaks from it")
    payload = build_send_body(
        to=[str(a) for a in params["to"]],
        subject=subject,
        body=str(params["body"]),
        cc=[str(a) for a in params.get("cc", [])],
        thread_id=str(params.get("thread_id", "")),
        in_reply_to=str(params.get("in_reply_to", "")),
    )
    status, body = request("POST", f"{API}/messages/send", payload)
    if status >= 300:
        return False, f"Gmail answered {status} to the send"
    sent_id = sent_ref(body).get("id", "")
    return True, f"sent to {', '.join(_checked(str(a)) for a in params['to'])} (message {sent_id})"


#: One handler per tool the spec declares (`builtin/gmail.json`); a parity test holds the two to the
#: same names, so a tool cannot be declared without a handler or kept without a tool.
TOOLS: dict[str, Handler] = {
    "search_mail": _search_mail,
    "read_mail": _read_mail,
    "read_thread": _read_thread,
    "send_mail": _send_mail,
}


def execute(request: Request, tool: str, params: Mapping[str, Any]) -> tuple[bool, str]:
    """Run one tool. `(ok, text)`: a read's text, a write's sentence, or a refusal's reason."""
    handler = TOOLS.get(tool)
    if handler is None:
        return False, f"gmail has no tool {tool!r}"
    return handler(request, params)
