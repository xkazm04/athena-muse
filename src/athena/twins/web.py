"""A twin's web channels (business Phase 2): Proton mail, a bio link, a YouTube comment, through her
browser. Always a card; on sign one recipe finds the controls again and sends, or hands the wheel (bio).
STUB (WP2.0) - WP2.3."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from athena.contracts import Card, ChannelKind, PasteBody, TwinDetail

if TYPE_CHECKING:
    from athena.app import Daemon
    from athena.engine import Engine

WEB_CHANNELS: tuple[ChannelKind, ...] = ("mail_web", "bio", "comment")


def draft(
    daemon: Daemon,
    engine: Engine,
    space_id: str,
    channel: ChannelKind,
    to: dict[str, Any],
    purpose: str,
    context: str,
    thread_key: str | None = None,
) -> Card | None:
    """One model call in the project's twin's voice for `channel` (compile_voice(..., channel)); files a
    `twin_send_web` card the person may edit. None when the project has no live twin. `to` is the
    creator's record body; `purpose` is "offer" or "reply"."""
    raise NotImplementedError


def sign(daemon: Daemon, card: Card) -> str:
    """Send a signed `twin_send_web` card: mail_web and comment by recipe through her browser, bio by
    opening the link and handing the wheel. An edit becomes an example for that channel."""
    raise NotImplementedError


def declined(daemon: Daemon, card: Card) -> None:
    raise NotImplementedError


def paste(daemon: Daemon, twin_id: str, body: PasteBody) -> TwinDetail:
    """A message the person wrote, kept as a sample for that channel's voice."""
    raise NotImplementedError
