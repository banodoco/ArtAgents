"""Inventory the legacy tree under ``projects/`` for the v10 migration.

Read-only walk. Emits ``inventory.json`` (deterministic ordering) covering:

- projects (skipping ``agentic-*`` test projects),
- timeline containers (``timelines/<ulid>/assembly.json``),
- legacy timeline docs (``timeline.json`` + sibling ``assets.json``, and
  ``hype.timeline.json`` + sibling ``hype.assets.json`` pairs),
- referenced media paths (per timeline and per run),
- eligible completed run.json records (``status in {completed, success}``,
  tool_id != ``builtin.agent_probe``),
- an unreferenced-media catalog.

SHA-256 is computed for **referenced** media only (the import set); the
unreferenced catalog records size/mtime without hashing so the ~8.5 GB of
legacy bytes is never read in full.

Usage::

    python3 scripts/migrations/v10/inventory.py \
        --root /Users/peteromalley/Documents/reigh-workspace/Astrid/projects \
        [--output scripts/migrations/v10/inventory.json]

Exit 0 on success.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    is_media_file,
    json_load_optional,
    resolve_media_path,
    sha256_hex,
    slugify,
    stable_rel,
    write_json,
)

SKIPPED_DIR_NAMES = frozenset({".astrid", ".git", "node_modules", "__pycache__"})
ULID_DIR_RE = None  # set below

# The legacy ULID directory names under timelines/ (20-26 Crockford chars).
import re  # noqa: E402

_ULID_RE = re.compile(r"^[0-9A-Za-z]{20,26}$")

AGENTIC_PREFIX = "agentic-"
SKIPPED_TOOL_IDS = frozenset({"builtin.agent_probe"})
COMPLETED_STATUSES = frozenset({"completed", "success"})


def _walk_files(root: Path) -> list[Path]:
    """Every regular file under *root* in deterministic sorted order."""
    results: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in SKIPPED_DIR_NAMES for part in rel.parts):
            continue
        if path.name == ".DS_Store":
            continue
        results.append(path)
    return results


def _is_container_dir(path: Path) -> bool:
    return _ULID_RE.fullmatch(path.name) is not None


def collect_timeline_refs(
    timeline: dict[str, Any],
    *,
    project_root: Path,
    name_index: dict[str, list[Path]],
) -> list[dict[str, Any]]:
    """Resolve the media references of one timeline record (read-only).

    Container: ``registry.json`` asset ``file`` values (plus an embedded
    top-level ``assets`` object when present in assembly.json). Legacy
    docs: the ``assets`` object of the sibling assets/hype.assets file.
    """
    refs: list[dict[str, Any]] = []
    kind = timeline["kind"]
    doc_dir = project_root / timeline["dir"]
    assets: dict[str, Any] = {}

    if kind == "container":
        if timeline["registry_path"]:
            registry = json_load_optional(project_root / timeline["registry_path"])
            if registry is not None:
                assets_obj = registry.get("assets")
                assets = assets_obj if isinstance(assets_obj, dict) else {}
        assembly = json_load_optional(project_root / timeline["config_path"])
        if assembly is not None and isinstance(assembly.get("assets"), dict):
            assets.update(assembly["assets"])
    elif kind == "hype_pair":
        if timeline["assets_path"]:
            assets_path = project_root / timeline["assets_path"]
            loaded = json_load_optional(assets_path)
            if loaded is not None:
                assets_obj = loaded.get("assets")
                assets = assets_obj if isinstance(assets_obj, dict) else {}
    else:  # timeline_doc
        if timeline["assets_path"]:
            assets_path = project_root / timeline["assets_path"]
            loaded = json_load_optional(assets_path)
            if loaded is not None:
                assets_obj = loaded.get("assets")
                assets = assets_obj if isinstance(assets_obj, dict) else {}

    for key, asset in sorted(assets.items()):
        raw = ""
        if isinstance(asset, dict):
            raw = asset.get("file", "")
        elif isinstance(asset, str):
            raw = asset
        if not raw:
            continue
        resolved, note = resolve_media_path(
            raw, doc_dir=doc_dir, project_root=project_root, name_index=name_index
        )
        refs.append(
            {
                "key": key,
                "raw": raw,
                "resolved": stable_rel(resolved, project_root) if resolved else None,
                "exists": resolved is not None,
                "note": note,
            }
        )
    return refs


def collect_run_refs(
    run: dict[str, Any],
    *,
    project_root: Path,
    name_index: dict[str, list[Path]],
) -> dict[str, list[dict[str, Any]]]:
    """Resolve a run's output (artifacts) and input media references.

    Outputs come from ``run.json.artifacts.outputs`` and (fallback) the
    ``outputs/`` dir. Inputs come from ``manifest.json`` /
    ``result.json`` ordered artifact paths plus the ``inputs/`` dir.
    """
    run_dir = project_root / run["dir"]
    outputs: list[dict[str, Any]] = []
    inputs: list[dict[str, Any]] = []

    run_json = json_load_optional(run_dir / "run.json") or {}
    artifacts = run_json.get("artifacts")
    if isinstance(artifacts, dict):
        out_list = artifacts.get("outputs")
        if isinstance(out_list, list):
            for entry in out_list:
                if isinstance(entry, dict) and entry.get("path"):
                    outputs.append({"raw": str(entry["path"]), "source": "artifacts"})
        in_list = artifacts.get("inputs")
        if isinstance(in_list, list):
            for entry in in_list:
                if isinstance(entry, dict) and entry.get("path"):
                    inputs.append({"raw": str(entry["path"]), "source": "artifacts"})

    manifest = json_load_optional(run_dir / "manifest.json") or {}
    manifest_inputs = manifest.get("inputs")
    if isinstance(manifest_inputs, dict):
        for entry in manifest_inputs.get("ordered_artifacts", []):
            if isinstance(entry, dict) and entry.get("path"):
                inputs.append({"raw": str(entry["path"]), "source": "manifest"})

    result = json_load_optional(run_dir / "result.json") or {}
    for entry in result.get("outputs", []):
        if isinstance(entry, dict) and entry.get("path"):
            outputs.append({"raw": str(entry["path"]), "source": "result"})
    for entry in result.get("ordered_inputs", []):
        if isinstance(entry, dict) and entry.get("path"):
            inputs.append({"raw": str(entry["path"]), "source": "result"})

    # Directory fallbacks: media files physically present under the run dir.
    for subdir, target in (("outputs", outputs), ("inputs", inputs)):
        base = run_dir / subdir
        if base.is_dir():
            for path in sorted(base.rglob("*")):
                if path.is_file() and is_media_file(path):
                    target.append(
                        {
                            "raw": path.relative_to(run_dir).as_posix(),
                            "source": subdir + "-dir",
                        }
                    )

    def resolve_all(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        resolved: list[dict[str, Any]] = []
        for entry in entries:
            resolved_path, note = resolve_media_path(
                entry["raw"],
                doc_dir=run_dir,
                project_root=project_root,
                name_index=name_index,
            )
            resolved.append(
                {
                    "raw": entry["raw"],
                    "source": entry["source"],
                    "resolved": (
                        stable_rel(resolved_path, project_root)
                        if resolved_path
                        else None
                    ),
                    "exists": resolved_path is not None,
                    "note": note,
                }
            )
        return resolved

    # Dedupe by (source, raw) preserving first-seen order.
    def dedupe(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str]] = set()
        result: list[dict[str, Any]] = []
        for entry in entries:
            key = (entry["source"], entry["raw"])
            if key in seen:
                continue
            seen.add(key)
            result.append(entry)
        return result

    return {
        "outputs": resolve_all(dedupe(outputs)),
        "inputs": resolve_all(dedupe(inputs)),
    }


def discover_timelines(
    project_dir: Path,
    *,
    project_root: Path,
    name_index: dict[str, list[Path]],
) -> list[dict[str, Any]]:
    """Discover timeline containers + legacy docs for one project (sorted)."""
    timelines: list[dict[str, Any]] = []

    # 1. Containers: timelines/<ULID>/assembly.json
    timelines_dir = project_dir / "timelines"
    if timelines_dir.is_dir():
        for container in sorted(
            path for path in timelines_dir.iterdir() if path.is_dir()
        ):
            if not _is_container_dir(container):
                continue
            assembly = container / "assembly.json"
            if not assembly.is_file():
                continue
            display = json_load_optional(container / "display.json") or {}
            registry = container / "registry.json"
            display_slug = str(display.get("slug") or "").strip()
            slug = slugify(display_slug, fallback=slugify(container.name))
            record = {
                "kind": "container",
                "dir": stable_rel(container, project_root),
                "ulid": container.name,
                "slug": slug,
                "name": str(display.get("name") or container.name),
                "is_default": bool(display.get("is_default", False)),
                "config_path": stable_rel(assembly, project_root),
                "registry_path": (
                    stable_rel(registry, project_root) if registry.is_file() else None
                ),
                "display_path": (
                    stable_rel(container / "display.json", project_root)
                    if display
                    else None
                ),
                "provenance_path": (
                    stable_rel(container / "assembly.jsonl", project_root)
                    if (container / "assembly.jsonl").is_file()
                    else None
                ),
            }
            record["media_refs"] = collect_timeline_refs(
                record, project_root=project_root, name_index=name_index
            )
            timelines.append(record)

    # 2. Legacy docs: hype.timeline.json + hype.assets.json pairs, and
    #    timeline.json + assets.json docs, anywhere under the project
    #    (excluding .astrid and container dirs).
    container_dirs: set[Path] = set()
    if timelines_dir.is_dir():
        container_dirs = {
            path
            for path in timelines_dir.iterdir()
            if path.is_dir() and _is_container_dir(path)
        }
    legacy: dict[Path, dict[str, Any]] = {}

    for path in sorted(project_dir.rglob("hype.timeline.json")):
        if any(
            part in SKIPPED_DIR_NAMES for part in path.relative_to(project_dir).parts
        ):
            continue
        doc_dir = path.parent
        if doc_dir in container_dirs:
            continue
        assets = doc_dir / "hype.assets.json"
        legacy[doc_dir] = {
            "kind": "hype_pair",
            "config_path": stable_rel(path, project_root),
            "assets_path": (
                stable_rel(assets, project_root) if assets.is_file() else None
            ),
        }

    for path in sorted(project_dir.rglob("timeline.json")):
        if any(
            part in SKIPPED_DIR_NAMES for part in path.relative_to(project_dir).parts
        ):
            continue
        doc_dir = path.parent
        if doc_dir in container_dirs:
            continue
        assets = doc_dir / "assets.json"
        legacy[doc_dir] = {
            "kind": "timeline_doc",
            "config_path": stable_rel(path, project_root),
            "assets_path": (
                stable_rel(assets, project_root) if assets.is_file() else None
            ),
        }

    for doc_dir, base in sorted(legacy.items()):
        config_path = project_root / base["config_path"]
        config = json_load_optional(config_path) or {}
        record = {
            "kind": base["kind"],
            "dir": stable_rel(doc_dir, project_root),
            "ulid": None,
            "slug": slugify(doc_dir.name),
            "name": doc_dir.name,
            "is_default": False,
            "config_path": base["config_path"],
            "registry_path": None,
            "assets_path": base["assets_path"],
            "provenance_path": None,
        }
        record["media_refs"] = collect_timeline_refs(
            record, project_root=project_root, name_index=name_index
        )
        timelines.append(record)

    timelines.sort(key=lambda t: (t["kind"], t["dir"]))
    return timelines


def discover_runs(
    project_dir: Path,
    *,
    project_root: Path,
    name_index: dict[str, list[Path]],
) -> list[dict[str, Any]]:
    """Discover every run.json under the project (sorted, per eligibility)."""
    runs: list[dict[str, Any]] = []
    container_dirs: set[Path] = set()
    timelines_dir = project_dir / "timelines"
    if timelines_dir.is_dir():
        container_dirs = {
            path
            for path in timelines_dir.iterdir()
            if path.is_dir() and _is_container_dir(path)
        }

    for path in sorted(project_dir.rglob("run.json")):
        if any(
            part in SKIPPED_DIR_NAMES for part in path.relative_to(project_dir).parts
        ):
            continue
        if path.parent in container_dirs:
            continue
        run_json = json_load_optional(path) or {}
        status = str(run_json.get("status") or "").strip().lower()
        tool_id = str(run_json.get("tool_id") or "").strip()
        run_id = str(run_json.get("run_id") or "").strip()
        eligible = (
            status in COMPLETED_STATUSES
            and bool(run_id)
            and tool_id not in SKIPPED_TOOL_IDS
        )
        record: dict[str, Any] = {
            "run_id": run_id,
            "dir": stable_rel(path.parent, project_root),
            "run_json_path": stable_rel(path, project_root),
            "status": status,
            "tool_id": tool_id,
            "eligible": eligible,
            "created_at": str(run_json.get("created_at") or ""),
            "updated_at": str(run_json.get("updated_at") or ""),
            "argv": run_json.get("argv") or [],
        }
        if eligible:
            refs = collect_run_refs(
                record, project_root=project_root, name_index=name_index
            )
            record["outputs"] = refs["outputs"]
            record["inputs"] = refs["inputs"]
        runs.append(record)
    runs.sort(key=lambda r: (r["dir"], r["run_id"]))
    return runs


def build_inventory(root: Path) -> dict[str, Any]:
    """Walk *root* and return the full inventory document (no writes)."""
    root = root.resolve()
    project_dirs = sorted(
        path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")
    )
    projects: list[dict[str, Any]] = []
    skipped: list[str] = []

    for project_dir in project_dirs:
        if project_dir.name.startswith(AGENTIC_PREFIX):
            skipped.append(project_dir.name)
            continue
        project_json = json_load_optional(project_dir / "project.json")
        all_files = [
            path
            for path in _walk_files(project_dir)
            if is_media_file(path)
        ]
        name_index = {}
        for path in sorted(all_files):
            name_index.setdefault(path.name, []).append(path)

        timelines = discover_timelines(
            project_dir, project_root=root, name_index=name_index
        )
        runs = discover_runs(
            project_dir, project_root=root, name_index=name_index
        )

        referenced: dict[str, dict[str, Any]] = {}
        for timeline in timelines:
            label = f"timeline:{timeline['kind']}:{timeline['dir']}"
            for ref in timeline["media_refs"]:
                if ref["resolved"]:
                    entry = referenced.setdefault(
                        ref["resolved"],
                        {"path": ref["resolved"], "size": 0, "sha256": None, "refs": []},
                    )
                    entry["refs"].append(label)
        for run in runs:
            if not run["eligible"]:
                continue
            label = f"run:{run['run_id']}"
            for group in ("outputs", "inputs"):
                for ref in run[group]:
                    if ref["resolved"]:
                        entry = referenced.setdefault(
                            ref["resolved"],
                            {
                                "path": ref["resolved"],
                                "size": 0,
                                "sha256": None,
                                "refs": [],
                            },
                        )
                        entry["refs"].append(label)

        for entry in referenced.values():
            path = root / entry["path"]
            entry["size"] = path.stat().st_size
            entry["sha256"] = sha256_hex(path)

        referenced_set = set(referenced)
        unreferenced = [
            {
                "path": stable_rel(path, root),
                "size": path.stat().st_size,
                "mtime": int(path.stat().st_mtime),
            }
            for path in sorted(all_files)
            if stable_rel(path, root) not in referenced_set
        ]

        projects.append(
            {
                "slug": project_dir.name,
                "name": str((project_json or {}).get("name") or project_dir.name),
                "path": project_dir.name,
                "project_json": project_json,
                "timelines": timelines,
                "runs": runs,
                "media": {
                    "referenced": sorted(referenced.values(), key=lambda e: e["path"]),
                    "unreferenced": unreferenced,
                },
            }
        )

    counts = _summarize(projects, skipped)
    return {
        "schema_version": 1,
        "root": str(root),
        "skipped_projects": sorted(skipped),
        "projects": projects,
        "counts": counts,
    }


def _summarize(
    projects: list[dict[str, Any]], skipped: list[str]
) -> dict[str, Any]:
    timeline_total = 0
    containers = 0
    legacy_docs = 0
    runs_total = 0
    runs_eligible = 0
    media_referenced = 0
    media_unreferenced = 0
    missing_refs = 0
    for project in projects:
        timeline_total += len(project["timelines"])
        containers += sum(
            1 for t in project["timelines"] if t["kind"] == "container"
        )
        legacy_docs += sum(
            1 for t in project["timelines"] if t["kind"] != "container"
        )
        runs_total += len(project["runs"])
        runs_eligible += sum(1 for r in project["runs"] if r["eligible"])
        media_referenced += len(project["media"]["referenced"])
        media_unreferenced += len(project["media"]["unreferenced"])
        for timeline in project["timelines"]:
            missing_refs += sum(
                1 for ref in timeline["media_refs"] if not ref["exists"]
            )
        for run in project["runs"]:
            if not run["eligible"]:
                continue
            missing_refs += sum(
                1 for group in ("outputs", "inputs") for ref in run[group]
                if not ref["exists"]
            )
    return {
        "projects": len(projects),
        "projects_skipped": len(skipped),
        "timelines": timeline_total,
        "timeline_containers": containers,
        "legacy_timeline_docs": legacy_docs,
        "runs_total": runs_total,
        "runs_eligible": runs_eligible,
        "media_referenced": media_referenced,
        "media_unreferenced": media_unreferenced,
        "media_missing_refs": missing_refs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventory the legacy Astrid tree for the v10 migration."
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[3] / "projects"),
        help="projects root (default: <repo>/projects)",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent / "inventory.json"),
        help="inventory.json output path",
    )
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"inventory: root is not a directory: {root}", file=sys.stderr)
        return 2

    inventory = build_inventory(root)
    write_json(Path(args.output), inventory)
    counts = inventory["counts"]
    print(
        "inventory: "
        + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    )
    print(f"inventory: wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
