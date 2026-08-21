"""Migrate referenced legacy media into the kernel media repository.

For every media file referenced by an inventoried timeline or eligible
run::

    prepared = prepare_media_file(path)          # hashing outside any txn
    media_id = derive_stable_id(core.media.import, project_id, key, 0)
    UnitOfWork(writer).run(
        lambda uow: media_repo.import_prepared(
            uow, project_id=..., prepared=prepared,
            idempotency_key=key, media_id=media_id, realm=realm,
            actor_kind="system"))

with ``key = v10-migrate:media:{slug}:{sha256}``. Dedupe is the
repository's project-scoped byte dedupe: identical bytes under the same
key derive the same media id and replay with zero new rows.

Non-media files (run.json / plan.json / tool-run.json / manifest.json and
anything without a media extension) and unresolvable/missing references
are skipped. Results are persisted to ``media_map.json`` (path -> media
id + prepared facts) so later phases reuse imported media without
re-hashing.

Dry-run by default; ``--apply`` mutates. The legacy tree is never
written — ``managed_local`` copies bytes into the managed media tree
under ``projects/.astrid/``, ``external_local`` references in place.

Usage::

    python3 scripts/migrations/v10/migrate_media.py --apply [--project SLUG]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import is_media_file, media_key, write_json  # noqa: E402

MEDIA_MAP_PATH = Path(__file__).resolve().parent / "media_map.json"


def set_media_map_path(path: Path) -> None:
    """Override the media_map location (scratch-root smoke tests)."""
    global MEDIA_MAP_PATH
    MEDIA_MAP_PATH = path


def load_media_map() -> dict:
    if MEDIA_MAP_PATH.is_file():
        return json.loads(MEDIA_MAP_PATH.read_text(encoding="utf-8"))
    return {"schema_version": 1, "projects": {}}


def save_media_map(media_map: dict) -> None:
    write_json(MEDIA_MAP_PATH, media_map)


def migrate_media(
    inventory: dict,
    apply: bool,
    project_filter: set[str],
    root: Path,
    realm: str,
) -> dict:
    from astrid.core.io.media_import import managed_media_path, prepare_media_file
    from astrid.core.repositories.media import CORE_MEDIA_IMPORT_COMMAND_KIND
    from astrid.core.store.uow import UnitOfWork
    from astrid.sdk.client import AstridClient
    from astrid.sdk.contracts import derive_stable_id

    media_map = load_media_map()
    projects_map = media_map.setdefault("projects", {})
    summary = {"imported": 0, "skipped_non_media": 0, "skipped_missing": 0, "replayed": 0}

    with AstridClient.open(projects_root=root) as client:
        for project in inventory["projects"]:
            slug = project["slug"]
            if project_filter and slug not in project_filter:
                continue
            shown = client.projects.show(slug)
            if shown.data is None:
                raise SystemExit(f"media: project {slug} missing from kernel DB")
            project_id = shown.data["id"]
            project_map = projects_map.setdefault(slug, {"files": {}})
            files_map = project_map.setdefault("files", {})

            for entry in project["media"]["referenced"]:
                path = root / entry["path"]
                if not is_media_file(path):
                    summary["skipped_non_media"] += 1
                    continue
                if not path.is_file():
                    summary["skipped_missing"] += 1
                    continue
                if entry["path"] in files_map:
                    summary["replayed"] += 1
                    continue
                if not apply:
                    summary["imported"] += 1
                    continue

                prepared = prepare_media_file(path)
                key = media_key(slug, prepared.digest)
                media_id = derive_stable_id(
                    command_kind=CORE_MEDIA_IMPORT_COMMAND_KIND,
                    scope=project_id,
                    idempotency_key=key,
                    ordinal=0,
                )
                try:
                    UnitOfWork(client.app.writer).run(
                        lambda uow: client.app.media.import_prepared(
                            uow,
                            project_id=project_id,
                            prepared=prepared,
                            idempotency_key=key,
                            media_id=media_id,
                            realm=realm,
                            actor_kind="system",
                        )
                    )
                except Exception as exc:  # noqa: BLE001 - surface typed errors
                    raise SystemExit(f"media {entry['path']}: import failed: {exc}")
                files_map[entry["path"]] = {
                    "media_id": media_id,
                    "digest": prepared.digest,
                    "byte_size": prepared.byte_size,
                    "media_kind": prepared.media_kind,
                    "mime_type": prepared.mime_type,
                    "rel_path": prepared.rel_path,
                    "realm": realm,
                    "locator": str(
                        managed_media_path(root, prepared.digest)
                        if realm == "managed_local"
                        else path
                    ),
                }
                summary["imported"] += 1

    if apply:
        save_media_map(media_map)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="v10: migrate referenced media")
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
        "--realm",
        default="managed_local",
        choices=["managed_local", "external_local"],
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
        print(f"migrate_media: inventory not found: {inventory_path}", file=sys.stderr)
        return 2
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    root = Path(args.root) if args.root else Path(__file__).resolve().parents[3] / "projects"
    summary = migrate_media(
        inventory,
        apply=args.apply,
        project_filter=set(args.project),
        root=root,
        realm=args.realm,
    )
    print(
        "migrate_media: "
        + ", ".join(f"{key}={value}" for key, value in sorted(summary.items()))
        + f" (realm={args.realm}, {'apply' if args.apply else 'dry-run'})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
