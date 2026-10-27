"""Chores: playbooks as data, their invented portals, and the featured status (ADR 0005).

A chore is a folder under `playbooks/<id>/`: `playbook.json` (what it is and its bar), `world.json`
(the invented portals: apps, tools, tables, phases), `truth.json` (the answer key, never shown to
Athena) and `senses/` (media index, fixtures, the sense answer key, and the built `sensed.json` and
`proofs.json`). `spec` loads and checks one; `portal` serves its apps to a turn; `routes` puts the
library on the wire.
"""
