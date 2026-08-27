"""Migrate legacy timelines into the kernel timeline repository.

Every inventoried timeline becomes one ``TimelineRepository.create``:

- **containers** (``timelines/<ulid>/assembly.json``): config =
  assembly.json, registry = registry.json (rewritten locators), the
  directory ULID is preserved as ``timeline_ulid`` (and ``timeline_id``),
  ``assembly.jsonl`` recorded as provenance inside ``config._v10_migration``
  (NOT replayed as events);
- **legacy docs** (``hype.timeline.json`` + ``hype.assets.json`` pairs,
  ``timeline.json`` + ``assets.json`` docs): config = the timeline
  document, registry = ``{"assets": <assets file>}``; no legacy ULID exists
  so ``timeline_ulid`` is derived deterministically from the receipt key.

Registry entries for referenced files receive an explicit ``media_id`` when
the file was imported by ``migrate_media`` (media_map lookup).  The original
``file``/source locator is retained for compatibility; it is never replaced
with a media identity.  Unresolvable/remote references keep their original
value and do not receive a ``media_id``.

``set_default`` is honored when the container's ``display.json`` marks the
timeline default or ``project.json.default_timeline_id`` names the ULID —
written through the repository (SD1), never via caller settings.

Dry-run by default; ``--apply`` mutates.

Usage::

    python3 scripts/migrations/v10/migrate_timelines.py --apply [--project SLUG]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import derive_ulid, load_json, timeline_key  # noqa: E402

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MEDIA_MAP_PATH = Path(__file__).resolve().parent / "media_map.json"


def set_media_map_path(path: Path) -> None:
    """Override the media_map location (scratch-root smoke tests)."""
    global MEDIA_MAP_PATH
    MEDIA_MAP_PATH = path


def _path_hash(config_path: str) -> str:
    return hashlib.sha256(config_path.encode("utf-8")).hexdigest()[:16]


def build_registry(
    timeline: dict,
    *,
    root: Path,
    files_map: dict[str, dict],
) -> dict:
    """Build the kernel registry with explicit managed-media identities.

    ``file`` is a locator/legacy alias, while ``media_id`` is the
    project-scoped managed-media identity consumed by the repository bridge.
    Keeping the source locator avoids breaking older consumers during the
    v10 transition, but importantly never aliases a UUID into ``file``.
    """
    assets: dict[str, dict] = {}
    if timeline["kind"] == "container":
        if timeline["registry_path"]:
            registry_path = root / timeline["registry_path"]
            loaded = load_json(registry_path) if registry_path.is_file() else {}
            if isinstance(loaded, dict) and isinstance(loaded.get("assets"), dict):
                assets = dict(loaded["assets"])
    else:
        assets_path = timeline.get("assets_path")
        if assets_path:
            path = root / assets_path
            loaded = load_json(path) if path.is_file() else {}
            if isinstance(loaded, dict) and isinstance(loaded.get("assets"), dict):
                assets = dict(loaded["assets"])

    # Add identities: referenced-file -> imported media id.  Do not overwrite
    # the source locator: bridge consumers that still understand ``file`` can
    # continue resolving it, while v10 consumers use the explicit identity.
    for ref in timeline["media_refs"]:
        if not ref["resolved"]:
            continue
        entry = files_map.get(ref["resolved"])
        if not entry:
            continue
        asset = assets.get(ref["key"])
        if isinstance(asset, dict):
            asset["media_id"] = entry["media_id"]
    return {"assets": assets}


def build_config(timeline: dict, *, root: Path) -> dict:
    """The kernel timeline config (loose editor document) + provenance."""
    config = load_json(root / timeline["config_path"])
    if not isinstance(config, dict):
        config = {}
    if timeline["kind"] == "container" and timeline.get("provenance_path"):
        config = dict(config)
        config["_v10_migration"] = {
            "provenance": timeline["provenance_path"],
            "registry": timeline["registry_path"],
            "display": timeline["display_path"],
            "container_ulid": timeline["ulid"],
            "note": "assembly.jsonl is provenance, not replayed",
        }
    return config


def migrate_timelines(
    inventory: dict,
    apply: bool,
    project_filter: set[str],
    root: Path,
) -> list[dict]:
    from astrid.core.receipts.service import ReceiptService
    from astrid.core.store.uow import UnitOfWork
    from astrid.packs.timeline.repository import (
        TimelineAlreadyExistsError,
        TimelineSlugConflictError,
        TimelineUlidConflictError,
    )
    from astrid.sdk.client import AstridClient

    receipts = ReceiptService()

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
                raise SystemExit(f"timelines: project {slug} missing from kernel DB")
            project_id = shown.data["id"]
            files_map = projects_map.get(slug, {}).get("files", {})
            project_json = project.get("project_json") or {}
            default_timeline_id = str(project_json.get("default_timeline_id") or "")

            for timeline in project["timelines"]:
                key = timeline_key(
                    slug,
                    timeline["ulid"] or _path_hash(timeline["config_path"]),
                )
                timeline_id = timeline["ulid"] or derive_ulid(key)
                timeline_ulid = timeline_id
                config = build_config(timeline, root=root)
                registry = build_registry(timeline, root=root, files_map=files_map)

                set_default = bool(
                    timeline["is_default"]
                    or (timeline["ulid"] and default_timeline_id == timeline["ulid"])
                )

                if not apply:
                    results.append(
                        {
                            "slug": slug,
                            "timeline_id": timeline_id,
                            "timeline_ulid": timeline_ulid,
                            "name": timeline["name"],
                            "config_slug": timeline["slug"],
                            "set_default": set_default,
                            "kind": timeline["kind"],
                            "action": "plan",
                            "key": key,
                        }
                    )
                    continue

                def _committed(use_key: str) -> bool:
                    with client.app.writer.read_only_connection() as conn:
                        return (
                            receipts.lookup_committed(
                                conn,
                                project_id=project_id,
                                idempotency_key=use_key,
                            )
                            is not None
                        )

                def _suffixed_slug() -> str:
                    suffix = timeline_ulid[:8].lower()
                    suffixed = f"{timeline['slug'][:40]}-{suffix}"
                    if not _SLUG_RE.fullmatch(suffixed):
                        suffixed = f"tl-{suffix}"
                    return suffixed

                def create_timeline(use_slug: str, use_key: str):
                    return UnitOfWork(client.app.writer).run(
                        lambda uow: client.app.timelines.create(
                            uow,
                            project_id=project_id,
                            slug=use_slug,
                            name=timeline["name"],
                            config=config,
                            registry=registry,
                            idempotency_key=use_key,
                            actor_kind="system",
                            timeline_id=timeline_id,
                            timeline_ulid=timeline_ulid,
                            set_default=set_default,
                        )
                    )

                def create_timeline_with_ulid(
                    use_ulid: str, use_slug: str, use_key: str
                ):
                    return UnitOfWork(client.app.writer).run(
                        lambda uow: client.app.timelines.create(
                            uow,
                            project_id=project_id,
                            slug=use_slug,
                            name=timeline["name"],
                            config=config,
                            registry=registry,
                            idempotency_key=use_key,
                            actor_kind="system",
                            timeline_id=use_ulid,
                            timeline_ulid=use_ulid,
                            set_default=set_default,
                        )
                    )

                if _committed(key):
                    action = "replay"
                else:
                    try:
                        create_timeline(timeline["slug"], key)
                        action = "created"
                    except TimelineSlugConflictError:
                        # Deterministic suffix + suffixed key: the original
                        # slug is taken by an earlier-created legacy doc.
                        suffixed_slug = _suffixed_slug()
                        s2 = f"{key}:slug2"
                        if _committed(s2):
                            action = "replay"
                        else:
                            create_timeline(suffixed_slug, s2)
                            action = "created"
                    except TimelineAlreadyExistsError:
                        # Same ULID appears in two legacy locations (e.g. a
                        # container and a copied run-level doc): derive a
                        # deterministic alternate ULID + suffixed key, and
                        # tolerate a taken slug on the derived identity too.
                        derived_ulid = derive_ulid(
                            f"timeline-ulid:{slug}:{timeline_ulid}"
                        )
                        d2 = f"{key}:id2"
                        if _committed(d2):
                            action = "replay"
                        else:
                            try:
                                create_timeline_with_ulid(
                                    derived_ulid, timeline["slug"], d2
                                )
                                action = "created"
                            except TimelineSlugConflictError:
                                create_timeline_with_ulid(
                                    derived_ulid, _suffixed_slug(), f"{d2}:slug2"
                                )
                                action = "created"
                    except TimelineUlidConflictError as exc:
                        raise SystemExit(
                            f"timeline {timeline['dir']}: ULID alias conflict: {exc}"
                        )
                    except Exception as exc:  # noqa: BLE001 - typed conflicts surface
                        raise SystemExit(
                            f"timeline {timeline['dir']}: create failed: {exc}"
                        )
                results.append(
                    {
                        "slug": slug,
                        "timeline_id": timeline_id,
                        "timeline_ulid": timeline_ulid,
                        "name": timeline["name"],
                        "config_slug": timeline["slug"],
                        "set_default": set_default,
                        "kind": timeline["kind"],
                        "action": action,
                        "key": key,
                    }
                )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="v10: migrate legacy timelines")
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
    args = parser.parse_args()

    set_media_map_path(Path(args.media_map))

    inventory_path = Path(args.inventory)
    if not inventory_path.is_file():
        print(f"migrate_timelines: inventory not found: {inventory_path}", file=sys.stderr)
        return 2
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    root = Path(args.root) if args.root else Path(__file__).resolve().parents[3] / "projects"
    results = migrate_timelines(
        inventory, apply=args.apply, project_filter=set(args.project), root=root
    )
    for row in results:
        print(
            f"timeline {row['slug']}/{row['timeline_ulid']}: {row['action']} "
            f"(kind={row['kind']}, slug={row['config_slug']}, "
            f"set_default={row['set_default']})"
        )
    print(
        f"migrate_timelines: {'applied' if args.apply else 'dry-run'} "
        f"{len(results)} timelines"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
