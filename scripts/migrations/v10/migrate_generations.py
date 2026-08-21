"""Migrate eligible completed legacy runs into the kernel run/task model.

Fidelity path (used whenever a completed run has at least one importable
artifact)::

    RunRepository.create(kind="tool_id", children=[one child], evidence=[obs])
    TaskRepository.claim(actor_kind="system", ...)      # FIFO picks the child
    TaskRepository.start(expected_status_version=1, ...)
    TaskRepository.complete(outputs=imported artifacts,
                            relations=derived_from -> inputs, ...)

The legacy run.json is stuffed verbatim into ``input`` and one evidence
item ``{kind: observation, data: {legacy_path, status, argv}}`` records
the migration. The task terminates ``succeeded`` and the run projection
recomputes to ``succeeded``. No unregistered legacy kinds are replayed.

Fallback path (completed run with **no** importable artifacts): the
claim/start/complete fences cannot be presented (``complete`` requires at
least one materialized output), so the run is created **zero-child** with
the same evidence. A zero-child run derives ``running`` forever (its
status is derived from children and ``total==0`` → ``running``), so the
run is then **closed succeeded** through the kernel ``core.run.close``
command: terminal status, ``finished_at`` (the legacy completion time),
and the ``core.run.closed`` event with its own receipt. Media relations
(``derived_from``) are wired when both output and input media exist.

Both paths are fully receipted and deterministic: the receipt key
``v10-migrate:run:{slug}:{run_id}`` gates the run fan-out and derived
suffix keys gate claim/start/complete; the zero-child close uses the
dedicated key ``v10-migrate:run-close:{slug}:{run_id}``. Reruns replay
with zero new rows. Cross-project run-id copies collide globally: the
second occurrence derives a deterministic ULID and a ``:id2`` key.

Dry-run by default; ``--apply`` mutates.

Usage::

    python3 scripts/migrations/v10/migrate_generations.py --apply [--project SLUG]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    derive_ulid,
    iso_max,
    load_json,
    run_key,
)

MEDIA_MAP_PATH = Path(__file__).resolve().parent / "media_map.json"
REPORT_PATH = Path(__file__).resolve().parent / "migration_report.json"


def set_media_map_path(path: Path) -> None:
    """Override the media_map location (scratch-root smoke tests)."""
    global MEDIA_MAP_PATH
    MEDIA_MAP_PATH = path


def set_report_path(path: Path) -> None:
    """Override the migration_report location (scratch-root smoke tests)."""
    global REPORT_PATH
    REPORT_PATH = path


def _evidence(run: dict, run_json_path: str) -> list[dict]:
    return [
        {
            "kind": "observation",
            "summary": f"legacy run migrated from {run_json_path}",
            "data": {
                "legacy_path": run_json_path,
                "status": run.get("status", ""),
                "argv": run.get("argv", []),
            },
        }
    ]


def _build_outputs(
    run: dict,
    *,
    root: Path,
    files_map: dict[str, dict],
    input_media_ids: list[str],
) -> list[dict]:
    """Prepared outputs for the complete command (imported artifacts)."""
    from astrid.core.io.media_import import PreparedMedia

    outputs: list[dict] = []
    importable = [
        ref for ref in run.get("outputs", []) if ref["resolved"] and ref["resolved"] in files_map
    ]
    for index, ref in enumerate(importable):
        entry = files_map[ref["resolved"]]
        source = root / ref["resolved"]
        prepared = PreparedMedia(
            source_path=source,
            digest=entry["digest"],
            byte_size=entry["byte_size"],
            media_kind=entry["media_kind"],
            mime_type=entry["mime_type"],
            rel_path=source.name,
        )
        output: dict = {
            "ordinal": index,
            "is_primary": index == 0,
            "role": "result" if index == 0 else "output",
            "label": source.name,
            "path": ref["raw"],
            "prepared": prepared,
            "media_id": entry["media_id"],
            "realm": entry["realm"],
            "locator": entry["locator"],
        }
        if index == 0 and input_media_ids:
            output["relations"] = [
                {
                    "from_media_id": entry["media_id"],
                    "to_media_id": input_id,
                    "kind": "derived_from",
                    "ordinal": ordinal,
                }
                for ordinal, input_id in enumerate(input_media_ids)
            ]
        outputs.append(output)
    return outputs


def _fence_path(
    client,
    *,
    project_id: str,
    slug: str,
    run: dict,
    run_json: dict,
    run_json_path: str,
    root: Path,
    files_map: dict[str, dict],
) -> dict:
    """Claim/start/complete the child task (system actor)."""
    from astrid.core.store.uow import UnitOfWork

    key = run_key(slug, run["run_id"])
    created_at = str(run_json.get("created_at") or "")
    started_at = _started_at(run_json, run, created_at)
    finished_at = _finished_at(run_json, run, started_at)

    input_media_ids = [
        files_map[ref["resolved"]]["media_id"]
        for ref in run.get("inputs", [])
        if ref["resolved"] and ref["resolved"] in files_map
    ]
    outputs = _build_outputs(
        run, root=root, files_map=files_map, input_media_ids=input_media_ids
    )

    # 1. Fan-out: one run + one child task + the evidence item.
    task_id = derive_ulid(f"{key}:task")
    child = {
        "capability": str(run.get("tool_id") or "legacy.tool"),
        "spec": {
            "tool_id": run.get("tool_id"),
            "run_id": run["run_id"],
            "argv": run.get("argv", []),
        },
        "input_manifest": [],
        "task_id": task_id,
        "max_attempts": 1,
    }
    evidence = _evidence(run, run_json_path)
    title = f"{run.get('tool_id') or 'legacy.tool'} ({run['run_id']})"

    def create_fanout(uow, key_override: str, run_id_override: str, task_id_override: str):
        return client.app.runs.create(
            uow,
            project_id=project_id,
            children=[dict(child, task_id=task_id_override)],
            evidence=evidence,
            idempotency_key=key_override,
            actor_kind="system",
            kind="tool_id",
            title=title,
            input=dict(run_json),
            created_at=created_at or None,
            run_id=run_id_override,
        )

    from astrid.core.repositories.runs import RunAlreadyExistsError

    try:
        fanout = UnitOfWork(client.app.writer).run(
            lambda uow: create_fanout(uow, key, run["run_id"], task_id)
        )
    except RunAlreadyExistsError:
        # Cross-project run-id copy: deterministic derived identity.
        derived_id = derive_ulid(f"run-id:{slug}:{run['run_id']}")
        derived_key = f"{key}:id2"
        fanout = UnitOfWork(client.app.writer).run(
            lambda uow: create_fanout(
                uow, derived_key, derived_id, derive_ulid(f"{derived_key}:task")
            )
        )
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"run {run['run_id']}: fan-out failed: {exc}")

    run_task_id = fanout.task_ids[0]

    # 2. Claim (FIFO: the fresh child is the only eligible task).
    claim_key = f"{key}:claim"
    try:
        claim = UnitOfWork(client.app.writer).run(
            lambda uow: client.app.tasks.claim(
                uow,
                project_id=project_id,
                idempotency_key=claim_key,
                actor_kind="system",
                executor_id="v10-migration",
                now=started_at,
            )
        )
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"run {run['run_id']}: claim failed: {exc}")
    if claim is None or claim.task.id != run_task_id:
        raise SystemExit(
            f"run {run['run_id']}: claim did not select migrated child "
            f"(got {getattr(claim, 'task', None)})"
        )
    attempt = claim.attempt

    # 3. Start (claimed -> running).
    try:
        UnitOfWork(client.app.writer).run(
            lambda uow: client.app.tasks.start(
                uow,
                project_id=project_id,
                task_id=run_task_id,
                attempt_id=attempt.id,
                expected_status_version=attempt.status_version,
                idempotency_key=f"{key}:start",
                actor_kind="system",
                lease_id=attempt.lease_id,
                now=started_at,
            )
        )
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"run {run['run_id']}: start failed: {exc}")

    # 4. Complete (running -> succeeded) with the imported artifacts.
    expected_version = attempt.status_version + 1
    try:
        UnitOfWork(client.app.writer).run(
            lambda uow: client.app.tasks.complete(
                uow,
                project_id=project_id,
                task_id=run_task_id,
                attempt_id=attempt.id,
                lease_id=attempt.lease_id,
                expected_status_version=expected_version,
                idempotency_key=f"{key}:complete",
                outputs=outputs,
                media_repo=client.app.media,
                actor_kind="system",
                now=finished_at,
            )
        )
    except Exception as exc:  # noqa: BLE001
        # Fenced terminal fallback: record the failure honestly instead of
        # leaving the attempt running.
        complete_error = str(exc)[:500]
        try:
            UnitOfWork(client.app.writer).run(
                lambda uow: client.app.tasks.fail(
                    uow,
                    project_id=project_id,
                    task_id=run_task_id,
                    attempt_id=attempt.id,
                    lease_id=attempt.lease_id,
                    expected_status_version=expected_version,
                    idempotency_key=f"{key}:fail",
                    actor_kind="system",
                    error={
                        "kind": "migration_complete_failed",
                        "message": complete_error,
                    },
                    now=finished_at,
                )
            )
        except Exception as fail_exc:  # noqa: BLE001
            raise SystemExit(
                f"run {run['run_id']}: complete failed ({complete_error}) and "
                f"fail also failed ({fail_exc})"
            )
        return {
            "run_id": run["run_id"],
            "path": "fence-complete-failed",
            "task_id": run_task_id,
            "outputs": len(outputs),
        }
    return {
        "run_id": run["run_id"],
        "path": "fence",
        "task_id": run_task_id,
        "outputs": len(outputs),
    }


def _zero_child_path(
    client,
    *,
    project_id: str,
    slug: str,
    run: dict,
    run_json: dict,
    run_json_path: str,
    files_map: dict[str, dict],
) -> dict:
    """Zero-child run + evidence (no materializable outputs)."""
    from astrid.core.repositories.runs import RunAlreadyExistsError
    from astrid.core.store.uow import UnitOfWork

    key = run_key(slug, run["run_id"])
    created_at = str(run_json.get("created_at") or "")
    close_key = f"v10-migrate:run-close:{slug}:{run['run_id']}"
    run_id = run["run_id"]
    try:
        UnitOfWork(client.app.writer).run(
            lambda uow: client.app.runs.create(
                uow,
                project_id=project_id,
                children=[],
                evidence=_evidence(run, run_json_path),
                idempotency_key=key,
                actor_kind="system",
                kind="tool_id",
                title=f"{run.get('tool_id') or 'legacy.tool'} ({run['run_id']})",
                input=dict(run_json),
                created_at=created_at or None,
                run_id=run_id,
            )
        )
    except RunAlreadyExistsError:
        # Cross-project run-id copy: deterministic derived identity (same
        # convention as the fenced path).
        run_id = derive_ulid(f"run-id:{slug}:{run['run_id']}")
        key = f"{key}:id2"
        close_key = f"{close_key}:id2"
        try:
            UnitOfWork(client.app.writer).run(
                lambda uow: client.app.runs.create(
                    uow,
                    project_id=project_id,
                    children=[],
                    evidence=_evidence(run, run_json_path),
                    idempotency_key=key,
                    actor_kind="system",
                    kind="tool_id",
                    title=f"{run.get('tool_id') or 'legacy.tool'} ({run['run_id']})",
                    input=dict(run_json),
                    created_at=created_at or None,
                    run_id=run_id,
                )
            )
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(f"run {run['run_id']}: zero-child run failed: {exc}")
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"run {run['run_id']}: zero-child run failed: {exc}")

    # The zero-child run derives ``running`` forever (``total==0``), so no
    # child transition can ever terminalize it: close it succeeded under a
    # dedicated receipt key. The close is fully receipted and idempotent —
    # a rerun replays both the fan-out (via ``key``) and this close (via
    # ``close_key``) with zero new rows.
    started_at = _started_at(run_json, run, created_at)
    finished_at = _finished_at(run_json, run, started_at)
    try:
        UnitOfWork(client.app.writer).run(
            lambda uow: client.app.runs.close(
                uow,
                project_id=project_id,
                run_id=run_id,
                outcome="succeeded",
                idempotency_key=close_key,
                actor_kind="system",
                now=finished_at,
            )
        )
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"run {run['run_id']}: zero-child close failed: {exc}")

    # Media relations (derived_from) when both sides exist.
    output_ids = [
        files_map[ref["resolved"]]["media_id"]
        for ref in run.get("outputs", [])
        if ref["resolved"] and ref["resolved"] in files_map
    ]
    input_ids = [
        files_map[ref["resolved"]]["media_id"]
        for ref in run.get("inputs", [])
        if ref["resolved"] and ref["resolved"] in files_map
    ]
    if output_ids and input_ids:
        relations = [
            {
                "from_media_id": output_ids[0],
                "to_media_id": input_id,
                "kind": "derived_from",
                "ordinal": ordinal,
            }
            for ordinal, input_id in enumerate(input_ids)
        ]
        try:
            client.media.relate(
                slug,
                relations=relations,
                idempotency_key=f"{key}:relate",
            )
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(f"run {run['run_id']}: relate failed: {exc}")
    return {"run_id": run["run_id"], "path": "zero-child", "outputs": len(output_ids)}


def _started_at(run_json: dict, run: dict, created_at: str) -> str:
    result = run_json.get("result")
    started = ""
    if isinstance(result, dict):
        started = str(result.get("started_at") or "")
    if not started:
        started = created_at or str(run.get("updated_at") or "")
    if created_at:
        started = iso_max(started, created_at)
    return started


def _finished_at(run_json: dict, run: dict, started_at: str) -> str:
    result = run_json.get("result")
    finished = ""
    if isinstance(result, dict):
        finished = str(result.get("completed_at") or "")
    if not finished:
        finished = str(run.get("updated_at") or "") or started_at
    return iso_max(finished, started_at)


def migrate_generations(
    inventory: dict,
    apply: bool,
    project_filter: set[str],
    root: Path,
) -> list[dict]:
    from astrid.sdk.client import AstridClient

    if MEDIA_MAP_PATH.is_file():
        media_map = json.loads(MEDIA_MAP_PATH.read_text(encoding="utf-8"))
        projects_map = media_map.get("projects", {})
    else:
        projects_map = {}

    results: list[dict] = []
    with AstridClient.open(projects_root=root) as client:
        for project in inventory["projects"]:
            slug = project["slug"]
            if project_filter and slug not in project_filter:
                continue
            shown = client.projects.show(slug)
            if shown.data is None:
                raise SystemExit(f"generations: project {slug} missing from kernel DB")
            project_id = shown.data["id"]
            files_map = projects_map.get(slug, {}).get("files", {})

            for run in project["runs"]:
                if not run["eligible"]:
                    continue
                run_json_path = root / run["run_json_path"]
                run_json = load_json(run_json_path)
                result_path = (root / run["dir"]) / "result.json"
                result_json = load_json(result_path) if result_path.is_file() else None
                run["result"] = result_json if isinstance(result_json, dict) else None

                importable_outputs = [
                    ref
                    for ref in run.get("outputs", [])
                    if ref["resolved"] and ref["resolved"] in files_map
                ]

                if not apply:
                    results.append(
                        {
                            "run_id": run["run_id"],
                            "path": "fence" if importable_outputs else "zero-child",
                            "outputs": len(importable_outputs),
                            "action": "plan",
                        }
                    )
                    continue

                if importable_outputs:
                    outcome = _fence_path(
                        client,
                        project_id=project_id,
                        slug=slug,
                        run=run,
                        run_json=run_json,
                        run_json_path=run["run_json_path"],
                        root=root,
                        files_map=files_map,
                    )
                else:
                    outcome = _zero_child_path(
                        client,
                        project_id=project_id,
                        slug=slug,
                        run=run,
                        run_json=run_json,
                        run_json_path=run["run_json_path"],
                        files_map=files_map,
                    )
                outcome["action"] = "created"
                results.append(outcome)

    if apply:
        write_report(results)
    return results


def write_report(results: list[dict]) -> None:
    from _common import write_json

    write_json(REPORT_PATH, {"runs": results})


def main() -> int:
    parser = argparse.ArgumentParser(description="v10: migrate eligible runs")
    parser.add_argument("--root", default=None, help="projects root")
    parser.add_argument(
        "--inventory",
        default=str(Path(__file__).resolve().parent / "inventory.json"),
    )
    parser.add_argument("--apply", action="store_true", help="mutate the kernel DB")
    parser.add_argument(
        "--project", action="append", default=[], help="restrict to one slug"
    )
    parser.add_argument(
        "--media-map",
        default=str(MEDIA_MAP_PATH),
        help="media_map.json path (default <scriptdir>/media_map.json)",
    )
    parser.add_argument(
        "--report",
        default=str(REPORT_PATH),
        help="migration_report.json path (default <scriptdir>/migration_report.json)",
    )
    args = parser.parse_args()

    set_media_map_path(Path(args.media_map))
    set_report_path(Path(args.report))

    inventory_path = Path(args.inventory)
    if not inventory_path.is_file():
        print(
            f"migrate_generations: inventory not found: {inventory_path}",
            file=sys.stderr,
        )
        return 2
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    root = Path(args.root) if args.root else Path(__file__).resolve().parents[3] / "projects"
    results = migrate_generations(
        inventory, apply=args.apply, project_filter=set(args.project), root=root
    )
    paths: dict[str, int] = {}
    for row in results:
        paths[row["path"]] = paths.get(row["path"], 0) + 1
    print(f"migrate_generations: {'applied' if args.apply else 'dry-run'} {len(results)} runs")
    print("migrate_generations: paths " + ", ".join(f"{k}={v}" for k, v in sorted(paths.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
