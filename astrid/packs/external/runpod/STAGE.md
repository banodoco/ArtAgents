---
name: runpod
description: Astrid executor pack for provisioning, executing, and tearing down RunPod GPU pods through the runpod-lifecycle substrate.
---

# RunPod

Curated Astrid executor metadata for managing RunPod GPU compute through
`runpod-lifecycle` (v0.2+).

## Executors

- **`external.runpod.provision`** — Launch a GPU pod, emit `pod_handle.json`.
  Does not terminate. Pair with `external.runpod.teardown`.
- **`external.runpod.exec`** — Reattach to a provisioned pod, ship code,
  execute a script, download artifacts. Leaves pod alive.
- **`external.runpod.pull`** — Reattach to a provisioned pod using the existing
  `pod_handle.json` and pull remote artifacts into a local directory via the
  SSH/SCP connection. Used for checkpoints, manifests, sample MP4s, and review
  assets that must exist locally before a training step can report success.
- **`external.runpod.teardown`** — Terminate a pod by handle. Idempotent.
- **`external.runpod.session`** — Composite provision → exec → teardown with
  `try/finally` guaranteed cleanup. Default for callers that don't need a
  hot pod across steps.

## Safety net

Run `astrid runpod sweep` to clean up orphaned pods. Default mode is safe
(skips pods with live sessions or in-flight exec). `--hard` mode bypasses
those checks.

## Requirements

Install `runpod-lifecycle>=0.3` before using these executors. The pack's
`requirements.txt` pins the minimum version.
