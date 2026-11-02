"""The 10 onboarding use cases. Each holds the need typed at describe, the persona card (who, the
persona's truth that grading compares the sketch against, how they talk) and the case's overrides of
the default policy: the persona answers (a suggestion when one matches its truth, else its own words),
ink all after each turn, exit when agreed or after MAX_TURNS, mark the cards from its truth, keep.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

MAX_TURNS = 9

# The staged need, as scripts/stage_seam.py and athena.drafts.demo type it.
STAGED_NEED = (
    "Each month I check the after-school club's invoice against the days my kids actually went "
    "(the school portal has attendance) and dispute the extra days."
)

Answer = Literal["first", "persona", "own_words"]
Exit = Literal["agreed", "first_frame"]
Marks = Literal["yes", "persona"]


@dataclass(frozen=True)
class Persona:
    who: str
    truth: str  # what is really true about the chore; grading's fidelity is measured against it
    style: str


@dataclass(frozen=True)
class Case:
    id: int
    name: str
    need: str
    persona: Persona
    answer: Answer = "persona"
    exit: Exit = "agreed"
    marks: Marks = "persona"
    ink_all: bool = True
    drop_after_turn: int | None = None  # case 7: review pencil labels and drop the wrong ones
    contradict_on_turn: int | None = None  # case 7: once take back an earlier answer, in own words
    revise_once: bool = False  # case 8: "Not quite" at the first verdict, with a note
    never_line: bool = False  # case 9: one "she must never" line at the check
    fault_on_turn: int | None = None  # case 10: one injected engine failure on this /say turn
    skip_sites: bool = True  # every case: Skip every site at access (no sign-in outside the shell)
    expected: str = "saved"
    focus: str = ""  # what grading looks at first
    tags: tuple[str, ...] = field(default=())


PARENT = Persona(
    who="Dana, a parent of two (Mia 8, Leo 6) who works shifts as a nurse; organised but short on time.",
    truth=(
        "Once a month, when the Sunny Days after-school club emails its invoice (a PDF, around the 1st), "
        "Dana compares the billed days per child with the attendance the school portal shows. Any day "
        "billed but not attended is a dispute: Dana wants a ready-to-send dispute email to the club's "
        "billing address listing the dates per child, and signs (sends) it herself. Output: the drafted "
        "email plus a short list of disputed dates. Athena must never pay the invoice or email the "
        "club without Dana's yes."
    ),
    style="Brief and friendly, answers in one or two sentences.",
)

CASES: dict[int, Case] = {
    1: Case(
        id=1,
        name="baseline",
        need=STAGED_NEED,
        persona=PARENT,
        answer="first",
        marks="yes",
        focus="The staged need, her first suggestion every time: the reference walk.",
    ),
    2: Case(
        id=2,
        name="new-domain",
        need=(
            "My tenants send repair requests by email and through the rental portal, and every Monday "
            "I put them into one list for my handyman."
        ),
        persona=Persona(
            who="Sam, a small landlord with 6 flats in two buildings, does the books on weekends.",
            truth=(
                "Requests arrive in Sam's Gmail inbox and in the TenantCloud portal's maintenance tab. "
                "Every Monday morning Sam wants one list for the handyman (Ray) grouped by building, "
                "each line with flat number, problem, how urgent, and the tenant's phone. Urgent ones "
                "(water, heating, locks) go to the top. Sam reviews the list and forwards it to Ray "
                "himself. Never contact tenants, never promise a repair date."
            ),
            style="Practical, a little terse, uses landlord words like 'unit' and 'work order'.",
        ),
        focus="An unfamiliar domain: are her guesses sensible and her questions in order?",
    ),
    3: Case(
        id=3,
        name="vague-need",
        need="Help me with my emails.",
        persona=Persona(
            who="Priya, a freelance translator who gets 60-80 emails a day.",
            truth=(
                "The real need: each evening, find the emails from agencies that offer a translation job "
                "(subject usually has 'job', 'request' or a language pair like EN>DE) in Outlook, and "
                "put them in a short digest: agency, language pair, word count, deadline, rate. Priya "
                "decides which to accept and replies herself. Never reply to an agency, never accept "
                "a job. Priya reveals each part only when Athena asks about it."
            ),
            style=(
                "Vague at first; answers only what is asked, never volunteers the rest. If asked "
                "something broad, gives a broad answer."
            ),
        ),
        focus="A vague need: does she narrow it logically, one question at a time?",
    ),
    4: Case(
        id=4,
        name="over-specified",
        need=(
            "Every Friday afternoon I go through the Shopify orders of the week and the returns that came "
            "in through the Loop returns app, match each return to its order, and work out the refund "
            "(item price minus the 5 EUR return fee, shipping not refunded). Then I put the refunds into "
            "a Google Sheet called 'Refunds week N' with order number, customer, items, amount and "
            "reason, and I approve each refund myself in Shopify before it goes out. Never refund "
            "anything over 200 EUR without me, and never email the customer."
        ),
        persona=Persona(
            who="Marta, runs a small online ceramics shop on Shopify, very precise.",
            truth=(
                "Exactly as written in the need: Shopify orders and Loop returns, matched weekly on "
                "Friday, refund = item price minus 5 EUR, no shipping, into the Google Sheet "
                "'Refunds week N' (order number, customer, items, amount, reason); Marta approves each "
                "refund in Shopify. Never refund over 200 EUR, never email the customer."
            ),
            style="Precise, slightly impatient when asked something already stated.",
        ),
        focus="Everything was said up front: does she ask about slots already given?",
    ),
    5: Case(
        id=5,
        name="own-words",
        need=(
            "I keep forgetting to renew things - car insurance, the domain for my website, the kids' "
            "passports - and want a heads-up before each one runs out."
        ),
        persona=Persona(
            who="Tomas, a graphic designer, father of one, keeps everything in Google Calendar and Gmail.",
            truth=(
                "The renewal dates are in old confirmation emails in Gmail (insurer, domain registrar "
                "Namecheap, the passport office). Tomas wants a monthly list of what expires in the next "
                "60 days with the date and the link to renew, and a calendar reminder he approves before "
                "it is added. Never renew or pay anything."
            ),
            style="Chatty, always answers in his own sentences, never picks offered options.",
        ),
        answer="own_words",
        focus="Free text only: does she understand answers that do not match her suggestions?",
    ),
    6: Case(
        id=6,
        name="early-exit",
        need=(
            "When a supplier invoice arrives in my inbox, check it against the purchase order and tell "
            "me if the amounts differ."
        ),
        persona=Persona(
            who="Lena, office manager at a 12-person architecture studio.",
            truth=(
                "Supplier invoices come as PDFs to the office Outlook inbox; purchase orders live in a "
                "shared Excel file on OneDrive. Lena wants a note per invoice: matches, or the lines that "
                "differ. She pays invoices herself in the bank. Never pay, never reply to suppliers."
            ),
            style="Busy, wants it done; clicks write before answering anything.",
        ),
        exit="first_frame",
        focus="Exit after the first frame: does writing work with defaults, or what blocks it?",
    ),
    7: Case(
        id=7,
        name="correction",
        need=(
            "After each of my yoga classes, people book the next class through my booking site and some "
            "pay by bank transfer; I want to know who booked but has not paid yet."
        ),
        persona=Persona(
            who="Ines, a yoga teacher with 4 classes a week, books through Momence.",
            truth=(
                "Bookings are in Momence (the booking site). Payments come by bank transfer and show in "
                "the Revolut Business account with the student's name in the reference. Every Sunday "
                "evening (not after each class - Ines corrects this) she wants a list of who booked "
                "the coming week but has not paid, with the amount. She sends reminders herself. Never "
                "message students, never cancel a booking. There is no spreadsheet and no Stripe."
            ),
            style="Warm, sometimes changes her mind, corrects wrong guesses plainly.",
        ),
        drop_after_turn=2,
        contradict_on_turn=3,
        focus="She drops wrong pencil pieces and takes back an earlier answer: does Athena follow?",
    ),
    8: Case(
        id=8,
        name="not-quite",
        need=(
            "I run a book club and every month I need to collect who is coming, what they are bringing "
            "to eat, and send the host a summary."
        ),
        persona=Persona(
            who="Grace, retired teacher, organises a 15-member book club.",
            truth=(
                "Members reply to the monthly invite in a WhatsApp group and some by email (Gmail). Grace "
                "wants, three days before the meeting, a summary for that month's host: who is coming, "
                "who brings which dish, and anyone with a food allergy (the allergy list is in a Google "
                "Doc). Grace sends the summary to the host herself. Never post in the group."
            ),
            style="Polite, detailed, likes to double-check.",
        ),
        revise_once=True,
        focus="'Not quite' at the verdict with one gap named: does she close the gap on the way back?",
    ),
    9: Case(
        id=9,
        name="marks",
        need=STAGED_NEED,
        persona=Persona(
            who=PARENT.who,
            truth=PARENT.truth
            + " Only Mia goes on Wednesdays; Leo never goes on Fridays, so a Friday billed for Leo is "
            "always a dispute. Holidays (school closed) are never billable.",
            style=PARENT.style,
        ),
        never_line=True,
        focus="The check step from the persona's truth (at least one no if a card is wrong), a never line.",
    ),
    10: Case(
        id=10,
        name="real-site-failure",
        need=(
            "Every month I download my electricity bill from my supplier's website and log the amount "
            "and the kWh in my household budget."
        ),
        persona=Persona(
            who="Olu, a software tester living in London, tracks every household cost.",
            truth=(
                "The supplier is Octopus Energy; the bill is in the account at octopus.energy (the "
                "persona names this website when asked about apps). The budget is a Google Sheet "
                "'Household 2026' with a row per month: date, kWh, amount in GBP. Olu checks the row "
                "before it is saved. Never change the tariff, never pay anything."
            ),
            style="Matter-of-fact, names the exact website when asked where things are.",
        ),
        fault_on_turn=2,
        focus="A real website on an app piece; one failed reply recovered with Try again; sites skipped.",
    ),
}


def parse_cases(spec: str) -> list[int]:
    """'1-10', '1,3,7' or '2-4,9' -> sorted case ids; unknown ids are an error."""
    ids: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = (int(x) for x in part.split("-", 1))
            ids.update(range(a, b + 1))
        else:
            ids.add(int(part))
    unknown = sorted(ids - set(CASES))
    if unknown:
        raise SystemExit(f"unknown case(s): {unknown}; the cases are {sorted(CASES)}")
    return sorted(ids)
