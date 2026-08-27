"""Repair a migrated timeline registry through the supported CAS save.

The v10 timeline migration once wrote imported media ids into ``file``.
This command repairs an existing projection without touching legacy files or
SQLite directly.  It is dry-run by default; ``--apply`` performs one
idempotent, expected-version-guarded ``timeline.save``.  The resulting
``timeline.saved`` event and receipt are the audit record.

Example (preview only)::

    python3 scripts/migrations/v10/repair_timeline_assets.py \
        --root /path/to/projects --project runaway-piano-colour-demo \
        --timeline rhzerepmv7mz8yw5jr0qkjk30b --asset-key source_audio \
        --media-id 08b43be5-58ad-534a-9713-d2e0f68ba151

Apply only after reviewing the printed registry diff::

    ... --apply
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Mapping


def repair_registry(
    registry: Mapping[str, Any],
    *,
    asset_key: str,
    media_id: str,
) -> dict[str, Any]:
    """Return a repaired registry without mutating *registry*.

    The source ``file`` locator is retained unless it is exactly the media
    id that the old migration incorrectly stored there.  An existing,
    different ``media_id`` is a conflict and fails closed rather than being
    silently replaced.
    """
    if not isinstance(asset_key, str) or not asset_key.strip():
        raise ValueError("asset_key must be a non-empty string")
    if not isinstance(media_id, str) or not media_id.strip():
        raise ValueError("media_id must be a non-empty string")
    if not isinstance(registry, Mapping):
        raise ValueError("registry must be an object")
    raw_assets = registry.get("assets")
    if not isinstance(raw_assets, Mapping):
        raise ValueError("registry.assets must be an object")
    raw_entry = raw_assets.get(asset_key)
    if not isinstance(raw_entry, Mapping):
        raise ValueError(f"registry asset {asset_key!r} must be an object")
    prior_media_id = raw_entry.get("media_id")
    if prior_media_id is not None and prior_media_id != media_id:
        raise ValueError(
            f"registry asset {asset_key!r} already points to a different media_id"
        )

    repaired = copy.deepcopy(dict(registry))
    assets = dict(repaired["assets"])
    entry = dict(assets[asset_key])
    # The historical bug used exactly this value as a file locator.  Remove
    # only that known-invalid alias; preserve every legitimate source locator.
    if entry.get("file") == media_id:
        entry.pop("file", None)
    entry["media_id"] = media_id
    assets[asset_key] = entry
    repaired["assets"] = assets
    return repaired


def repair_timeline(
    *,
    root: Path,
    project: str,
    timeline: str,
    asset_key: str,
    media_id: str,
    apply: bool,
) -> dict[str, Any]:
    """Preview or CAS-apply one registry repair and return an evidence row."""
    from astrid.sdk.client import AstridClient

    idempotency_key = f"v10-repair:timeline-assets:{project}:{timeline}:{asset_key}:{media_id}"
    with AstridClient.open(projects_root=root) as client:
        shown = client.timelines.show(project, timeline)
        if not shown.ok or shown.data is None:
            raise SystemExit(
                f"timeline show failed: {shown.error.code if shown.error else 'unknown'}"
            )
        current = shown.data
        current_registry = current.get("registry", {"assets": {}})
        repaired = repair_registry(
            current_registry, asset_key=asset_key, media_id=media_id
        )
        changed = repaired != current_registry
        row: dict[str, Any] = {
            "project": project,
            "timeline": timeline,
            "asset_key": asset_key,
            "media_id": media_id,
            "expected_version": current["config_version"],
            "changed": changed,
            "action": "noop" if not changed else ("apply" if apply else "plan"),
            "idempotency_key": idempotency_key,
        }
        if apply and changed:
            media = client.media.show(project, media_id)
            if not media.ok or media.data is None:
                raise SystemExit(
                    f"media lookup failed: {media.error.code if media.error else 'unknown'}"
                )
            saved = client.timelines.save(
                project,
                timeline,
                config=current.get("config", {}),
                registry=repaired,
                expected_version=int(current["config_version"]),
                idempotency_key=idempotency_key,
            )
            if not saved.ok or saved.data is None:
                raise SystemExit(
                    f"timeline repair failed: {saved.error.code if saved.error else 'unknown'}"
                )
            row["resulting_version"] = saved.data["config_version"]
        return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="Astrid projects root")
    parser.add_argument("--project", required=True)
    parser.add_argument("--timeline", required=True)
    parser.add_argument("--asset-key", required=True)
    parser.add_argument("--media-id", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    row = repair_timeline(
        root=args.root,
        project=args.project,
        timeline=args.timeline,
        asset_key=args.asset_key,
        media_id=args.media_id,
        apply=args.apply,
    )
    print(json.dumps(row, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
