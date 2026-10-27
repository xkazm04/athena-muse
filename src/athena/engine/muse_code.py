"""Muse Code on the person's plan: the pre-submission check of Athena on Muse, one `muse exec` per call.

Measured on Muse Code 1.4.13, 2026-10-27: the prompt comes from `--prompt-file` (nothing is read on
stdin); stdout is MSP JSON lines; every call carries about 15k input tokens of Muse Code's own
instructions (plan allowance, not money). The working directory must not contain the process temp
directory, so each call runs in a fresh temp directory of its own. A run reports no dollar cost.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from athena.contracts import EngineId
from athena.engine import EngineError, Usage
from athena.engine.cli import CliCall, OpLineEngine, Reply, child_env
from athena.engine.oplines import system_text, transcript

DEFAULT_MODEL = "muse-spark-1.3"
NOT_SIGNED_IN = "not logged in"


def argv(program: str, model: str, prompt_file: Path) -> list[str]:
    return [
        program,
        "exec",
        "--json",
        "--prompt-file",
        str(prompt_file),
        "--model",
        model,
        "--contributor-mode",
        "off",
        "--preset",
        "empty",
        "--no-session-log",
        "--disable-shell",
        "--disable-write",
        "--disable-web-tools",
        "--disable-reminders",
        "--no-foreign-personal-context",
        "--reasoning-effort",
        "low",
    ]


def read_stream(lines: list[str]) -> tuple[str, Usage | None, bool, str | None]:
    """(reply text, usage, ended, failure reason). Lines that are not MSP JSON are skipped."""
    text: list[str] = []
    usage: Usage | None = None
    ended = False
    failed: str | None = None
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("payload_type")
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        if kind == "run.output.delta":
            text.append(str(payload.get("text") or ""))
        elif kind == "run.usage":
            models = [m for m in payload.get("models") or [] if isinstance(m, dict)]
            usage = Usage(
                sum(int(m.get("input_tokens") or 0) for m in models),
                sum(int(m.get("output_tokens") or 0) for m in models),
            )
        elif kind == "run.terminal.completed":
            ended = True
        elif kind == "run.terminal.failed":
            ended = True
            failed = str(payload.get("reason") or "no reason given")[:200]
    return "".join(text), usage, ended, failed


class MuseCodeEngine(OpLineEngine):
    id: EngineId = "muse_code"
    #: On the plan: no cost on the wire.
    cost_estimated = False

    def _call(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], notes: list[str], workdir: Path
    ) -> Reply:
        system = system_text(messages, tools)
        body = transcript([m for m in messages if m.get("role") != "system"], notes=notes)
        prompt_file = workdir / "prompt.md"
        prompt_file.write_text(f"## System\n{system}\n\n{body}" if system else body, encoding="utf-8")
        result = self._run(CliCall(argv(self.program, self.model, prompt_file), None, child_env(), workdir))
        if NOT_SIGNED_IN in result.stderr.lower():
            raise EngineError("Muse Code is not signed in: run muse login")
        text, usage, ended, failed = read_stream(result.stdout)
        if failed is not None:
            raise EngineError(f"Muse Code could not answer: {failed}")
        if not ended:
            raise EngineError(f"Muse Code stopped without an answer (exit {result.code})")
        return Reply(text, usage)
