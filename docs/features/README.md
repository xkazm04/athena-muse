# Features

What is built, how it works, how it was verified. A concept moves here from `docs/concepts/` once it
is built; its design history stays in git.

- [Chore onboarding](chore-onboarding.md) - describe a need, watch it sketched in two views, test it against your own expectations, keep it (ADR 0007)
- [Twins](twins/README.md) - a clone that speaks for you on Gmail and Notion, set up with Athena (ADRs 0008-0010)
- [Settings](settings.md) - the engine her turns run on, the look both windows wear, the connected accounts and where the data lives (ADR 0012)
- [Devices](devices.md) - pair a phone or another computer with this one: a constellation, a pairing wizard that grows from the '+' node, and approvals armed after a pause (ADR 0017)
- [Apps](apps.md) - a project's apps wired by kind (a website, a page on this computer, an app on this computer, a tool she starts), and a paired computer's copy used for one job (ADRs 0025, 0026)
- [The Spread](the-spread.md) - every exchange is a two-page spread read like a book: what you asked and what she did, with its moments, length and est. cost, on the left, her answer on the right; pages for the history, the report, a chore being drawn, the report seen elsewhere and the costs; her window is the book folded to one page (ADR 0024)
- [Her window - her words](her-window.md) - her words as rich text through one door, tool lines and cards in the order they streamed and kept after a reload, report parts in a comparative answer (ADR 0022); its layout and look are The Spread's
- The frame both windows wear (ADR 0016): the surface as the landing, a bar that says where you are, a depth rail, a dock with her pill and the five places, and every page in the winning variant's idiom; the mapping, and what is not mapped, are in the ADR

## Open

- **Twins: the real-account run.** It waits for the owner: their own Google client and Notion key, and one real email. Steps in [Twins](twins/README.md#open-the-real-account-run-owner-present).
- **Blue Hour: the first run's art, the Rail view, and the rehearsal sandbox.** Parked; the key paste and probe are built. Design in [concepts/blue-hour-onboarding](../concepts/blue-hour-onboarding/README.md).
