"""Phase 5 lifecycle verbs: start/abort/status/runs ls/next; cmd_ack lives
in lifecycle_ack.py to keep both modules under the size budget.

cmd_runs_ls (FLAG-P5-006): natural completion does not clear active_run.json
in V1, so the lister surfaces only 'aborted' vs 'in-progress'.
cmd_start (SD-007): does not silently invoke compile when the pre-built JSON
manifest is missing — prints the compile recovery and returns non-zero.
Author-test replays are the exception: they deliberately use compiled smoke
plans even for orchestrators that normally build dynamic start plans.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from astrid.core.pack.alias_resolver import (
    _register_pack_aliases,
    create_shared_alias_resolver,
    extract_pack_aliases,
)
from astrid.core.pack import DEFAULT_PACKS_ROOT, discover_packs
from astrid.core.util.log_and_swallow import log_and_swallow


def _resolve_packs_root(packs_root: Optional[Path]) -> Path:
    if packs_root is not None:
        return Path(packs_root)
    return DEFAULT_PACKS_ROOT

def _qualified_split(qualified_id: str) -> tuple[str, str]:
    if not isinstance(qualified_id, str) or "." not in qualified_id:
        raise ValueError(
            f"orchestrator id {qualified_id!r} must be '<pack>.<name>'"
        )
    pack, _, name = qualified_id.partition(".")
    if not pack or not name or "." in name:
        raise ValueError(
            f"orchestrator id {qualified_id!r} must be exactly '<pack>.<name>'"
        )
    return pack, name

def _canonical_orchestrator_id(
    orchestrator_id: str,
    *,
    packs_root: Path,
) -> str:
    """Resolve legacy orchestrator aliases to the canonical id for start-time checks."""
    packs = discover_packs(root=packs_root, include_hidden=True)
    if not packs:
        return orchestrator_id
    resolver = create_shared_alias_resolver()
    _register_pack_aliases(resolver, extract_pack_aliases(packs, kind="orchestrator"))
    return resolver.resolve(orchestrator_id)

def _list_orchestrator_ids(packs_root: Optional[Path] = None) -> tuple[list[str], str | None]:
    """List installable orchestrators as qualified ids.

    Returns ``(ids, error_summary)``. On registry-load failure the ids list
    is empty AND ``error_summary`` is a one-line hint pointing at the
    underlying issue so the next-hint can say "registry is broken" instead
    of "nothing installed".

    Two-source union: YAML-manifested orchestrators (via the registry) AND
    DSL-authored orchestrators that have a compiled ``build/<name>.json``
    (which is enough for ``astrid start`` to work but doesn't show up in
    the registry today). The v6 probe found that DSL-compiled orchestrators
    were invisible to `astrid next`'s suggestions even though they ran
    fine — the agent could start them only by knowing their id externally.

    Sort order (polish #30): orchestrators with a recently-modified
    ``build/<name>.json`` first (most recently compiled / used), then
    alphabetical. The v6 probe found ``mini_research`` and ``agent_probe``
    were buried below alphabetically-earlier orchestrators the agent didn't
    want; recency surfaces what the operator just touched.
    """
    ids: set[str] = set()
    registry_err: str | None = None
    try:
        from astrid.core.orchestrator.registry import load_default_registry
        registry = load_default_registry()
        ids.update(o.id for o in registry.list())
    except Exception as exc:
        registry_err = f"{type(exc).__name__}: {exc}"

    # Add DSL-compiled orchestrators discovered from build/*.json files.
    # Each `<pack>/build/<name>.json` corresponds to qualified id
    # `<pack>.<name>`. Defensive — never raises if a pack dir is missing.
    #
    # Canonical orchestrators (video_editing.hype, video_editing.event_talks,
    # video_editing.thumbnail_maker) build their plans dynamically at start
    # time via plan_template.build_plan_v2(). Their compiled build JSON
    # artifacts (if present) are NOT product surface — they must never
    # be treated as the canonical plan source or discovered from the
    # build/ directory for listing/suggestion purposes.
    _CANONICAL_DYNAMIC_IDS = {
        "video_editing.hype",
        "video_editing.event_talks",
        "video_editing.thumbnail_maker",
    }
    try:
        if DEFAULT_PACKS_ROOT.is_dir():
            for pack_dir in DEFAULT_PACKS_ROOT.iterdir():
                if not pack_dir.is_dir():
                    continue
                build_dir = pack_dir / "build"
                if not build_dir.is_dir():
                    continue
                for build_file in build_dir.glob("*.json"):
                    qid = f"{pack_dir.name}.{build_file.stem}"
                    if qid not in _CANONICAL_DYNAMIC_IDS:
                        ids.add(qid)
    except Exception as exc:  # noqa: BLE001
        log_and_swallow(exc, context="orchestrator_resolver.build_dir_scan")

    if not ids:
        return [], registry_err

    def _build_mtime(qualified_id: str) -> float:
        if "." not in qualified_id:
            return 0.0
        pack, _, name = qualified_id.partition(".")
        try:
            build_path = DEFAULT_PACKS_ROOT / pack / "build" / f"{name}.json"
            return build_path.stat().st_mtime if build_path.is_file() else 0.0
        except Exception:
            return 0.0

    id_list = sorted(ids, key=lambda qid: (-_build_mtime(qid), qid))
    return id_list, registry_err
