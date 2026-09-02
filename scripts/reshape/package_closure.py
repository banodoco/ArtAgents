"""Deterministic source-side closure for canonical bundled-pack resources.

The canonical catalog resolves ownership and confinement.  This module only
projects the handles needed by release packaging; it does not create a second
manifest parser or an evidence store.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from astrid.core.pack.canonical import BundledCatalog, CanonicalPackError


@dataclass(frozen=True)
class SourceResourceClosure:
    """The release resources resolved from one source checkout."""

    paths: tuple[str, ...]
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def check_source_resource_closure(repository_root: str | Path) -> SourceResourceClosure:
    """Resolve every bundled manifest/doc/migration/runtime declaration.

    Content roots contain Python packages and component authoring material;
    those are handled by normal package discovery and their explicit data
    patterns.  This release projection covers the canonical resource handles:
    manifests, direct guidance, required context, migrations, rendering
    extension files, and standalone ``resources`` declarations.
    """

    root = Path(repository_root).expanduser().resolve()
    packs_root = root / "astrid" / "packs"
    errors: list[str] = []
    paths: set[str] = set()
    try:
        catalog = BundledCatalog.from_root(packs_root)
    except CanonicalPackError as exc:
        return SourceResourceClosure((), (f"invalid bundled catalog: {exc}",))
    for entry in catalog.entries:
        owner = entry.root.resolve()
        handles = (entry.manifest, *entry.resource_handles)
        for handle in handles:
            if handle.kind.startswith("content:"):
                continue
            relative = f"astrid/packs/{entry.id}/{handle.path}"
            paths.add(relative)
            try:
                resolved = handle.resolved.resolve()
                if not resolved.is_relative_to(owner):
                    errors.append(f"{relative}: resolved outside owner root")
                if handle.file_kind != "file" or not resolved.is_file():
                    errors.append(f"{relative}: declared handle is not a regular file")
            except OSError as exc:
                errors.append(f"{relative}: cannot inspect resolved handle: {exc}")
    core_skill = root / "astrid" / "packs" / "_core" / "skill" / "SKILL.md"
    core_skill_relative = core_skill.relative_to(root).as_posix()
    paths.add(core_skill_relative)
    if not core_skill.is_file():
        errors.append(f"{core_skill_relative}: core census guidance is not a regular file")

    core_root = root / "astrid" / "core" / "migrations" / "sql" / "core"
    for migration in sorted(core_root.glob("*.sql")):
        relative = migration.relative_to(root).as_posix()
        paths.add(relative)
        if not migration.is_file():
            errors.append(f"{relative}: core migration is not a regular file")
    return SourceResourceClosure(tuple(sorted(paths)), tuple(sorted(set(errors))))


def declared_source_resource_paths(repository_root: str | Path) -> tuple[str, ...]:
    """Return resolved release paths, raising on an incomplete source tree."""

    closure = check_source_resource_closure(repository_root)
    if not closure.ok:
        raise ValueError("source resource closure failed: " + "; ".join(closure.errors))
    return closure.paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    closure = check_source_resource_closure(args.root)
    print(json.dumps({"ok": closure.ok, "paths": closure.paths, "errors": closure.errors}))
    return 0 if closure.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SourceResourceClosure",
    "check_source_resource_closure",
    "declared_source_resource_paths",
]
