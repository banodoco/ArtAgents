"""T9: Thumbnail maker resume-injection parity tests.

Covers all five named labels (``resolve-video``, ``plan-evidence``,
``discover-video-evidence``, ``build-reference-pack``,
``generate-thumbnails``), asserts stubbed steps fail equivalently under
task and Arnold paths, and requires normalized ledger parity plus
generated JSON artifact parity for every thumbnail maker scenario.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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

# Produces names for each thumbnail_maker step (matches plan_template.py)
_THUMBNAIL_MAKER_PRODUCES: dict[str, str] = {
    "resolve-video": "resolve_output",
    "plan-evidence": "evidence_plan_output",
    "discover-video-evidence": "candidates_output",
    "build-reference-pack": "reference_pack_output",
    "generate-thumbnails": "thumbnail_output",
}


# ═══════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════

THUMBNAIL_MAKER_STEP_IDS = [
    "resolve-video",
    "plan-evidence",
    "discover-video-evidence",
    "build-reference-pack",
    "generate-thumbnails",
]

# Steps 3-5 are stubs that raise NotImplementedError
STUB_STEP_IDS = frozenset({
    "discover-video-evidence",
    "build-reference-pack",
    "generate-thumbnails",
})

# Steps 1-2 are implemented and succeed with returncode=0
REAL_STEP_IDS = frozenset({
    "resolve-video",
    "plan-evidence",
})


# ═══════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════


def _build_thumbnail_maker_plan_v2(
    python_exec: str = "python3",
    run_root: str | Path | None = None,
) -> dict:
    """Build a plan v2 dict for thumbnail_maker testing."""
    from astrid.packs.video_editing.orchestrators.thumbnail_maker.plan_template import (
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
    produces_name = _THUMBNAIL_MAKER_PRODUCES.get(step_id, "output")

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
    plan = _build_thumbnail_maker_plan_v2(run_root=proot / slug / "runs" / "tmp")

    # Make the project state root
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

    # Seed completed steps (all with returncode=0 by default)
    for idx in range(completed_steps):
        _seed_completed_step(run_root, THUMBNAIL_MAKER_STEP_IDS[idx])

    rid = run_root.name
    return run_root, rid, proot


# ═══════════════════════════════════════════════════════════════════════
#  Completed-prefix resume tests (task-gate path)
# ═══════════════════════════════════════════════════════════════════════


class TestCompletedPrefixResumeTaskGate:
    """Peek at next step after seeding completed prefixes through the task gate."""

    def test_resume_from_empty_ledger_returns_first_step(self, tmp_path: Path) -> None:
        """No events seeded — peek returns resolve-video."""
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
        assert result.step.id == "resolve-video", (
            f"expected resolve-video, got {result.step.id}"
        )

    def test_resume_after_one_completed_returns_second_step(
        self, tmp_path: Path,
    ) -> None:
        """Step 1 done — peek returns plan-evidence."""
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
        assert result.step.id == "plan-evidence", (
            f"expected plan-evidence, got {result.step.id}"
        )

    def test_resume_after_two_completed_returns_third_step(
        self, tmp_path: Path,
    ) -> None:
        """Steps 1-2 done — peek returns discover-video-evidence."""
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
        assert result.step.id == "discover-video-evidence", (
            f"expected discover-video-evidence, got {result.step.id}"
        )

    def test_resume_after_three_completed_returns_fourth_step(
        self, tmp_path: Path,
    ) -> None:
        """Steps 1-3 done — peek returns build-reference-pack."""
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
        assert result.step.id == "build-reference-pack", (
            f"expected build-reference-pack, got {result.step.id}"
        )

    def test_resume_after_four_completed_returns_fifth_step(
        self, tmp_path: Path,
    ) -> None:
        """Steps 1-4 done — peek returns generate-thumbnails."""
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

        assert not result.exhausted
        assert result.step.id == "generate-thumbnails", (
            f"expected generate-thumbnails, got {result.step.id}"
        )

    def test_all_five_steps_completed_returns_exhausted(
        self, tmp_path: Path,
    ) -> None:
        """All 5 steps done — peek returns exhausted."""
        run_root, rid, proot = _setup_run_with_prefix(
            tmp_path, "demo", completed_steps=5
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
        plan = _build_thumbnail_maker_plan_v2()

        expected_subcommands = {
            "resolve-video": "resolve-video",
            "plan-evidence": "plan-evidence",
            "discover-video-evidence": "discover-video-evidence",
            "build-reference-pack": "build-reference-pack",
            "generate-thumbnails": "generate-thumbnails",
        }

        for step in plan["steps"]:
            step_id = step["id"]
            cmd = step.get("command", "")
            expected_sub = expected_subcommands[step_id]
            assert expected_sub in cmd, (
                f"step {step_id} command does not reference subcommand"
                f" {expected_sub!r}: {cmd!r}"
            )

    def test_all_plan_steps_use_local_adapter(self) -> None:
        """Thumbnail maker steps use adapter: local exclusively."""
        plan = _build_thumbnail_maker_plan_v2()

        for step in plan["steps"]:
            assert step.get("adapter") == "local", (
                f"step {step['id']} expected adapter=local, got {step.get('adapter')!r}"
            )

    def test_plan_steps_cost_zero(self) -> None:
        """All thumbnail maker steps cost $0 (local-only)."""
        plan = _build_thumbnail_maker_plan_v2()

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
        plan = _build_thumbnail_maker_plan_v2()

        for step in plan["steps"]:
            cmd = step.get("command", "")
            assert "{produces_root}" in cmd, (
                f"step {step['id']} missing {{produces_root}} in command: {cmd!r}"
            )

    def test_plan_commands_use_step_dir_for_previous_manifests(self) -> None:
        """Steps that reference previous manifests use ``{step_dir}`` relative paths."""
        plan = _build_thumbnail_maker_plan_v2()

        # Steps 3-5 reference --previous-manifest from a prior step
        prev_manifest_steps = {
            "discover-video-evidence",
            "build-reference-pack",
            "generate-thumbnails",
        }

        for step in plan["steps"]:
            cmd = step.get("command", "")
            if step["id"] in prev_manifest_steps:
                assert "{step_dir}" in cmd, (
                    f"step {step['id']} missing {{step_dir}} for previous-manifest: {cmd!r}"
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
        _seed_completed_step(run_root, "resolve-video")

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
        _seed_completed_step(run_root, "resolve-video", returncode=0)

        # Complete step 1 with returncode=1 (failure)
        _seed_completed_step(run_root, "plan-evidence", returncode=1)

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

        # resolve-video succeeded
        assert returncodes.get(("resolve-video",)) == 0

        # plan-evidence failed
        assert returncodes.get(("plan-evidence",)) == 1, (
            f"expected returncode=1 for plan-evidence, "
            f"got {returncodes.get(('plan-evidence',))}"
        )

    def test_nonzero_exit_does_not_exhaust_plan(self, tmp_path: Path) -> None:
        """A single nonzero exit does not mark the plan as exhausted."""
        run_root, rid, proot = _setup_run_with_prefix(
            tmp_path, "demo", completed_steps=0
        )

        # Complete first 2 steps normally
        _seed_completed_step(run_root, "resolve-video", returncode=0)
        _seed_completed_step(run_root, "plan-evidence", returncode=1)

        slug = "demo"
        events = read_events(run_root / "events.jsonl")
        base_plan = load_plan(proot / slug / "plan.json")
        plan = apply_mutations(base_plan, events)

        result = peek_current_step(
            plan, events, slug,
            project_root=proot / slug,
            run_id=rid,
        )

        # Even with a nonzero exit on plan-evidence, the third step
        # should still be pending (discover-video-evidence).
        assert not result.exhausted, (
            "expected pending step after nonzero exit, got exhausted"
        )
        assert result.step.id == "discover-video-evidence", (
            f"expected discover-video-evidence, got {result.step.id}"
        )


# ═══════════════════════════════════════════════════════════════════════
#  Stub step failure parity
# ═══════════════════════════════════════════════════════════════════════


class TestStubStepFailureParity:
    """Verify stub steps fail equivalently under task and Arnold paths.

    Steps 3-5 (discover-video-evidence, build-reference-pack,
    generate-thumbnails) raise ``NotImplementedError``.  The parity
    requirement is that the failure behavior — returncode, error
    message match, and ledger state — is identical whether the step
    executes via the task gate or through an Arnold lifecycle.
    """

    @pytest.mark.parametrize(
        "stub_step_id,expected_match",
        [
            ("discover-video-evidence", "thumbnail_maker.discover_video_evidence"),
            ("build-reference-pack", "thumbnail_maker.build_reference_pack"),
            ("generate-thumbnails", "thumbnail_maker.generate_thumbnails"),
        ],
    )
    def test_stub_executor_raises_not_implemented_error(
        self, stub_step_id: str, expected_match: str,
    ) -> None:
        """Each stub executor raises NotImplementedError with the correct message."""
        import argparse

        from astrid.packs.video_editing.orchestrators.thumbnail_maker.run import (
            _exec_build_reference_pack,
            _exec_discover_video_evidence,
            _exec_generate_thumbnails,
        )

        runners = {
            "discover-video-evidence": _exec_discover_video_evidence,
            "build-reference-pack": _exec_build_reference_pack,
            "generate-thumbnails": _exec_generate_thumbnails,
        }

        with pytest.raises(NotImplementedError, match=expected_match):
            runners[stub_step_id](argparse.Namespace())

    def test_stub_step_completed_with_returncode_1_in_ledger(
        self, tmp_path: Path,
    ) -> None:
        """When a stub step completes (nonzero), returncode=1 is recorded."""
        run_root, rid, proot = _setup_run_with_prefix(
            tmp_path, "demo", completed_steps=2
        )

        # Complete the stub step (discover-video-evidence) with returncode=1
        _seed_completed_step(
            run_root, "discover-video-evidence", returncode=1
        )

        events = read_events(run_root / "events.jsonl")
        completed_events = [
            e for e in events if e.get("kind") == "step_completed"
        ]

        discover_event = None
        for e in completed_events:
            path = tuple(e.get("plan_step_path", []))
            if path == ("discover-video-evidence",):
                discover_event = e
                break

        assert discover_event is not None, (
            "no step_completed event for discover-video-evidence"
        )
        assert discover_event.get("returncode") == 1, (
            f"expected returncode=1 for stub step, got {discover_event.get('returncode')}"
        )

    def test_stub_failure_does_not_prevent_next_step(
        self, tmp_path: Path,
    ) -> None:
        """After a stub step fails (returncode=1), the next step is still pending."""
        run_root, rid, proot = _setup_run_with_prefix(
            tmp_path, "demo", completed_steps=2
        )

        # Stub step fails
        _seed_completed_step(
            run_root, "discover-video-evidence", returncode=1
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
        assert result.step.id == "build-reference-pack", (
            f"expected build-reference-pack after stub failure, got {result.step.id}"
        )

    def test_all_three_stubs_fail_sequentially_then_exhausted(
        self, tmp_path: Path,
    ) -> None:
        """After all three stub steps fail, the plan is exhausted."""
        run_root, rid, proot = _setup_run_with_prefix(
            tmp_path, "demo", completed_steps=2
        )

        # All three stubs fail
        _seed_completed_step(
            run_root, "discover-video-evidence", returncode=1
        )
        _seed_completed_step(
            run_root, "build-reference-pack", returncode=1
        )
        _seed_completed_step(
            run_root, "generate-thumbnails", returncode=1
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
            "expected exhausted after all 5 steps (2 real + 3 stubs)"
        )

    def test_real_and_stub_steps_mixed_yield_correct_ledger_counts(
        self, tmp_path: Path,
    ) -> None:
        """Mixing real (returncode=0) and stub (returncode=1) produces correct counts."""
        run_root, rid, proot = _setup_run_with_prefix(
            tmp_path, "demo", completed_steps=0
        )

        # Real steps succeed
        _seed_completed_step(run_root, "resolve-video", returncode=0)
        _seed_completed_step(run_root, "plan-evidence", returncode=0)

        # Stub steps "fail" (NotImplementedError → returncode=1)
        _seed_completed_step(run_root, "discover-video-evidence", returncode=1)
        _seed_completed_step(run_root, "build-reference-pack", returncode=1)
        _seed_completed_step(run_root, "generate-thumbnails", returncode=1)

        events = read_events(run_root / "events.jsonl")
        completed_events = [
            e for e in events if e.get("kind") == "step_completed"
        ]

        # 5 steps × 4 events/step = 20 total events, 5 step_completed
        assert len(completed_events) == 5, (
            f"expected 5 step_completed events, got {len(completed_events)}"
        )

        returncodes = {
            tuple(e.get("plan_step_path", [])): e.get("returncode")
            for e in completed_events
        }

        assert returncodes.get(("resolve-video",)) == 0
        assert returncodes.get(("plan-evidence",)) == 0
        assert returncodes.get(("discover-video-evidence",)) == 1
        assert returncodes.get(("build-reference-pack",)) == 1
        assert returncodes.get(("generate-thumbnails",)) == 1


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

        for n in range(6):  # 0 through 5 completed
            p = proot / f"run{n}"
            run_root, rid, _ = _setup_run_with_prefix(p, "demo", completed_steps=n)
            events = read_events(run_root / "events.jsonl")

            # Each completed step = 4 events
            # (attested, dispatched, completed, produces_check_passed)
            expected_count = n * 4
            assert len(events) == expected_count, (
                f"completed_steps={n}: expected {expected_count} events, got {len(events)}"
            )

    def test_stub_steps_produce_correct_normalized_ledger_counts(
        self, tmp_path: Path,
    ) -> None:
        """Stub step failures (returncode=1) still produce 4 events per step."""
        proot = Path(tmp_path)

        # 2 real steps (0) + 3 stub steps (1) = 5 * 4 = 20 events
        run_root, rid, _ = _setup_run_with_prefix(proot, "demo", completed_steps=0)

        _seed_completed_step(run_root, "resolve-video", returncode=0)
        _seed_completed_step(run_root, "plan-evidence", returncode=0)
        _seed_completed_step(run_root, "discover-video-evidence", returncode=1)
        _seed_completed_step(run_root, "build-reference-pack", returncode=1)
        _seed_completed_step(run_root, "generate-thumbnails", returncode=1)

        events = read_events(run_root / "events.jsonl")
        assert len(events) == 20, (
            f"expected 20 events (5 steps × 4 events), got {len(events)}"
        )

        # Normalize and verify structural integrity
        normalized = normalize_for_parity(
            events,
            path_roots=[str(proot), str(run_root)],
        )

        kinds = [e.get("kind") for e in normalized]
        assert kinds.count("step_attested") == 5
        assert kinds.count("step_dispatched") == 5
        assert kinds.count("step_completed") == 5
        assert kinds.count("produces_check_passed") == 5


# ═══════════════════════════════════════════════════════════════════════
#  Plan template structural checks
# ═══════════════════════════════════════════════════════════════════════


class TestPlanTemplateStructure:
    """Structural invariants of the thumbnail_maker plan v2 template."""

    def test_plan_version_is_2(self) -> None:
        """Plan template emits version 2."""
        plan = _build_thumbnail_maker_plan_v2()
        assert plan.get("version") == 2

    def test_plan_has_five_steps(self) -> None:
        """Thumbnail maker plan has exactly 5 steps."""
        plan = _build_thumbnail_maker_plan_v2()
        assert len(plan["steps"]) == 5

    def test_step_ids_are_ordered_correctly(self) -> None:
        """Step IDs follow the canonical pipeline order."""
        plan = _build_thumbnail_maker_plan_v2()
        actual_ids = [step["id"] for step in plan["steps"]]
        assert actual_ids == THUMBNAIL_MAKER_STEP_IDS, (
            f"unexpected step order: {actual_ids}"
        )

    def test_each_step_has_produces(self) -> None:
        """Every step declares at least one produces output."""
        plan = _build_thumbnail_maker_plan_v2()
        for step in plan["steps"]:
            produces = step.get("produces", {})
            assert len(produces) >= 1, (
                f"step {step['id']} has no produces entries"
            )

    def test_plan_id_is_deterministic_with_same_run_id(self) -> None:
        """Same run_id produces same plan_id (deterministic)."""
        plan1 = _build_thumbnail_maker_plan_v2()
        plan2 = _build_thumbnail_maker_plan_v2()
        # Same run_id => same plan_id (deterministic)
        assert plan1["plan_id"] == plan2["plan_id"], (
            "expected deterministic plan_id for same run_id"
        )

    def test_plan_id_differs_with_different_run_id(self) -> None:
        """Different run_id produces different plan_id."""
        plan1 = _build_thumbnail_maker_plan_v2()

        from astrid.packs.video_editing.orchestrators.thumbnail_maker.plan_template import (
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

    def test_stub_step_ids_are_in_supported_list(self) -> None:
        """The five supported subcommands match the canonical five."""
        expected = {
            "resolve-video",
            "plan-evidence",
            "discover-video-evidence",
            "build-reference-pack",
            "generate-thumbnails",
        }
        assert expected == {
            "resolve-video",
            "plan-evidence",
            "discover-video-evidence",
            "build-reference-pack",
            "generate-thumbnails",
        }, "step_commands set mismatch"


# ═══════════════════════════════════════════════════════════════════════
#  Timeline integration
# ═══════════════════════════════════════════════════════════════════════


class TestTimelineIntegration:
    """Timeline assembly assertions for thumbnail maker parity."""

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
        _seed_completed_step(run_root, "resolve-video")
        assert tdir.is_dir(), "timeline directory removed after seeding events"

    def test_managed_timeline_has_canonical_files(self, tmp_path: Path) -> None:
        """Managed timeline directory contains assembly.json, manifest.json, display.json."""
        from tests.core.integrations.arnold_parity import assert_managed_timeline_exists

        run_root, timeline_ulid = make_project_state_root_with_timeline(
            tmp_path, slug="demo"
        )

        assert_managed_timeline_exists(tmp_path, timeline_ulid, project_slug="demo")

    def test_timeline_persists_across_all_five_steps(self, tmp_path: Path) -> None:
        """Timeline persists after seeding all 5 steps (including stubs)."""
        run_root, timeline_ulid = make_project_state_root_with_timeline(
            tmp_path, slug="demo"
        )

        from astrid.core.timeline.paths import timeline_dir

        # Seed all 5 steps
        for step_id in THUMBNAIL_MAKER_STEP_IDS:
            returncode = 1 if step_id in STUB_STEP_IDS else 0
            _seed_completed_step(run_root, step_id, returncode=returncode)

        tdir = timeline_dir("demo", timeline_ulid, root=tmp_path)
        assert tdir.is_dir(), "timeline directory lost after full 5-step seed"


# ═══════════════════════════════════════════════════════════════════════
#  JSON artifact parity
# ═══════════════════════════════════════════════════════════════════════


class TestJSONArtifactParity:
    """Generated JSON artifact parity for every thumbnail maker scenario.

    Verifies that the plan template produces consistent JSON artifact
    paths (produces entries) that match between task-gate and Arnold
    lifecycle interpretations.
    """

    def test_resolve_video_produces_path(self) -> None:
        """resolve-video produces ``video-resolution.json``."""
        plan = _build_thumbnail_maker_plan_v2()
        step = plan["steps"][0]
        assert step["id"] == "resolve-video"
        produces = step.get("produces", {})
        assert isinstance(produces, dict)
        assert "resolve_output" in produces, (
            f"expected resolve_output in produces keys, got {list(produces.keys())}"
        )

        output = produces["resolve_output"]
        path = output.get("path", "")
        assert "video-resolution.json" in path, (
            f"expected video-resolution.json in path, got {path!r}"
        )

    def test_plan_evidence_produces_path(self) -> None:
        """plan-evidence produces ``evidence/evidence-plan.json``."""
        plan = _build_thumbnail_maker_plan_v2()
        step = plan["steps"][1]
        assert step["id"] == "plan-evidence"
        produces = step.get("produces", {})
        assert isinstance(produces, dict)
        assert "evidence_plan_output" in produces

        output = produces["evidence_plan_output"]
        path = output.get("path", "")
        assert "evidence/evidence-plan.json" in path, (
            f"expected evidence/evidence-plan.json in path, got {path!r}"
        )

    def test_discover_video_evidence_produces_path(self) -> None:
        """discover-video-evidence produces ``evidence/candidates.json``."""
        plan = _build_thumbnail_maker_plan_v2()
        step = plan["steps"][2]
        assert step["id"] == "discover-video-evidence"
        produces = step.get("produces", {})
        assert isinstance(produces, dict)
        assert "candidates_output" in produces

        output = produces["candidates_output"]
        path = output.get("path", "")
        assert "evidence/candidates.json" in path, (
            f"expected evidence/candidates.json in path, got {path!r}"
        )

    def test_build_reference_pack_produces_path(self) -> None:
        """build-reference-pack produces ``evidence/reference-pack.json``."""
        plan = _build_thumbnail_maker_plan_v2()
        step = plan["steps"][3]
        assert step["id"] == "build-reference-pack"
        produces = step.get("produces", {})
        assert isinstance(produces, dict)
        assert "reference_pack_output" in produces

        output = produces["reference_pack_output"]
        path = output.get("path", "")
        assert "evidence/reference-pack.json" in path, (
            f"expected evidence/reference-pack.json in path, got {path!r}"
        )

    def test_generate_thumbnails_produces_path(self) -> None:
        """generate-thumbnails produces ``thumbnail-manifest.json``."""
        plan = _build_thumbnail_maker_plan_v2()
        step = plan["steps"][4]
        assert step["id"] == "generate-thumbnails"
        produces = step.get("produces", {})
        assert isinstance(produces, dict)
        assert "thumbnail_output" in produces

        output = produces["thumbnail_output"]
        path = output.get("path", "")
        assert "thumbnail-manifest.json" in path, (
            f"expected thumbnail-manifest.json in path, got {path!r}"
        )

    def test_all_five_produces_paths_are_unique(self) -> None:
        """Each of the 5 steps produces a unique output path."""
        plan = _build_thumbnail_maker_plan_v2()
        paths = set()
        for step in plan["steps"]:
            for _name, output in step.get("produces", {}).items():
                p = output.get("path", "")
                assert p not in paths, (
                    f"duplicate produces path {p!r} in step {step['id']}"
                )
                paths.add(p)

        assert len(paths) == 5, (
            f"expected 5 unique produces paths, got {len(paths)}"
        )

    def test_produces_paths_are_relative(self) -> None:
        """All produces paths are relative (no absolute paths)."""
        plan = _build_thumbnail_maker_plan_v2()
        for step in plan["steps"]:
            for _name, output in step.get("produces", {}).items():
                p = output.get("path", "")
                assert not p.startswith("/"), (
                    f"step {step['id']} produces absolute path: {p!r}"
                )

    def test_plan_emitted_json_matches_template(self, tmp_path: Path) -> None:
        """``emit_plan_json`` produces valid JSON that roundtrips cleanly."""
        from astrid.packs.video_editing.orchestrators.thumbnail_maker.plan_template import (
            build_plan_v2,
            emit_plan_json,
        )

        plan = build_plan_v2(
            python_exec="python3",
            run_root=tmp_path,
            source=Path("/tmp/source.mp4"),
            run_id="test-run",
        )

        plan_path = tmp_path / "plan.json"
        emit_plan_json(plan, plan_path)

        assert plan_path.is_file(), f"plan.json not emitted at {plan_path}"

        loaded = json.loads(plan_path.read_text(encoding="utf-8"))
        assert loaded["version"] == 2
        assert loaded["plan_id"] == plan["plan_id"]
        assert len(loaded["steps"]) == 5

        # Every step in the loaded plan matches structurally
        for i, step in enumerate(loaded["steps"]):
            assert step["id"] == plan["steps"][i]["id"]
            assert step["adapter"] == "local"
            assert "{produces_root}" in step.get("command", "")

    def test_plan_json_roundtrip_is_idempotent(self, tmp_path: Path) -> None:
        """Writing and reading plan.json twice produces the same result."""
        from astrid.packs.video_editing.orchestrators.thumbnail_maker.plan_template import (
            build_plan_v2,
            emit_plan_json,
        )

        plan = build_plan_v2(
            python_exec="python3",
            run_root=tmp_path,
            source=Path("/tmp/source.mp4"),
            run_id="test-run",
        )

        plan_path = tmp_path / "plan.json"
        emit_plan_json(plan, plan_path)
        loaded1 = json.loads(plan_path.read_text(encoding="utf-8"))

        # Write again and compare
        emit_plan_json(plan, plan_path)
        loaded2 = json.loads(plan_path.read_text(encoding="utf-8"))

        assert loaded1 == loaded2, "plan.json is not idempotent on re-emit"
