# SDK broader validation cleanup

Date: 2026-08-24  
Scope: public SDK test harnesses and adjacent documented project-selection UX  
Severity: **P3 test-harness drift**  
Product-code change: **none**

## Outcome

The broader public SDK slice is green again without weakening behavioral
assertions:

```text
tests/test_sdk_public_surface.py
96 passed in 121.29s

tests/sdk + tests/test_sdk_render_context.py + tests/test_sdk_rendering.py
205 passed in 66.43s

tests/v10/test_selection_isolation.py + tests/v10/test_preferences.py
9 passed in 0.14s
```

The failures that had stopped validation were stale test doubles and one stale
selection-boundary assumption. No live public SDK or CLI product regression
was confirmed, so no product source was changed.

## Baseline evidence

I first ran the public surface file unchanged:

```bash
python3 -m pytest tests/test_sdk_public_surface.py -q
```

Baseline result:

```text
11 failed, 85 passed in 79.72s
```

Ten failures had the same root cause. Local `fake_kernel_invoke` functions
still accepted only:

```text
capability, kind, project, projects_root, inputs, outputs
```

The current invocation seam also forwards the already-public
`extra_pack_roots` context and the managed-timeline idempotency/authority
context:

```text
extra_pack_roots
idempotency_context
```

Every affected test stopped at Python argument binding with:

```text
TypeError: fake_kernel_invoke() got an unexpected keyword argument
'extra_pack_roots'
```

The product invocation path was never reached, so these ten errors could not
be evidence of a product regression.

The eleventh failure was
`test_video_execution_inference_single_backend`. Its fake public invocation
was correctly preceded by the newer local-generation readiness preflight.
The host does not have `vibecomfy` installed in Astrid's Python environment,
so the unit stopped with the documented actionable
`CapabilityPreconditionError` before it could assert that `ltx-2.3`/`flf`
infers `execution=local`. That was environment interception of the unit's
narrow routing concern, not incorrect inference behavior.

## Test-harness corrections

### Kernel invocation doubles

All ten `_kernel_invoke` fakes in `tests/test_sdk_public_surface.py` now name
the current parameters explicitly:

```python
extra_pack_roots,
idempotency_context,
```

I deliberately did not use permissive `**kwargs`: future signature drift
will still fail loudly. A representative forwarding test now additionally
asserts:

```text
extra_pack_roots == ()
idempotency_context is None
```

Existing result, manifest-discovery, exception-cause, typed-error, project,
and error-taxonomy assertions remain intact.

### Local inference unit

The single-backend video inference test now stubs only
`require_local_generation_readiness`. It still uses the real model registry,
mode inference, execution selection, request construction, and fake public
invoke boundary. The readiness stub records and asserts the exact gate input:

```text
model             ltx-2.3
mode              flf
python_executable null
```

The original assertions that the forwarded request contains `mode=flf` and
`execution=local` are unchanged. This isolates the unit's intended concern
without pretending that local readiness is absent from the public contract.

Focused replay of the original 11 failures:

```bash
python3 -m pytest -q \
  tests/test_sdk_public_surface.py::test_invoke_executor_prefers_universal_manifest_path_from_payload \
  tests/test_sdk_public_surface.py::test_invoke_executor_discovers_universal_manifest_from_out_dir \
  tests/test_sdk_public_surface.py::test_invoke_executor_ignores_domain_manifest_payload_paths \
  tests/test_sdk_public_surface.py::test_invoke_defaults_to_subprocess_execution_mode \
  tests/test_sdk_public_surface.py::test_invoke_executor_allows_project_without_explicit_out \
  tests/test_sdk_public_surface.py::test_invoke_reuses_loaded_registries_and_preserves_runner_exception_cause \
  tests/test_sdk_public_surface.py::test_invoke_maps_typed_sdk_exceptions_from_internal_failures \
  tests/test_sdk_public_surface.py::test_invoke_missing_input_runner_errors_raise_sdk_missing_input \
  tests/test_sdk_public_surface.py::test_invoke_maps_executor_result_error_into_public_taxonomy \
  tests/test_sdk_public_surface.py::test_invoke_maps_orchestrator_result_errors_into_public_taxonomy \
  tests/test_sdk_public_surface.py::test_video_execution_inference_single_backend
```

Result:

```text
11 passed in 19.45s
```

The complete file then passed all 96 cases.

## Wider SDK stop point and live classification

I widened validation to:

```bash
python3 -m pytest \
  tests/sdk \
  tests/test_sdk_render_context.py \
  tests/test_sdk_rendering.py -q
```

The first wider run reached a new stop point:

```text
1 failed, 204 passed in 59.98s
```

The sole failure expected two shells with the **same**
`ASTRID_PROJECTS_ROOT` to receive distinct implicit workspace selections based
on process cwd. Before changing anything, I replayed that scenario through
the public CLI in fresh real directories:

```text
/tmp/astrid-sdk-selection-live.Decq7L/
  projects/
  workspace-a/
  workspace-b/
```

With a shared root, the public commands behaved as follows:

```text
workspace-a: projects select alpha
selection.path = <projects-root>/.astrid/config.json

workspace-b: projects select beta
selection.path = <projects-root>/.astrid/config.json

workspace-a: projects current
project.slug = beta
```

This exactly matches the current CLI help, core skill, getting-started guide,
and focused v10 contract: when `ASTRID_PROJECTS_ROOT` is set and `--cwd` is
omitted, that projects root is the default workspace-preference boundary.
The behavior keeps separate disposable roots launched from the same checkout
from overwriting each other's selection. Therefore the failing untracked
orientation test—not product behavior—was stale.

I modernized that case to exercise the actual documented invariant. It now
uses two workspaces with two isolated projects roots, selects `alpha` and
`beta` independently, omits `--project` for real timeline create/list
commands, and proves neither root sees the other's timeline. The test remains
end-to-end subprocess CLI coverage; no repository/store shortcuts were added.

Focused result:

```text
test_selected_project_routes_omitted_cli_project_without_cross_root_leak
1 passed in 13.29s
```

The wider 205-test SDK/rendering slice then passed completely. The existing
narrow root-isolation and explicit-workspace preference suites also passed all
9 cases, confirming that the revised expectation did not weaken either
selection boundary.

## Files changed

- `tests/test_sdk_public_surface.py`
  - current explicit `_kernel_invoke` fake signatures;
  - default forwarding assertions;
  - isolated, asserted local-readiness stub for the inference unit.
- `tests/sdk/test_project_orientation_ux.py`
  - updated the stale same-root/cwd expectation to the documented
    cross-projects-root isolation contract.
- this finding.

No Astrid product module, CLI implementation, SDK implementation, public
schema, or documentation was changed by this cleanup.

After recording the live evidence, I removed the disposable
`/tmp/astrid-sdk-selection-live.Decq7L` tree. No workspace data was removed.

## Verdict

**PASS.** The broader SDK validation lane now gets beyond the stale fake
signature boundary and completes 301 public-surface/domain/rendering tests,
plus 9 focused preference guards. The cleanup keeps strict fakes and stronger
context assertions, and the one apparently product-shaped failure was
black-box reproduced and correctly classified as an obsolete test
expectation.
