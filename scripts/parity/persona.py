"""The persona: a small model playing the person on the stage, from a case's card.

One `claude -p` call per decision (no tools, no session kept, run from a temp folder so no project
instructions load). It answers with one JSON object:
    {"pick": 1-4|null, "words": str|null, "drop": [labels], "marks": {expected_id: "yes"|"no"},
     "never": str|null, "note": str|null}
and fills only what the step asks for. An unreadable reply is asked once more; then the runner falls
back (the first suggestion, or "yes" to every card) and records `persona_fallback`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any

from cases import Persona

MODEL = "haiku"
TIMEOUT_S = 120
# Keys a child process never inherits (as src/athena/engine/cli.py STRIPPED_KEYS): each would move the
# call off the person's plan.
STRIPPED_KEYS = ("ANTHROPIC_API_KEY", "META_API_KEY")

SYSTEM = (
    "You play a person setting up a helper on a desktop app called Athena. You are given who you are, "
    "the truth about what you need (never contradict it unless told to), and how you talk. Stay in "
    "character. Never mention being an AI or a test. Reply with exactly one JSON object and nothing else."
)


@dataclass
class Reply:
    pick: int | None = None
    words: str | None = None
    drop: list[str] = field(default_factory=list)
    marks: dict[str, str] = field(default_factory=dict)
    never: str | None = None
    note: str | None = None
    fallback: bool = False
    raw: str = ""


def _card(p: Persona) -> str:
    return f"WHO YOU ARE: {p.who}\nYOUR TRUTH: {p.truth}\nHOW YOU TALK: {p.style}\n"


def _json_in(text: str) -> dict[str, Any] | None:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _call(prompt: str) -> str:
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("the claude CLI is not on PATH")
    env = {k: v for k, v in os.environ.items() if k not in STRIPPED_KEYS}
    args = [exe, "-p", "--model", MODEL, "--output-format", "json", "--tools", ""]
    args += ["--no-session-persistence", "--system-prompt", SYSTEM]
    done = subprocess.run(
        args,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=tempfile.gettempdir(),
        timeout=TIMEOUT_S,
    )
    outer = _json_in(done.stdout) or {}
    if outer.get("is_error") or "result" not in outer:
        raise RuntimeError(f"persona call failed: {(done.stdout or done.stderr)[:300]}")
    return str(outer["result"])


def _ask(prompt: str, valid: Any) -> tuple[dict[str, Any] | None, str]:
    """The persona's JSON, asked at most twice; None when neither reply was readable and valid."""
    raw = ""
    for attempt in range(2):
        try:
            raw = _call(prompt if attempt == 0 else prompt + "\nYour last reply was not valid. JSON only.")
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            raw = f"<error: {e}>"
            continue
        value = _json_in(raw)
        if value is not None and valid(value):
            return value, raw
    return None, raw


class PersonaModel:
    """One persona per case run; it remembers its own answers so it stays consistent."""

    def __init__(self, persona: Persona, enabled: bool = True) -> None:
        self.persona = persona
        self.enabled = enabled
        self.said: list[str] = []
        self.fallbacks = 0

    def _history(self) -> str:
        if not self.said:
            return ""
        return "WHAT YOU HAVE SAID SO FAR:\n" + "\n".join(f"- {s}" for s in self.said[-8:]) + "\n"

    def answer(
        self,
        line: str,
        ask: str,
        suggestions: list[str],
        pieces: list[str],
        mode: str = "persona",
        contradict: bool = False,
    ) -> Reply:
        """A turn's answer. mode 'persona': a suggestion if one matches the truth, else own words;
        'own_words': always own words."""
        if not self.enabled:
            return self._fallback_answer(suggestions, mode)
        options = "\n".join(f"{i}. {s}" for i, s in enumerate(suggestions[:4], 1)) or "(none)"
        rule = (
            'Answer in your own words: {"pick": null, "words": "<your answer>"}.'
            if mode == "own_words" or not suggestions
            else 'If one option says what is true for you, pick it: {"pick": <number>, "words": null}. '
            'Otherwise answer in your own words: {"pick": null, "words": "<your answer>"}.'
        )
        if contradict:
            rule = (
                "This time, take back one thing you said earlier that does not match your truth (or "
                "that you now want to put differently), plainly, in your own words, and answer the "
                'question too: {"pick": null, "words": "<your answer>"}.'
            )
        prompt = (
            f"{_card(self.persona)}{self._history()}"
            f"THE SKETCH SO FAR: {', '.join(pieces) or '(empty)'}\n"
            f"ATHENA SAYS: {line}\nATHENA ASKS: {ask}\nOPTIONS:\n{options}\n\n{rule} "
            "Keep words under 40 words, in character."
        )

        def valid(v: dict[str, Any]) -> bool:
            pick, words = v.get("pick"), v.get("words")
            if isinstance(pick, int) and 1 <= pick <= len(suggestions) and mode != "own_words":
                return not contradict
            return isinstance(words, str) and bool(words.strip())

        value, raw = _ask(prompt, valid)
        if value is None:
            self.fallbacks += 1
            r = self._fallback_answer(suggestions, mode)
            r.raw = raw
            return r
        pick = value.get("pick") if isinstance(value.get("pick"), int) else None
        words = value.get("words") if pick is None else None
        if mode == "own_words" or contradict:
            pick, words = None, value.get("words")
        r = Reply(pick=pick, words=(words or "").strip() or None, raw=raw)
        self.said.append(suggestions[pick - 1] if pick else str(r.words))
        return r

    def _fallback_answer(self, suggestions: list[str], mode: str) -> Reply:
        if suggestions and mode != "own_words":
            return Reply(pick=1, fallback=True)
        return Reply(words="Yes, that is right.", fallback=True)

    def review(self, labels: list[str]) -> Reply:
        """Which of her pencil pieces are wrong for the persona's truth."""
        if not self.enabled or not labels:
            return Reply(drop=[], fallback=not self.enabled)
        listing = "\n".join(f"- {label}" for label in labels)
        prompt = (
            f"{_card(self.persona)}Athena drew these guesses in pencil on your sketch:\n{listing}\n\n"
            "Which of them are wrong for your truth? Copy their text exactly. "
            '{"drop": ["<label>", ...]} (an empty list if all are right).'
        )
        value, raw = _ask(prompt, lambda v: isinstance(v.get("drop"), list))
        if value is None:
            self.fallbacks += 1
            return Reply(fallback=True, raw=raw)
        return Reply(drop=[str(x) for x in value["drop"] if str(x) in labels], raw=raw)

    def mark(self, cards: list[dict[str, Any]], never: bool) -> Reply:
        """Yes or no for each card she expects to file, from the truth; and a never line if asked."""
        ids = [str(c["id"]) for c in cards]
        if not self.enabled:
            return Reply(
                marks=dict.fromkeys(ids, "yes"), never="Never pay anything." if never else None, fallback=True
            )
        listing = "\n".join(f'- id "{c["id"]}": {c.get("label", "")} ({c.get("why", "")})' for c in cards)
        ask_never = (
            ' Also add one rule Athena must never break, in your words: "never": "<line>".'
            if never
            else ' "never": null.'
        )
        prompt = (
            f"{_card(self.persona)}Before a test run, Athena lists the cards she expects to file for you. "
            f"Mark each: yes if it should be filed according to your truth, no if not.\n{listing}\n\n"
            '{"marks": {"<id>": "yes"|"no", ...}, "never": ...}.' + ask_never
        )

        def valid(v: dict[str, Any]) -> bool:
            m = v.get("marks")
            return isinstance(m, dict) and all(str(m.get(i, "")).lower() in ("yes", "no") for i in ids)

        value, raw = _ask(prompt, valid)
        if value is None:
            self.fallbacks += 1
            return Reply(
                marks=dict.fromkeys(ids, "yes"),
                never="Never pay anything." if never else None,
                fallback=True,
                raw=raw,
            )
        marks = {i: str(value["marks"][i]).lower() for i in ids}
        line = value.get("never") if never and isinstance(value.get("never"), str) else None
        return Reply(marks=marks, never=line or ("Never pay anything." if never else None), raw=raw)

    def gap(self, sketch: list[str], cards: list[str]) -> Reply:
        """At the verdict: one gap between what was built and the truth, as a short note."""
        if not self.enabled:
            return Reply(note="It should also say when to do it.", fallback=True)
        prompt = (
            f"{_card(self.persona)}Athena built this from your words.\nSKETCH: {', '.join(sketch)}\n"
            f"CARDS IT FILES: {'; '.join(cards) or '(none)'}\n\nName the ONE most important thing that "
            'is missing or wrong compared to your truth, in one short sentence: {"note": "<sentence>"}.'
        )
        value, raw = _ask(prompt, lambda v: isinstance(v.get("note"), str) and bool(v["note"].strip()))
        if value is None:
            self.fallbacks += 1
            return Reply(note="It should also say when to do it.", fallback=True, raw=raw)
        return Reply(note=str(value["note"]).strip(), raw=raw)


if __name__ == "__main__":  # a quick parse check against the live persona (a few cents)
    from cases import CASES

    pm = PersonaModel(CASES[2].persona)
    r = pm.answer(
        "Two places requests come from - got it.",
        "Which app is the rental portal?",
        ["Buildium", "AppFolio", "TenantCloud", "A portal I built myself"],
        ["Repair requests by email", "Weekly list for the handyman"],
    )
    print(r)
    print(pm.mark([{"id": "e1", "label": "Leaking tap in flat 3", "why": "request by email"}], never=True))
