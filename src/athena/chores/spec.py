"""Load and check one chore folder (stub: WP2 fills the bodies, keeping every name and signature)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from athena.contracts import ChoreDetail, ChoreSummary, FeaturedStatus

#: Where the library lives: `ATHENA_PLAYBOOKS` when set, else `playbooks/` at the repo root.
PLAYBOOKS_ENV = "ATHENA_PLAYBOOKS"


class ChoreError(ValueError):
    """Every problem with one chore folder, at once."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Tool:
    name: str
    kind: str  # "READ", or a gated kind such as "REACHES_A_PERSON" / "PERMANENT"
    description: str
    params: dict[str, dict[str, Any]]
    returns: dict[str, Any] = field(default_factory=dict)  # READ: table, match, page_size...
    says: str = ""  # gated: the page's answer once it runs, with {param} slots


@dataclass(frozen=True)
class App:
    app_id: str
    name: str
    origin: str
    tools: tuple[Tool, ...]
    view: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Phase:
    app: str
    message: str
    nudges: int = 0


@dataclass(frozen=True)
class Target:
    tool: str
    key: str
    eligible: dict[str, dict[str, Any]]  # key value -> {value_usd, why, expect?}
    traps: dict[str, str]
    neutral: tuple[str, ...] = ()


@dataclass(frozen=True)
class Chore:
    id: str
    root: Path
    showcase: dict[str, Any]  # playbook.json as written
    today: str
    apps: tuple[App, ...]
    tables: dict[str, list[dict[str, Any]]]  # world tables plus sensed tables
    phases: tuple[Phase, ...]
    targets: tuple[Target, ...]
    forbidden: tuple[str, ...] = ()

    def app(self, app_id: str) -> App:
        raise NotImplementedError


def library_dir() -> Path:
    raise NotImplementedError


def load_chore(root: Path) -> Chore:
    raise NotImplementedError


def load_library(base: Path | None = None) -> list[Chore]:
    raise NotImplementedError


def featured_status(root: Path) -> FeaturedStatus:
    raise NotImplementedError


def summary(chore: Chore) -> ChoreSummary:
    raise NotImplementedError


def detail(chore: Chore) -> ChoreDetail:
    raise NotImplementedError
