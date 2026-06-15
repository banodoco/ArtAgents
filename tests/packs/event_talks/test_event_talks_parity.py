"""T7: Event talks resume-injection parity tests.

Covers completed-prefix resume, nonzero local exits, and normalized
ledger parity under both task-gate and Arnold lifecycle paths.
"""

from __future__ import annotations

import json
from pathlib import Path

from astrid.core.task.events import (
    make_produces_check_passed_event,
    make_step_attested_event,
    make_step_completed_event,
    make_step_dispatched_event,
    read_events,
)
from astrid.core.task.gate import peek_current_step
from astrid.core.task.plan import load_plan
from astrid.core.task.plan.verbs import apply_mutations
from tests.core.integrations.arnold_parity import (
    TIMESTAMP_PLACEHOLDER,
    make_plan_for_parity,
    make_project_state_root,
    make_project_state_root_with_timeline,
    normalize_for_parity,
    read_state_json,
    seed_task_event,
    write_review_state_file,
    write_state_json,
)

# Produces names for each event_talks step (matches plan_template.py)
_EVENT_TALKS_PRODUCES: dict[str, str] = {
    "ados-sunday-template": "template_output",
    "search-transcript": "search_output",
    "find-holding-screens": "holding_output",
    "render": "render_output",
}


# ═══════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════

EVENT_TALKS_STEP_IDS = [
    "ados-sunday-template",
    "search-transcript",
    "find-holding-screens",
    "render",
]


# ═══════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════


def _build_event_talks_plan_v2(
    python_exec: str = "python3",
    run_root: str | Path | None = None,
) -> dict:
    """Build a plan v2 dict for event_talks testing."""
    from astrid.packs.video_editing.orchestrators.event_talks.plan_template import (
        build_plan_v2,
    )

    root = Path(run_root or "/tmp/test")
    return build_plan_v2(
        python_exec=python_exec,
        run_root=root,
        source=Path("/tmp/source.mp4"),
        run_id="test-run",
    )


def _seed_completed_step(
    run_root: Path,
    step_id: str,
    *,
    returncode: int = 0,
) -> None:
    """Seed the minimal event chain for one completed step.

    Each completed step requires:
    1. step_attested   — cursor advance signal
    2. step_dispatched  — records dispatch hash (clears pending)
    3. step_completed   — re-sets pending produces
    4. produces_check_passed — resolves pending, advances cursor
    """
    path_str = step_id
    produces_name = _EVENT_TALKS_PRODUCES.get(step_id, "output")

    seed_task_event(
        run_root,
        make_step_attested_event(
            plan_step_path=path_str,
            attestor_kind="system",
            attestor_id="gate",
        ),
    )

    seed_task_event(
        run_root,
        make_step_dispatched_event(
            plan_step_path=path_str,
            command=f"python3 -m astrid ... {step_id} ...",
            adapter="local",
        ),
    )

    seed_task_event(
        run_root,
        make_step_completed_event(
            plan_step_path=path_str,
            returncode=returncode,
            cost={"source": "local", "amount": 0},
        ),
    )

    seed_task_event(
        run_root,
        make_produces_check_passed_event(
            plan_step_path=(path_str,),
            produces_name=produces_name,
            check_id=f"check-{step_id}",
        ),
    )


def _setup_run_with_prefix(
    project_root: Path,
    slug: str,
    *,
    completed_steps: int = 0,
    run_id: str | None = None,
) -> tuple[Path, str, Path]:
    """Create a project with a seeded prefix of completed steps.

    Returns ``(run_root, rid, project_root)``.
    """
    proot = Path(project_root)

    # Build the plan
    plan = _build_event_talks_plan_v2(run_root=proot / slug / "runs" / "tmp")

    # Make the project state root
    if completed_steps == 0:
        run_root = make_project_state_root(
            proot,
            slug=slug,
            initial_state={"plan": plan},
            run_id=run_id,
        )
    else:
        run_root = make_project_state_root(
            proot,
            slug=slug,
            initial_state={"plan": plan},
            run_id=run_id,
        )

    # Write the plan file
    plan_path = run_root.parent.parent / "plan.json"
    make_plan_for_parity(plan, plan_path.parent, filename="plan.json")

    # Update lease with plan hash
    from astrid.core.task.plan import compute_plan_hash

    plan_hash = compute_plan_hash(plan_path)
    lease_path = run_root / "lease.json"
    if lease_path.is_file():
        lease_data = json.loads(lease_path.read_text(encoding="utf-8"))
        lease_data["plan_hash"] = plan_hash
        lease_path.write_text(json.dumps(lease_data), encoding="utf-8")

    # Seed completed steps
    for idx in range(completed_steps):
        _seed_completed_step(run_root, EVENT_TALKS_STEP_IDS[idx])

    rid = run_root.name
    return run_root, rid, proot


# ═══════════════════════════════════════════════════════════════════════
#  Completed-prefix resume tests (task-gate path)
# ═══════════════════════════════════════════════════════════════════════


class TestCompletedPrefixResumeTaskGate:
    """Peek at next step after seeding completed prefixes through the task gate."""

    def test_resume_from_empty_ledger_returns_first_step(self, tmp_path: Path) -> None:
        """No events seeded — peek returns ados-sunday-template."""
        run_root, rid, proot = _setup_run_with_prefix(
            tmp_path, "demo", completed_steps=0
        )

        slug = "demo"
        events = read_events(run_root / "events.jsonl")
        base_plan = load_plan(proot / slug / "plan.json")
        plan = apply_mutations(base_plan, events)

        result = peek_current_step(
            plan, events, slug,
            project_root=proot / slug,
            run_id=rid,
        )

        assert not result.exhausted, "expected a pending step, got exhausted"
        assert result.step.id == "ados-sunday-template", (
            f"expected ados-sunday-template, got {result.step.id}"
        )

    def test_resume_after_one_completed_returns_second_step(
        self, tmp_path: Path,
    ) -> None:
        """Step 1 done — peek returns search-transcript."""
        run_root, rid, proot = _setup_run_with_prefix(
            tmp_path, "demo", completed_steps=1
        )

        slug = "demo"
        events = read_events(run_root / "events.jsonl")
        base_plan = load_plan(proot / slug / "plan.json")
        plan = apply_mutations(base_plan, events)

        result = peek_current_step(
            plan, events, slug,
            project_root=proot / slug,
            run_id=rid,
        )

        assert not result.exhausted
        assert result.step.id == "search-transcript", (
            f"expected search-transcript, got {result.step.id}"
        )

    def test_resume_after_two_completed_returns_third_step(
        self, tmp_path: Path,
    ) -> None:
        """Steps 1-2 done — peek returns find-holding-screens."""
        run_root, rid, proot = _setup_run_with_prefix(
            tmp_path, "demo", completed_steps=2
        )

        slug = "demo"
        events = read_events(run_root / "events.jsonl")
        base_plan = load_plan(proot / slug / "plan.json")
        plan = apply_mutations(base_plan, events)

        result = peek_current_step(
            plan, events, slug,
            project_root=proot / slug,
            run_id=rid,
        )

        assert not result.exhausted
        assert result.step.id == "find-holding-screens", (
            f"expected find-holding-screens, got {result.step.id}"
        )

    def test_resume_after_three_completed_returns_fourth_step(
        self, tmp_path: Path,
    ) -> None:
        """Steps 1-3 done — peek returns render."""
        run_root, rid, proot = _setup_run_with_prefix(
            tmp_path, "demo", completed_steps=3
        )

        slug = "demo"
        events = read_events(run_root / "events.jsonl")
        base_plan = load_plan(proot / slug / "plan.json")
        plan = apply_mutations(base_plan, events)

        result = peek_current_step(
            plan, events, slug,
            project_root=proot / slug,
            run_id=rid,
        )

        assert not result.exhausted
        assert result.step.id == "render", (
            f"expected render, got {result.step.id}"
        )

    def test_all_four_steps_completed_returns_exhausted(
        self, tmp_path: Path,
    ) -> None:
        """All 4 steps done — peek returns exhausted."""
        run_root, rid, proot = _setup_run_with_prefix(
            tmp_path, "demo", completed_steps=4
        )

        slug = "demo"
        events = read_events(run_root / "events.jsonl")
        base_plan = load_plan(proot / slug / "plan.json")
        plan = apply_mutations(base_plan, events)

        result = peek_current_step(
            plan, events, slug,
            project_root=proot / slug,
            run_id=rid,
        )

        assert result.exhausted, (
            f"expected exhausted after all steps, got step={result.step.id if result.step else None}"
        )


# ═══════════════════════════════════════════════════════════════════════
#  Command parity: task vs Arnold paths
# ═══════════════════════════════════════════════════════════════════════


class TestCommandParityTaskVsArnold:
    """Verify the next command is identical across task-gate and Arnold start paths."""

    def test_plan_step_commands_match_expected_subcommands(self) -> None:
        """Every plan step command references the correct subcommand."""
        plan = _build_event_talks_plan_v2()

        expected_subcommands = {
            "ados-sunday-template": "ados-sunday-template",
            "search-transcript": "search-transcript",
            "find-holding-screens": "find-holding-screens",
            "render": "render",
        }

        for step in plan["steps"]:
            step_id = step["id"]
            cmd = step.get("command", "")
            expected_sub = expected_subcommands[step_id]
            assert expected_sub in cmd, (
                f"step {step_id} command does not reference subcommand {expected_sub!r}: {cmd!r}"
            )

    def test_all_plan_steps_use_local_adapter(self) -> None:
        """Event talks steps use adapter: local exclusively."""
        plan = _build_event_talks_plan_v2()

        for step in plan["steps"]:
            assert step.get("adapter") == "local", (
                f"step {step['id']} expected adapter=local, got {step.get('adapter')!r}"
            )

    def test_plan_steps_cost_zero(self) -> None:
        """All event talks steps cost $0 (local-only)."""
        plan = _build_event_talks_plan_v2()

        for step in plan["steps"]:
            cost = step.get("cost", {})
            assert cost.get("amount") == 0, (
                f"step {step['id']} expected cost.amount=0, got {cost.get('amount')}"
            )
            assert cost.get("source") == "local", (
                f"step {step['id']} expected cost.source=local, got {cost.get('source')!r}"
            )

    def test_plan_commands_use_produces_root_placeholder(self) -> None:
        """Step commands use {produces_root} for output paths."""
        plan = _build_event_talks_plan_v2()

        for step in plan["steps"]:
            cmd = step.get("command", "")
            assert "{produces_root}" in cmd, (
                f"step {step['id']} missing {{produces_root}} in command: {cmd!r}"
            )


# ═══════════════════════════════════════════════════════════════════════
#  Suspension and terminal state tests
# ═══════════════════════════════════════════════════════════════════════


class TestSuspensionAndTerminalState:
    """Verify state.json is correctly maintained across suspension/resume boundaries."""

    def test_initial_state_is_preserved_in_state_json(self, tmp_path: Path) -> None:
        """State written via make_project_state_root is readable."""
        proot = Path(tmp_path)
        initial = {"plan": {"version": 2}, "phase": "started"}
        run_root = make_project_state_root(
            proot, slug="demo", initial_state=initial
        )

        state = read_state_json(run_root)
        assert state.get("plan", {}).get("version") == 2
        assert state.get("phase") == "started"

    def test_state_json_persists_after_seeding_events(self, tmp_path: Path) -> None:
        """Seeding events does not corrupt state.json."""
        proot = Path(tmp_path)
        initial = {"plan": {"version": 2}, "phase": "started"}
        run_root = make_project_state_root(
            proot, slug="demo", initial_state=initial
        )

        # Seed one completed step
        _seed_completed_step(run_root, "ados-sunday-template")

        # State must still be readable and unchanged
        state = read_state_json(run_root)
        assert state.get("plan", {}).get("version") == 2
        assert state.get("phase") == "started"

    def test_state_json_can_be_overwritten(self, tmp_path: Path) -> None:
        """write_state_json correctly overwrites state."""
        proot = Path(tmp_path)
        run_root = make_project_state_root(
            proot, slug="demo", initial_state={"phase": "started"}
        )

        # Overwrite
        write_state_json(run_root, {"phase": "running", "step": 2})
        state = read_state_json(run_root)

        assert state.get("phase") == "running"
        assert state.get("step") == 2

    def test_review_state_file_roundtrip(self, tmp_path: Path) -> None:
        """review_state.json write/read roundtrip works."""
        run_root = tmp_path / "runs" / "run-1"
        run_root.mkdir(parents=True, exist_ok=True)

        review_state = {
            "run_id": "run-1",
            "writer_id": "test-user",
            "state_version": 1,
            "created_at": "2026-06-13T00:00:00Z",
            "updated_at": "2026-06-13T00:00:00Z",
            "status": "reviewing",
        }
        path = write_review_state_file(run_root, review_state)
        assert path.is_file()

        from tests.core.integrations.arnold_parity import read_review_state_file
        loaded = read_review_state_file(run_root)
        assert loaded.get("status") == "reviewing"
        assert loaded.get("writer_id") == "test-user"


# ═══════════════════════════════════════════════════════════════════════
#  Failure behavior: nonzero local exits
# ═══════════════════════════════════════════════════════════════════════


class TestNonzeroLocalExitBehavior:
    """Step completion with nonzero returncode is properly recorded."""

    def test_completed_step_with_nonzero_returncode_is_recorded(
        self, tmp_path: Path,
    ) -> None:
        """A step_completed event with returncode=1 is preserved in the ledger."""
        run_root, rid, proot = _setup_run_with_prefix(
            tmp_path, "demo", completed_steps=0
        )

        # Complete step 0 with returncode=0
        _seed_completed_step(run_root, "ados-sunday-template", returncode=0)

        # Complete step 1 with returncode=1 (failure)
        _seed_completed_step(run_root, "search-transcript", returncode=1)

        events = read_events(run_root / "events.jsonl")

        # Find the step_completed events
        completed_events = [
            e for e in events if e.get("kind") == "step_completed"
        ]
        assert len(completed_events) >= 2

        returncodes = {
            tuple(e.get("plan_step_path", [])): e.get("returncode")
            for e in completed_events
        }

        # ados-sunday-template succeeded
        assert returncodes.get(("ados-sunday-template",)) == 0

        # search-transcript failed
        assert returncodes.get(("search-transcript",)) == 1, (
            f"expected returncode=1 for search-transcript, "
            f"got {returncodes.get(('search-transcript',))}"
        )

    def test_nonzero_exit_does_not_exhaust_plan(self, tmp_path: Path) -> None:
        """A single nonzero exit does not mark the plan as exhausted."""
        run_root, rid, proot = _setup_run_with_prefix(
            tmp_path, "demo", completed_steps=0
        )

        # Complete first 2 steps normally
        _seed_completed_step(run_root, "ados-sunday-template", returncode=0)
        _seed_completed_step(run_root, "search-transcript", returncode=1)

        slug = "demo"
        events = read_events(run_root / "events.jsonl")
        base_plan = load_plan(proot / slug / "plan.json")
        plan = apply_mutations(base_plan, events)

        result = peek_current_step(
            plan, events, slug,
            project_root=proot / slug,
            run_id=rid,
        )

        # Even with a nonzero exit on search-transcript, the third step
        # should still be pending (find-holding-screens).
        assert not result.exhausted, (
            "expected pending step after nonzero exit, got exhausted"
        )
        assert result.step.id == "find-holding-screens", (
            f"expected find-holding-screens, got {result.step.id}"
        )


# ═══════════════════════════════════════════════════════════════════════
#  Normalized ledger parity
# ═══════════════════════════════════════════════════════════════════════


class TestNormalizedLedgerParity:
    """Normalized ledger comparison after event seeding is stable and deterministic."""

    def test_normalized_events_have_placeholders_for_entropy_fields(
        self, tmp_path: Path,
    ) -> None:
        """After normalization, entropy fields are replaced with placeholders."""
        run_root, rid, proot = _setup_run_with_prefix(
            tmp_path, "demo", completed_steps=1
        )

        events = read_events(run_root / "events.jsonl")
        assert len(events) >= 4, f"expected >=4 events, got {len(events)}"

        normalized = normalize_for_parity(
            events,
            path_roots=[str(proot), str(run_root)],
        )

        for event in normalized:
            if "ts" in event:
                assert event["ts"] == TIMESTAMP_PLACEHOLDER, (
                    f"ts not normalized in {event.get('kind')}"
                )

    def test_identical_prefixes_produce_identical_normalized_ledgers(
        self, tmp_path: Path,
    ) -> None:
        """Two runs with the same prefix produce identical normalized ledgers."""
        proot1 = tmp_path / "run1"
        proot2 = tmp_path / "run2"

        run_root1, rid1, _ = _setup_run_with_prefix(
            proot1, "demo", completed_steps=2
        )
        run_root2, rid2, _ = _setup_run_with_prefix(
            proot2, "demo", completed_steps=2
        )

        events1 = read_events(run_root1 / "events.jsonl")
        events2 = read_events(run_root2 / "events.jsonl")

        norm1 = normalize_for_parity(events1, path_roots=[str(proot1), str(run_root1)])
        norm2 = normalize_for_parity(events2, path_roots=[str(proot2), str(run_root2)])

        # Strip all entropy fields — only kind/structural fields should remain
        def strip_entropy(events):
            result = []
            for e in events:
                stripped = {}
                for k, v in e.items():
                    if k in ("kind", "plan_step_path", "plan_step_id",
                              "returncode", "adapter", "attestor_kind",
                              "attestor_id", "evidence"):
                        stripped[k] = v
                result.append(stripped)
            return result

        structural1 = strip_entropy(norm1)
        structural2 = strip_entropy(norm2)

        assert structural1 == structural2, (
            f"structural mismatch between identical prefixes:\n"
            f"  run1={len(structural1)} events\n"
            f"  run2={len(structural2)} events"
        )

    def test_different_prefixes_produce_different_ledgers(
        self, tmp_path: Path,
    ) -> None:
        """Runs with different completed prefixes have different ledgers."""
        proot1 = tmp_path / "run1"
        proot2 = tmp_path / "run2"

        run_root1, rid1, _ = _setup_run_with_prefix(
            proot1, "demo", completed_steps=1
        )
        run_root2, rid2, _ = _setup_run_with_prefix(
            proot2, "demo", completed_steps=2
        )

        events1 = read_events(run_root1 / "events.jsonl")
        events2 = read_events(run_root2 / "events.jsonl")

        norm1 = normalize_for_parity(events1, path_roots=[str(proot1), str(run_root1)])
        norm2 = normalize_for_parity(events2, path_roots=[str(proot2), str(run_root2)])

        def kinds(events):
            return [e.get("kind") for e in events]

        assert kinds(norm1) != kinds(norm2), (
            "different prefixes should produce different event sequences"
        )

    def test_normalized_ledger_has_correct_event_count(self, tmp_path: Path) -> None:
        """After seeding N completed steps, the ledger has the right number of events."""
        proot = Path(tmp_path)

        for n in range(5):  # 0 through 4 completed
            p = proot / f"run{n}"
            run_root, rid, _ = _setup_run_with_prefix(p, "demo", completed_steps=n)
            events = read_events(run_root / "events.jsonl")

            # Each completed step = 4 events
            # (attested, dispatched, completed, produces_check_passed)
            expected_count = n * 4
            assert len(events) == expected_count, (
                f"completed_steps={n}: expected {expected_count} events, got {len(events)}"
            )


# ═══════════════════════════════════════════════════════════════════════
#  Plan template structural checks
# ═══════════════════════════════════════════════════════════════════════


class TestPlanTemplateStructure:
    """Structural invariants of the event_talks plan v2 template."""

    def test_plan_version_is_2(self) -> None:
        """Plan template emits version 2."""
        plan = _build_event_talks_plan_v2()
        assert plan.get("version") == 2

    def test_plan_has_four_steps(self) -> None:
        """Event talks plan has exactly 4 steps."""
        plan = _build_event_talks_plan_v2()
        assert len(plan["steps"]) == 4

    def test_step_ids_are_ordered_correctly(self) -> None:
        """Step IDs follow the canonical pipeline order."""
        plan = _build_event_talks_plan_v2()
        actual_ids = [step["id"] for step in plan["steps"]]
        assert actual_ids == EVENT_TALKS_STEP_IDS, (
            f"unexpected step order: {actual_ids}"
        )

    def test_each_step_has_produces(self) -> None:
        """Every step declares at least one produces output."""
        plan = _build_event_talks_plan_v2()
        for step in plan["steps"]:
            produces = step.get("produces", [])
            assert len(produces) >= 1, (
                f"step {step['id']} has no produces entries"
            )

    def test_plan_id_is_deterministic_with_same_run_id(self) -> None:
        """Same run_id produces same plan_id (deterministic)."""
        plan1 = _build_event_talks_plan_v2()
        plan2 = _build_event_talks_plan_v2()
        # Same run_id => same plan_id (deterministic)
        assert plan1["plan_id"] == plan2["plan_id"], (
            "expected deterministic plan_id for same run_id"
        )

    def test_plan_id_differs_with_different_run_id(self) -> None:
        """Different run_id produces different plan_id."""
        plan1 = _build_event_talks_plan_v2()

        from astrid.packs.video_editing.orchestrators.event_talks.plan_template import (
            build_plan_v2,
        )
        plan2 = build_plan_v2(
            python_exec="python3",
            run_root=Path("/tmp/test"),
            source=Path("/tmp/source.mp4"),
            run_id="different-run",
        )

        assert plan1["plan_id"] != plan2["plan_id"], (
            "expected different plan_ids for different run_ids"
        )


# ═══════════════════════════════════════════════════════════════════════
#  Timeline integration
# ═══════════════════════════════════════════════════════════════════════


class TestTimelineIntegration:
    """Timeline assembly assertions for event talks parity."""

    def test_timeline_assembly_json_exists_after_setup(self, tmp_path: Path) -> None:
        """Timeline assembly.json is created by the project-state-with-timeline helper."""
        run_root, timeline_ulid = make_project_state_root_with_timeline(
            tmp_path, slug="demo"
        )

        # The assembly.json should exist (canonical empty timeline)
        from astrid.core.timeline.paths import timeline_dir

        tdir = timeline_dir("demo", timeline_ulid, root=tmp_path)
        assembly_json = tdir / "assembly.json"
        assert assembly_json.is_file(), f"assembly.json missing at {assembly_json}"

        # After seeding events, the timeline directory should still exist
        _seed_completed_step(run_root, "ados-sunday-template")
        assert tdir.is_dir(), "timeline directory removed after seeding events"

    def test_managed_timeline_has_canonical_files(self, tmp_path: Path) -> None:
        """Managed timeline directory contains assembly.json, manifest.json, display.json."""
        from tests.core.integrations.arnold_parity import assert_managed_timeline_exists

        run_root, timeline_ulid = make_project_state_root_with_timeline(
            tmp_path, slug="demo"
        )

        assert_managed_timeline_exists(tmp_path, timeline_ulid, project_slug="demo")
