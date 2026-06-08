"""Static inventory for Sprint 1 task-run/event-log mutation surfaces.

This file intentionally does not assert the final WriterContext-only shape.
Batch T2 is the inventory checkpoint: every known production mutation surface is
named and classified so later batches can move entries between categories
without letting new raw writers slip in unnoticed.
"""

from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
ASTRID_ROOT = REPO_ROOT / "astrid"

SPRINT1_STOP_LINE_XFAIL = pytest.mark.xfail(
    strict=True,
    reason="Sprint 1 stop-line: pending writer-context inventory entries must be gone",
)

WATCHED_CALLS = {
    "append_event",
    "append_event_locked",
    "record_dispatch_complete",
    "bump_epoch_and_swap_session",
    "claim_orphan_lease",
    "release_writer_lease",
    "append_event_to_locked_handle",
}


@dataclass(frozen=True)
class CallSite:
    path: str
    qualname: str
    call: str


EXPECTED_TASK_RUN_CALLS: dict[CallSite, tuple[int, str]] = {
    CallSite(
        "astrid/core/session/lease.py",
        "mutate_lease_for_takeover",
        "bump_epoch_and_swap_session",
    ): (1, "takeover_bootstrap_lease_rewriter"),
    CallSite(
        "astrid/core/session/lease.py",
        "mutate_lease_for_takeover",
        "claim_orphan_lease",
    ): (1, "takeover_bootstrap_lease_rewriter"),
    CallSite(
        "astrid/core/session/writer.py",
        "WriterContext.append",
        "append_event_locked",
    ): (1, "normal_writer_context_boundary"),
    CallSite("astrid/core/task/events.py", "append_event", "append_event_locked"): (
        1,
        "guarded_legacy_test_migration_wrapper",
    ),
    CallSite(
        "astrid/core/session/lease.py",
        "bump_epoch_and_swap_session",
        "append_event_to_locked_handle",
    ): (1, "same_lock_takeover_event_exception"),
    CallSite(
        "astrid/core/session/lease.py",
        "claim_orphan_lease",
        "append_event_to_locked_handle",
    ): (1, "same_lock_takeover_event_exception"),
    CallSite("astrid/core/task/inbox.py", "consume_inbox_entry", "release_writer_lease"): (
        1,
        "lease_release_after_inbox_abort",
    ),
    CallSite("astrid/core/task/run_store.py", "cmd_abort", "release_writer_lease"): (
        1,
        "lease_release_after_abort",
    ),
    CallSite(
        "astrid/core/task/lifecycle_ack.py",
        "_ack_approve",
        "record_dispatch_complete",
    ): (1, "dispatch_complete_caller"),
    CallSite(
        "astrid/core/orchestrate/test_runner.py",
        "_finish_code_step",
        "record_dispatch_complete",
    ): (1, "author_fixture_dispatch_complete_caller"),
    CallSite("astrid/core/gateway/__init__.py", "_main_impl", "record_dispatch_complete"): (
        1,
        "gateway_dispatch_complete_caller",
    ),
    CallSite(
        "astrid/packs/video_editing/orchestrators/event_talks/run.py",
        "_run_step_subcommand",
        "record_dispatch_complete",
    ): (1, "canonical_pack_step_reentry_dispatch_complete_caller"),
    CallSite(
        "astrid/packs/video_editing/orchestrators/thumbnail_maker/run.py",
        "_run_step_subcommand",
        "record_dispatch_complete",
    ): (1, "canonical_pack_step_reentry_dispatch_complete_caller"),
    CallSite(
        "astrid/core/integrations/runpod/sweeper.py",
        "append_runpod_sweeper_event",
        "append_event_locked",
    ): (1, "runpod_sweeper_owned_event_append"),
}

EXPECTED_LEASE_REWRITE_CALLS = {
    CallSite("astrid/core/session/lease.py", "write_lease_init", "write_json_atomic"): 1,
    CallSite(
        "astrid/core/session/lease.py",
        "bump_epoch_and_swap_session",
        "write_json_atomic",
    ): 1,
    CallSite(
        "astrid/core/session/lease.py",
        "claim_orphan_lease",
        "write_json_atomic",
    ): 1,
    CallSite(
        "astrid/core/session/lease.py",
        "release_writer_lease",
        "write_json_atomic",
    ): 1,
}

EXPECTED_DIRECT_EVENT_WRITES = {
    CallSite("astrid/core/task/events.py", "append_event_locked", "handle.write"): (
        1,
        "generic_event_transport",
    ),
    CallSite(
        "astrid/core/task/events.py",
        "append_event_to_locked_handle",
        "handle.write",
    ): (1, "generic_same_lock_event_transport"),
    CallSite("astrid/core/task/normalize.py", "dump_events_jsonl", "fh.write"): (
        2,
        "author_test_normalized_event_output",
    ),
    CallSite(
        "astrid/core/timeline/eventlog/local_fs.py",
        "LocalFsBackend._append_line_locked",
        "handle.write",
    ): (1, "timeline_event_log_backend_non_task"),
}

APPROVED_PRODUCTION_LEGACY_APPEND_EVENT_CALLS: dict[CallSite, str] = {}

APPROVED_PRODUCTION_APPEND_EVENT_LOCKED_CALLS: dict[CallSite, str] = {
    CallSite(
        "astrid/core/session/writer.py",
        "WriterContext.append",
        "append_event_locked",
    ): "normal_writer_context_boundary",
    CallSite(
        "astrid/core/task/events.py",
        "append_event",
        "append_event_locked",
    ): "guarded_legacy_test_migration_wrapper",
    CallSite(
        "astrid/core/integrations/runpod/sweeper.py",
        "append_runpod_sweeper_event",
        "append_event_locked",
    ): "runpod_sweeper_owned_event_append",
}

APPROVED_PRODUCTION_IN_HANDLE_APPEND_CALLS: dict[CallSite, str] = {
    CallSite(
        "astrid/core/session/lease.py",
        "bump_epoch_and_swap_session",
        "append_event_to_locked_handle",
    ): "same_lock_takeover_event_exception",
    CallSite(
        "astrid/core/session/lease.py",
        "claim_orphan_lease",
        "append_event_to_locked_handle",
    ): "same_lock_takeover_event_exception",
}

APPROVED_PRODUCTION_DIRECT_EVENT_WRITES: dict[CallSite, str] = {
    CallSite(
        "astrid/core/task/events.py",
        "append_event_locked",
        "handle.write",
    ): "generic_event_transport",
    CallSite(
        "astrid/core/task/events.py",
        "append_event_to_locked_handle",
        "handle.write",
    ): "generic_same_lock_event_transport",
    CallSite(
        "astrid/core/task/normalize.py",
        "dump_events_jsonl",
        "fh.write",
    ): "author_test_normalized_event_output_non_task",
}

EXPECTED_PACK_LOCAL_LOG_WRITES = {
    CallSite(
        "astrid/packs/video_editing/orchestrators/event_talks/run.py",
        "_append_pack_run_started",
        "handle.write",
    ): (1, "pack_local_event_talks_audit_log_non_task"),
    CallSite(
        "astrid/packs/video_editing/orchestrators/thumbnail_maker/run.py",
        "_append_pack_run_started",
        "handle.write",
    ): (1, "pack_local_thumbnail_maker_audit_log_non_task"),
}

EXPECTED_RUNPOD_NON_TASK_AUDIT_WRITES = {
    CallSite(
        "astrid/core/integrations/runpod/sweeper.py",
        "_append_sweep_audit",
        "handle.write",
    ): (1, "runpod_sweeper_supplemental_audit_log_non_task"),
}

EXPECTED_LEASE_REWRITER_DEFS = {
    CallSite("astrid/core/session/lease.py", "write_lease_init", "def"): (
        "lease_initializer"
    ),
    CallSite("astrid/core/session/lease.py", "bump_epoch_and_swap_session", "def"): (
        "lease_rewriter_same_lock_takeover"
    ),
    CallSite("astrid/core/session/lease.py", "claim_orphan_lease", "def"): (
        "lease_rewriter_same_lock_orphan_claim"
    ),
    CallSite("astrid/core/session/lease.py", "release_writer_lease", "def"): (
        "lease_rewriter_release"
    ),
}


def _python_files() -> list[Path]:
    return sorted(ASTRID_ROOT.rglob("*.py"))


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        owner = node.func.value
        if node.func.attr == "write" and isinstance(owner, ast.Name):
            return f"{owner.id}.write"
        return node.func.attr
    return None


def _collect_calls(*, watched: set[str]) -> Counter[CallSite]:
    found: Counter[CallSite] = Counter()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        stack: list[str] = []

        class Visitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                stack.append(node.name)
                self.generic_visit(node)
                stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                stack.append(node.name)
                self.generic_visit(node)
                stack.pop()

            def visit_Call(self, node: ast.Call) -> None:
                name = _call_name(node)
                if name in watched:
                    found[CallSite(_relative(path), ".".join(stack), name)] += 1
                self.generic_visit(node)

        Visitor().visit(tree)
    return found


def _collect_defs(names: set[str]) -> dict[CallSite, str]:
    found: dict[CallSite, str] = {}
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))

        class Visitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                if node.name in names:
                    found[CallSite(_relative(path), node.name, "def")] = ""
                self.generic_visit(node)

        Visitor().visit(tree)
    return found


def test_task_run_mutation_call_inventory_is_fully_classified() -> None:
    actual = _collect_calls(watched=WATCHED_CALLS)
    actual = Counter(
        {
            site: count
            for site, count in actual.items()
            if not site.path.startswith("astrid/core/timeline/")
        }
    )
    expected = Counter(
        {
            site: count_and_category[0]
            for site, count_and_category in EXPECTED_TASK_RUN_CALLS.items()
        }
    )
    assert actual == expected
    assert {category for _, category in EXPECTED_TASK_RUN_CALLS.values()} >= {
        "gateway_dispatch_complete_caller",
        "normal_writer_context_boundary",
    }


def test_stop_line_no_pending_task_run_mutation_categories_remain() -> None:
    pending = {
        site: category
        for site, (_count, category) in EXPECTED_TASK_RUN_CALLS.items()
        if "pending" in category
    }
    assert pending == {}


def test_lease_rewrite_inventory_is_metadata_preservation_surface() -> None:
    actual = _collect_calls(watched={"write_json_atomic"})
    actual = Counter(
        {
            site: count
            for site, count in actual.items()
            if site.path == "astrid/core/session/lease.py"
        }
    )
    assert actual == Counter(EXPECTED_LEASE_REWRITE_CALLS)


def test_direct_event_line_writers_are_classified() -> None:
    actual = _collect_calls(watched={"handle.write", "fh.write"})
    relevant = Counter(
        {
            site: count
            for site, count in actual.items()
            if site in EXPECTED_DIRECT_EVENT_WRITES
        }
    )
    assert relevant == Counter(
        {
            site: count_and_category[0]
            for site, count_and_category in EXPECTED_DIRECT_EVENT_WRITES.items()
        }
    )
    unclassified_task_writes = {
        site: count
        for site, count in actual.items()
        if site.path.startswith("astrid/core/task/")
        and site not in EXPECTED_DIRECT_EVENT_WRITES
    }
    assert unclassified_task_writes == {}


def test_static_allowlists_reject_raw_task_run_append_bypasses() -> None:
    actual = _collect_calls(
        watched={"append_event", "append_event_locked", "append_event_to_locked_handle"}
    )
    production_actual = Counter(
        {
            site: count
            for site, count in actual.items()
            if site.path.startswith("astrid/")
            and not site.path.startswith("astrid/core/timeline/")
        }
    )

    legacy_append_calls = {
        site: count
        for site, count in production_actual.items()
        if site.call == "append_event"
    }
    assert legacy_append_calls == Counter(
        {site: 1 for site in APPROVED_PRODUCTION_LEGACY_APPEND_EVENT_CALLS}
    )

    locked_calls = {
        site: count
        for site, count in production_actual.items()
        if site.call == "append_event_locked"
    }
    assert locked_calls == Counter(
        {site: 1 for site in APPROVED_PRODUCTION_APPEND_EVENT_LOCKED_CALLS}
    )

    in_handle_calls = {
        site: count
        for site, count in production_actual.items()
        if site.call == "append_event_to_locked_handle"
    }
    assert in_handle_calls == Counter(
        {site: 1 for site in APPROVED_PRODUCTION_IN_HANDLE_APPEND_CALLS}
    )


def test_static_allowlist_rejects_direct_task_event_line_writes() -> None:
    actual = _collect_calls(watched={"handle.write", "fh.write"})
    production_task_writes = Counter(
        {
            site: count
            for site, count in actual.items()
            if site.path.startswith("astrid/core/task/")
        }
    )
    assert production_task_writes == Counter(
        {
            site: EXPECTED_DIRECT_EVENT_WRITES[site][0]
            for site in APPROVED_PRODUCTION_DIRECT_EVENT_WRITES
        }
    )


def test_builtin_pack_local_logs_are_classified_non_task() -> None:
    actual_writes = _collect_calls(watched={"handle.write", "fh.write"})
    relevant_writes = Counter(
        {
            site: count
            for site, count in actual_writes.items()
            if site in EXPECTED_PACK_LOCAL_LOG_WRITES
        }
    )
    assert relevant_writes == Counter(
        {
            site: count_and_category[0]
            for site, count_and_category in EXPECTED_PACK_LOCAL_LOG_WRITES.items()
        }
    )

    pack_append_calls = {
        site: count
        for site, count in _collect_calls(watched={"append_event"}).items()
        if site.path
        in {
            "astrid/packs/video_editing/orchestrators/event_talks/run.py",
            "astrid/packs/video_editing/orchestrators/thumbnail_maker/run.py",
        }
    }
    assert pack_append_calls == {}


def test_runpod_sweeper_supplemental_audit_writes_are_classified_non_task() -> None:
    actual_writes = _collect_calls(watched={"handle.write", "fh.write"})
    relevant_writes = Counter(
        {
            site: count
            for site, count in actual_writes.items()
            if site in EXPECTED_RUNPOD_NON_TASK_AUDIT_WRITES
        }
    )
    assert relevant_writes == Counter(
        {
            site: count_and_category[0]
            for site, count_and_category in EXPECTED_RUNPOD_NON_TASK_AUDIT_WRITES.items()
        }
    )


def test_runpod_sweeper_event_append_is_classified() -> None:
    actual_writes = _collect_calls(watched={"handle.write", "fh.write"})
    runpod_direct_writes = {
        site: count
        for site, count in actual_writes.items()
        if site.path == "astrid/core/integrations/runpod/sweeper.py"
    }
    assert runpod_direct_writes == Counter(
        {
            site: count_and_category[0]
            for site, count_and_category in EXPECTED_RUNPOD_NON_TASK_AUDIT_WRITES.items()
        }
    )

    runpod_raw_task_appends = {
        site: count
        for site, count in _collect_calls(watched={"append_event_locked"}).items()
        if site.path == "astrid/core/integrations/runpod/sweeper.py"
    }
    assert runpod_raw_task_appends == {
        CallSite(
            "astrid/core/integrations/runpod/sweeper.py",
            "append_runpod_sweeper_event",
            "append_event_locked",
        ): 1
    }


def test_lease_rewriter_definitions_are_named() -> None:
    lease_defs = _collect_defs(
        {
            "write_lease_init",
            "bump_epoch_and_swap_session",
            "claim_orphan_lease",
            "release_writer_lease",
        }
    )
    assert set(EXPECTED_LEASE_REWRITER_DEFS) <= set(lease_defs)
