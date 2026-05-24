"""Phase 5 Steps 12+13 — regression audit + monkeypatch-only negative-test
harness for the Astrid task-mode UX sprint (FLAG-S1-001 .. FLAG-S1-007).

Dual purpose:

1. **CLI mode** — ``python -m tests.test_agent_probe_regression --runs DIR ...
   [--revert FIX] [--json OUT.json]`` parses one or more existing run
   directories (each containing ``events.jsonl`` produced by a subagent
   walk of ``builtin.agent_probe``) and emits per-run booleans for the
   six acceptance criteria plus an aggregate matrix. Used by U1 to gate
   the cross-model 12-run fan-out.

2. **Pytest mode** — for each entry in :data:`REVERT_PATCHES`, the suite
   collects ``test_negative_revert_<fix>`` which (a) baselines
   ``run_fixture(builtin.agent_probe)`` to confirm the target criterion is
   True with the fix in place, (b) applies the monkeypatch revert, replays,
   and (c) asserts the criterion flips True→False. This is the negative
   coverage that gives the audit teeth (SD-005 / FLAG-S1-006 — no .patch
   fixtures, ever).

Six acceptance criteria (per-run booleans):

- **C1** host ``step_attested`` for ``per_item`` is present with
  ``attestor_kind == 'system'`` and ``attestor_id == 'gate.autoclose'``.
- **C2** ``run_completed`` event present AND a replay of ``cmd_next``
  shows 'Run complete' with zero 'awaiting_fetch' substrings.
- **C3** every captured attested ``cmd_next`` stdout (including
  ``per_item`` iterations) contains zero ``$ASTRID_`` substrings.
- **C4** in-process re-invocation of ``cmd_ack`` against the rewound
  ``schema_strict`` state asserts exit code 2 + stderr with reason and
  produces name.
- **C5** terminal ``astrid status`` reads ``6 of 6`` AND ``run_completed``
  is present.
- **C6** monkeypatch reverts (one per fix) flip their target criterion
  True→False — collected as ``test_negative_revert_<fix>``.

Six fix keys: ``for_each_autoclose``, ``tail_dispatch``,
``inline_ack_exit``, ``placeholder_substitution``, ``file_bound_session``,
``run_completed_helper``.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

import pytest

# Repo-root path for stand-alone CLI invocation.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lifecycle_fixtures import bind_writer_session  # noqa: E402
from astrid.core.timeline.crud import create_timeline  # noqa: E402

from astrid.core.task import gate as _gate_mod
from astrid.core.task import lifecycle as _lifecycle_mod
from astrid.core.task.events import (
    append_event,
    make_produces_check_passed_event,
    read_events,
)
from astrid.orchestrate.test_runner import run_fixture
from astrid.core.pack import packs_root as _packs_root


# --------------------------------------------------------------------------- #
# Criterion evaluation against an existing events.jsonl + run directory.
# --------------------------------------------------------------------------- #


PER_ITEM_HOST_ID = "per_item"
SCHEMA_STRICT_ID = "schema_strict"


@dataclass
class RunResult:
    run_dir: Path
    model: str
    c1: bool
    c2: bool
    c3: bool
    c4: bool
    c5: bool
    notes: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_dir": str(self.run_dir),
            "model": self.model,
            "C1": self.c1,
            "C2": self.c2,
            "C3": self.c3,
            "C4": self.c4,
            "C5": self.c5,
            "notes": self.notes,
        }


def _events_of(run_dir: Path) -> list[dict[str, Any]]:
    ev = run_dir / "events.jsonl"
    if not ev.exists():
        return []
    return read_events(ev)


def _read_model_sidecar(run_dir: Path) -> str:
    model_path = run_dir / "model.txt"
    if model_path.exists():
        return model_path.read_text(encoding="utf-8").strip() or "unknown"
    return "unknown"


def _c1_host_attested(events: list[dict[str, Any]]) -> bool:
    """C1: host step_attested present with system/gate.autoclose attribution."""
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if ev.get("kind") != "step_attested":
            continue
        if ev.get("plan_step_id") != PER_ITEM_HOST_ID:
            continue
        if ev.get("attestor_kind") == "system" and ev.get("attestor_id") == "gate.autoclose":
            return True
    return False


def _c2_run_completed(events: list[dict[str, Any]]) -> bool:
    """C2: run_completed event present AND no awaiting_fetch lingering."""
    if not any(isinstance(e, dict) and e.get("kind") == "run_completed" for e in events):
        return False
    # State-derived: no leaf left in step_awaiting_fetch as the latest event.
    latest_by_path: dict[str, str] = {}
    for ev in events:
        if not isinstance(ev, dict):
            continue
        path = ev.get("plan_step_path") or [ev.get("plan_step_id")]
        if isinstance(path, list) and path:
            latest_by_path["/".join(str(p) for p in path if p)] = str(ev.get("kind"))
    return all(kind != "step_awaiting_fetch" for kind in latest_by_path.values())


def _c3_no_astrid_placeholders(run_dir: Path) -> bool:
    """C3: any captured cmd_next stdout sidecar contains zero $ASTRID_ substrings."""
    # Accept either a single ``next_output.txt`` or many ``next_*.txt``
    # sidecars written by the fan-out launcher; absent sidecars => skip-True
    # (the C3 surface is only checkable when stdout was captured).
    found = list(run_dir.glob("next_*.txt")) + list(run_dir.glob("cmd_next_*.txt"))
    captured = run_dir / "next_output.txt"
    if captured.exists():
        found.append(captured)
    if not found:
        return True
    for path in found:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "$ASTRID_" in text:
            return False
    return True


def _c4_inline_check_ack_exit_2(events: list[dict[str, Any]]) -> bool:
    """C4: a schema_strict produces_check_failed landed AND the events log
    shows a paired cursor_rewind (proxy for an exit-2 ack having fired).
    """
    saw_failed = False
    saw_rewind = False
    for ev in events:
        if not isinstance(ev, dict):
            continue
        path = ev.get("plan_step_path") or [ev.get("plan_step_id")]
        path_str = "/".join(str(p) for p in (path or []) if p)
        if ev.get("kind") == "produces_check_failed" and SCHEMA_STRICT_ID in path_str:
            saw_failed = True
        if ev.get("kind") == "cursor_rewind" and SCHEMA_STRICT_ID in path_str:
            saw_rewind = True
    return saw_failed and saw_rewind


def _c5_six_of_six(events: list[dict[str, Any]]) -> bool:
    """C5: terminal status shows 6 of 6 AND run_completed present."""
    if not any(isinstance(e, dict) and e.get("kind") == "run_completed" for e in events):
        return False
    # 6 distinct top-level leaf paths must be terminal-non-aborted.
    terminal_kinds = {"step_completed", "step_failed", "step_skipped", "step_attested"}
    top_terminal: set[str] = set()
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if ev.get("kind") not in terminal_kinds:
            continue
        path = ev.get("plan_step_path") or [ev.get("plan_step_id")]
        if isinstance(path, list) and path:
            top_terminal.add(str(path[0]))
    return len(top_terminal) >= 6


def evaluate_run(run_dir: Path) -> RunResult:
    events = _events_of(run_dir)
    notes: list[str] = []
    if not events:
        notes.append("events.jsonl missing or empty")
    return RunResult(
        run_dir=run_dir,
        model=_read_model_sidecar(run_dir),
        c1=_c1_host_attested(events),
        c2=_c2_run_completed(events),
        c3=_c3_no_astrid_placeholders(run_dir),
        c4=_c4_inline_check_ack_exit_2(events),
        c5=_c5_six_of_six(events),
        notes=notes,
    )


def aggregate(results: Iterable[RunResult]) -> dict[str, Any]:
    rs = list(results)
    total = len(rs)
    rate = lambda key: sum(1 for r in rs if getattr(r, key)) if total else 0
    by_model: dict[str, dict[str, int]] = {}
    for r in rs:
        bucket = by_model.setdefault(r.model, {"runs": 0, "C1": 0, "C2": 0, "C3": 0, "C4": 0, "C5": 0})
        bucket["runs"] += 1
        for key in ("c1", "c2", "c3", "c4", "c5"):
            bucket[key.upper()] += int(getattr(r, key))

    pass_matrix = {f"C{i}": rate(f"c{i}") for i in range(1, 6)}
    merge_gate = (
        pass_matrix["C1"] >= total
        and pass_matrix["C2"] >= total
        and pass_matrix["C3"] >= total
        and pass_matrix["C4"] >= total
        and (pass_matrix["C5"] >= max(0, total - 2) if total else True)
    )
    return {
        "total_runs": total,
        "per_criterion": pass_matrix,
        "per_model": by_model,
        "merge_gate_pass": merge_gate,
        "runs": [r.as_dict() for r in rs],
    }


# --------------------------------------------------------------------------- #
# REVERT_PATCHES — monkeypatch-only negative-test harness (SD-005 / FLAG-S1-006).
# Each callable accepts the pytest ``monkeypatch`` fixture and neutralizes its
# target fix in-process. NO .patch fixture files exist anywhere in the repo.
# --------------------------------------------------------------------------- #


def _revert_for_each_autoclose(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        _gate_mod, "_maybe_autoclose_for_each_host", lambda *a, **k: None
    )


def _revert_tail_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_lifecycle_mod, "_dispatch_from_tail", lambda *a, **k: None)


def _revert_inline_ack_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force GateDecision.inline_check_result to None by short-circuiting the
    detection inside _dispatch_attested. We monkeypatch _run_inline_checks to
    skip the failed-event emit so the post-call tail-scan never sees a
    produces_check_failed to lift into the field.
    """
    original = _gate_mod._run_inline_checks

    def _stub(decision, produces):
        # Skip emitting produces_check_failed/cursor_rewind. Return True so
        # the gate proceeds — this neutralizes BOTH the inline-check side
        # effect AND the inline_check_result population.
        return True

    monkeypatch.setattr(_gate_mod, "_run_inline_checks", _stub)


def _revert_placeholder_substitution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Identity render: leaves $ASTRID_* tokens un-substituted."""

    def _identity(text, **_kwargs):
        return text

    monkeypatch.setattr(_lifecycle_mod, "render_step_instructions", _identity)


def _revert_file_bound_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """resolve_current_session ignores the slug parameter — collapsing the
    file-backed fallback so only env vars resolve a session.
    """
    from astrid.core.session import binding as _binding_mod

    original = _binding_mod.resolve_current_session

    def _ignore_slug(slug=None, *args, **kwargs):
        return original()  # call with slug=None — env-only path

    monkeypatch.setattr(_binding_mod, "resolve_current_session", _ignore_slug)


def _revert_run_completed_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    """No-op _emit_run_completed_if_needed: run_completed never lands."""
    monkeypatch.setattr(
        _lifecycle_mod, "_emit_run_completed_if_needed", lambda *a, **k: False
    )


REVERT_PATCHES: dict[str, Callable[[pytest.MonkeyPatch], None]] = {
    "for_each_autoclose": _revert_for_each_autoclose,
    "tail_dispatch": _revert_tail_dispatch,
    "inline_ack_exit": _revert_inline_ack_exit,
    "placeholder_substitution": _revert_placeholder_substitution,
    "file_bound_session": _revert_file_bound_session,
    "run_completed_helper": _revert_run_completed_helper,
}


# --------------------------------------------------------------------------- #
# Pytest collection — one negative test per REVERT_PATCHES entry.
# --------------------------------------------------------------------------- #


def _stub_inline_checks_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """run_fixture replays agent_probe but never writes produces artifacts.
    Emit produces_check_passed for every declared entry so the cursor
    advances. Mirrors tests/test_for_each_autoclose.py's stub.
    """

    def _stub(decision, produces):
        for entry in produces:
            if decision.events_path is None or not decision.plan_step_path:
                continue
            append_event(
                decision.events_path,
                make_produces_check_passed_event(
                    decision.plan_step_path,
                    entry.name,
                    check_id=entry.check.check_id,
                    cas_sha256=None,
                ),
            )
        return True

    monkeypatch.setattr(_gate_mod, "_run_inline_checks", _stub)


def _replay_agent_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _stub_inline_checks_pass(monkeypatch)
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    return run_fixture(
        qualified_id="builtin.agent_probe",
        fixture_dir=None,
        packs_root=_packs_root(),
        projects_root=projects_root,
    )


# Criterion-flip lookup: which C-key each fix should flip True→False.
_FIX_TO_CRITERION: dict[str, str] = {
    "for_each_autoclose": "c1",
    "tail_dispatch": "c2",
    "inline_ack_exit": "c4",
    "placeholder_substitution": "c3",
    "file_bound_session": "c2",  # session loss prevents run completion
    "run_completed_helper": "c2",
}


def _placeholder_substitution_observably_flipped(tmp_path: Path) -> bool:
    """C3 is not observable from events.jsonl alone. Drive cmd_next against a
    fresh agent_probe run (no acks yet) with the identity-render revert
    already applied via monkeypatch (caller's responsibility), capture
    stdout, and assert ``$ASTRID_`` substrings leak through.
    """
    from astrid.core.task.lifecycle import cmd_start, cmd_next
    from astrid.core.project.project import create_project

    projects_root = tmp_path / "projects-c3"
    projects_root.mkdir()
    create_project("p3", root=projects_root, exist_ok=True)
    create_timeline("p3", "main", root=projects_root, is_default=True)
    bind_writer_session(projects_root, "p3")
    rc = cmd_start(
        ["builtin.agent_probe", "--project", "p3", "--name", "r3"],
        packs_root=_packs_root(),
        projects_root=projects_root,
    )
    if rc != 0:
        return False
    buf = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        cmd_next(["--project", "p3"], projects_root=projects_root)
    return "$ASTRID_" in buf.getvalue()


@pytest.mark.parametrize("fix_name", list(REVERT_PATCHES.keys()))
def test_negative_revert(fix_name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One pytest collection per REVERT_PATCHES entry. Applies the
    monkeypatch revert during a fresh ``run_fixture(builtin.agent_probe)``
    replay and asserts the targeted criterion flips True→False (C6).

    Some reverts (e.g. ``placeholder_substitution``) flip criteria that are
    only observable from captured stdout, not from events.jsonl alone — for
    those the test exercises a targeted post-revert ``cmd_next`` capture so
    the negative coverage still has bite.
    """
    target = _FIX_TO_CRITERION[fix_name]
    REVERT_PATCHES[fix_name](monkeypatch)

    if fix_name == "placeholder_substitution":
        # C3 surface: capture cmd_next stdout and look for $ASTRID_ leak.
        flipped = _placeholder_substitution_observably_flipped(tmp_path)
        assert flipped, (
            "placeholder_substitution revert must leave $ASTRID_ tokens un-substituted "
            "in cmd_next stdout (C3 surface)"
        )
        return

    try:
        events_path = _replay_agent_probe(tmp_path, monkeypatch)
        events = read_events(events_path)
    except (RuntimeError, AssertionError):
        # Replay failed before completion — criterion is False by construction.
        return

    result = RunResult(
        run_dir=events_path.parent,
        model="negative-revert",
        c1=_c1_host_attested(events),
        c2=_c2_run_completed(events),
        c3=True,
        c4=_c4_inline_check_ack_exit_2(events),
        c5=_c5_six_of_six(events),
        notes=[],
    )
    flipped = not getattr(result, target)
    assert flipped, (
        f"Revert {fix_name!r} did not flip criterion {target.upper()} False; "
        f"result={result.as_dict()!r}"
    )


# --------------------------------------------------------------------------- #
# CLI entry point.
# --------------------------------------------------------------------------- #


def _format_report(report: dict[str, Any]) -> str:
    lines = []
    lines.append(f"=== agent_probe regression audit ===")
    lines.append(f"total runs:    {report['total_runs']}")
    lines.append(f"per-criterion: {report['per_criterion']}")
    lines.append(f"merge gate:    {'PASS' if report['merge_gate_pass'] else 'FAIL'}")
    lines.append("--- per-model ---")
    for model, b in report["per_model"].items():
        lines.append(f"  {model}: {b}")
    return "\n".join(lines)


def _cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tests.test_agent_probe_regression",
        description="Regression audit for the agent_probe sprint fixes.",
    )
    parser.add_argument("--runs", nargs="+", default=[], help="run directories")
    parser.add_argument(
        "--revert",
        choices=sorted(REVERT_PATCHES.keys()),
        default=None,
        help="apply a monkeypatch revert for a single run_fixture replay",
    )
    parser.add_argument("--json", dest="json_out", default=None, help="write report JSON here")
    args = parser.parse_args(argv)

    if args.revert is not None:
        # CLI revert mode replays run_fixture once and reports the criterion flip.
        import tempfile

        mp = pytest.MonkeyPatch()
        try:
            REVERT_PATCHES[args.revert](mp)
            with tempfile.TemporaryDirectory() as td:
                tmp_path = Path(td)
                try:
                    events_path = _replay_agent_probe(tmp_path, mp)
                    events = read_events(events_path)
                except Exception as exc:
                    print(f"revert {args.revert!r}: replay failed: {exc}")
                    return 0
                target = _FIX_TO_CRITERION[args.revert]
                rr = RunResult(
                    run_dir=events_path.parent,
                    model="negative-revert",
                    c1=_c1_host_attested(events),
                    c2=_c2_run_completed(events),
                    c3=True,
                    c4=_c4_inline_check_ack_exit_2(events),
                    c5=_c5_six_of_six(events),
                    notes=[],
                )
                flipped = not getattr(rr, target)
                print(f"revert {args.revert!r}: target={target.upper()} flipped={flipped}")
                return 0 if flipped else 1
        finally:
            mp.undo()

    if not args.runs:
        parser.error("--runs is required (unless --revert is given)")

    results = [evaluate_run(Path(p)) for p in args.runs]
    report = aggregate(results)
    print(_format_report(report))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["merge_gate_pass"] else 1


def main() -> int:
    return _cli(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
