# Custody baseline — integrated Astrid workstreams

This record preserves the custody facts from both source runs. It is historical
provenance; the integration worktree and branch are recorded separately below.

## Unified-execution source custody

Captured at run start (2026-08-22), before mutation.

- HEAD: `b4c70e0ac766c69de0298fa19f3d7fede796a97c` (main @ b4c70e0a,
  "docs(round6b): correct three falsifiable run-ledger claims (Sol #5)").
- Run worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-unified-oracle`.
- Run branch: `oracle-unified-execution`.
- Source worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid`
  (branch `main`).
- Origin: `https://github.com/peteromallet/Astrid.git`; `origin/main` was
  `b4c70e0a` and equal to local main at capture.
- Other worktrees intentionally untouched: `/Users/peteromalley/Documents/Astrid-oracle`
  (`oracle-run`, `0b69557b`) and
  `/Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle`
  (`oracle-packification`, `0c93fd8a`).

### Protected main-worktree material at that capture

- Generation backends/model catalog/utilities, generation executor packs, and
  their tests/docs were user-owned in-flight work.
- `.megaplan/initiatives/{pluggable-timeline-renderers,timeline-visualization}/`
  and `.oracle/findings/stacked-render-proof.txt` were protected untracked work.
- The complete path inventory remains available in the unified-execution parent
  commit; no integration operation authorizes overwriting it.

## Phase-B source custody

Captured by the Phase-B run on its source line:

- Branch: `phase-b`, based on `oracle-run` / Phase-A tip
  `0b69557bfcca417bc32a3f0edff0753bac67712a`.
- Environment: `container reigh-phase-a-exec`, Python 3.11.11, dependencies
  installed.
- Protected material: reviewed `track-K/S/R` branches and the Astrid main
  checkout's owner WIP were not to be mutated by that run.
- Phase-B's frozen plan, tasklist, and exploration findings remain available in
  the Phase-B merge parent and are summarized in `.oracle/plan-v1.txt`.

## Integration custody

- Integration branch: `codex/phase-b-live-ux-integration`.
- Integration worktree: `/private/tmp/astrid-phase-b-integration.XnwUwK`.
- Inputs: current `main` at `d8335c9a59499bff48841bdb068780f19c8c3036` and
  refreshed `origin/phase-b` at merge time; these histories are divergent and
  are being merged as a history unit, not fast-forwarded.
- The active live-UX safety snapshot and protected owner WIP remain outside this
  conflict resolution. No push, tag, branch deletion, reset, or destructive
  cleanup is authorized by this record.

## Environment notes

The unified run recorded macOS arm64/Python 3.11.11 and constrained disk space.
The Phase-B run recorded the same Python line in its execution container. Any
GPU-only criterion must retain an explicit blocked/unavailable result rather than
silently substituting a cloud or GPU path.
