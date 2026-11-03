# Features

What is built, how it works, how it was verified. A concept moves here from `docs/concepts/` once it
is built; its design history stays in git.

- [Chore onboarding](chore-onboarding.md) - describe a need, watch it sketched in two views, test it against your own expectations, keep it (ADR 0007)
- [Twins](twins/README.md) - a clone that speaks for you on Gmail and Notion, set up with Athena (ADRs 0008-0010)
- [Settings](settings.md) - the engine her turns run on, the look both windows wear, the connected accounts and where the data lives (ADR 0012)
- [Devices](devices.md) - pair a phone or another computer with this one: a constellation, a pairing wizard that grows from the '+' node, and approvals armed after a pause (ADR 0017)
- [Her window - the transcript](her-window.md) - her words as rich text through one door, a reply's text, tool lines and cards in the order they streamed, new words fading in
- The frame both windows wear (ADR 0016): the surface as the landing, a bar that says where you are, a depth rail, a dock with her pill and the five places, and every page in the winning variant's idiom; the mapping, and what is not mapped, are in the ADR

## Open

- **Twins: the real-account run.** It waits for the owner: their own Google client and Notion key, and one real email. Steps in [Twins](twins/README.md#open-the-real-account-run-owner-present).
- **Blue Hour: the first run's art, the Rail view, and the rehearsal sandbox.** Parked; the key paste and probe are built. Design in [concepts/blue-hour-onboarding](../concepts/blue-hour-onboarding/README.md).
