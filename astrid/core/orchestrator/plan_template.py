"""Canonical helpers for authoring task-mode orchestrator plan templates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, TypedDict, cast

from astrid.core.task.plan import (
    AckRule,
    AdapterKind,
    CostEntry,
    ProducesEntry,
    Repeat,
    RepeatForEach,
    RepeatUntil,
    Step,
    TaskPlan,
)
from astrid.core.verify import Check, canonical_check_params


class PlanStep(TypedDict, total=False):
    """A single step in a plan-v2 document."""

    id: str
    adapter: str
    command: str
    produces: dict[str, Any]
    cost: dict[str, Any]
    repeat: dict[str, Any]
    children: list["PlanStep"]


class PlanV2(TypedDict):
    """Top-level plan-v2 document."""

    plan_id: str
    version: int
    steps: list[PlanStep]


def file_output(
    name: str,
    path: str | Path,
    *,
    check_id: str = "file_nonempty",
    params: Mapping[str, object] | None = None,
    sentinel: bool = False,
    checksum: str | None = None,
) -> ProducesEntry:
    """Build a named produced-file entry with the default file_nonempty check."""

    return ProducesEntry(
        name=name,
        path=str(path),
        check=Check(
            check_id=check_id,
            params=canonical_check_params(dict(params or {})),
            sentinel=sentinel,
        ),
        checksum=checksum,
    )


def cost_entry(
    amount: float,
    *,
    source: str,
    currency: str = "USD",
) -> CostEntry:
    return CostEntry(amount=float(amount), currency=currency, source=source)


def repeat_for_each_from(ref: str) -> RepeatForEach:
    return RepeatForEach(items_source="from", from_ref=ref)


def repeat_for_each_items(items: Iterable[str]) -> RepeatForEach:
    return RepeatForEach(items_source="static", items=tuple(items))


def repeat_until(
    condition: str,
    *,
    max_iterations: int,
    on_exhaust: str = "escalate",
) -> RepeatUntil:
    if on_exhaust not in {"escalate", "fail"}:
        raise ValueError("on_exhaust must be 'escalate' or 'fail'")
    return RepeatUntil(
        condition=condition,
        max_iterations=max_iterations,
        on_exhaust=cast(Literal["escalate", "fail"], on_exhaust),
    )


def build_leaf_template(
    step_id: str,
    *,
    command: str,
    adapter: AdapterKind = "local",
    produces: Iterable[ProducesEntry] = (),
    cost: CostEntry | None = None,
    repeat: Repeat | None = None,
    instructions: str | None = None,
    requires_ack: bool = False,
    ack_kind: Literal["agent", "human"] = "agent",
    assignee: str = "system",
    optional: bool = False,
) -> Step:
    """Build a collapsed-schema leaf step for pack plan templates."""

    return Step(
        id=step_id,
        adapter=adapter,
        command=command,
        instructions=instructions,
        requires_ack=requires_ack,
        ack=AckRule(kind=ack_kind) if requires_ack else None,
        assignee=assignee,
        produces=tuple(produces),
        cost=cost,
        repeat=repeat,
        optional=optional,
    )


def build_group_template(
    step_id: str,
    *,
    children: Iterable[Step],
    adapter: AdapterKind = "local",
    re_export: Mapping[str, str] | None = None,
    repeat: Repeat | None = None,
    assignee: str = "system",
    optional: bool = False,
) -> Step:
    """Build a collapsed-schema group step for pack plan templates."""

    return Step(
        id=step_id,
        adapter=adapter,
        children=tuple(children),
        re_export=tuple((re_export or {}).items()) if re_export is not None else None,
        repeat=repeat,
        assignee=assignee,
        optional=optional,
    )


def build_plan_template(*, plan_id: str, steps: Iterable[Step]) -> dict[str, object]:
    """Return the canonical JSON-ready plan v2 dict for template emitters."""

    return TaskPlan(plan_id=plan_id, version=2, steps=tuple(steps)).to_dict()


def emit_plan_json(plan: Mapping[str, object], path: str | Path) -> None:
    """Write canonical plan JSON used by built-in plan templates."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    output_path.write_text(payload, encoding="utf-8")


def build_step_command(
    python_exec: str,
    run_root: Path,
    step_id: str,
    module_path: str,
    *,
    extra_args: str = "",
) -> str:
    """Construct a canonical step command string."""

    out = run_root / "steps" / step_id / "v1" / "produces"
    cmd = f"{python_exec} -m {module_path} --out {out}"
    if extra_args:
        cmd += f" {extra_args}"
    return cmd


def make_produces(path: str, check_id: str = "file_nonempty") -> dict[str, Any]:
    """Return a minimal ``produces`` block for a plan step."""

    return {
        path: {
            "path": path,
            "check": {
                "check_id": check_id,
                "params": {},
                "sentinel": False,
            },
        }
    }


__all__ = [
    "build_group_template",
    "build_leaf_template",
    "build_plan_template",
    "build_step_command",
    "cost_entry",
    "emit_plan_json",
    "file_output",
    "make_produces",
    "PlanStep",
    "PlanV2",
    "repeat_for_each_from",
    "repeat_for_each_items",
    "repeat_until",
]
