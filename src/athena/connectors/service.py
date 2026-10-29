"""One connector's tools over its spec and the vault (ADR 0008; ported from athena-portable).

Every rule a connector tool obeys is decided here, before a provider runs, from the record read live
on each call:

1. **The parameters fit the tool.** A call whose parameters do not fit the spec's schema is refused
   before anything is dialled (athena-portable's gate did this; here there is no gate in front).
2. **The writes switch.** A write (any tool not declared reversible, or that leaves the machine)
   runs only while the connector's writes switch is on. It is off until a twin needs it.
3. **The egress check.** A write's named parameters are checked against the allow-list, values
   normalised, the offending address named; an empty allow-list refuses every write. Reads are
   never egress-checked. ADR 0008 makes one exception, and it is a separate door:
   `Service.send_for_twin` sends Gmail to any recipient. Only the twins package calls it, and the
   send rule (ADR 0009) is its guard. Every other write keeps the allow-list.
4. **Reads are fenced and capped.** A read's text is cut to `READ_CAP` with the cut announced, then
   wrapped in the nonce fence, so a model never reads a mailbox as instructions.
5. **Three error channels.** A provider's refusal is `ok=False` with a sanitised reason; a grant
   that is gone is the sentence that asks the person to sign in again; a write whose answer never
   came (a timeout, a dropped connection after it was sent, a 5xx) is `outcome_unknown`, not a
   failure: it may have run, and a record that said "failed" would invite a second send.
6. **No secret surface.** Nothing here lists, shows or rotates a credential.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from athena.connectors._fence import cut_text, wrap_untrusted
from athena.connectors._manifest import ExecResult, check_params
from athena.connectors.addresses import one_address, refusal_reason
from athena.connectors.providers import gmail, notion
from athena.connectors.spec import ConnectorSpec, ToolSpec
from athena.connectors.vault import NeedsReauth, NoAnswer, Vault, VaultError

__all__ = [
    "READ_CAP",
    "THREAD_CAP",
    "Service",
    "ServiceError",
    "check_egress",
    "fenced",
    "services_for",
]

#: What one tool read gives a model, as athena-portable held every READ.
READ_CAP = 1600
#: A whole conversation for a twin to answer: longer than one read, still bounded.
THREAD_CAP = 12_000

Provider = Callable[[Any, str, Mapping[str, Any]], tuple[bool, str]]
PROVIDERS: dict[str, Provider] = {"gmail": gmail.execute, "notion": notion.execute}


class ServiceError(RuntimeError):
    """A structured read that could not be made. `error` is the word, the message plain words."""

    def __init__(self, error: str, reason: str) -> None:
        super().__init__(reason)
        self.error = error


def _values(params: Mapping[str, Any], names: Sequence[str]) -> list[str]:
    out: list[str] = []
    for name in names:
        value = params.get(name)
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, list):
            out.extend(str(v) for v in value)
    return out


def _normal(value: str, kind: str) -> str:
    text = value.strip().lower()
    if kind == "resources":
        return text.replace("-", "")
    return one_address(text) or text  # "Name <a@b>" is the address inside


def check_egress(
    spec: ConnectorSpec, tool: ToolSpec, params: Mapping[str, Any], allowlist: Sequence[str]
) -> str | None:
    """The reason a write must not leave, or None when every address is allowed."""
    if not tool.egress_params:
        return None
    allowed = {_normal(v, spec.egress) for v in allowlist}
    if not allowed:
        noun = "recipients" if spec.egress == "recipients" else "pages"
        return f"{spec.label} has no allowed {noun}; nothing is written until some are allowed"
    for value in _values(params, tool.egress_params):
        if spec.egress == "recipients" and one_address(value) is None:
            return refusal_reason(value)
        if _normal(value, spec.egress) not in allowed:
            return f"{value!r} is not on {spec.label}'s allow-list"
    return None


def _one_address_each(spec: ConnectorSpec, tool: ToolSpec, params: Mapping[str, Any]) -> str | None:
    """With no allow-list in play, every recipient must still be exactly one address."""
    for value in _values(params, tool.egress_params):
        if spec.egress == "recipients" and one_address(value) is None:
            return refusal_reason(value)
    return None


def fenced(text: str, label: str, cap: int = READ_CAP) -> str:
    """Capped inside the fence, so the cut is announced and nothing outside the fence is cut.
    `label` is the connector id, the fence's own slug rule."""
    return wrap_untrusted(cut_text(text, cap), label=label)


class Service:
    """One connector's door: the rules above, then the provider, which dials through the vault."""

    def __init__(self, spec: ConnectorSpec, vault: Vault, provider: Provider | None = None) -> None:
        self.spec = spec
        self.vault = vault
        provider = provider or PROVIDERS.get(spec.id)
        if provider is None:
            raise VaultError(f"no provider is built for connector {spec.id!r}")
        self._provider = provider

    def call(self, name: str, params: Mapping[str, Any]) -> ExecResult:
        """Run one tool under every rule, the allow-list included."""
        return self._run(name, params, any_recipient=False)

    def send_for_twin(self, params: Mapping[str, Any]) -> ExecResult:
        """ADR 0008: a twin's Gmail send may go to any recipient. The writes switch, the one-address
        rule and everything else still hold; only the allow-list is not consulted. The twins package
        is the one caller, after the send rule (ADR 0009) let the draft go or the person signed it.
        `data` carries Gmail's message `id` and its `thread_id`."""
        if self.spec.id != "gmail":
            return ExecResult.failure("validator_failed", f"{self.spec.label} does not send mail")
        return self._run("send_mail", params, any_recipient=True)

    def read_thread(self, thread_id: str) -> list[gmail.ThreadMessage]:
        """A Gmail conversation, oldest first, for a twin. The texts are untrusted: a model reads them
        through `fenced(gmail.render_thread(messages), "gmail", THREAD_CAP)`, never bare."""
        if self.spec.id != "gmail":
            raise ServiceError("unknown_ref", f"{self.spec.label} has no threads")
        try:
            status, messages = gmail.fetch_thread(self._request(), thread_id)
        except NeedsReauth as exc:
            raise ServiceError("validator_failed", str(exc)) from None
        except VaultError as exc:
            raise ServiceError("engine_error", str(exc)) from None
        except ValueError as exc:
            raise ServiceError("validator_failed", str(exc)) from None
        if status >= 300:
            raise ServiceError("engine_error", f"Gmail answered {status} to the thread read")
        return messages

    def _request(self, answers: list[tuple[int, Any]] | None = None) -> gmail.Request:
        def request(method: str, url: str, json_body: Any) -> tuple[int, Any]:
            status, body = self.vault.request(self.spec.id, method, url, json_body)
            if answers is not None:
                answers.append((status, body))
            return status, body

        return request

    def _run(self, name: str, params: Mapping[str, Any], *, any_recipient: bool) -> ExecResult:
        tool = self.spec.tool(name)
        if tool is None:
            return ExecResult.failure("unknown_ref", f"{self.spec.label} has no tool {name!r}")
        misfit = check_params(tool.tool.params_schema, params)
        if misfit is not None:
            return ExecResult.failure("validator_failed", misfit)
        record = self.vault.record(self.spec.id)
        write = tool.tool.is_write()
        if write:
            if not record.writes_enabled:
                return ExecResult.failure(
                    "validator_failed", f"writing is switched off for {self.spec.label}"
                )
            refusal = (
                _one_address_each(self.spec, tool, params)
                if any_recipient
                else check_egress(self.spec, tool, params, record.allowlist)
            )
            if refusal is not None:
                return ExecResult.failure("validator_failed", refusal)

        answers: list[tuple[int, Any]] = []
        try:
            ok, text = self._provider(self._request(answers), name, params)
        except NeedsReauth as exc:
            return ExecResult.failure("validator_failed", str(exc))
        except NoAnswer as exc:
            if write:
                return self._unknown(f"{self.spec.label}: {exc}")
            return ExecResult.failure("engine_error", str(exc))
        except VaultError as exc:
            return ExecResult.failure("engine_error", str(exc))
        except gmail.SubjectRefused as exc:
            return ExecResult.failure("validator_failed", str(exc))
        except ValueError as exc:  # a provider's own refusal never ends the turn
            return ExecResult.failure("engine_error", f"{self.spec.label} could not build the request: {exc}")
        if not ok:
            if write and answers and answers[-1][0] >= 500:
                return self._unknown(text)
            return ExecResult.failure("engine_error", text)
        if write:
            data = gmail.sent_ref(answers[-1][1]) if name == "send_mail" and answers else {}
            return ExecResult(ok=True, output=text, data=data)
        return ExecResult(ok=True, output=fenced(text, self.spec.id))

    @staticmethod
    def _unknown(said: str) -> ExecResult:
        """A write that was sent and whose outcome nobody heard."""
        return ExecResult.failure(
            "outcome_unknown", f"{said}; the write may have gone through, so check before trying it again"
        )


def services_for(vault: Vault) -> dict[str, Service]:
    """One service per spec that has a provider. A spec without one is left out, not broken."""
    return {cid: Service(spec, vault) for cid, spec in vault.specs.items() if cid in PROVIDERS}
