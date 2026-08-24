# Canonical managed-timeline render fix

Date: 2026-08-24

## Outcome

Astrid now has an explicit canonical managed-timeline render route without
changing the meaning of the existing file route:

- `rendering.render` with `timeline=<file>` remains explicit project-owned
  file mode. A value such as `timeline="main"` is never interpreted as a slug.
- `rendering.render` with `timeline_ref=<slug|UUID|ULID>` is canonical kernel
  mode. `timeline` and `timeline_ref` are mutually exclusive.
- `astrid timelines render <ref>` exposes canonical mode as a discoverable
  product verb. `--expected-version` is an optional positive stream-head CAS
  guard.
- Resolution happens read-only against the project and timeline kernel before
  task/run admission. Missing, ambiguous, archived, and stale refs fail with
  actionable validation.
- The admitted task pins the canonical project/timeline IDs, ULID and slug,
  stream version, tail event ID/hash, config hash, canonical stored registry
  hash, and materialized registry hash. The same authority object contributes
  to cache identity and is stamped into the render provenance sidecar.
- Managed registry locators are derived through the shared content-hash-aware
  resolver, so canonical managed media is renderable. The stored registry hash
  remains stable across root changes; the separate materialized hash records
  the effective local renderer input.
- Managed-mode provenance stamping fails closed. File-mode provenance retains
  the older best-effort locator rewrite behavior.

Renderer inputs are materialized deterministically under
`<project>/.astrid/render-snapshots/<authority-hash>/`. An unchanged authority
reuses one immutable directory; there is no random staging accumulation. These
are derived retry inputs rather than authority and can be regenerated from the
kernel. Any future cleanup must retain directories referenced by retryable
tasks.

## Live reproduction and acceptance

Fresh root: `/private/tmp/astrid-canonical-render.KPtNh4`

The old ambiguous attempt was reproduced through the public SDK with:

```text
rendering.render inputs={timeline: "main", backend: "rendering.remotion",
                         output_name: "legacy-slug.mp4"}
```

It failed as file mode (`ok=false`, run
`afba9406c93b645f4dc0fded7f`); it did not silently resolve the slug.

The managed v1 command was:

```text
ASTRID_PROJECTS_ROOT=/private/tmp/astrid-canonical-render.KPtNh4 \
python3 -m astrid timelines render main --project render-demo \
  --expected-version 1 --backend rendering.remotion \
  --output-name canonical-v1.mp4 --json
```

It succeeded as run `85c77ae2976394506c295fec4d`, producing managed MP4
SHA-256 `a91cc5ef29fbf72e3d6d9c925d680bc43f7144665ead7c077244a8875df7b408`
and provenance SHA-256
`7ae2850019f46239abb2d7726e980614123d419bf9867e2f8ffc80943cc83e9a`.
The provenance `canonical_timeline` recorded timeline
`915c3086-31c5-57de-97ef-1d416a467856`, version 1, tail event
`cb584f092ef04776b9945b1dc517a8fc`, tail hash
`47e5963eab783eb79c18942d9868df4c0455376a1b3a1639d2d37d4f0aa43b36`,
and config hash
`83c37937ce6713abcf92d858e4d319340ce69bfddfd03004176b3b3147c550f3`.
The task `spec_json` contains the same authority and deterministic private
timeline/registry paths.

A public `timelines save main --expected-version 1` changed the title and
advanced the stream to version 2. Repeating render with
`--expected-version 1` failed before admission with `kernel_run_id`,
`kernel_task_id`, and `kernel_attempt_id` all null. Rendering with
`--expected-version 2` succeeded as distinct run
`767d3c4cdbbde6a3a723ee48cc`, MP4 SHA-256
`f2a23032ccb27fcd2c53e3ee854e54fbf9cc30146a10beeb363fdc2ca4967073`,
and provenance SHA-256
`a5f08c785c4e3153e7e21956e0674920c6ea5a2f028bef0b8c4d1ffaa7456165`.
Its tail event/hash changed to
`41e5ddab6af9432498a94762a0722c55` /
`4333f381eac3bd7b2a0b3a58f6fe772af3b9f562f6b3207f2ad0cb5546a6ac2c`
and config hash changed to
`e6ef09f8d7791d468edfaad6dbdab4029be0f6b23dff2b3947fe2a8bfccc1291`.

Archiving advanced the stream to version 3. A subsequent public render failed
with `timeline 'main' is archived; unarchive it before rendering`; task count
was 4 both before and after that attempt, proving pre-admission rejection.

## Focused verification

Final focused command covering the new resolver/provenance contracts, durable
frozen navigation, SDK preflight, and timeline product CLI:

```text
pytest -q tests/packs/rendering/test_managed_timeline_render.py \
  tests/packs/rendering/test_timeline_visualize_frozen.py \
  tests/sdk/test_maker_preflight_contracts.py \
  tests/v10/test_domain_cli_projects_timelines.py
```

Result: **92 passed in 48.24s**. `compileall` and `git diff --check` also
completed cleanly in the same verification command.

An earlier broader selection produced **76 passed, 6 failed**. Two failures
were stale tests corrected in the final 92-pass run (timeline verb census and
an invalid empty visualization fixture). Four failures remain in
`tests/packs/rendering/test_render_facade_run_ownership.py`:

- `test_facade_standalone_with_project_creates_one_run_json_and_rewrites_out_to_run_root`
- `test_facade_run_root_in_request_is_replaced_by_run_context_root`
- `test_facade_task_attached_reuses_run_context_without_new_run_json`
- `test_facade_task_attached_retains_caller_selected_output`

Those assert the retired direct executor-runner `run.json` ownership behavior;
the current runner explicitly delegates authoritative run/task ledgers to
kernel admission. They are not failures of the new managed render route and
were left unchanged.

The previously stale frozen-view assertions were modernized for durable CAS
manifests and rehydrated packs. Parent navigation now retains the original
durable source manifest instead of leaking a temporary rehydration path.
