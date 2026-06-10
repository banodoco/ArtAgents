#!/usr/bin/env python3
"""Validate the example capability manifests against ArtifactTypeRegistry.

Two checks:
  1. Conceptual resolution — parse the conceptual-form YAMLs
     (consumes/produces/port) with yaml.safe_load and confirm every
     artifact_type value resolves against the real ARTIFACT_TYPE_REGISTRY.
  2. Canonical smoke test — load the real cross-fade element manifest
     via load_element_definition() and verify its inputs/outputs carry
     artifact_type values.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repo root is on sys.path so `astrid` is importable.
# This file lives at docs/examples/capability-contract/validate.py,
# so parents[3] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import yaml

from astrid.core.contracts.artifact_types import ARTIFACT_TYPE_REGISTRY
from astrid.core.element.schema import load_element_definition


def _examples_dir() -> Path:
    return Path(__file__).resolve().parent


def _repo_root() -> Path:
    return _REPO_ROOT


def check_conceptual_manifest(path: Path) -> int:
    """Parse a conceptual-form YAML and check every artifact_type resolves."""
    failures = 0
    with open(path) as fh:
        doc = yaml.safe_load(fh)

    manifest_id = doc.get("id", path.name)
    print(f"  Checking conceptual manifest: {manifest_id} ({path.name})")

    # consumes: list of { port, type, artifact_type }
    for port in doc.get("consumes", []) or []:
        atype = port.get("artifact_type")
        if atype is not None:
            resolved = ARTIFACT_TYPE_REGISTRY.resolve(atype)
            if resolved is None:
                print(f"    FAIL: unresolved artifact_type {atype!r} in consumes.{port.get('port')!r}")
                failures += 1
            else:
                print(f"    OK: consumes.{port.get('port')!r} artifact_type={atype!r} -> {resolved!r}")

    # produces: list of { port, type, artifact_type }
    for port in doc.get("produces", []) or []:
        atype = port.get("artifact_type")
        if atype is not None:
            resolved = ARTIFACT_TYPE_REGISTRY.resolve(atype)
            if resolved is None:
                print(f"    FAIL: unresolved artifact_type {atype!r} in produces.{port.get('port')!r}")
                failures += 1
            else:
                print(f"    OK: produces.{port.get('port')!r} artifact_type={atype!r} -> {resolved!r}")

    return failures


def check_canonical_cross_fade() -> int:
    """Load the real cross-fade manifest via load_element_definition()."""
    failures = 0
    cross_fade_root = _repo_root() / "astrid" / "packs" / "rendering" / "elements" / "transitions" / "cross-fade"
    print(f"\n  Loading canonical cross-fade from: {cross_fade_root}")

    if not cross_fade_root.is_dir():
        print(f"    FAIL: cross-fade element directory not found at {cross_fade_root}")
        return 1

    try:
        ed = load_element_definition(
            root=cross_fade_root,
            kind="transitions",
            source="pack:rendering",
            editable=False,
            priority=0,
        )
    except Exception as exc:
        print(f"    FAIL: load_element_definition raised {type(exc).__name__}: {exc}")
        return 1

    print(f"    OK: loaded element {ed.id!r} (kind={ed.kind})")
    print(f"        inputs:  {[(p.name, p.artifact_type) for p in ed.inputs]}")
    print(f"        outputs: {[(o.name, o.artifact_type) for o in ed.outputs]}")

    # Verify artifact_type values on the loaded element are known
    for p in ed.inputs:
        if p.artifact_type is not None:
            resolved = ARTIFACT_TYPE_REGISTRY.resolve(p.artifact_type)
            if resolved is None:
                print(f"    FAIL: input {p.name!r} has unknown artifact_type {p.artifact_type!r}")
                failures += 1
            else:
                print(f"    OK: input {p.name!r} artifact_type={p.artifact_type!r} -> {resolved!r}")

    for o in ed.outputs:
        if o.artifact_type is not None:
            resolved = ARTIFACT_TYPE_REGISTRY.resolve(o.artifact_type)
            if resolved is None:
                print(f"    FAIL: output {o.name!r} has unknown artifact_type {o.artifact_type!r}")
                failures += 1
            else:
                print(f"    OK: output {o.name!r} artifact_type={o.artifact_type!r} -> {resolved!r}")

    return failures


def main() -> int:
    print("=== Capability Contract Validation ===\n")

    print("Part 1: Conceptual manifest resolution")
    failures = 0
    for name in ("flux-dev.model.yaml", "cross-fade.element.yaml"):
        path = _examples_dir() / name
        if not path.is_file():
            print(f"  FAIL: missing {path}")
            failures += 1
        else:
            failures += check_conceptual_manifest(path)

    print("\nPart 2: Canonical load_element_definition() smoke test")
    failures += check_canonical_cross_fade()

    print(f"\n{'='*40}")
    if failures:
        print(f"FAILED with {failures} failure(s)")
    else:
        print("ALL CHECKS PASSED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
