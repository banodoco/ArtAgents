# Rework T1.1R2 — Fix baseline evidence issues (oracle re-review issue 1)

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. You
MAY edit files (file, web, terminal toolsets). Python:
`PYENV_VERSION=3.11.11`.

## Context

The Batch 1 re-review (`.oracle/checkins/batch-1-r1.md`, final ISSUES block,
issue 1) found two problems in `.oracle/baseline.md`. Fix ONLY these. A Sol
agent is fixing contracts/schemas/registry in parallel — do NOT touch
`astrid/core/rendering/`, `tests/core/rendering/`, `docs/contracts/`, or
production render code.

## Issue 1a — C0/C1 evidence mislabeled and not truly before/after

`baseline.md:51` labels results "C0 evidence", but line 53 says they ran at
`f8af4b2`/C1 and misidentifies C0. C1 changed shared pack/executor code, so
the "before" inference is invalid.

Rework:
- Run the SAME relevant suites at the ACTUAL C0 commit (`efbfcaa`) and at the
  current head in the same environment, and record exact deltas. Practical
  approach: use `git worktree add` for a C0 checkout (or `git -C` archive
  copy) under /tmp, run `pytest -q tests/packs/rendering
  tests/packs/test_audio_render.py tests/packs/hype tests/packs/iteration
  tests/packs/editorial` there, record pass/fail/skip counts and the failure
  names; then run the identical command in the current worktree and record.
  Note the C0 worktree needs the same PYENV_VERSION.
- Correct the section headers and labels: distinguish "C0 (efbfcaa)",
  "C1 (f8af4b2)", and "current head" evidence explicitly with commit ids.
- If running a second worktree is impractical in your sandbox, record C0
  evidence as: check out efbfcaa into /tmp via `git archive efbfcaa | tar -x
  -C /tmp/c0checkout` plus `git show efbfcaa` for any missing submodule/
  ignored files, run the suites there, and document the method.

## Issue 1b — Generated-source coverage maps the wrong test

`baseline.md:416` maps the "generated-source" row to unrelated URL/Hype
behavior instead of `tests/packs/rendering/test_remotion_element_generation.py:22`
(`test_generated_registries_use_element_scope_aliases`) and the rest of that
file (element-scope aliases, manifest component hashing).

Rework: correct the coverage map for props/theme/registry/staging/environment/
generated-source rows to point at the ACTUAL tests:
- `tests/packs/rendering/test_remotion_element_generation.py` (generated
  registries, element scope aliases, hashing);
- `tests/packs/rendering/test_render_remotion_registry.py` (env, staging,
  cleanup, provenance, secret non-leak);
- `tests/packs/hype/test_hype_e2e.py:1040` (registry + merged render props
  golden);
- `tests/golden/hype/` fixtures.
Verify each mapping by reading the test, and list any behavior with NO
coverage explicitly as a gap.

## Acceptance

- `.oracle/baseline.md` has correct C0/C1/head labels with commit ids and
  genuine before/after evidence for the named suite matrix.
- `.oracle/baseline.md` coverage rows point at the real test files/lines.
- No production code or other files changed (baseline.md only).

Run ONLY the pytest commands needed to gather the evidence (the two suite
runs above). Do NOT run the full suite, formatters, or linters. Do NOT touch
anything under `astrid/` or `tests/` (report-only doc changes). Preserve all
existing work. Report: the before/after evidence table, corrected mappings.
