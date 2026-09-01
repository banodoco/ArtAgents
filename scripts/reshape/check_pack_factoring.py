"""Check the flattened Astrid schema boundary.

Astrid used to have three domain schema packs and a local migration registry.
That architecture has been removed: the neutral workspace runtime owns the
reviewed migration stream, while Astrid packs remain executable capabilities.
This check is intentionally read-only and proves the new factoring invariant
directly instead of simulating removal of files that no longer exist.
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOMAIN_PACKS: tuple[str, ...] = ("timeline", "shots", "references")
RUNTIME_MIGRATIONS: tuple[str, ...] = (
    "003_domains.sql",
    "014_project_shots_references.sql",
)


@dataclass(frozen=True)
class FactoringResult:
    """Evidence from one flattened-schema factoring check."""

    removed_pack: str
    ok: bool
    catalog_output: str
    lane_output: str = ""
    kernel_returncode: int = 0
    kernel_error: str = ""


def _runtime_root() -> Path:
    configured = os.environ.get("BANODOCO_RUNTIME_CHECKOUT")
    return Path(configured).expanduser() if configured else REPO_ROOT.parent / (
        "banodoco-workspace-runtime-stage1-convergence"
    )


def _local_schema_paths() -> list[Path]:
    astrid = REPO_ROOT / "astrid"
    paths: list[Path] = []
    host = astrid / "core" / "schema_packs"
    if host.exists():
        paths.append(host)
    paths.extend(astrid.rglob("schema-pack.yaml"))
    paths.extend(path for path in astrid.rglob("migrations") if path.is_dir())
    return sorted(paths)


def _runtime_tables() -> set[str]:
    tables: set[str] = set()
    migration_dir = _runtime_root() / "runtime_protocol" / "migrations"
    for name in RUNTIME_MIGRATIONS:
        path = migration_dir / name
        if not path.is_file():
            continue
        tables.update(
            match.group(1).lower()
            for match in re.finditer(
                r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)",
                path.read_text(encoding="utf-8"),
                re.IGNORECASE,
            )
        )
    return tables


def check_flattened_schema() -> tuple[bool, list[str], dict[str, object]]:
    """Return ``(ok, violations, evidence)`` for the schema boundary."""
    violations: list[str] = []
    local_paths = _local_schema_paths()
    violations.extend(f"local schema authority remains: {path}" for path in local_paths)

    astrid = REPO_ROOT / "astrid"
    stale_sources: list[str] = []
    for path in astrid.rglob("*.py"):
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "astrid.core.schema_packs" in source or "schema-pack.yaml" in source:
            stale_sources.append(str(path.relative_to(REPO_ROOT)))
    violations.extend(f"stale local schema reference: {path}" for path in stale_sources)

    runtime_dir = _runtime_root() / "runtime_protocol" / "migrations"
    missing_runtime = [name for name in RUNTIME_MIGRATIONS if not (runtime_dir / name).is_file()]
    violations.extend(f"neutral runtime migration missing: {name}" for name in missing_runtime)
    tables = _runtime_tables()
    required_tables = {
        "timelines",
        "timeline_shots",
        "timeline_references",
        "project_documents",
        "generations",
        "generation_variants",
        "project_shots",
        "shot_items",
        "project_references",
        "media_references",
        "reference_links",
    }
    missing_tables = sorted(required_tables - tables)
    violations.extend(f"neutral runtime table missing: {name}" for name in missing_tables)

    capability_manifests = sorted(
        str(path.relative_to(REPO_ROOT))
        for path in (REPO_ROOT / "astrid" / "packs").glob("*/pack.yaml")
    )
    if not capability_manifests:
        violations.append("no executable capability-pack manifests remain")
    evidence = {
        "local_schema_paths": [str(path.relative_to(REPO_ROOT)) for path in local_paths],
        "stale_sources": stale_sources,
        "runtime_root": str(_runtime_root()),
        "runtime_migrations": list(RUNTIME_MIGRATIONS),
        "runtime_tables": sorted(tables),
        "missing_runtime_tables": missing_tables,
        "capability_manifests": capability_manifests,
    }
    return not violations, violations, evidence


def verify_sketch_kernel_inventory() -> str:
    """Retain the sketch hook without reviving a local migration catalog."""
    sketch = REPO_ROOT / "docs" / "architecture" / "software-engineering-pack-sketch.md"
    if not sketch.is_file():
        return "sketch not present; no local schema inventory expected"
    text = sketch.read_text(encoding="utf-8")
    if "CORE_MIGRATIONS" in text or "schema-pack" in text.lower():
        return "sketch contains historical schema language; treated as documentation only"
    return "sketch contains no local schema inventory"


def check_removal(
    removed_pack: str,
    *,
    python: str | None = None,
    keep_temp: bool = False,
    lane_timeout: float = 300.0,
) -> FactoringResult:
    """Compatibility API: each former pack is absent by construction."""
    del python, keep_temp, lane_timeout
    if removed_pack not in DOMAIN_PACKS:
        raise ValueError(f"unknown former domain pack {removed_pack!r}; expected {DOMAIN_PACKS}")
    ok, violations, evidence = check_flattened_schema()
    return FactoringResult(
        removed_pack=removed_pack,
        ok=ok,
        catalog_output=(
            "flattened runtime schema boundary verified"
            if ok
            else "; ".join(violations)
        ),
        lane_output=str(evidence),
        kernel_returncode=0 if ok else 1,
        kernel_error="; ".join(violations),
    )


def check_artifact_removal(*args: object, **kwargs: object) -> FactoringResult:
    """Compatibility alias for callers of the pre-flattening checker."""
    del kwargs
    removed = str(args[0]) if args else DOMAIN_PACKS[0]
    return check_removal(removed)


def check_artifact_factoring(
    packs: tuple[str, ...] = DOMAIN_PACKS,
    **_: object,
) -> list[FactoringResult]:
    """Check the flattened boundary once for each former domain pack."""
    return [check_removal(pack) for pack in packs]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packs", nargs="*", default=list(DOMAIN_PACKS))
    args = parser.parse_args(argv)
    try:
        results = check_artifact_factoring(tuple(args.packs))
    except Exception as exc:  # noqa: BLE001 - CLI reports deterministic failure
        print(f"[FAIL] factoring check: {exc}")
        return 1
    failures = [result for result in results if not result.ok]
    for result in results:
        label = "PASS" if result.ok else "FAIL"
        print(f"[{label}] former {result.removed_pack}: {result.catalog_output}")
    if failures:
        return 1
    print("[PASS] schema authority is flattened into the neutral workspace runtime")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
