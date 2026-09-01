#!/usr/bin/env bash
set -euo pipefail

# Build one wheel and run the small installed-product smoke through the shared
# artifact harness.  The harness owns wheel selection, identity, isolation,
# credential scrubbing, lane evidence, and cleanup; this wrapper only chooses
# the smoke lanes and reports their results.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
EXPLICIT_WORKSPACE="${SMOKE_WHEEL_WORKSPACE:-}"

cd "$REPO_ROOT"

set --
if [[ -n "$EXPLICIT_WORKSPACE" ]]; then
  set -- "$REPO_ROOT" --workspace "$EXPLICIT_WORKSPACE"
else
  set -- "$REPO_ROOT"
fi

exec "$PYTHON_BIN" - "$@" <<'PY'
from __future__ import annotations

import json
import sys
from importlib import resources
from pathlib import Path

repo_root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo_root))

from scripts.reshape.installed_artifact import build_once


args = sys.argv[2:]
workspace = None
if args:
    if len(args) != 2 or args[0] != "--workspace":
        raise SystemExit(f"invalid workspace arguments: {args!r}")
    workspace = Path(args[1]).expanduser().resolve()

print("=== installed Astrid wheel smoke ===")
print(f"repository: {repo_root}")
if workspace is not None:
    print(f"workspace: {workspace}")

harness = build_once(
    repo_root,
    workspace=workspace,
    # The smoke is a user-facing product check, so install the wheel with its
    # declared runtime dependencies.  T3's no-dependency harness remains the
    # stricter dependency-leak proof.
    install_dependencies=True,
)
owned_workspace = workspace is None
workspace_path = harness.workspace
try:
    version = harness.run_module("version", "astrid", ["--version"], check=True)
    assert version.stdout.strip() == "astrid", version.stdout

    help_record = harness.run_module("help", "astrid", ["help"], check=True)
    assert "Family census (exactly eight families):" in help_record.stdout
    assert "timelines shots       [pack: shots]" in help_record.stdout
    assert "media references      [pack: references]" in help_record.stdout

    # ``doctor --json`` is intentionally run against the fresh isolated
    # workspace.  A clean workspace has no database yet, so either a healthy
    # result (if a caller pre-seeded it) or doctor’s documented fail-closed
    # result is valid; import/parse failures are not.
    doctor = harness.run_module("doctor", "astrid", ["doctor", "--json"])
    if doctor.returncode not in (0, 1):
        raise RuntimeError(doctor.error or doctor.output)
    doctor_payload = json.loads(doctor.stdout)
    assert isinstance(doctor_payload.get("checks"), list)
    assert isinstance(doctor_payload.get("ok"), bool)

    resource_probe = harness.run_lane(
        "resources",
        [
            "-c",
            "from importlib import resources; "
            "required=('packs/rendering/pack.yaml','packs/generation/pack.yaml',"
            "'packs/typed_timeline/pack.yaml'); "
            "root=resources.files('astrid'); "
            "missing=[name for name in required if not root.joinpath(*name.split('/')).is_file()]; "
            "assert not missing, missing; print('package resources: OK')",
        ],
        check=True,
    )
    assert "package resources: OK" in resource_probe.stdout

    # Adversarial lanes prove that a missing resource and a checkout import
    # cannot be mistaken for a passing installed-artifact result.
    missing = harness.run_lane(
        "missing-resource",
        [
            "-c",
            "from importlib import resources; "
            "assert resources.files('astrid').joinpath('not-shipped.txt').is_file()",
        ],
    )
    if missing.returncode == 0 or missing.status != "failed":
        raise RuntimeError(f"missing-resource adversary unexpectedly passed: {missing.as_dict()}")

    checkout = harness.run_lane(
        "checkout-import",
        ["-c", f"print({str(repo_root)!r})"],
    )
    if checkout.returncode != 0 or checkout.status != "failed":
        raise RuntimeError(f"checkout-import adversary was not rejected: {checkout.as_dict()}")
    if not checkout.error or "source-tree path" not in checkout.error:
        raise RuntimeError(f"checkout-import failure lacked source evidence: {checkout.as_dict()}")

    print(json.dumps({
        "schema": "astrid.installed_smoke.v1",
        "wheel_sha256": harness.artifact_digest,
        "version": harness.installed_version,
        "doctor_ok": doctor_payload["ok"],
        "resource_lane": resource_probe.as_dict(),
        "missing_resource_lane": missing.as_dict(),
        "checkout_import_lane": checkout.as_dict(),
    }, sort_keys=True))
finally:
    harness.close()

if owned_workspace:
    if workspace_path.exists():
        raise RuntimeError(f"owned harness workspace was not cleaned: {workspace_path}")
else:
    if not workspace_path.is_dir():
        raise RuntimeError(f"explicit harness workspace was not preserved: {workspace_path}")

print("=== installed Astrid wheel smoke PASSED ===")
PY
