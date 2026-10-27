"""The senses: recorded media to cited tables, and the proofs that they read it right (ADR 0005).

A chore's `senses/media.json` lists its media; each item names the sense that reads it. A sense
works through three roles (segmenter, transcriber, reader) whose backends are chosen per run:
recorded fixtures, Muse Code on the person's plan, or Meta's API. `build` writes `sensed.json`,
the tables the chore's portals read; `prove` writes `proofs.json`, each spike proof measured
against `senses/key.json`, which Athena never sees. Run `python -m athena.senses --help`.
"""
