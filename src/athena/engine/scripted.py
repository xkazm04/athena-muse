"""The no-key engine: deterministic, labelled simulated everywhere it shows."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

from athena.contracts import LABEL_MAX, EngineId, Probe
from athena.engine import TextDelta, ToolCall, Usage

URL = re.compile(r"https?://[^\s,;)\"']+", re.IGNORECASE)


def _words(text: str) -> int:
    return len(text.split())


def _rest(text: str, word: str) -> str:
    i = text.lower().find(word)
    rest = text[i + len(word) :] if i >= 0 else text
    return rest.strip(" \t\r\n:,-.") or text.strip()


def _chunks(text: str) -> Iterator[str]:
    parts = text.split(" ")
    for i in range(0, len(parts), 3):
        yield " ".join(parts[i : i + 3]) + (" " if i + 3 < len(parts) else "")


# --- the stage (ADR 0007, 0010) -------------------------------------------------------------------
# The simulated frame reads the design frame the way a model would: the places it lists (in order,
# with each one's meaning and usual kind) and the coverage lines under them. Any rubric plays.

_PLACE_LINE = re.compile(r"^- ([a-z_]+): (.+) \(usual kind: ([a-z_]+)\)$", re.M)
_COVERAGE_LINE = re.compile(r"^- ([a-z_]+): (0\.5|0|1|skipped)$", re.M)
QUOTE_WORDS = 8  # the person's first words, quoted into the first place's node

_PROPOSALS: dict[str, tuple[str, str, list[str]]] = {
    # the chore's places: (the proposal's label, the question, its suggested answers)
    "apps": ("The website where it happens", "Where does this happen?", ["A website", "Email", "Both"]),
    "inputs": (
        "The page she reads first",
        "What should she read first?",
        ["A web page", "My email", "A letter"],
    ),
    "steps": (
        "Check, then compare",
        "What order does she work in?",
        ["Check, then compare", "Compare first", "You tell her"],
    ),
    "hand": (
        "You sign before anything is sent",
        "What should wait for your signature?",
        ["Anything she sends", "Only payments", "Nothing"],
    ),
    "output": (
        "A short summary for you",
        "What do you get at the end?",
        ["A short summary", "A list of problems", "A filled form"],
    ),
    "never": (
        "Never pay anything",
        "What must she never do?",
        ["Never pay", "Never delete", "Never write to anyone"],
    ),
}
_ANY_ANSWERS = ["Like that", "Something else", "Not sure yet"]


def _cut(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _proposal(place: str, meaning: str) -> tuple[str, str, list[str]]:
    """The canned proposal for a place: the chore's own lines, else one made from its meaning."""
    if place in _PROPOSALS:
        return _PROPOSALS[place]
    words = " ".join(meaning.split())
    return _cut(words[:1].upper() + words[1:], LABEL_MAX), f"What about {words}?", _ANY_ANSWERS


def _frame(messages: list[dict[str, Any]]) -> tuple[list[tuple[str, str, str]], dict[str, str]]:
    """((place, meaning, usual kind) in rubric order, coverage per place) from the design frame."""
    system = str(messages[0].get("content") or "") if messages else ""
    places = _PLACE_LINE.findall(system)
    names = {p for p, _, _ in places}
    return places, {p: v for p, v in _COVERAGE_LINE.findall(system) if p in names}


def _stage(messages: list[dict[str, Any]], said: str) -> tuple[str, list[ToolCall]]:
    """The first time (the first place empty): draw it in the person's first words, ask about the
    next empty place. Later: propose one node for the next empty place and ask about it."""
    places, cov = _frame(messages)
    if not places:
        return "(Simulated) I have nothing to draw here.", []
    first, _, first_kind = places[0]
    if cov.get(first, "0") == "0":
        words = " ".join(said.split()[:QUOTE_WORDS]) or "The job"
        draw = ToolCall(
            "call_sim1",
            "sketch",
            {"op": "add", "kind": first_kind, "slot": first, "label": _cut(words, LABEL_MAX), "quote": words},
        )
        cov[first] = "1"
        line = "(Simulated) I drew what you said."
    else:
        draw = None
        line = "(Simulated) Here is a guess for you to check."
    nxt = next(((p, m, k) for p, m, k in places[1:] if cov.get(p, "0") == "0"), None)
    if nxt is None:
        return "(Simulated) Every part of the sketch has something in it; confirm what is right.", (
            [draw] if draw else []
        )
    place, meaning, kind = nxt
    label, question, answers = _proposal(place, meaning)
    calls = (
        [draw]
        if draw
        else [ToolCall("call_sim1", "sketch", {"op": "add", "kind": kind, "slot": place, "label": label})]
    )
    calls.append(
        ToolCall("call_sim2", "ask", {"slot": place, "text": question, "suggestions": " | ".join(answers)})
    )
    return line, calls


# --- a twin (ADR 0008-0010): its setup, the slips' engine call, the dress rehearsal, its missions and
# how it sounds ---------------------------------------------------------------------------------------
# The setup plays the prototype's staged Partnerships example step by step; the step is the number of
# questions asked so far, which the twin's frame lists per place. The person's own words are quoted
# back, so what they picked decides what is ink. The JSON calls are recognised by their headings.

TWIN_SETUP = "## Setting up a twin with the person"
TWIN_VOICE = "## Learning the person's voice"
TWIN_CAST = "## Casting the rehearsal"
TWIN_OTHER = "## Playing the other side"
TWIN_DRAFT = "## Drafting the next message"
TWIN_JUDGE = "## Judging the rehearsal"
TWIN_MISSION_JUDGE = "## Judging the mission"
TWIN_PREVIEW = "## Previewing the voice"
TWIN_GOALS = "## Suggesting goals"
_FROM = re.compile(r"^from: .*$", re.M)
_DIAL = re.compile(r"^- (\w+): (\d) of 5", re.M)
_YES = re.compile(r"\b(go for it|go ahead|sounds (good|fair|great)|yes|deal|agreed)\b", re.I)
_ASKED_LINE = re.compile(r"^- ([a-z_]+) asked (\d+)$", re.M)
_SO_FAR = re.compile(r"Messages so far: (\d+)")
_MONEY = re.compile(r"\$|\bmoney\b|\bfee\b", re.I)
_VERBS = frozenset({"Get", "Ask", "Follow", "Book", "Win", "Chase", "Agree", "Find", "Thank"})


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


class _Twin:
    """One simulated setup reply: piece adds and dials, at most one question."""

    def __init__(self) -> None:
        self.calls: list[ToolCall] = []

    def _call(self, name: str, args: dict[str, Any]) -> None:
        self.calls.append(ToolCall(f"call_sim{len(self.calls) + 1}", name, args))

    def add(
        self, piece_id: str, place: str, kind: str, label: str, detail: str = "", quote: str = ""
    ) -> None:
        args = {"op": "add", "id": piece_id, "place": place, "kind": kind, "label": _cut(label, LABEL_MAX)}
        if detail:
            args["detail"] = detail
        if quote:
            args["quote"] = quote
        self._call("sketch", args)

    def dial(self, dial: str, value: int, quote: str) -> None:
        self._call("sketch", {"op": "dial", "dial": dial, "value": str(value), "quote": quote})

    def ask(self, place: str, text: str, answers: list[str]) -> None:
        self._call("ask", {"place": place, "text": text, "suggestions": " | ".join(answers)})


# (her line, the question's place, its text, its suggested answers), per step; the pieces are below.
_STEPS: tuple[tuple[str, str, str, list[str]], ...] = (
    (
        "A twin for creator outreach: it writes as you and keeps each conversation going until you have "
        "a yes. I'll build it here while we talk.",
        "who",
        "Who should it sign as when it writes?",
        ["As me, by my first name", "As me, from my studio", "As my assistant, on my behalf"],
    ),
    (
        "It signs that way. To write to people it needs your mailbox: sign in with Google; I'll only ask "
        "to read and send mail.",
        "channels",
        "Sign in with the Google account it should write from.",
        ["Sign in with Google", "Use a different account", "Skip mail for now"],
    ),
    (
        "To sound like you, it learns only from mail you wrote yourself. Here is your sent mail; I'd keep "
        "the ones I marked.",
        "voice",
        "Which of these sound like you?",
        ["The ones you marked", "All of them", "I'll pick others"],
    ),
    (
        "From those, this is how you write. I've set its style to match; the dials show where each value "
        "came from.",
        "voice",
        "Is that a bit too casual for a first message to a stranger?",
        ["Keep it as it is", "A little more formal at first contact", "Shorter still"],
    ),
    (
        "Noted. Next, what it may know: connect Notion and pick the pages it can answer from.",
        "knowledge",
        "Paste the key from your Notion integration, then choose its pages.",
        ["I've pasted it", "Show me where to find it", "Skip Notion for now"],
    ),
    (
        "These are the pages it can see. I'd leave anything personal out.",
        "knowledge",
        "Which pages may it answer from?",
        ["The ones you marked", "Everything it can see", "Only the first one"],
    ),
    (
        "It will answer from those and nothing else. Notion can do more than answer: these are "
        "ready-made chores it can run there.",
        "chores",
        "Which should it run?",
        ["The ones you marked", "All it can run", "None for now"],
    ),
    (
        "Now the lines it must never cross. I'd start with these.",
        "never",
        "Anything to add?",
        ["Those are right", "Also: never send attachments", "Also: never write after 9 pm their time"],
    ),
    (
        "How much may it send without you? If anything is on its risk list, it always waits for you.",
        "autonomy",
        "For Gmail?",
        ["Assist: I sign every send", "First message Assist, replies Auto", "Auto, with the risk check"],
    ),
    (
        "Reading your mail, I noticed a few things about you. It only uses the ones you keep.",
        "memory",
        "Keep these?",
        ["Yes to the ones you marked", "Yes to all of them", "One by one"],
    ),
    (
        "It's ready to try: give it a first mission. It will rehearse on your practice page, with me "
        "playing the other side.",
        "mission",
        "What should it get done first?",
        [
            "Get Lumen Vale's yes to feature 'Glass Harbor'",
            "Ask three shortlisted creators if they're open",
            "Follow up with Mira Soleil",
        ],
    ),
)
_MISSION_SET = (
    "Mission set. I'll play the other side on your practice page. Mark each draft 'that's me' or "
    "'not me'; anything you change teaches it."
)


def _twin_stage(messages: list[dict[str, Any]], said: str) -> tuple[str, list[ToolCall]]:
    system = str(messages[0].get("content") or "") if messages else ""
    step = sum(int(n) for _, n in _ASKED_LINE.findall(system))
    said = " ".join(said.split())
    low = said.lower()
    t = _Twin()
    if step == 0:
        t.add("p_name", "who", "name", "Partnerships", "the name I'd give it")
        t.add("p_purpose", "who", "purpose", said, quote=" ".join(said.split()[:QUOTE_WORDS]))
        t.add(
            "p_mtype",
            "mission",
            "line",
            "Get a creator's permission to feature their track",
            "the kind of mission it will run",
        )
    elif step == 1:
        t.add("p_sign", "who", "line", "Signs " + _lower_first(said), quote=said)
        t.add("p_gmail", "channels", "gmail", "Gmail", "waiting for you to sign in")
    elif step == 4:
        if "formal" in low:
            t.add("p_v5", "voice", "line", "First message: full sentences, no slang", quote=said)
            t.dial("formality", 3, said)
        elif "shorter" in low:
            t.add("p_v5", "voice", "line", "Shorter than it would write on its own", quote=said)
            t.dial("length", 1, said)
        t.add("p_notion", "channels", "notion", "Notion", "waiting for your key")
    elif step == 6:
        t.add("p_n0", "never", "line", "Never quote a page you didn't share")
    elif step == 7:
        t.add("p_n1", "never", "line", "Never promise money or a fee")
        t.add("p_n2", "never", "line", "Never agree to exclusive rights")
        t.add("p_n3", "never", "line", "Never share another creator's contact")
    elif step == 8 and low.startswith("also:"):
        rest = said[5:].strip()
        t.add("p_n4", "never", "line", rest[:1].upper() + rest[1:], quote=rest)
    elif step == len(_STEPS):
        t.add("p_ms", "mission", "line", said, "rehearse first", quote=said)
    if step < len(_STEPS):
        line, place, text, answers = _STEPS[step]
        t.ask(place, text, answers)
    else:
        line = _MISSION_SET if step == len(_STEPS) else "It's ready to rehearse whenever you are."
    return f"(Simulated) {line}", t.calls


def _who(goal: str) -> str:
    found = re.search(r"([A-Z][\w&]*(?:\s+[A-Z][\w&]*)*)'s\b", goal) or re.search(
        r"\b(?:with|to|from)\s+([A-Z][\w&]*(?:\s+[A-Z][\w&]*)*)", goal
    )
    if found is None:
        return "Practice partner"
    words = found.group(1).split()
    return " ".join(words[1:] if len(words) > 1 and words[0] in _VERBS else words)


def _voice(user: str) -> dict[str, Any]:
    ids = re.findall(r"^sample id: (\S+)$", user, re.M) or ["s1"]

    def some(*at: int) -> list[str]:
        return list(dict.fromkeys(ids[i % len(ids)] for i in at))

    return {
        "voice": [
            {"label": "Warm and short, first name first", "evidence": some(0, 1, 3)},
            {"label": "Opens with something specific about their work", "evidence": some(0, 2)},
            {"label": "Ends with one clear question", "evidence": some(1, 2, 3)},
            {"label": "Signs off the same way every time", "evidence": some(0, 1, 2, 3)},
        ],
        "dials": {
            "formality": 2,
            "warmth": 4,
            "humor": 2,
            "energy": 3,
            "length": 2,
            "directness": 4,
            "expressiveness": 3,
        },
        "memory": [
            {
                "fact": "You make a free visualizer in exchange for a credit",
                "sample": ids[0],
                "suggest": "keep",
            },
            {"fact": "You publish on Fridays", "sample": some(2)[0], "suggest": "keep"},
            {
                "fact": "Your channel has about 12,000 subscribers",
                "sample": some(3)[0],
                "suggest": "drop",
                "reason": "It changes; it reads the page fresh instead",
            },
            # suggested keep here; the code suggests drop: a promise of money
            {"fact": "You once offered $50 for a track", "sample": some(1)[0], "suggest": "keep"},
        ],
    }


def _other(system: str, goal: str, so_far: int) -> dict[str, Any]:
    """Athena playing the other side: a question, then a yes. A goal about money gets a money ask."""
    who = m.group(1) if (m := re.search(r"playing (.+?) in a dress rehearsal", system)) else "them"
    if so_far >= 3:
        return {
            "text": f"(Simulated) Sounds fair. Go for it, credit me as {who} and link the track please.",
            "done": True,
        }
    if _MONEY.search(goal):
        return {"text": "(Simulated) Hey, I'd want $200 for it, is that OK?", "done": False}
    return {
        "text": "(Simulated) Hey! That sounds great honestly. What would I get out of it? And would it need "
        "to be exclusive to your channel?",
        "done": False,
    }


def _draft(user: str, goal: str, so_far: int) -> dict[str, Any]:
    """The twin's draft: the staged first message, the held reply, the reply that goes alone."""
    to = m.group(1).strip() if (m := re.search(r"You write to: (.+)", user)) else "there"
    # the quoted title, not an apostrophe ("Lumen Vale's yes to feature 'Glass Harbor'")
    track = m.group(1) if (m := re.search(r"(?:^|\s)'([^']+)'", goal)) else "your track"
    if so_far == 0:
        text = (
            f"(Simulated) Hi {to.split()[0]}, I've had '{track}' on repeat all week; the way it opens up "
            "after the second chorus is lovely. I make music visualizers and feature tracks I love every "
            f"Friday. Would you be open to me featuring '{track}' with a full visualizer and a credit to "
            "you?\n\ncheers"
        )
        return {"text": text, "confidence": 84, "risks": []}
    if so_far < 4 and "$" in user:
        text = "(Simulated) Thanks for saying so. Let me check what I can do and come back to you.\n\ncheers"
        return {"text": text, "confidence": 62, "risks": []}
    if so_far < 4:
        text = (
            "(Simulated) Great question! You'd get a free visualizer you can use anywhere, plus a credit and "
            "link in the description. And no, totally not exclusive, it's yours to share wherever you "
            "like!\n\ncheers"
        )
        return {"text": text, "confidence": 77, "risks": []}
    text = (
        f"(Simulated) Brilliant, thank you! It goes out this Friday, credited to {to} with a link to "
        f"'{track}'. I'll send you the link when it's live.\n\ncheers"
    )
    return {"text": text, "confidence": 91, "risks": []}


# --- a live twin's own calls: a mission's judgement and drafts, and how it sounds -----------------------
# A mission reads a real Gmail thread, fenced as `gmail`; a rehearsal's drafts read the practice page.


def _their_last(user: str) -> str:
    """The text of the thread's last message: what follows its last `from:` header block."""
    found = list(_FROM.finditer(user))
    if not found:
        return ""
    rest = user[found[-1].end() :]
    body = rest.split("\n\n", 1)[1] if "\n\n" in rest else rest
    return body.split("gmail:", 1)[0].strip()


def _said_yes(user: str) -> bool:
    """Their last message says yes and asks nothing more."""
    last = _their_last(user)
    return bool(_YES.search(last)) and "?" not in last


def _mission_judge(user: str) -> dict[str, Any]:
    """Resolved once their last message says yes; otherwise it is still going."""
    if _said_yes(user):
        return {"state": "resolved", "note": "(Simulated) They said yes.", "confidence": 88}
    return {"state": "open", "note": "(Simulated) They wrote back; it answers.", "confidence": 80}


def _mission_draft(user: str, goal: str) -> dict[str, Any]:
    """A mission's draft: a first message toward the goal, an answer to their question (below the
    usual bar of 80, so on Auto it waits for the person), or a thank-you once they said yes."""
    to = m.group(1).strip() if (m := re.search(r"You write to: (.+)", user)) else "there"
    first = (to.split("@")[0].split() or ["there"])[0]
    if "This is the first message" in user:
        text = (
            f"(Simulated) Hi {first}, I'm writing about this: {_lower_first(goal)}. "
            "Would that work for you?\n\ncheers"
        )
        return {"text": text, "confidence": 84, "risks": [], "subject": _cut(goal, 60)}
    if _said_yes(user):
        text = f"(Simulated) Brilliant, thank you {first}! I'll take it from here and let you know.\n\ncheers"
        return {"text": text, "confidence": 92, "risks": []}
    text = (
        f"(Simulated) Thanks for getting back to me, {first}. To your question: it is as I said, and "
        "nothing more is asked of you. Shall I go ahead?\n\ncheers"
    )
    return {"text": text, "confidence": 74, "risks": []}


def _preview(system: str, user: str) -> dict[str, Any]:
    """How the twin sounds: its reply to the message given, or to one it writes first. The reply moves
    with its formality and length dials, so a change shows."""
    dials = {name.lower(): int(v) for name, v in _DIAL.findall(system)}
    inbound = (
        ""
        if "The message to answer:" in user
        else (
            "(Simulated) Hi! I came across your work and wondered if you'd be open to working together. "
            "What would that look like?"
        )
    )
    hello = "Hello" if dials.get("formality", 3) >= 3 else "Hey"
    text = f"(Simulated) {hello}, thanks for writing! Happy to: here is what I had in mind."
    if dials.get("length", 3) >= 3:
        text += " I'd keep it simple, credit you properly and send everything over before it goes out."
    if "Signs off the same way every time" in system:
        text += "\n\ncheers"
    return {"inbound": inbound, "text": text}


def _goals(user: str) -> dict[str, Any]:
    """Three goals for a new mission: toward a yes on the conversation's subject, or, to someone new,
    a first introduction. Plain, so the person may take one as it is."""
    to = m.group(1).strip() if (m := re.search(r"Who it writes to: (.+)", user)) else "them"
    first = (to.split("@")[0].split() or ["them"])[0]
    subject = m.group(1).strip() if (m := re.search(r"^Subject: (.+)$", user, re.M)) else ""
    if "They have not written yet" in user:
        goals = [
            f"Introduce yourself to {first} and ask for a short call",
            f"Ask {first} whether they would like to work together",
            f"Get {first}'s yes to a first meeting",
        ]
    else:
        goals = [
            f"Get {first}'s yes to '{_cut(subject, 40)}'" if subject else f"Get {first}'s yes",
            f"Answer {first}'s questions and agree on next steps",
            f"Thank {first} and close the conversation kindly",
        ]
    return {"goals": goals}


def _twin_json(system: str, user: str) -> str | None:
    """The answer to one of a twin's JSON calls, or None when the call is not a twin's."""
    so_far = int(m.group(1)) if (m := _SO_FAR.search(user)) else 0
    goal = m.group(1) if (m := re.search(r"(?:The twin's goal|The goal): (.+)", user)) else ""
    answer: dict[str, Any] | None = None
    if TWIN_VOICE in system:
        answer = _voice(user)
    elif TWIN_CAST in system:
        answer = {"with": _who(goal)}
    elif TWIN_OTHER in system:
        answer = _other(system, goal, so_far)
    elif TWIN_DRAFT in system and ("<<<gmail:" in user or "starts a new conversation" in system):
        answer = _mission_draft(user, goal)
    elif TWIN_DRAFT in system:
        answer = _draft(user, goal, so_far)
    elif TWIN_JUDGE in system:
        answer = {"state": "resolved", "note": "(Simulated) They agreed to the feature."}
    elif TWIN_MISSION_JUDGE in system:
        answer = _mission_judge(user)
    elif TWIN_PREVIEW in system:
        answer = _preview(system, user)
    elif TWIN_GOALS in system:
        answer = _goals(user)
    return json.dumps(answer) if answer is not None else None


class ScriptedEngine:
    id: EngineId = "scripted"
    model = "scripted"
    simulated = True
    cost_estimated = False

    def probe(self) -> Probe:
        return {"ok": True, "model": "scripted", "latency_ms": 0}

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]:
        offered = {t.get("function", {}).get("name") for t in tools}
        prompt = sum(_words(str(m.get("content") or "")) for m in messages)
        last = messages[-1] if messages else {}
        system = str(messages[0].get("content") or "") if messages else ""
        if "ask" in offered:  # a stage turn (ADR 0007): one simulated frame, then nothing more
            if last.get("role") != "tool":
                stage = _twin_stage if TWIN_SETUP in system else _stage
                reply, calls = stage(messages, self._last_person(messages))
                for chunk in _chunks(reply):
                    yield TextDelta(chunk)
                yield from calls
            yield Usage(input_tokens=prompt, output_tokens=0)
            return
        answer = None if offered else _twin_json(system, self._last_person(messages))
        if answer is not None:  # a twin's JSON call: the slips' learning, the rehearsal's parts
            yield TextDelta(answer)
            yield Usage(input_tokens=prompt, output_tokens=_words(answer))
            return
        call: ToolCall | None = None
        if last.get("role") == "tool":
            body = str(last.get("content") or "").strip().splitlines()
            first = body[0][:120] if body else "done"
            reply = f"(Simulated) Done. {first}"
        else:
            reply, call = self._reply(self._last_person(messages), offered)
        for chunk in _chunks(reply):
            yield TextDelta(chunk)
        if call is not None:
            yield call
        yield Usage(input_tokens=prompt, output_tokens=_words(reply))

    @staticmethod
    def _last_person(messages: list[dict[str, Any]]) -> str:
        for m in reversed(messages):
            if m.get("role") == "user":
                return str(m.get("content") or "")
        return ""

    @staticmethod
    def _reply(text: str, offered: set[Any]) -> tuple[str, ToolCall | None]:
        low = text.lower()
        url = URL.search(text)
        if "remember" in low and "remember" in offered:
            fact = _rest(text, "remember")
            return "(Simulated) I will keep that.", ToolCall("call_sim1", "remember", {"text": fact})
        if "brief" in low and "propose_brief" in offered:
            brief = _rest(text, "brief")
            return "(Simulated) Here is a brief for you to sign.", ToolCall(
                "call_sim1", "propose_brief", {"brief": brief}
            )
        if url and "app" in low and "add_app" in offered:
            return "(Simulated) I can add that app once you sign.", ToolCall(
                "call_sim1", "add_app", {"origin": url.group(0)}
            )
        if ("what do you know" in low or "recall" in low) and "recall" in offered:
            query = _rest(text, "recall") if "recall" in low else text.strip()
            return "(Simulated) Let me look.", ToolCall("call_sim1", "recall", {"query": query})
        topic = text.strip()[:80] or "that"
        return f"(Simulated reply, no Meta key yet.) You said: {topic}", None
