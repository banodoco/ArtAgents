# Extra-pack render propagation fix

Date: 2026-08-23

## Conclusion

Fixed the live SDK/render gap from `waves/live-pack-customization-1.md`.
`sdk.invoke(..., extra_pack_roots=(... ,))` and invocations discovered through
`ASTRID_PACKS_PATH` now carry the selected pack collection into the kernel task
spec and into the nested renderer environment. Remotion registry generation and
its webpack aliases therefore see the same external elements as public SDK
discovery. The existing project-scoped `astrid/packs/local` remains in place
and unchanged.

Rendering now resolves all requested animation and transition references before
Remotion executes. An unknown external effect/animation/transition fails closed
with a typed runtime error and no media artifact, rather than silently rendering
the stock timeline. The backend provenance fragment records each resolved
element id, source pack id, source string, element root, and clip ids; the active
pack order records the external pack's id, source kind, and root.

## Disposable-pack proof

Using the existing disposable pack at
`/tmp/astrid-gentle-fade-pack.Allqk4`:

- `python3 -m astrid.core.pack.cli list --json` and `inspect gentle_fade_pack`
  now find the pack through `ASTRID_PACKS_PATH`.
- An explicit-root SDK render completed successfully. Its provenance's
  `backend_fragments.rendering.remotion.legacy_v1.resolved_animations` contains
  `element_id: gentle-fade`, `source_pack_id: gentle_fade_pack`,
  `source: pack:gentle_fade_pack`, and the absolute custom element root.
- An environment-root SDK render also completed and recorded the same
  resolution. Its `active_pack_order` includes `gentle_fade_pack` with
  `source_kind: env` and the disposable pack root.
- Replacing the animation id with `missing-external-animation` returned
  `ok: false` and a `CapabilityRuntimeError`/`handler_failed` payload naming
  the unregistered animation; no output artifacts were returned or published.

## Code and guard scope

- `astrid/sdk/invocation.py` includes extra roots in kernel idempotency/spec
  identity and passes them to the task execution boundary.
- `astrid/core/task_executor/capability_handler.py` scopes explicit roots into
  `ASTRID_PACKS_PATH`; `astrid/core/subprocess_env.py` propagates that safe,
  non-secret discovery variable to nested pack/render processes.
- Remotion config and webpack alias helpers add aliases for external pack
  element roots only for the current invocation.
- Remotion support/render paths validate animation and transition references and
  extend provenance with their resolution evidence.
- Pack CLI `list`, `status`, and `inspect` now share the documented additional
  root scope via `ASTRID_PACKS_PATH` and repeatable `--pack-root`; docs identify
  `python3 -m astrid.core.pack.cli` as the real internal CLI. No ninth gateway
  family was added.

## Verification

Passed narrow checks:

```text
python3 -m compileall -q [changed Python modules]
pytest -q tests/packs/rendering/test_remotion_backend.py \
  -k 'unregistered_animation or support_is_request_sensitive'
2 passed
```

The broader pre-existing rendering test selection had one unrelated failure in
`test_support_rejects_legacy_output_profile_remotion_cannot_honor`; the custom
pack propagation and fail-closed guard checks passed.
