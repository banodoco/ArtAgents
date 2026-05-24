#!/usr/bin/env python3
"""Migrate Sprint 2 plan.json files to the Sprint 3 collapsed schema.

Usage:
  scripts/migrations/sprint-3/migrate_plans.py --dry-run   # default: preview
  scripts/migrations/sprint-3/migrate_plans.py --apply      # commit changes
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Ensure the repo root is on sys.path so `astrid` is importable.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

PROJECTS_ROOT_DEFAULT = os.path.expanduser("~/Documents/reigh-workspace/astrid-projects")
PLAN_BACKUP_SUFFIX = ".sprint3.bak"
EVENTS_BACKUP_SUFFIX = ".plan_initialized.sprint3.bak"
_LEGACY_ACTOR_FLAG_RE = re.compile(r"(?<!\S)--actor(?=(\s|=|$))")


def _read_legacy_plan_payload(path: str | Path) -> Any:
    """Load + JSON-parse a plan.json WITHOUT calling _validate_plan.

    Public load_plan() rejects version != 2; this private reader bypasses
    the gate so we can inspect and rewrite v1 plans.

    Sprint 5b T4: inlined from astrid.core.task.plan._read_legacy_plan_payload
    so the migration script survives the legacy reader removal.
    """
    import json as _json
    p = Path(path)
    try:
        return _json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except _json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {p}: {exc.msg}") from exc
    except OSError as exc:
        raise ValueError(f"failed to read {p}: {exc}") from exc


def _migrate_step(step: dict[str, Any]) -> dict[str, Any]:
    """Rewrite a single v1 step dict to the collapsed schema shape."""
    kind = step.get("kind", "code")  # v1 defaults to code when kind absent
    new: dict[str, Any] = {"id": step["id"], "adapter": "local", "version": 1}

    # Fields that survive any kind transition.
    for field in ("produces", "check"):
        if field in step:
            new[field] = step[field]
    if "repeat" in step:
        new["repeat"] = _migrate_repeat(step["repeat"])

    if kind in ("code", None):
        new["adapter"] = "local"
        new["assignee"] = "system"
        new["command"] = _migrate_legacy_text(step.get("command"))
        new["version"] = 1
        return new

    if kind == "attested":
        new["adapter"] = "manual"
        new["command"] = _migrate_legacy_text(step.get("command", ""))
        new["assignee"] = _broadened_assignee(step)
        new["requires_ack"] = True
        new["version"] = 1
        instructions = step.get("instructions")
        if instructions:
            new["instructions"] = _migrate_legacy_text(instructions)
        # Preserve ack rule if present.
        ack = step.get("ack")
        if isinstance(ack, dict) and ack.get("kind") in ("agent", "actor", "human"):
            ack_kind = "human" if ack.get("kind") == "actor" else ack["kind"]
            new["ack"] = {"kind": ack_kind}
        return new

    if kind == "nested":
        child_plan = step.get("plan")
        if isinstance(child_plan, dict) and isinstance(child_plan.get("steps"), list):
            children = [_migrate_step(s) for s in child_plan["steps"]]
            new["children"] = children
            # Aggregate produces from children (best-effort).
            produces: dict[str, Any] = {}
            for child in children:
                if isinstance(child.get("produces"), dict):
                    produces.update(child["produces"])
            if produces:
                new["produces"] = produces
        # No command or other fields — it's a group step.
        new["adapter"] = "local"  # group steps keep 'local' default
        new["assignee"] = "system"
        new.pop("command", None)
        new["version"] = 1
        return new

    # Unknown kind — fall back to local.
    new["adapter"] = "local"
    new["assignee"] = "system"
    new["command"] = _migrate_legacy_text(step.get("command"))
    new["version"] = 1
    return new


def _migrate_legacy_text(value: Any) -> Any:
    """Normalize legacy CLI spelling in migrated plan text fields."""
    if not isinstance(value, str):
        return value
    return _LEGACY_ACTOR_FLAG_RE.sub("--human", value)


def _migrate_repeat(value: Any) -> Any:
    """Copy repeat payloads while recursively normalizing embedded text.

    Legacy repeat-until condition names remain as compatibility data because
    the runtime still marks them as supported legacy reads. The migration's job
    here is to keep repeat payloads valid and idempotent while eliminating
    legacy actor flag spelling from any text-bearing nested values.
    """
    if isinstance(value, dict):
        return {k: _migrate_repeat(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_migrate_repeat(v) for v in value]
    return _migrate_legacy_text(value)


def _broadened_assignee(step: dict[str, Any]) -> str:
    """Derive assignee for an attested step per SD-A broadening rules.

    SD-A compatibility: attested steps with no concrete identity get broadened
    to canonical forms only. Legacy actor maps to any-human; legacy any-agent
    no longer appears in migrated output.
    """
    ack = step.get("ack")
    if isinstance(ack, dict):
        if ack.get("kind") == "agent":
            return "system"
        if ack.get("kind") in ("actor", "human"):
            return "any-human"
    return "any-human"  # default fallback


def migrate_plan(plan_path: Path) -> tuple[bool, dict[str, Any], list[str]]:
    """Migrate a single plan.json file.

    Returns ``(changed, new_payload, broadening_notes)``. This function is pure
    with respect to disk writes so dry-run and tests can inspect output without
    mutating source plans.
    """
    try:
        payload = _read_legacy_plan_payload(plan_path)
    except FileNotFoundError:
        return False, {}, []
    except Exception as exc:
        print(f"  WARN: could not read {plan_path}: {exc}", file=sys.stderr)
        return False, {}, []

    if not isinstance(payload, dict):
        print(f"  WARN: {plan_path} is not a JSON object", file=sys.stderr)
        return False, {}, []

    version = payload.get("version")
    if version == 2:
        return False, {}, []  # already migrated, idempotent

    steps_raw = payload.get("steps")
    if not isinstance(steps_raw, list):
        print(f"  WARN: {plan_path} steps is not a list", file=sys.stderr)
        return False, {}, []

    migrated_steps: list[dict[str, Any]] = []
    broadening_notes: list[str] = []

    for step in steps_raw:
        if not isinstance(step, dict):
            migrated_steps.append(step)
            continue
        migrated = _migrate_step(step)
        migrated_steps.append(migrated)

        # Track assignee broadening.
        if migrated.get("assignee") in ("any-human",):
            step_id = migrated.get("id", step.get("id", "?"))
            broadening_notes.append(
                f"    {step_id}: {step.get('assignee', '?')} → {migrated['assignee']}"
            )

    new_payload: dict[str, Any] = {
        "plan_id": payload.get("plan_id", "unknown"),
        "version": 2,
        "steps": migrated_steps,
    }
    return True, new_payload, broadening_notes


def _backup_path(plan_path: Path) -> Path:
    return plan_path.with_name(plan_path.name + PLAN_BACKUP_SUFFIX)


def _write_backup_once(plan_path: Path) -> Path:
    backup_path = _backup_path(plan_path)
    if backup_path.exists():
        return backup_path
    backup_path.write_bytes(plan_path.read_bytes())
    return backup_path


def _events_backup_path(events_path: Path) -> Path:
    return events_path.with_name(events_path.name + EVENTS_BACKUP_SUFFIX)


def _write_events_backup_once(events_path: Path) -> Path:
    backup_path = _events_backup_path(events_path)
    if backup_path.exists():
        return backup_path
    backup_path.write_bytes(events_path.read_bytes())
    return backup_path


def _event_hash(prev_hash: str, event: dict[str, Any]) -> str:
    import hashlib as _hashlib

    payload = {k: v for k, v in event.items() if k != "hash"}
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "sha256:" + _hashlib.sha256((prev_hash + "\n" + canonical).encode("utf-8")).hexdigest()


def _seed_plan_initialized_event(
    run_dir: Path,
    plan_payload: dict[str, Any],
    *,
    apply: bool,
) -> bool:
    events_path = run_dir / "events.jsonl"
    if not events_path.exists():
        return False
    try:
        events = [
            json.loads(line)
            for line in events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  WARN: could not seed plan_initialized in {events_path}: {exc}", file=sys.stderr)
        return False
    if not events:
        return False
    if events[0].get("kind") == "plan_initialized":
        return False

    first = events[0]
    plan_hash = first.get("plan_hash")
    if not isinstance(plan_hash, str) or not plan_hash:
        plan_hash = "unknown"
    run_id = first.get("run_id") if isinstance(first.get("run_id"), str) else run_dir.name
    seeded = {
        "kind": "plan_initialized",
        "run_id": run_id,
        "plan_hash": plan_hash,
        "plan": plan_payload,
        "ts": first.get("ts") if isinstance(first.get("ts"), str) else "1970-01-01T00:00:00Z",
    }
    raw_events = [seeded] + [
        {k: v for k, v in event.items() if k != "hash"}
        for event in events
    ]

    prev_hash = "sha256:" + "0" * 64
    rehashed: list[dict[str, Any]] = []
    for event in raw_events:
        stored = dict(event)
        stored["hash"] = _event_hash(prev_hash, stored)
        rehashed.append(stored)
        prev_hash = stored["hash"]

    if apply:
        _write_events_backup_once(events_path)
        events_path.write_text(
            "".join(
                json.dumps(ev, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
                for ev in rehashed
            ),
            encoding="utf-8",
        )
    return True


def _find_run_dirs(projects_root: Path) -> list[Path]:
    """Return all run directories under projects_root."""
    run_dirs: list[Path] = []
    if not projects_root.exists():
        return run_dirs
    # Structure: projects_root/<slug>/runs/<run-id>
    runs_glob = projects_root.glob("*/runs/*")
    for candidate in runs_glob:
        if candidate.is_dir() and (candidate / "plan.json").exists():
            run_dirs.append(candidate)
    return sorted(run_dirs)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate Sprint 2 plan.json to Sprint 3 collapsed schema."
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Preview changes without modifying files (default)"
    )
    parser.add_argument("--apply", action="store_true", help="Commit changes to disk")
    parser.add_argument(
        "--projects-root",
        default=PROJECTS_ROOT_DEFAULT,
        help=f"Root of astrid-projects (default: {PROJECTS_ROOT_DEFAULT})",
    )
    parser.add_argument(
        "--log-path",
        default=None,
        help="Path for plan.migration.log (default: <projects-root>/plan.migration.log)",
    )
    args = parser.parse_args()

    if args.apply:
        args.dry_run = False

    projects_root = Path(os.path.expanduser(args.projects_root))
    log_path = Path(args.log_path) if args.log_path else projects_root / "plan.migration.log"

    if not projects_root.exists():
        print(f"Projects root {projects_root} does not exist. Nothing to migrate.")
        return 0

    run_dirs = _find_run_dirs(projects_root)
    if not run_dirs:
        print(f"No run directories with plan.json found under {projects_root}")
        return 0

    migrated_count = 0
    skipped_count = 0
    all_broadening_notes: list[tuple[str, list[str]]] = []

    for run_dir in run_dirs:
        plan_path = run_dir / "plan.json"
        try:
            changed, new_payload, broadening_notes = migrate_plan(plan_path)
        except Exception as exc:
            print(f"  ERROR migrating {plan_path}: {exc}", file=sys.stderr)
            skipped_count += 1
            continue

        seed_payload: dict[str, Any] | None = new_payload if changed else None
        if seed_payload is None:
            try:
                current_payload = _read_legacy_plan_payload(plan_path)
                if isinstance(current_payload, dict) and current_payload.get("version") == 2:
                    seed_payload = current_payload
            except Exception:
                seed_payload = None

        seeded = False
        if seed_payload is not None:
            seeded = _seed_plan_initialized_event(
                run_dir,
                seed_payload,
                apply=False,
            )

        if not changed and not seeded:
            skipped_count += 1
            continue

        rel = plan_path.relative_to(projects_root) if plan_path.is_relative_to(projects_root) else plan_path
        print(f"  migrate: {rel}")
        if seeded:
            print(f"  seed-plan-initialized: {rel.parent / 'events.jsonl'}")

        if args.apply:
            try:
                if changed:
                    _write_backup_once(plan_path)
                    plan_path.write_text(
                        json.dumps(new_payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )
                if seeded and seed_payload is not None:
                    _seed_plan_initialized_event(run_dir, seed_payload, apply=True)
            except OSError as exc:
                print(f"  ERROR writing {plan_path}: {exc}", file=sys.stderr)
                skipped_count += 1
                continue

        if broadening_notes:
            all_broadening_notes.append((str(rel), broadening_notes))
        migrated_count += 1

    # Write migration log.
    log_lines: list[str] = []
    if all_broadening_notes:
        total_broadened = sum(len(notes) for _, notes in all_broadening_notes)
        log_lines.append(
            f"WARNING: {total_broadened} step(s) had their assignee broadened to "
            f"any-human. Run `astrid claim <step> --for ...` post-migration "
            f"to pin a concrete identity."
        )
        log_lines.append("")
        for plan_rel, notes in all_broadening_notes:
            log_lines.append(f"Plan: {plan_rel}")
            log_lines.extend(notes)
            log_lines.append("")

    action = "DRY-RUN" if args.dry_run else "APPLIED"
    summary = (
        f"Plan migration {action}: {migrated_count} migrated, "
        f"{skipped_count} skipped (already v2 or errors)"
    )
    print(summary)
    log_lines.insert(0, summary)
    log_lines.insert(1, "")

    if all_broadening_notes or migrated_count > 0:
        try:
            log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
            print(f"Log written to {log_path}")
        except OSError as exc:
            print(f"WARN: could not write log to {log_path}: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
