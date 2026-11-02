"""The blind check: a transcript the Director grades must not say which engine or model ran it.

    python scripts/parity/blind.py --self-test      # proves the check fails on a crafted transcript
    python scripts/parity/blind.py <out>            # checks every transcript.md under a run folder

Product text (her lines, the persona's words) that names an engine is redacted with REDACTED before it
reaches the transcript, and the count is kept in run.json (`ui.redacted`); `assert_blind` then fails
loudly on whatever is left. "Athena" is her own name and is fine.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# A name counts when no letter touches it: "Claude Code", "claude_code" and "muse-spark-1.3" are
# caught, "Museum" and "metadata" are not.
NAMES = ("claude", "sonnet", "muse", "haiku", "meta", "opus")
REDACTED = "[redacted]"


def _pattern(extra: tuple[str, ...] = ()) -> re.Pattern[str]:
    words = sorted({w.lower() for w in (*NAMES, *extra) if w}, key=len, reverse=True)
    alt = "|".join(re.escape(w) for w in words)
    return re.compile(rf"(?<![a-z])(?:{alt})(?![a-z])", re.IGNORECASE)


def redact(text: str, extra: tuple[str, ...] = ()) -> tuple[str, int]:
    """The text with every engine or model name replaced by REDACTED, and how many were replaced."""
    return _pattern(extra).subn(REDACTED, text)


def leaks(text: str, extra: tuple[str, ...] = ()) -> list[str]:
    """Every engine or model name still in the text (case-insensitive), in order."""
    return [m.group(0) for m in _pattern(extra).finditer(text)]


class BlindLeak(AssertionError):
    pass


def assert_blind(text: str, where: str, extra: tuple[str, ...] = ()) -> None:
    found = leaks(text, extra)
    if found:
        raise BlindLeak(f"{where} names an engine or model: {sorted(set(found))}")


def self_test() -> None:
    crafted = "## Turn 1\nHer line: I am Muse, here to help.\nYou: fine\n"
    try:
        assert_blind(crafted, "crafted transcript")
    except BlindLeak as e:
        print(f"ok: the check fails on a crafted transcript ({e})")
    else:
        raise SystemExit("FAIL: a transcript naming Muse passed the blind check")
    for name in ("Claude Code", "claude_code", "muse-spark-1.3", "SONNET", "Haiku", "Meta"):
        if not leaks(f"x {name} y"):
            raise SystemExit(f"FAIL: {name!r} was not caught")
    for fine in ("Athena", "Museum", "metadata", "a claudestine plan"):
        if leaks(fine):
            raise SystemExit(f"FAIL: {fine!r} was caught but names no engine")
    clean, n = redact("Muse says hi to Claude")
    if n != 2 or leaks(clean):
        raise SystemExit(f"FAIL: redaction left {clean!r} ({n})")
    print("ok: names caught, ordinary words pass, redaction counts")


def main() -> None:
    if sys.argv[1:] == ["--self-test"]:
        self_test()
        return
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    bad = 0
    for t in sorted(Path(sys.argv[1]).glob("*/transcript.md")):
        try:
            assert_blind(t.read_text(encoding="utf-8"), t.parent.name)
        except BlindLeak as e:
            bad += 1
            print(f"LEAK {e}")
    if bad:
        raise SystemExit(f"{bad} transcript(s) are not blind")
    print("ok: every transcript is blind")


if __name__ == "__main__":
    main()
