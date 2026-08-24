---
name: runpod
description: Astrid executor pack for provisioning, executing, and tearing down RunPod GPU pods through the runpod-lifecycle substrate.
---

# RunPod

Curated Astrid executor metadata for managing RunPod GPU compute through
`runpod-lifecycle>=0.3`.

## Executors

- **`runpod.provision`** — Launch a GPU pod, emit `pod_handle.json`.
  Does not terminate. Pair with `runpod.teardown`. The handle is
  durable and intentionally secret-safe: it stores `api_key_ref:
  RUNPOD_API_KEY`, not the API key value.
- **`runpod.exec`** — Reattach to a provisioned pod, ship code,
  execute a script, and collect the fixed artifact directory emitted by
  `runpod-lifecycle` v0.3. Leaves pod alive. This executor does **not** expose
  requested artifact paths and must not pass unsupported detached-run kwargs
  such as `artifact_paths`, `guard_factory`, `poll_command_template`, or
  `poll_exit_marker`.
- **`runpod.pull`** — Reattach to a provisioned pod using the existing
  `pod_handle.json` and pull remote artifacts into a local directory via the
  SSH/SCP connection. Used for checkpoints, manifests, sample MP4s, and review
  assets that must exist locally before a training step can report success.
  This is a compatibility remote-copy executor for callers such as
  `training.training_run`; it is distinct from detached execution artifact
  collection in `exec`/`session`.
- **`runpod.teardown`** — Terminate a pod by handle. Idempotent.
- **`runpod.session`** — Composite provision → exec → teardown with
  `try/finally` guaranteed cleanup. Default for callers that don't need a
  hot pod across steps. It writes the same `pod_handle.json` shape as
  `provision` immediately after launch as a sweeper breadcrumb, then removes
  the transient handle only after successful or idempotent teardown.

## Storage contract

`storage_name` is optional for `provision` and `session`; storage-free modes
run without it. When a caller passes `--storage-name`, or marks the path as
storage-required with `--require-storage` / `RUNPOD_REQUIRE_STORAGE`, Astrid
checks that the named RunPod network volume already exists before provisioning.
The executor never creates a volume implicitly. If storage is required but not
configured or the named volume is missing, create the named volume first with
the storage helper (`ensure_storage` in `astrid/core/integrations/runpod/storage.py`),
then retry with `--storage-name <storage-name>`.

## Artifacts and cost

`runpod-lifecycle` v0.3 detached execution has a fixed artifact behavior:
`exec` and `session` mirror the returned artifact root into
`produces/artifact_dir` when one is present and otherwise create an empty
artifact directory. They do not accept caller-specified artifact paths.

Successful `provision`, `exec`, `teardown`, and `session` paths write
`cost.json` with `amount`, `currency`, and `source`; Astrid also includes a
local diagnostic `basis` string for auditability.

## Remote-artifact smoke

The task adapter stays provider-neutral. A RunPod smoke step should use the
generic `remote-artifact` subprocess-plus-manifest contract and put the RunPod
executor behind the call:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "runpod.session",
        kind="executor", project="demo",
    inputs={
        "gpu_type": "NVIDIA_L40S",
        "local_root": ".",
        "remote_root": "/workspace",
        "remote_script": "smoke.sh",
    },
)
```

Expected manifest/fetch shape:

```json
{
  "result.txt": {
    "path": "result.txt",
    "source": "/local/pulled/result.txt",
    "sha256": "<sha256>",
    "provider": "runpod"
  }
}
```

`path` is relative to the canonical task produces directory, `source` is a
local fetched file, and `sha256` is verified before the task can complete.
The fetch state records `fetched`, `missing`, `mismatched`, and computed
`checksums`; retries are idempotent. If a smoke keeps a pod alive and uses
`runpod.pull`, repeated `remote_path` values must be supplied as separate
`remote_path` entries in the `inputs` dict so the downstream command emits
ordered repeated `--remote-path` flags.

Live RunPod validation is opt-in only. Run it only when `RUNPOD_API_KEY` and
the required RunPod environment are present and spend is approved, for example:

```bash
ASTRID_LIVE_RUNPOD_SMOKE=1 RUNPOD_API_KEY=... \
python3 -m pytest tests/packs/runpod/test_manifest_contract.py
```

Without those variables, CI runs the mocked smoke only: command rendering,
manifest checksum/fetch behavior, repeated pull paths, and cleanup contract
documentation are verified without contacting RunPod.

## Requirements

Install `runpod-lifecycle>=0.3` before using these executors. The pack's
`requirements.txt` pins this minimum because Astrid targets the v0.3
`ship_and_run_detached` signature and artifact contract.
