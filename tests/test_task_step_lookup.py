"""Phase C safety net for Step 22's _find_step_by_path consolidation.

This is the minimum guard — NOT a full module test suite for lifecycle_ack,
run_store, or operator_view.  Its sole purpose is to pin the three independent
copies of _find_step_by_path to the same contract so Step 22's consolidation
(merge all three into a single shared helper in plan.py) cannot silently break
any caller.

After Step 22's consolidation, lifecycle_ack, run_store, and operator_view all
delegate to find_step_by_path from plan.py.  This file verifies the canonical
contract.  Empty-tuple equivalence: the canonical returns None for () because
the loop does not execute and current is initialised to None — same as the
former private guard `if not path_tuple: return None`.

Do not broaden this file's scope beyond the find_step_by_path contract.
"""

from __future__ import annotations

import pytest

from astrid.core.task.plan import Step, TaskPlan, find_step_by_path


def _leaf(step_id: str) -> Step:
    return Step(id=step_id, command=f"echo {step_id}")


def _group(step_id: str, children: tuple[Step, ...]) -> Step:
    return Step(id=step_id, children=children)


def _plan(*steps: Step) -> TaskPlan:
    return TaskPlan(plan_id="test-plan", version=2, steps=steps)


# ---------------------------------------------------------------------------
# The canonical find_step_by_path; all three modules now import it from plan.
# ---------------------------------------------------------------------------
_ALL_IMPLS = [
    pytest.param(find_step_by_path, id="plan"),
]


@pytest.mark.parametrize("find_fn", _ALL_IMPLS)
class TestFindStepByPath:
    def test_empty_path_returns_none(self, find_fn) -> None:
        plan = _plan(_leaf("step-a"))
        assert find_fn(plan, ()) is None

    def test_single_segment_hit(self, find_fn) -> None:
        leaf = _leaf("step-a")
        plan = _plan(leaf)
        result = find_fn(plan, ("step-a",))
        assert result is not None
        assert result.id == "step-a"

    def test_single_segment_miss(self, find_fn) -> None:
        plan = _plan(_leaf("step-a"))
        assert find_fn(plan, ("nonexistent",)) is None

    def test_deep_nested_hit(self, find_fn) -> None:
        leaf = _leaf("leaf-child")
        inner_group = _group("inner", (leaf,))
        outer_group = _group("outer", (inner_group,))
        plan = _plan(outer_group)
        result = find_fn(plan, ("outer", "inner", "leaf-child"))
        assert result is not None
        assert result.id == "leaf-child"

    def test_deep_nested_miss_at_intermediate(self, find_fn) -> None:
        leaf = _leaf("leaf-child")
        group = _group("group-a", (leaf,))
        plan = _plan(group)
        # Wrong intermediate segment
        assert find_fn(plan, ("nonexistent-group", "leaf-child")) is None

    def test_deep_nested_miss_at_leaf(self, find_fn) -> None:
        leaf = _leaf("leaf-child")
        group = _group("group-a", (leaf,))
        plan = _plan(group)
        # Intermediate correct but leaf missing
        assert find_fn(plan, ("group-a", "no-such-leaf")) is None

    def test_path_through_leaf_as_group_returns_none(self, find_fn) -> None:
        leaf = _leaf("leaf-a")
        plan = _plan(leaf)
        # Treat leaf-a as a group — it isn't, so the traversal fails.
        assert find_fn(plan, ("leaf-a", "child")) is None

    def test_multiple_steps_at_root(self, find_fn) -> None:
        plan = _plan(_leaf("s1"), _leaf("s2"), _leaf("s3"))
        assert find_fn(plan, ("s1",)) is not None
        assert find_fn(plan, ("s2",)) is not None
        assert find_fn(plan, ("s3",)) is not None
        assert find_fn(plan, ("s4",)) is None
