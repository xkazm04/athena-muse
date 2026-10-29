"""Shared by the connector tests: a fake provider in place of the network, vaults over it, and a check
that an answer has its contract shape.

Nothing here reaches a network. `FakeProvider` is the vault's transport: it records every request
and answers from a script, so a test can assert what left the process and, above all, what did not.
Ported from athena-portable's `tests/connectors/conftest.py`.
"""

from __future__ import annotations

import json
import re
import typing
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from athena.connectors.part import Connectors
from athena.connectors.seal import FileSeal
from athena.connectors.spec import load_builtin
from athena.connectors.vault import Vault

__all__ = [
    "ACCOUNT",
    "CLIENT_ID",
    "CLIENT_SECRET",
    "NOTION_KEY",
    "FakeProvider",
    "Seen",
    "assert_plain",
    "callback",
    "conforms",
    "connectors_over",
    "google",
    "vault_over",
]

#: `(status, body)`, or `(status, body, headers)` for an answer that carries headers.
Answer = tuple[int, Any] | tuple[int, Any, Mapping[str, str]]
Script = Callable[[str, str, Mapping[str, str], bytes | None], Answer]

ACCOUNT = "me@example.test"
NOTION_KEY = "ntn_test_key_0123456789abcdef"
CLIENT_ID = "test-client.apps.example"
CLIENT_SECRET = "test-client-secret-value"
ACCESS = "ya29.test_access_0123456789"
REFRESH = "1//test_refresh_0123456789"


@dataclass
class Seen:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes | None

    @property
    def path(self) -> str:
        return urlsplit(self.url).path

    @property
    def json(self) -> Any:
        return json.loads(self.body) if self.body else None

    @property
    def form(self) -> dict[str, str]:
        return dict(urllib.parse.parse_qsl((self.body or b"").decode("ascii")))


@dataclass
class FakeProvider:
    """The transport. `script` answers a request; the default accepts every probe."""

    script: Script | None = None
    seen: list[Seen] = field(default_factory=list)

    def __call__(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float
    ) -> tuple[int, bytes] | tuple[int, bytes, Mapping[str, str]]:
        self.seen.append(Seen(method, url, dict(headers), body))
        replied: list[Mapping[str, str]] = []
        if self.script is None:
            status, answer = (
                200,
                {"id": "0123456789abcdef0123456789abcdef", "name": "Test User", "emailAddress": ACCOUNT},
            )
        else:
            status, answer, *replied = self.script(method, url, headers, body)
        raw = answer if isinstance(answer, bytes) else json.dumps(answer).encode("utf-8")
        return (status, raw, replied[0]) if replied else (status, raw)


def google(*, account: str = ACCOUNT, token_status: int = 200, extra: Script | None = None) -> Script:
    """Google's side of a sign-in: the token endpoint grants (or refuses), the profile names `account`.
    `extra` answers anything else (Gmail's own calls); without it they are a 404."""

    def script(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> Answer:
        path = urlsplit(url).path
        if path == "/token":
            if token_status >= 300:
                return token_status, {"error": "invalid_grant"}
            return 200, {"access_token": ACCESS, "refresh_token": REFRESH, "expires_in": 3600}
        if path == "/revoke":
            return 200, {}
        if path.endswith("/profile"):
            return 200, {"emailAddress": account}
        if extra is not None:
            return extra(method, url, headers, body)
        return 404, {"error": {"message": "not found"}}

    return script


def vault_over(root: Path | None, provider: FakeProvider, opened: list[str] | None = None) -> Vault:
    """A vault over `provider`, sealing into an owner-only file under `root` (memory when None).
    The browser it opens is `opened.append`."""
    seal = FileSeal(root / "sealed") if root is not None else None
    sink = opened if opened is not None else []
    return Vault(root, specs=load_builtin(), transport=provider, seal=seal, open_browser=sink.append)


def connectors_over(root: Path | None, provider: FakeProvider, opened: list[str] | None = None) -> Connectors:
    return Connectors(vault_over(root, provider, opened))


def callback(authorize_url: str, **query: str) -> tuple[int, str]:
    """Play Google's redirect: the browser lands on the flow's loopback listener with `query`."""
    params = dict(urllib.parse.parse_qsl(urlsplit(authorize_url).query))
    url = f"{params['redirect_uri']}?{urllib.parse.urlencode(query)}"
    try:
        with urllib.request.urlopen(url, timeout=5) as reply:
            return int(reply.status), reply.read().decode()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode()


def state_of(authorize_url: str) -> str:
    return dict(urllib.parse.parse_qsl(urlsplit(authorize_url).query))["state"]


def conforms(value: Any, shape: type) -> None:
    """`value` has the contract shape: every required key, no unknown key, no null, enums in range."""
    hints = typing.get_type_hints(shape, include_extras=True)
    assert isinstance(value, dict), value
    assert set(value) <= set(hints), (shape.__name__, sorted(set(value) - set(hints)))
    for name, hint in hints.items():
        optional = typing.get_origin(hint) is typing.NotRequired
        if optional:
            hint = typing.get_args(hint)[0]
        if name not in value:
            assert optional, (shape.__name__, name)
            continue
        got = value[name]
        assert got is not None, (shape.__name__, name)
        if typing.get_origin(hint) is typing.Literal:
            assert got in typing.get_args(hint), (shape.__name__, name, got)
        elif hint in (str, bool, int):
            assert type(got) is hint, (shape.__name__, name, got)


BANNED = re.compile(r"\b(tokens?|connectors?|oauth|api|prompts?|nodes?|slots?)\b", re.I)


def assert_plain(text: str) -> None:
    """Plain words on screen: never token, connector, OAuth, API, prompt, node or slot."""
    assert not BANNED.search(text), text
