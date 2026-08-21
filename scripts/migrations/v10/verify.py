"""Verify a completed v10 migration against the inventory (read-only).

Checks (exit 0 = all pass):

1. counts vs ``inventory.json``: projects / timelines / runs / media rows;
2. every referenced media file has a media row with a matching SHA-256 and
   a location (managed or external) whose file still exists on disk;
3. every event stream's hash chain is intact genesis -> head;
4. no forbidden (legacy/importer) tables exist in the kernel DB;
5. legacy files are still on disk (the legacy tree was read-only).

Raw SQL here is strictly read-only (event-stream enumeration, table
listing); every mutation path stays SDK/repository-only.

Usage::

    python3 scripts/migrations/v10/verify.py [--root ...] [--inventory ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

FORBIDDEN_TABLE_PREFIXES = ("migration_", "legacy_", "importer_", "import_")


def _stream_ids(client) -> list[str]:
    return client.app.writer.submit(
        lambda session: [
            str(row[0])
            for row in session.query("SELECT id FROM event_streams ORDER BY id")
        ]
    )


def _table_names(client) -> list[str]:
    return client.app.writer.submit(
        lambda session: [
            str(row[0])
            for row in session.query(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        ]
    )


def run_verification(
    inventory: dict,
    *,
    root: Path,
    media_map_path: Path,
) -> tuple[bool, dict]:
    from astrid.sdk.client import AstridClient

    media_map = (
        json.loads(media_map_path.read_text(encoding="utf-8"))
        if media_map_path.is_file()
        else {"projects": {}}
    )
    report: dict = {}

    with AstridClient.open(projects_root=root) as client:
        # 1. Counts vs inventory.
        projects = client.projects.list()
        project_rows = projects.data or []
        report["projects_expected"] = len(inventory["projects"])
        report["projects_created"] = len(project_rows)
        if report["projects_expected"] != report["projects_created"]:
            return False, {**report, "failure": "project count mismatch"}

        timelines_total = 0
        runs_total = 0
        media_rows = 0
        for project in inventory["projects"]:
            slug = project["slug"]
            shown = client.projects.show(slug)
            if shown.data is None:
                return False, {**report, "failure": f"project {slug} missing"}
            project_id = shown.data["id"]

            timelines = client.timelines.list(slug)
            timelines_total += len(timelines.data or [])
            runs = client.runs.list(project_id)
            runs_total += len(runs.data or [])
            media = client.media.list(slug)
            media_rows += len(media.data or [])

        report["timelines_expected"] = sum(
            len(p["timelines"]) for p in inventory["projects"]
        )
        report["timelines_created"] = timelines_total
        report["runs_expected"] = sum(
            1 for p in inventory["projects"] for r in p["runs"] if r["eligible"]
        )
        report["runs_created"] = runs_total
        report["media_expected"] = sum(
            len(p["media"]["referenced"]) for p in inventory["projects"]
        )
        report["media_rows"] = media_rows
        if timelines_total != report["timelines_expected"]:
            return False, {**report, "failure": "timeline count mismatch"}
        if runs_total != report["runs_expected"]:
            return False, {**report, "failure": "run count mismatch"}

        # 2. Every referenced file has media + location with matching hash.
        media_checked = 0
        media_failures: list[str] = []
        for project in inventory["projects"]:
            slug = project["slug"]
            files_map = media_map.get("projects", {}).get(slug, {}).get("files", {})
            for entry in project["media"]["referenced"]:
                mapped = files_map.get(entry["path"])
                if mapped is None:
                    media_failures.append(f"{slug}:{entry['path']}:not-mapped")
                    continue
                shown_media = client.media.show(slug, mapped["media_id"])
                if shown_media.data is None:
                    media_failures.append(f"{slug}:{entry['path']}:no-media-row")
                    continue
                model = shown_media.data
                if model["content_hash"] != entry["sha256"]:
                    media_failures.append(
                        f"{slug}:{entry['path']}:hash-mismatch "
                        f"({model['content_hash']} vs {entry['sha256']})"
                    )
                    continue
                locations = [
                    loc
                    for loc in model.get("locations", [])
                    if loc["realm"] == mapped["realm"]
                ]
                if not locations:
                    media_failures.append(f"{slug}:{entry['path']}:no-location")
                    continue
                if not Path(locations[0]["locator"]).is_file():
                    media_failures.append(
                        f"{slug}:{entry['path']}:locator-missing "
                        f"({locations[0]['locator']})"
                    )
                    continue
                media_checked += 1
        report["media_checked"] = media_checked
        report["media_failures"] = len(media_failures)
        if media_failures:
            return False, {**report, "failure": "media failures", "details": media_failures[:10]}

        # 3. Hash chain genesis -> head for every stream.
        chains_checked = 0
        chain_failures: list[str] = []
        for stream_id in _stream_ids(client):
            verification = client.app.events.verify_stream(client.app.writer, stream_id)
            if (
                verification.event_count != verification.head_seq
                or verification.head_hash is None
            ):
                chain_failures.append(
                    f"{stream_id}: events={verification.event_count} "
                    f"head_seq={verification.head_seq}"
                )
                continue
            chains_checked += 1
        report["streams_verified"] = chains_checked
        report["chain_failures"] = len(chain_failures)
        if chain_failures:
            return False, {**report, "failure": "hash chain failures", "details": chain_failures[:10]}

        # 4. No forbidden tables.
        tables = _table_names(client)
        forbidden = sorted(
            name
            for name in tables
            if name.startswith(FORBIDDEN_TABLE_PREFIXES)
        )
        report["tables"] = len(tables)
        report["forbidden_tables"] = len(forbidden)
        if forbidden:
            return False, {**report, "failure": "forbidden tables", "details": forbidden}

        # 5. Legacy tree still on disk (read-only proof).
        legacy_checked = 0
        legacy_missing: list[str] = []
        for project in inventory["projects"]:
            for entry in project["media"]["referenced"]:
                if not (root / entry["path"]).is_file():
                    legacy_missing.append(entry["path"])
                legacy_checked += 1
            for timeline in project["timelines"]:
                if not (root / timeline["config_path"]).is_file():
                    legacy_missing.append(timeline["config_path"])
                legacy_checked += 1
            for run in project["runs"]:
                if not (root / run["run_json_path"]).is_file():
                    legacy_missing.append(run["run_json_path"])
                legacy_checked += 1
        report["legacy_checked"] = legacy_checked
        report["legacy_missing"] = len(legacy_missing)
        if legacy_missing:
            return False, {**report, "failure": "legacy files missing", "details": legacy_missing[:10]}

    return True, report


def main() -> int:
    parser = argparse.ArgumentParser(description="v10: verify the migration")
    parser.add_argument("--root", default=None, help="projects root")
    parser.add_argument(
        "--inventory",
        default=str(Path(__file__).resolve().parent / "inventory.json"),
    )
    parser.add_argument(
        "--media-map",
        default=str(Path(__file__).resolve().parent / "media_map.json"),
    )
    args = parser.parse_args()

    inventory_path = Path(args.inventory)
    if not inventory_path.is_file():
        print(f"verify: inventory not found: {inventory_path}", file=sys.stderr)
        return 2
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    root = Path(args.root) if args.root else Path(__file__).resolve().parents[3] / "projects"
    ok, report = run_verification(
        inventory, root=root, media_map_path=Path(args.media_map)
    )
    print("verify: " + ("PASS" if ok else "FAIL"))
    for key, value in sorted(report.items()):
        if key in ("details",):
            continue
        print(f"verify:   {key}={value}")
    if report.get("details"):
        for line in report["details"]:
            print(f"verify:     {line}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
