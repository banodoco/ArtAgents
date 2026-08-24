# Timeline visualization and generation preflight UX fix

Date: 2026-08-23  
Surface: live SDK/runner usage (maker-facing agent UX)

## Finding

The discovered `rendering.timeline_visualize` contract and the executable
runner disagreed in several ways: discovery required `project_slug` even when
the SDK already carried `project=...`; the runner required `--out`; the
runner accepted only repeatable singular `--format`; and a managed timeline
could be selected only by its slug, not its UUID/ULID or an owned file. This
made otherwise reasonable discovered calls either fail before the pack or
admit a run that was certain to fail.

Invalid generation model/mode requests had the opposite ergonomics problem:
the typed preflight exception was correct and side-effect-free, but a generic
maker loop using `sdk.invoke` had to catch exceptions rather than consume the
same structured result shape as a failed admitted run.

## Changes

- `rendering.timeline_visualize` now treats `project_slug` as runner-derived
  when SDK `project`/`ASTRID_PROJECT_SLUG` supplies it.
- The public input schema documents a managed timeline directory or a file
  inside one, and accepts a list or comma-separated `formats` value (`png`,
  `svg`, `md`, or `all`). `all` cannot be mixed with another format.
- SDK pre-admission rejects contradictory `timeline_source`/`timeline_slug`/
  `all`, incomplete navigation pairs, invalid formats, and mismatched project
  identity with typed `CapabilityValidationError`; no ledger is created.
- SDK pre-admission also resolves canonical kernel timeline rows, including
  the project default, when no legacy event-log directory exists. Valid kernel
  rows are materialized into a private staging source for visualization;
  invalid foreign/missing refs still fail before admission.
- Timeline selectors accept stable slug, UUID, or ULID. Direct runner usage
  retains explicit `--out`; the managed SDK path owns output staging and
  publication.
- In-process executor commands now receive the same project-scoped
  environment as subprocess commands, so a bound SDK `project_root` cannot
  accidentally resolve the user's ambient workspace.
- Added `astrid.sdk.invoke_result(...)` as a JSON-safe sibling for maker loops.
  It serializes typed pre-admission `AstridSDKError`s into
  `InvocationResult(ok=False, error=...)`; exception-oriented `sdk.invoke` and
  typed `astrid.generate.*` APIs remain unchanged.
- Updated the rendering STAGE/skill, SDK reference, and focused SDK tests.
- Added the discovered public nested command `astrid timelines visualize`.
  It stays beneath the existing eight-family gateway, routes through the
  canonical `AstridClient.invoke_result` boundary, and exposes optional
  selected-project routing, default/slug/UUID/ULID selectors, repeatable or
  comma-separated `--format`, legacy `--timeline-source`, documented focus
  and frozen-view flags, and the stable `--json` envelope. Successful `data`
  includes run/kernel IDs and durable artifact records; typed validation
  failures retain null admission IDs. A positional timeline ref remains an
  accepted compatibility spelling, while `--timeline-slug` is the discoverable
  flag.

## Live proof

All live runs used disposable temporary project roots and the real packaged
runner; no user project was modified.

With ambient `ASTRID_PROJECTS_ROOT` and `ASTRID_PROJECT_SLUG` deliberately
unset, bound SDK invocations against a copied managed fixture timeline
returned `ok=True` in both the in-process and subprocess lanes for:

1. timeline UUID selector with `formats=["png", "svg"]`: 15 durable managed
   artifacts, including `manifest.json`, PNG and SVG pages;
2. project-owned `assembly.jsonl` source file with `formats=["md"]`: 10
   durable managed artifacts, including the manifest and reading guide.

The artifact paths were present as files below the temporary root's
`.astrid/media/sha256/...` store after completion. This proves the output is
published and consumable after staging cleanup.

`sdk.invoke_result(...)` live proofs returned structured validation envelopes
for an unknown generation model and unsupported mode, both with
`sdk_error=CapabilityValidationError` and `sdk_category=validation`; neither
created `.astrid/astrid.sqlite3`. Invalid visualization format, contradictory
selector, and `all`+`png` likewise returned structured validation envelopes
with no database.

A second fresh live journey used only the public timeline identity path:
`AstridClient.projects.create` → `client.timelines.create(...,
set_default=True)` → `client.timelines.save(...)`, with no hand-created
timeline directory. Visualization succeeded for project default, slug, UUID,
and the public ULID, producing 10 durable managed artifacts for each selector.
The kernel service emits lowercase ULID aliases while the legacy event-log
snapshot contract uses uppercase canonical IDs; the private kernel projection
normalizes that case for evidence without changing the kernel row.

The same journey was replayed through the public CLI with a disposable
`ASTRID_PROJECTS_ROOT`: `astrid timelines visualize --project edge-demo
--format md --json` succeeded for the project default and for `primary`, the
timeline UUID, and the public ULID, with synchronous run IDs and durable
artifact records. A foreign source supplied while targeting `other-demo`
returned exit 1 and `error.code=validation_error` with all run/task IDs null;
the SQLite run count was unchanged (4 before and after). This verifies the
CLI does not admit a doomed foreign-source request.

After `astrid projects select edge-demo`, the same command with no
`--project` also succeeded, confirming selected-project routing is wired at
the product gateway boundary rather than duplicated in the visualization
handler.

## Focused verification

Passed:

```text
python3 -m pytest -q tests/sdk/test_maker_preflight_contracts.py tests/core/generation/test_preflight.py tests/core/timeline/test_timeline_visualize_select.py
74 passed in 9.56s

python3 -m pytest -q tests/core/timeline/test_timeline_visualize_validate.py
14 passed in 0.35s

python3 -m pytest -q tests/v10/test_domain_cli_projects_timelines.py tests/test_canonical_aliases.py
82 passed, 24 subtests passed

Combined focused gate (SDK preflight, timeline selectors/validation, and
public CLI):

```text
python3 -m pytest -q tests/sdk/test_maker_preflight_contracts.py tests/core/generation/test_preflight.py tests/core/timeline/test_timeline_visualize_select.py tests/core/timeline/test_timeline_visualize_validate.py tests/v10/test_domain_cli_projects_timelines.py tests/test_canonical_aliases.py
170 passed, 24 subtests passed
```

python3 -m py_compile [changed SDK/runner/visualize modules]
```

The broader packaged executor file was intentionally not used as a gate: in
this shared worktree it currently reports 1 pass/8 failures in assertions for
manifest paths, staging roots, idempotent replay, and run logs. Those failures
are in the parent worktree's existing kernel/result-path cleanup behavior,
outside this UX fix; the live proof above verifies the new public behavior
directly.
