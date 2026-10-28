"""Load and check one chore folder (ADR 0005).

`load_chore` reads `playbook.json`, `world.json`, `truth.json` and, when built, `senses/sensed.json`,
and reports every problem with the folder at once. `featured_status`, `summary` and `detail` put a
loaded chore on the wire.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast, get_args

from athena.contracts import (
    BenchSummary,
    ChoreDetail,
    ChoreOrigin,
    ChoreSummary,
    FeaturedStatus,
    ProofRow,
    SenseName,
)
from athena.errors import ApiError

#: Where the library lives: `ATHENA_PLAYBOOKS` when set, else `playbooks/` at the repo root.
PLAYBOOKS_ENV = "ATHENA_PLAYBOOKS"
#: The person's own chores (ADR 0007): `<data_dir>/chores/<id>/`, never in the repository.
USER_LIBRARY = "chores"
TAXONOMY = "taxonomy.json"
#: A chore id is its folder name: lowercase words joined by hyphens.
CHORE_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,79}")

log = logging.getLogger(__name__)

PARAM_TYPES = frozenset({"string", "integer", "number", "boolean"})
SENSES: frozenset[str] = frozenset(get_args(SenseName))
FEATURED_KEYS = frozenset({"senses", "spike", "since"})
#: A proof run on one of these backends was run on one of Meta's models.
META_BACKENDS = frozenset({"meta", "muse_code"})
#: The phrase a missing-table problem carries, so a caller can tell that rule's problems apart.
MISSING_TABLE = "which no world or sensed table has"


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
    origin: ChoreOrigin = "library"

    def app(self, app_id: str) -> App:
        for a in self.apps:
            if a.app_id == app_id:
                return a
        raise ApiError("unknown_ref", f"the chore {self.id} has no app called {app_id}")


def library_dir() -> Path:
    env = os.environ.get(PLAYBOOKS_ENV, "").strip()
    if env:
        return Path(env)
    # src/athena/chores/spec.py -> the repo root is three folders above this package.
    return Path(__file__).resolve().parents[3] / "playbooks"


def user_library_dir(data_dir: Path | None) -> Path | None:
    """`<data_dir>/chores`: the chores the person kept; None with nothing on disk."""
    return data_dir / USER_LIBRARY if data_dir is not None else None


def taxonomy_path(root: Path) -> Path:
    """The taxonomy a chore is checked against: the one beside it (the library's own), else the
    app library's. Authored and kept chores live in the data folder, which has none."""
    beside = root.parent / TAXONOMY
    return beside if beside.is_file() else library_dir() / TAXONOMY


# --- reading --------------------------------------------------------------------------------------


def _read_json(path: Path, problems: list[str], *, required: bool = True) -> Any:
    if not path.is_file():
        if required:
            problems.append(f"{path.name} is missing")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        problems.append(f"{path.name} cannot be read as JSON: {e}")
        return None


def _obj(value: Any) -> dict[str, Any]:
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _taxonomy(path: Path, problems: list[str]) -> tuple[set[str], set[str]]:
    data = _obj(_read_json(path, problems))
    cats = {str(_obj(c).get("id")) for c in _list(data.get("categories"))}
    jobs = {str(_obj(j).get("id")) for j in _list(data.get("jobs"))}
    return cats, jobs


def _check_playbook(root: Path, pb: dict[str, Any], problems: list[str]) -> None:
    if pb.get("id") != root.name:
        problems.append(f"playbook.json id {pb.get('id')!r} is not the folder name {root.name!r}")
    for key in ("title", "promise", "expectation"):
        if not pb.get(key):
            problems.append(f"playbook.json has no {key}")
    cats, jobs = _taxonomy(taxonomy_path(root), problems)
    if pb.get("category") not in cats:
        problems.append(f"category {pb.get('category')!r} is not in taxonomy.json")
    if pb.get("job") not in jobs:
        problems.append(f"job {pb.get('job')!r} is not in taxonomy.json")
    if "featured" not in pb:
        return
    featured = pb["featured"]
    if not isinstance(featured, dict):
        problems.append("featured must be an object with senses, spike and since")
        return
    if "status" in featured:
        problems.append("featured.status is computed from proofs.json, never written")
    extra = sorted(set(featured) - FEATURED_KEYS - {"status"})
    if extra:
        problems.append(f"featured has keys it should not: {', '.join(extra)}")
    senses = featured.get("senses")
    if not isinstance(senses, list) or not senses:
        problems.append("featured.senses must name at least one sense")
    else:
        bad = [str(s) for s in senses if s not in SENSES]
        if bad:
            problems.append(f"featured.senses has unknown senses: {', '.join(bad)}")
    for key in ("spike", "since"):
        if not featured.get(key):
            problems.append(f"featured has no {key}")


def _tool(raw: dict[str, Any]) -> Tool:
    params = {str(k): _obj(v) for k, v in _obj(raw.get("params")).items()}
    return Tool(
        name=str(raw.get("name", "")),
        kind=str(raw.get("kind", "")),
        description=str(raw.get("description", "")),
        params=params,
        returns=_obj(raw.get("returns")),
        says=str(raw.get("says", "")),
    )


def _check_tool(where: str, tool: Tool, tables: dict[str, list[dict[str, Any]]], problems: list[str]) -> None:
    if not tool.name:
        problems.append(f"{where}: a tool has no name")
    if not tool.kind:
        problems.append(f"{where}: has no kind")
    for p, spec in tool.params.items():
        if spec.get("type", "string") not in PARAM_TYPES:
            problems.append(f"{where}: param {p} has type {spec.get('type')!r}")
    if tool.kind != "READ":
        if not tool.says:
            problems.append(f"{where}: a {tool.kind or 'gated'} tool needs says")
        return
    table = tool.returns.get("table")
    if not isinstance(table, str) or not table:
        problems.append(f"{where}: a READ tool must return a table")
        return
    if table not in tables:
        problems.append(f"{where}: reads table {table!r}, {MISSING_TABLE}")
    match = _obj(tool.returns.get("match"))
    for key, label in (
        (list(match), "matches on"),
        (_list(tool.returns.get("require")), "requires"),
        (list(_obj(tool.returns.get("default"))), "defaults"),
    ):
        foreign = [str(p) for p in key if p not in tool.params]
        if foreign:
            problems.append(f"{where}: {label} {', '.join(foreign)}, which are not its params")
    rows = tables.get(table) or []
    if rows:
        columns = {c for r in rows for c in r}
        missing = [str(c) for c in match.values() if c not in columns]
        if missing:
            problems.append(f"{where}: matches columns {table} does not have: {', '.join(missing)}")
    size = tool.returns.get("page_size")
    if size is not None and (not isinstance(size, int) or isinstance(size, bool) or size < 1):
        problems.append(f"{where}: page_size must be a whole number above 0")


def _tables(raw: Any, origin: str, problems: list[str]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for name, rows in _obj(raw).items():
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            problems.append(f"{origin} table {name} must be a list of rows")
            continue
        out[str(name)] = cast("list[dict[str, Any]]", rows)
    return out


def load_chore(root: Path, *, origin: ChoreOrigin = "library") -> Chore:
    problems: list[str] = []
    pb = _read_json(root / "playbook.json", problems)
    world = _read_json(root / "world.json", problems)
    truth = _read_json(root / "truth.json", problems)
    sensed = _read_json(root / "senses" / "sensed.json", problems, required=False)
    if pb is not None and not isinstance(pb, dict):
        problems.append("playbook.json must be an object")
    if world is not None and not isinstance(world, dict):
        problems.append("world.json must be an object")
    if truth is not None and not isinstance(truth, dict):
        problems.append("truth.json must be an object")
    pb, world, truth = _obj(pb), _obj(world), _obj(truth)
    if pb:
        _check_playbook(root, pb, problems)

    tables = _tables(world.get("tables"), "world", problems)
    if sensed is not None:
        for name, rows in _tables(_obj(sensed).get("tables"), "sensed", problems).items():
            if name in tables:
                problems.append(f"sensed table {name} would shadow the world table of that name")
            else:
                tables[name] = rows

    apps: list[App] = []
    for raw in _list(world.get("apps")):
        a = _obj(raw)
        app_id = str(a.get("app_id", ""))
        if not app_id:
            problems.append("an app has no app_id")
        if any(x.app_id == app_id for x in apps):
            problems.append(f"app {app_id} appears twice")
        tools = tuple(_tool(_obj(t)) for t in _list(a.get("tools")))
        names = [t.name for t in tools]
        for t in tools:
            _check_tool(f"{app_id}.{t.name}", t, tables, problems)
        for dup in sorted({n for n in names if names.count(n) > 1}):
            problems.append(f"app {app_id} has two tools called {dup}")
        apps.append(
            App(
                app_id=app_id,
                name=str(a.get("name", app_id)),
                origin=str(a.get("origin", "")),
                tools=tools,
                view=_obj(a.get("view")),
            )
        )
    app_ids = {a.app_id for a in apps}
    every_tool = {t.name for a in apps for t in a.tools}

    phases: list[Phase] = []
    for raw in _list(world.get("phases")):
        p = _obj(raw)
        phase = Phase(
            app=str(p.get("app", "")), message=str(p.get("message", "")), nudges=int(p.get("nudges", 0))
        )
        if phase.app not in app_ids:
            problems.append(f"a phase opens app {phase.app!r}, which the world does not have")
        phases.append(phase)

    targets: list[Target] = []
    for raw in _list(truth.get("targets")):
        doc = _obj(raw)
        neutral = doc.get("neutral")
        target = Target(
            tool=str(doc.get("tool", "")),
            key=str(doc.get("key", "")),
            eligible={str(k): _obj(v) for k, v in _obj(doc.get("eligible")).items()},
            traps={str(k): str(v) for k, v in _obj(doc.get("traps")).items()},
            neutral=tuple(str(k) for k in (neutral if isinstance(neutral, dict | list) else ())),
        )
        if target.tool not in every_tool:
            problems.append(f"truth target {target.tool!r} is a tool no app has")
        targets.append(target)
    forbidden = tuple(str(f) for f in _list(truth.get("forbidden")))
    for f in forbidden:
        if f not in every_tool:
            problems.append(f"forbidden tool {f!r} is a tool no app has")

    if problems:
        raise ChoreError(problems)
    return Chore(
        id=root.name,
        root=root,
        showcase=pb,
        today=str(world.get("today", "")),
        apps=tuple(apps),
        tables=tables,
        phases=tuple(phases),
        targets=tuple(targets),
        forbidden=forbidden,
        origin=origin,
    )


def load_library(base: Path | None = None, *, origin: ChoreOrigin = "library") -> list[Chore]:
    """Every loadable chore under `base`, by id. A broken one is logged and skipped."""
    base = base if base is not None else library_dir()
    if not base.is_dir():
        return []
    out: list[Chore] = []
    for root in sorted(p for p in base.iterdir() if (p / "playbook.json").is_file()):
        try:
            out.append(load_chore(root, origin=origin))
        except ChoreError as e:
            log.warning("chore %s skipped: %s", root.name, e)
    return out


def load_both(data_dir: Path | None) -> list[Chore]:
    """The library, then the person's own chores. Ids never collide: a chore of hers whose id the
    library has is skipped and logged."""
    library = load_library()
    taken = {c.id for c in library}
    yours: list[Chore] = []
    base = user_library_dir(data_dir)
    for chore in load_library(base, origin="yours") if base is not None else []:
        if chore.id in taken:
            log.warning("chore %s of yours skipped: the library has a chore by that id", chore.id)
            continue
        yours.append(chore)
    return library + yours


def chore_ids(data_dir: Path | None) -> set[str]:
    """Every id taken in either library, loadable or not (a folder holds its id either way)."""
    out: set[str] = set()
    for base in (library_dir(), user_library_dir(data_dir)):
        if base is not None and base.is_dir():
            out |= {p.name for p in base.iterdir() if p.is_dir()}
    return out


def find_chore(chore_id: str, data_dir: Path | None) -> tuple[Path, ChoreOrigin] | None:
    """Where a chore by this id lives, the library first; None for an id that is not a chore's."""
    if not CHORE_ID.fullmatch(chore_id):
        return None
    root = library_dir() / chore_id
    if (root / "playbook.json").is_file():
        return root, "library"
    base = user_library_dir(data_dir)
    if base is not None and (base / chore_id / "playbook.json").is_file():
        return base / chore_id, "yours"
    return None


# --- featured status, bench and proofs ------------------------------------------------------------


def _proofs(root: Path) -> dict[str, Any]:
    """`senses/proofs.json` as written: `{passed?, backends, proofs: [ProofRow]}` (`rows` also read)."""
    path = root / "senses" / "proofs.json"
    if not path.is_file():
        return {}
    try:
        return _obj(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        log.warning("chore %s: proofs.json cannot be read", root.name)
        return {}


def _proof_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = data.get("proofs", data.get("rows"))
    return [_obj(r) for r in _list(rows) if isinstance(r, dict)]


def featured_status(root: Path) -> FeaturedStatus:
    data = _proofs(root)
    rows = _proof_rows(data)
    if not rows:
        return "unproven"
    passed = data.get("passed", True) is True and all(r.get("passed") is True for r in rows)
    if not passed:
        return "failing"
    backends = _obj(data.get("backends"))
    if any(v in META_BACKENDS for v in backends.values()):
        return "proven"
    return "rehearsed"


_BENCH_KEYS = tuple(BenchSummary.__annotations__)
#: Spelled out: under postponed annotations a TypedDict cannot see its own NotRequired keys.
_BENCH_OPTIONAL = frozenset({"cost_usd"})
_PROOF_KEYS = tuple(ProofRow.__annotations__)


def _bench(root: Path) -> BenchSummary | None:
    path = root / "bench.json"
    if not path.is_file():
        return None
    try:
        data = _obj(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        log.warning("chore %s: bench.json cannot be read", root.name)
        return None
    src = _obj(data.get("summary")) or data
    out = {k: src[k] for k in _BENCH_KEYS if k in src and src[k] is not None}
    if not set(_BENCH_KEYS) - _BENCH_OPTIONAL <= set(out):
        log.warning("chore %s: bench.json lacks the summary keys", root.name)
        return None
    return cast("BenchSummary", out)


def summary(chore: Chore) -> ChoreSummary:
    pb = chore.showcase
    featured = _obj(pb.get("featured"))
    out: ChoreSummary = {
        "id": chore.id,
        "title": str(pb.get("title", "")),
        "short_title": str(pb.get("short_title") or pb.get("title", "")),
        "promise": str(pb.get("promise", "")),
        "category": str(pb.get("category", "")),
        "job": str(pb.get("job", "")),
        "senses": [cast("SenseName", s) for s in _list(featured.get("senses")) if s in SENSES],
        "featured": featured_status(chore.root),
        "origin": chore.origin,
    }
    bench = _bench(chore.root)
    if bench is not None:
        out["bench"] = bench
    return out


def detail(chore: Chore) -> ChoreDetail:
    data = _proofs(chore.root)
    proofs = [
        cast("ProofRow", {k: r[k] for k in _PROOF_KEYS if k in r and r[k] is not None})
        for r in _proof_rows(data)
    ]
    return {
        "chore": summary(chore),
        "brief": str(chore.showcase.get("brief", "")),
        "persona": str(chore.showcase.get("persona", "")),
        "apps": [{"app_id": a.app_id, "name": a.name} for a in chore.apps],
        "proofs": proofs,
        "backends": {str(k): str(v) for k, v in _obj(data.get("backends")).items()},
    }
