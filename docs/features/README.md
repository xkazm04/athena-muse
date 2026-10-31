# Features

What is built, how it works, how it was verified. A concept moves here from `docs/concepts/` once it
is built; its design history stays in git.

- [Chore onboarding](chore-onboarding.md) - describe a need, watch it sketched in two views, test it against your own expectations, keep it (ADR 0007)
- [Twins](twins/README.md) - a clone that speaks for you on Gmail and Notion, set up with Athena (ADRs 0008-0010)
- [Settings](settings.md) - the engine her turns run on, the look both windows wear, the connected accounts and where the data lives (ADR 0012)

## Open

- **Twins: the real-account run.** It waits for the owner: their own Google client and Notion key, and one real email. Steps in [Twins](twins/README.md#open-the-real-account-run-owner-present).
- **Blue Hour: the first run's art, the Rail view, and the rehearsal sandbox.** Parked; the key paste and probe are built. Design in [concepts/blue-hour-onboarding](../concepts/blue-hour-onboarding/README.md).
