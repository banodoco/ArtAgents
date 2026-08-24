# Generation local preflight fix

Date: 2026-08-23  
Surface: public `astrid.generate.image()` facade and direct SDK image invocation  
Isolation: live calls used a fresh `/tmp/astrid-local-preflight-*` projects root

## Finding

The documented `z-image` + `local` pair was valid in the model registry but
was admitted before the local runtime was checked. On this machine the task
then failed inside the executor with `ModuleNotFoundError: vibecomfy`, leaving
a failed run/task behind.

## Fix

`astrid.core.generation.preflight` now performs a read-only, pre-admission
check for the selected local image model path:

- the selected local backend has a VibeComfy template;
- the `vibecomfy` Python package is discoverable in the active interpreter;
- a managed ComfyUI runtime is discoverable as `comfy.cmd.main` or the
  `comfyui` executable.

Failures raise `CapabilityPreconditionError` with an actionable command. The
typed image facade and direct SDK image invocation use the same guard before
kernel admission. Video behavior is unchanged by this image-specific fix. No
import of `vibecomfy`, subprocess, network
probe, output-directory creation, run, task, or staging write occurs during
the check.

The boundary is intentional: Astrid's local adapter starts a managed ComfyUI
server when the runtime is installed. It therefore does not require a live
endpoint/configuration just to pass preflight, and it does not turn a
temporarily offline server into an unsupported-installation error. Endpoint
startup/reachability remains a runtime condition with the existing runtime
diagnostics. There is no cloud or Codex fallback.

## Live proof

With an empty isolated projects root:

1. `flux-schnell` + `backend="local"` still rejects with the existing
   available-backends validation (`cloud, codex`).
2. `z-image` with `execution="cloud", backend="local"` still rejects with
   the existing conflicting-selector validation.
3. `z-image` + `backend="local"` now rejects before invocation with:

   `Local generation is not ready: ... 'vibecomfy' Python package ... Next: <python> -m pip install vibecomfy ...`

   The isolated root remained empty: no project database, run, task, output,
   or staging directory was created.
4. A structural-ready path (simulated read-only discovery of both modules)
   was admitted to the SDK invocation seam; cloud and Codex paths remain
   unaffected.
5. A direct `sdk.invoke("generation.generate_image", ...)` local call also
   rejected with the same precondition before the isolated root was created.

## Verification

```text
pytest -q tests/core/generation/test_preflight.py
5 passed

pytest -q tests/core/generation/test_preflight.py tests/test_sdk_public_surface.py \
  -k 'image_backend_alias or explicit_execution or execution_ambiguous or typed_local_generation'
13 passed, 88 deselected
```
