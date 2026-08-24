# Generation backend honesty fix

Date: 2026-08-23  
Scope: public `astrid.generate.image()` facade; live isolated-root replay plus
narrow regression guards

## Root cause

The public facade exposes `execution` as the canonical generation selector, but
did not declare `backend`. A caller using the natural spelling
`backend="local"` had that value captured by `**inputs` and then dropped by the
generation executor's supported-feature filtering. Because `execution` was
still unset, the facade inferred the only non-Codex backend for
`flux-schnell` (`cloud`). The kernel admitted a cloud run, and Fal then failed
at runtime because `FAL_KEY` was absent.

This was not a model-registry error: `flux-schnell/t2i` is intentionally
cloud+Codex only, while `z-image/t2i` is local-capable.

## Live reproduction before the fix

Fresh root: `/tmp/astrid-backend-honesty-t9bb9C/projects`, with `FAL_KEY`
unset. The unchanged call:

```python
astrid.generate.image(
    model="flux-schnell", prompt="a red paper boat", project="poster-lab",
    project_root=root, backend="local", size="256x256", count=1,
)
```

raised the generic public `CapabilityInvocationError: generation invocation
failed`. The resulting `runs list` input proved the silent switch:

```json
{"backend":"local","count":1,"execution":"cloud","mode":"t2i","model":"flux-schnell","prompt":"a red paper boat","size":"256x256"}
```

One failed run and one failed child were admitted. This is the unwanted
behavior: a caller's explicit local/no-paid preference reached the cloud Fal
adapter.

## Fix

`astrid/sdk/generation.py` now declares `backend` on both image and video
facades as a compatibility alias for canonical `execution`. The alias is
resolved before model/mode/backend validation and before destination
resolution or kernel invocation.

- `backend="local"` remains local; if the model has no local backend, the
  facade raises `CapabilityValidationError` listing valid backends.
- `backend="cloud"` and `backend="codex"` remain explicit selections and are
  forwarded as `inputs["execution"]`.
- Supplying both spellings requires an exact match; conflicts fail before
  invocation.
- Empty/non-string aliases fail with an actionable validation message.
- `execution` remains the documented canonical spelling.

No fallback was added for explicit local. The existing explicit Codex
availability behavior is unchanged.

## Live verification after the fix

Fresh root: `/tmp/astrid-backend-honesty-fixed-3wBXaZ/projects`, with `FAL_KEY`
unset. These calls all failed before invocation as intended:

```text
backend alias       CapabilityValidationError  Execution 'local' is not available for model 'flux-schnell' mode 't2i'. Available: cloud, codex
canonical execution CapabilityValidationError  Execution 'local' is not available for model 'flux-schnell' mode 't2i'. Available: cloud, codex
conflict            CapabilityValidationError  conflicting generation backend selections: execution='cloud' and backend='local'; provide only one or make them match
```

The root contained no files afterward, including no `.astrid/astrid.sqlite3`.
`runs list --project poster-lab --json` returned `not_found`, proving that pure
request validation did not admit a run or child task and never contacted Fal.

The valid compatibility path was also regression-tested with a non-network
fake invoke: `backend="cloud"` arrived as `execution="cloud"`, and the
ambiguous `backend` key was absent from the admitted input payload.

## Verification

```text
python3 -m pytest -q tests/test_sdk_public_surface.py -k 'backend_alias or image_explicit_execution_rejected_when_unavailable or image_explicit_execution_validated'
4 passed, 92 deselected
```

Focused guards live in `tests/test_sdk_public_surface.py` and documentation is
updated in `astrid/packs/generation/skill/SKILL.md` and
`docs/generation/30-image-contract.md`.
