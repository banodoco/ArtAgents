#!/usr/bin/env python3
"""URL-backed asset cache for the hype pipeline.

Thin CLI wrapper over the reusable primitives in
``astrid.core.rendering.asset_cache`` (kept here so ``training.asset_cache``
remains a compatible pack entrypoint).

Assets are cached under ${HYPE_CACHE_DIR:-~/.cache/banodoco-hype}/assets.
Delete that directory manually if you need to clear all cached bytes. Run
`python -m asset_cache --prune-older-than N` to reclaim space from entries
that have not been accessed recently.
"""

from __future__ import annotations

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint('training.asset_cache')

import argparse
from pathlib import Path

from astrid.core.rendering.asset_cache import (  # noqa: F401  (re-exported for drop-in compatibility)
    ContentDriftError,
    EphemeralSession,
    _cache_dir,
    _lock_for,
    _meta_path,
    _path_for,
    _read_meta,
    _write_meta,
    ephemeral_session,
    fetch,
    is_url,
    metadata,
    prune,
    resolve,
    resolve_input,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the hype asset cache.")
    parser.add_argument("--prune-older-than", type=int, metavar="DAYS")
    args = parser.parse_args()
    if args.prune_older_than is None:
        parser.error("--prune-older-than is required")
    before: dict[Path, int] = {}
    for meta_path in _cache_dir().glob("*.meta.json"):
        asset_path = Path(str(meta_path)[: -len(".meta.json")])
        if asset_path.exists():
            before[asset_path] = asset_path.stat().st_size
    removed = prune(older_than_days=args.prune_older_than)
    freed = sum(before.get(path, 0) for path in removed)
    print(f"removed={len(removed)} freed_bytes={freed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
