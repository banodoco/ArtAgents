"""Source persistence APIs for projects."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from astrid.core._shared.jsonio import read_json, write_json_atomic
from astrid.core.contracts.errors import AstridError
from astrid.core.foundation import project_paths as paths

from .project import require_project
from .schema import build_source, validate_source


def add_source(
    project_slug: str,
    source_id: str,
    *,
    asset: dict[str, Any],
    kind: str | None = None,
    metadata: dict[str, Any] | None = None,
    root: str | Path | None = None,
    exist_ok: bool = False,
) -> dict[str, Any]:
    require_project(project_slug, root=root)
    source_path = paths.source_json_path(project_slug, source_id, root=root)
    if source_path.exists() and not exist_ok:
        raise AstridError(
            f"source already exists: {source_id}",
            recovery_command=f"pass exist_ok=True to overwrite, or choose a different source_id",
        )
    source_dir = paths.source_dir(project_slug, source_id, root=root)
    source_dir.mkdir(parents=True, exist_ok=True)
    paths.source_analysis_dir(project_slug, source_id, root=root).mkdir(parents=True, exist_ok=True)

    # When the asset has a local file (not a URL), import it into the project.
    # Only trigger when file is present and url is NOT — the "both file and url"
    # case is caught by build_source/_normalize_asset validation below.
    had_old_media = False
    backup_dest: Path | None = None
    if isinstance(asset.get("file"), str) and asset["file"] and not asset.get("url"):
        input_file = Path(asset["file"]).expanduser().resolve()
        if not input_file.is_file():
            raise AstridError(
                f"source file not found or not readable: {input_file}",
                recovery_command="check that the --file path exists and is a regular file",
            )
        original_suffix = input_file.suffix
        canonical_dest = source_dir / f"{source_id}{original_suffix}"
        temp_dest = source_dir / f".{source_id}{original_suffix}.importing"
        backup_dest = source_dir / f".{source_id}{original_suffix}.backup"
        # Validate the full payload (kind, asset fields incl. duration) BEFORE
        # touching the canonical media: a bad --force import must not replace
        # the old bytes and leave a stale source.json behind.
        validated_asset = dict(asset)
        validated_asset["file"] = str(canonical_dest.resolve())
        build_source(project_slug, source_id, asset=validated_asset, kind=kind, metadata=metadata)
        had_old_media = canonical_dest.exists()
        try:
            shutil.copy2(input_file, temp_dest)
            if had_old_media:
                os.replace(canonical_dest, backup_dest)
            os.replace(temp_dest, canonical_dest)
        except Exception:
            # Roll back the canonical file and remove any staged temp.
            try:
                temp_dest.unlink(missing_ok=True)
            except OSError:
                pass
            try:
                if backup_dest is not None and backup_dest.exists():
                    os.replace(backup_dest, canonical_dest)
            except OSError:
                pass
            raise
        finally:
            try:
                temp_dest.unlink(missing_ok=True)
            except OSError:
                pass
        # Record the absolute in-project destination path.
        asset = validated_asset

    payload = build_source(project_slug, source_id, asset=asset, kind=kind, metadata=metadata)
    try:
        write_json_atomic(source_path, payload)
    except Exception:
        # A failed payload write must not leave replaced media behind: restore
        # the previous bytes when we had backed them up.
        try:
            if backup_dest is not None and backup_dest.exists():
                os.replace(backup_dest, source_dir / f"{source_id}{Path(asset['file']).suffix}")
        except OSError:
            pass
        raise
    finally:
        # Drop the backup of the old media once the payload is safely on disk.
        try:
            if backup_dest is not None and backup_dest.exists():
                backup_dest.unlink(missing_ok=True)
        except OSError:
            pass
    return payload


def load_source(project_slug: str, source_id: str, *, root: str | Path | None = None) -> dict[str, Any]:
    return validate_source(read_json(paths.source_json_path(project_slug, source_id, root=root)))


def require_source(project_slug: str, source_id: str, *, root: str | Path | None = None) -> dict[str, Any]:
    source_path = paths.source_json_path(project_slug, source_id, root=root)
    if not source_path.exists():
        raise AstridError(
            f"source not found: {source_id}",
            recovery_command=f"python3 -m astrid projects source add --project {project_slug} {source_id} --file <path>",
        )
    return validate_source(read_json(source_path))
