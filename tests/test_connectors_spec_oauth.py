"""The spec parser refuses whole, the builtin specs load, and the sign-in flow answers only its own
callback. Ported from athena-portable's `tests/connectors/test_spec_and_oauth.py`."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from typing import Any

import pytest

from athena.connectors.oauth import OAuthFlow, verify_state
from athena.connectors.providers import gmail, notion
from athena.connectors.spec import SpecError, load_builtin, parse_spec

GOOD: dict[str, Any] = {
    "id": "demo",
    "label": "Demo",
    "auth": {"type": "token"},
    "api_hosts": ["api.demo.test"],
    "probe": {"method": "get", "url": "https://api.demo.test/me", "identity_field": "name"},
    "egress": "resources",
    "tools": [
        {"name": "read", "description": "Read.", "reversible": True, "side_effects": "none"},
        {
            "name": "write",
            "description": "Write.",
            "reversible": False,
            "side_effects": "external",
            "egress_params": ["page"],
        },
    ],
}


def test_the_builtin_specs_load_and_name_their_tools() -> None:
    specs = load_builtin()
    assert sorted(specs) == ["gmail", "notion"]
    assert [t.name for t in specs["gmail"].tools] == ["search_mail", "read_mail", "read_thread", "send_mail"]
    assert specs["gmail"].auth.type == "oauth" and specs["gmail"].auth.pkce
    assert specs["notion"].auth.type == "token"
    assert specs["notion"].auth.extra_headers == {"Notion-Version": "2022-06-28"}
    assert specs["gmail"].auth.guide and specs["notion"].auth.guide


def test_gmail_asks_only_to_read_and_send() -> None:
    """ADR 0008: never to delete mail, never the contacts or the calendar."""
    scopes = load_builtin()["gmail"].auth.scopes
    assert scopes == (
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    )


def test_every_declared_tool_has_a_handler_and_every_handler_a_tool() -> None:
    specs = load_builtin()
    assert [t.name for t in specs["gmail"].tools] == list(gmail.TOOLS)
    assert [t.name for t in specs["notion"].tools] == list(notion.TOOLS)


def test_reads_are_reads_and_sends_are_writes() -> None:
    specs = load_builtin()
    writes = {s.id: [t.name for t in s.tools if t.tool.is_write()] for s in specs.values()}
    assert writes == {"gmail": ["send_mail"], "notion": ["append_to_page", "create_page"]}


def test_a_spec_parses_and_the_probe_method_is_upper_cased() -> None:
    spec = parse_spec(GOOD)
    assert spec.probe.method == "GET"
    tool = spec.tool("write")
    assert tool is not None and tool.egress_params == ("page",)


@pytest.mark.parametrize(
    ("broken", "match"),
    [
        ({**GOOD, "id": "Demo"}, "lowercase slug"),
        ({**GOOD, "auth": {"type": "magic"}}, "not one of"),
        ({**GOOD, "auth": {"type": "oauth"}}, "authorize_url"),
        ({**GOOD, "api_hosts": []}, "at least one host"),
        ({**GOOD, "egress": "everything"}, "not one of"),
        ({**GOOD, "tools": []}, "non-empty list"),
        ({**GOOD, "egress": "none"}, "egress_params"),
        (
            {**GOOD, "tools": [{"name": "read", "description": "Read.", "side_effects": "none"}]},
            "must declare reversible",
        ),
        (
            {**GOOD, "tools": [{"name": "read", "reversible": True, "side_effects": "sometimes"}]},
            "side_effects must be one of",
        ),
        (
            {**GOOD, "tools": [{"name": "read", "reversible": "false", "side_effects": "none"}]},
            "reversible must be true or false",
        ),
        ({**GOOD, "tools": [GOOD["tools"][0], GOOD["tools"][0]]}, "duplicate tool"),
    ],
)
def test_a_malformed_spec_is_refused_whole(broken: dict[str, Any], match: str) -> None:
    """Refused at load, never at connect: no credential is sealed for a connector that cannot be used."""
    with pytest.raises(SpecError, match=match):
        parse_spec(broken)


# -- the sign-in flow -----------------------------------------------------------------------------


def _get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as reply:
            return reply.status, reply.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def _flow_with(on_code: Any, ttl_s: float = 10) -> OAuthFlow:
    return OAuthFlow(
        "gmail", load_builtin()["gmail"].auth, client_id="cid", on_code=on_code, ttl_s=ttl_s
    ).start()


def test_the_flow_answers_its_own_callback_and_refuses_a_stranger() -> None:
    exchanged: list[str] = []

    def on_code(flow: OAuthFlow, code: str) -> str:
        exchanged.append(code)
        return "me@example.test"

    flow = _flow_with(on_code)
    try:
        assert flow.authorize_url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        assert "code_challenge=" in flow.authorize_url and "state=" in flow.authorize_url
        assert verify_state(flow.state, flow._key)
        base = f"http://127.0.0.1:{flow.port}/callback"
        status, text = _get(f"{base}?state=forged.state&code=abc")
        assert status == 404 and "not for this flow" in text
        assert flow.phase == "awaiting_consent"
        status, text = _get(f"{base}?state={flow.state}&code=the-code")
        assert status == 200 and "connected" in text
        assert flow.wait(5) and flow.phase == "done"
        assert exchanged == ["the-code"]
        assert flow.view()["authorize_url"] == "", "the URL is not offered after consent"
    finally:
        flow.cancel()


def test_a_refused_consent_fails_the_flow() -> None:
    flow = _flow_with(lambda f, c: "")
    try:
        _get(f"http://127.0.0.1:{flow.port}/callback?state={flow.state}&error=access_denied")
        assert flow.wait(5) and flow.phase == "failed"
        assert "access_denied" in flow.detail
    finally:
        flow.cancel()


def test_an_unanswered_consent_page_runs_out() -> None:
    flow = _flow_with(lambda f, c: "", ttl_s=0.05)
    assert flow.wait(5) and flow.phase == "failed"
    assert "not answered in time" in flow.detail


def test_a_flow_view_carries_no_verifier_or_key() -> None:
    flow = OAuthFlow(
        "gmail", load_builtin()["gmail"].auth, client_id="cid", on_code=lambda f, c: "", ttl_s=10
    )
    text = json.dumps(flow.view())
    # The client id is in the authorize URL by design (it is not a secret); the verifier and the
    # signing key never leave the process.
    assert flow.verifier not in text and flow._key.hex() not in text
    flow.cancel()


def test_the_browser_page_says_connected_only_once_the_grant_is_admitted() -> None:
    def refused(flow: OAuthFlow, code: str) -> str:
        raise RuntimeError("Gmail refused the code with 400")

    flow = _flow_with(refused)
    try:
        status, text = _get(f"http://127.0.0.1:{flow.port}/callback?state={flow.state}&code=c")
        assert status == 200 and "connected." not in text
        assert "could not finish connecting" in text and "refused the code with 400" in text
        assert isinstance(flow.error, RuntimeError)
    finally:
        flow.cancel()


def test_the_browser_page_for_a_declined_consent_says_so_not_that_it_is_a_stranger() -> None:
    flow = _flow_with(lambda f, c: "")
    try:
        status, text = _get(f"http://127.0.0.1:{flow.port}/callback?state={flow.state}&error=access_denied")
        assert status == 200 and "not for this flow" not in text
        assert "access_denied" in text
    finally:
        flow.cancel()


def test_the_browser_page_for_a_slow_admission_says_it_is_still_finishing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("athena.connectors.oauth.CALLBACK_WAIT_S", 0.2)
    gate = threading.Event()

    def slow(flow: OAuthFlow, code: str) -> str:
        assert gate.wait(5)
        return "me@example.test"

    flow = _flow_with(slow)
    try:
        status, text = _get(f"http://127.0.0.1:{flow.port}/callback?state={flow.state}&code=c")
        assert status == 200 and "connected." not in text and "finishing" in text
        gate.set()
        assert flow.wait(5) and flow.phase == "done"
    finally:
        gate.set()
        flow.cancel()
