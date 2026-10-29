"""A connector tool's shape, its parameter check and its result (ADR 0008).

athena-portable merged connector tools into a catalog through its `contracts.manifest.HostTool` and
`HostManifest`, and returned `contracts.registry.ExecResult`. This repository has no such catalog,
so only what the connectors themselves read is kept here: a tool's name and gate flags, the spec's
load-time check, a small JSON-schema check of the parameters (the portable gate ran it before a
tool did), and the result. None of it is on the wire.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

SIDE_EFFECTS: tuple[str, ...] = ("none", "internal", "external")
ExecError = str  # unknown_ref | validator_failed | engine_error | outcome_unknown


@dataclass(frozen=True)
class HostTool:
    """One tool a spec declares. `reversible` is None until the spec says, and None is a write."""

    name: str
    description: str = ""
    params_schema: dict[str, Any] = field(default_factory=dict)
    reversible: bool | None = None
    side_effects: str = "external"
    problems: tuple[str, ...] = field(default=(), compare=False, repr=False)

    def is_write(self) -> bool:
        """A write is anything not declared reversible, or that leaves the machine, or that was
        refused at parse: it never runs without the writes switch."""
        return bool(self.problems) or self.reversible is not True or self.side_effects == "external"

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> HostTool:
        """Each gate flag by its JSON type: `"false"` is not `True`, and a missing flag is a problem."""
        problems: list[str] = []
        name = str(d.get("name", ""))
        raw = d.get("reversible")
        reversible = raw if isinstance(raw, bool) else None
        if raw is not None and not isinstance(raw, bool):
            problems.append(f"tool {name!r}: reversible must be true or false, got {type(raw).__name__}")
        effects = d.get("side_effects")
        if not isinstance(effects, str):
            problems.append(f"tool {name!r} must declare side_effects")
            effects = "external"
        schema = d.get("params_schema") or {}
        return cls(
            name=name,
            description=str(d.get("description", "")),
            params_schema=dict(schema) if isinstance(schema, dict) else {},
            reversible=reversible,
            side_effects=effects,
            problems=tuple(problems)
            + (() if isinstance(schema, dict) else (f"tool {name!r}: params_schema must be an object",)),
        )


def tool_problems(tools: Sequence[HostTool]) -> list[str]:
    """Every problem with a spec's tools; an empty list means the spec may load."""
    problems: list[str] = []
    seen: set[str] = set()
    for tool in tools:
        problems.extend(tool.problems)
        if not tool.name.strip():
            problems.append("a tool has an empty name")
        elif tool.name in seen:
            problems.append(f"duplicate tool {tool.name!r}")
        seen.add(tool.name)
        if tool.reversible is None:
            problems.append(f"tool {tool.name!r} must declare reversible")
        if tool.side_effects not in SIDE_EFFECTS:
            problems.append(
                f"tool {tool.name!r}: side_effects must be one of {SIDE_EFFECTS}, got {tool.side_effects!r}"
            )
        for pname, pschema in tool.params_schema.get("properties", {}).items():
            if isinstance(pschema, dict) and pschema.get("type") == "array" and "maxItems" not in pschema:
                problems.append(f"{tool.name}.{pname}: an array parameter needs maxItems")
    return problems


def _value_problem(name: str, schema: Mapping[str, Any], value: Any) -> str | None:
    kind = schema.get("type")
    if kind == "string":
        if not isinstance(value, str):
            return f"{name} must be text"
        if "maxLength" in schema and len(value) > int(schema["maxLength"]):
            return f"{name} is longer than {schema['maxLength']} characters"
    elif kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return f"{name} must be a whole number"
        if "minimum" in schema and value < int(schema["minimum"]):
            return f"{name} is below {schema['minimum']}"
        if "maximum" in schema and value > int(schema["maximum"]):
            return f"{name} is above {schema['maximum']}"
    elif kind == "array":
        if not isinstance(value, list):
            return f"{name} must be a list"
        if len(value) < int(schema.get("minItems", 0)):
            return f"{name} needs at least {schema['minItems']} items"
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            return f"{name} has more than {schema['maxItems']} items"
        items = schema.get("items")
        if isinstance(items, Mapping):
            for i, item in enumerate(value):
                found = _value_problem(f"{name}[{i}]", items, item)
                if found:
                    return found
    return None


def check_params(schema: Mapping[str, Any], params: Mapping[str, Any]) -> str | None:
    """Why `params` do not fit the tool's schema, or None. The subset the specs use: required keys,
    no unknown keys, and strings, whole numbers and lists with their bounds."""
    props = schema.get("properties", {})
    for name in schema.get("required", []):
        if name not in params:
            return f"{name} is required"
    if schema.get("additionalProperties") is False:
        extra = sorted(set(params) - set(props))
        if extra:
            return f"{', '.join(extra)} is not a parameter here"
    for name, value in params.items():
        found = _value_problem(name, props.get(name, {}), value)
        if found:
            return found
    return None


@dataclass(frozen=True)
class ExecResult:
    """What a connector call returns: a read's text (fenced), a write's sentence, or a refusal's
    reason with its error word. `data` carries what a write made (Gmail's message and thread ids)."""

    ok: bool
    output: str = ""
    error: ExecError = ""
    data: dict[str, str] = field(default_factory=dict)

    @classmethod
    def failure(cls, error: ExecError, reason: str) -> ExecResult:
        return cls(ok=False, output=reason, error=error)
