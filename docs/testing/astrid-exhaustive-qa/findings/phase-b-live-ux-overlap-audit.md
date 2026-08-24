# Phase-b / live-UX overlap audit

Date: 2026-08-24  
Audit mode: read-only Git/ref/worktree inspection; this report is the only file created  
Current branch/HEAD: `main` at `d8335c9a59499bff48841bdb068780f19c8c3036`  
Candidate: `origin/phase-b` at `c8b68b994eae6ca50c33fd395d2207a377515c7e`  
Merge base: `dd1bbe3a872eb4adfaa644c7a377e9ab32bad160`

## Verdict

Do not merge, pull, switch, reset, or stash phase-b in the current worktree.

This is not a fast-forward integration. `main...origin/phase-b` is `25 / 57` commits divergent, neither tip is an ancestor of the other, and a clean three-way merge already predicts 12 content conflicts. The live worktree then adds 15 modified tracked paths also changed by phase-b plus one differing untracked path that phase-b adds. A direct merge in this worktree will be refused before useful integration can begin, and attempting to force it would put a large, partly untracked UX wave at risk.

The safest route is:

1. stop concurrent writers/agents;
2. preserve the entire live worktree on a dedicated safety branch with a real temporary commit (including intended untracked files);
3. create a new integration worktree from clean `main`;
4. merge `origin/phase-b` there and resolve the 12 branch-history conflicts first;
5. replay the live-UX snapshot onto that resolved merge, reconciling the 16 live overlaps by domain;
6. run phase-b and live-UX gates together; and
7. only then fast-forward `main` to the verified integration branch.

Keep the safety branch until the combined tree has passed the full validation gate.

## Inventory at audit snapshot

The worktree was actively dirty. The counts below were captured immediately before this report was added; this report itself adds one more untracked path under `docs/testing`.

```text
phase-b delta paths (merge-base..phase-b): 166
dirty tracked paths (HEAD..worktree/index): 201
untracked paths:                            181
all dirty paths:                            382

exact phase/live path overlaps:              16
  tracked modified overlaps:                 15
  untracked add/add overlap:                  1

phase-b paths disjoint from dirty paths:    150
dirty paths disjoint from phase-b:          366
phase-b files absent from current HEAD:     109
```

No phase-b delta file is byte-identical to either current `HEAD` or the current worktree. There is therefore no whole-file phase change that can simply be discarded as already present.

The 150 phase-disjoint paths are mostly phase-b's new Reigh task/orchestrator bridge, model setup/acquisition, Wan2GP/VibeComfy bindings, generation tables/repository, workflows, and their test corpora. The 366 live-disjoint paths are mostly the broad CLI/SDK live-UX corrections, pack `STAGE.md` contract updates, 145 QA reports, timeline/rendering implementation, and corresponding SDK/core tests. Exact path disjointness makes these lower-risk, not semantically independent; the combined gate remains required.

## Branch-history conflicts before live changes are considered

A non-writing three-input `git merge-tree <base> HEAD origin/phase-b` predicts 12 conflict files in a clean worktree:

### Oracle/bookkeeping conflicts

- `.oracle/agent_goal.md` — add/add
- `.oracle/custody.md` — add/add
- `.oracle/findings/_report.json` — modify/modify
- `.oracle/northstar.md` — add/add
- `.oracle/plan-v1.txt` — add/add
- `.oracle/tasklist.md` — modify/modify

These should be resolved as provenance records, not with blanket `ours` or `theirs`. Preserve the completed histories from both lines or regenerate the authoritative combined bookkeeping if the Oracle format has a documented merge procedure.

### Product/test conflicts

- `astrid/core/gateway/dispatch.py`
- `astrid/core/repositories/tasks.py`
- `astrid/packs/__init__.py`
- `tests/integrations/reigh/test_local_bridge_server.py`
- `tests/packs/test_generate_image_openai.py`
- `tests/v10/test_m8_installed_journey.py`

These conflicts exist between committed `main` and phase-b even after all current live edits are safely removed from the worktree. They must be resolved and tested as the first integration layer.

## Live worktree versus phase-b classification

### Disjoint

- 150 of phase-b's 166 paths do not have a current tracked or untracked live edit.
- 366 of the live tree's 382 dirty paths are not changed by phase-b.
- All 145 current `docs/testing` paths are disjoint from phase-b.
- The new managed-render, generation-preflight, project-workspace, kernel-database, and SDK live-regression files are disjoint by exact path from phase-b.

These files should flow through the integration mechanically once branch-history conflicts are resolved. Do not infer that they are behaviorally independent: phase-b changes schemas, task completion, bridge composition, and store lifecycle used by many live-UX paths.

### Identical/redundant

There are zero byte-identical files.

One evidence artifact is semantically redundant but not identical:

- `.oracle/findings/stacked-render-proof.txt`

The current worktree has this file untracked, while phase-b adds a tracked version. Both record the same test, planner/finalizer, 24-frame 320x180 output, and layer ordering, but differ in pixel format (`yuvj420p` versus `yuv420p`) and sampled text RGB. Their Git blob IDs are different:

```text
worktree: 125547613880233b2b3f4eac1dbb2d2253bd9a5e
phase-b:  2c4492a406bf276bc6b14471c272f5a2d0db9965
```

Operationally this is a hard untracked-file blocker: Git will not overwrite it with phase-b's added file. Semantically it should not be line-merged or arbitrarily choose one historical machine result. Preserve both in the safety snapshot, then rerun the proof on the final integrated tree and publish one newly generated canonical record.

### Overlapping but compatible with deliberate reconciliation

These nine tracked paths carry distinct concerns that should coexist. They may still produce patch/context conflicts when the live snapshot is replayed.

| Path | Live-UX change | Phase-b change | Resolution |
|---|---|---|---|
| `astrid/core/io/media_import.py` | Reject undecodable audio/video before admission | Publish managed bytes before `BEGIN IMMEDIATE`; presence validation primitives | Preserve both. Re-run media import rejection and phase fault/atomicity tests. |
| `astrid/core/repositories/media.py` | Multi-location verification selectors and clearer results | Pre-published media completion boundary | Preserve both repository APIs and transaction ordering. |
| `astrid/core/task_executor/service.py` | Durable error/result propagation and staging behavior | Named `TaskHandler` binding registry | Preserve both; check imports and exported public names. |
| `astrid/packs/shots/repository.py` | Actionable media errors and removal result ergonomics | Export phase-b `GenerationRepository` | Preserve the local read-model changes plus the generation export. |
| `astrid/packs/timeline/schema-pack.yaml` | `timeline.unarchived` event and `timeline.unarchive` command | `timeline.registry_merged` event | Register all three; do not choose one event family. |
| `astrid/sdk/exceptions.py` | Broad typed/actionable service error mapping | `WriterSidecarError` mapping | Preserve the sidecar mapping inside the newer mapper; check import duplication and redaction. |
| `remotion/remotion.config.ts` | External pack element aliases | Chromium renderer `angle` to `swangle` | Keep `swangle` and the alias overlay. Run typecheck and a real render. |
| `tests/v10/test_m6_gate.py` | Serve route-discovery and doctor-state assertions | Standard schema table count 20 to 22 | Keep the new UX assertions and phase's 22-table expectation. |
| `tests/v10/test_registry.py` | Optional-manifest/no-discovery guard plus builder/checksum parity | Shots v2 table count and ownership assertions | Preserve the allowlist/parity guard and update its catalog expectations to phase's 22-table schema. |

### High-conflict live overlaps

These six paths combine changes within the same authority/lifecycle functions. Do not resolve them with whole-file `ours`/`theirs`.

| Path | Why high conflict | Required combined behavior |
|---|---|---|
| `astrid/core/doctor.py` | Live UX adds `uninitialized/ready/unhealthy`, external locator verification, and canonical DB authority; phase-b adds `doctor setup`, deep repair, acquisition, and journal reconciliation in the same parser/main flow | Plain read-only doctor retains the state envelope and no repair; explicit setup mode owns repair/networking and reports it honestly. |
| `astrid/core/gateway/dispatch.py` | Already a committed branch conflict; live changes add help-before-client composition and serve ownership/routes guidance, while phase-b adds boot-manifest fencing and sweeper shutdown | Help remains DB-free; serve verifies/stamps the boot manifest before advertising; shutdown stops sweeper and closes composition; ownership errors remain typed/actionable. |
| `astrid/core/integrations/reigh/local_bridge_server.py` | Phase-b adds roughly 725 lines of trust-token, multipart, task, gallery, and workflow routes; live UX adds `/routes`, asset GET/HEAD, save schema, and persisted-save correction in the same handler | Discovery must enumerate the final route set, all phase mutation/trust gates remain enforced, HEAD/body behavior stays correct, and timeline saves reach the canonical writer exactly once. |
| `astrid/core/repositories/tasks.py` | Already a committed conflict; live changes substantially reshape dependency projections, validation, retries, and failure evidence while phase-b adds completion/orchestrator/generation settlement | Preserve phase completion atomicity and child gates together with the live operator/error contract. Validate attempts, events, receipts, dependencies, retry, and failure persistence. |
| `astrid/packs/__init__.py` | Already a committed conflict in the standard bridge composition; live change adds typed store-owner recovery while phase-b adds setup journal replay and lease sweeper lifecycle | One canonical writer/lock; journal recovery before open; sweeper tied to composition lifecycle; typed owner guidance; deterministic close order. |
| `astrid/packs/timeline/repository.py` | Live work broadly changes archive/unarchive, identity, validation, history/diff, and read models; phase-b adds completion-time registry merge and its event in the same repository/head authority | Keep registry merge additive and receipt-free within completion UoW while preserving archive fences, unarchive authority, version/head behavior, and live read models. |

## Why direct integration is unsafe

### Fast-forward

Impossible. Both ancestry probes fail:

```text
HEAD is ancestor of origin/phase-b: false
origin/phase-b is ancestor of HEAD: false
git rev-list --left-right --count HEAD...origin/phase-b: 25 57
```

`git pull --ff-only` or `git merge --ff-only origin/phase-b` cannot integrate these histories even with a clean worktree. Moving the branch ref directly to phase-b would abandon the 25 current-main commits and is not an integration strategy.

### Normal merge in the current worktree

Unsafe and likely refused:

- 15 locally modified tracked files are also changed by phase-b;
- phase-b would add an untracked file already present with different bytes;
- 181 total untracked paths are not protected by an ordinary tracked-only stash;
- the tree was being updated by multiple agents during this audit; and
- the underlying clean histories already conflict in 12 files.

### Stash

`git stash` without `-u` loses coverage of the 181 untracked paths. `git stash -u` would include them but leaves the entire large UX wave in one opaque, easy-to-drop stash and later produces the same replay conflicts. Ignored files would still not be captured. A real safety branch and commit are easier to inspect, diff, recover, and retain until validation is complete.

### Cherry-picking all phase-b commits

Not recommended. Phase-b contains 57 commits, including merge/convergence history. Replaying them individually over current main would repeatedly surface conflicts and can invalidate phase-b's own sequencing/provenance. Merge the phase-b tip as a history unit.

## Recommended integration sequence

No step below was executed by this audit.

1. **Quiesce the tree.** Stop all agents/processes that can edit Astrid. Capture fresh `git status --porcelain=v2`, tracked diff, untracked inventory, and current refs. The counts above are a point-in-time snapshot, not a lock.
2. **Audit untracked material.** Confirm no secrets, local media, databases, renderer caches, or generated dependency trees are among the 181 untracked paths. The source/tests/QA reports and both megaplan initiatives appear intentional; do not blindly `git add -A` without this check.
3. **Create a lossless safety branch from current `main`.** Use a name such as `codex/live-ux-pre-phase-b-20260824`. Commit every intended tracked and untracked live change. Prefer thematic commits if feasible (kernel/CLI, timeline/render, generation/media, docs/tests); at minimum create one complete WIP snapshot commit before any integration operation.
4. **Verify the snapshot.** The safety branch should be clean, and `git diff main..codex/live-ux-pre-phase-b-20260824` should account for every intended change. Retain an external patch/tar only for intentionally uncommitted or ignored local material.
5. **Create a dedicated integration worktree from clean `main`.** After the current worktree switches to the safety branch, `main` is free for a new `codex/phase-b-live-ux-integration` worktree. Do not reuse the existing Oracle/extension/editor worktrees.
6. **Merge `origin/phase-b` into that clean integration branch with a merge commit.** Resolve the 12 predicted branch-history conflicts first. Run phase-b's focused bridge/task/setup/generation/schema gates before introducing live-UX changes.
7. **Replay the live snapshot onto the resolved phase merge.** Apply thematic commits one at a time. If only one safety snapshot exists, apply it without finalizing, reconcile the 16 overlaps by the tables above, review the complete diff, then commit the live layer.
8. **Regenerate the stacked-render proof.** Do not pick either historical pixel sample. Run the proof against the integrated renderer configuration and replace the artifact with that result.
9. **Run combined validation.** At minimum: registry/migration and 22-table gates; task/attempt/run/event/receipt suites; Reigh bridge/trust/gallery/task routes; doctor plain/setup; backup/restore; media fault atomicity; timeline archive/unarchive/registry merge/render/visualize; Remotion typecheck and real render; SDK/CLI live-UX slices. Finish with the broad suite used by phase-b.
10. **Promote only after green.** With the original safety branch retained, switch the original worktree back to `main` and fast-forward `main` to the verified integration branch. At this final step a fast-forward is appropriate because the integration branch was built from current `main` and contains both lines.
11. **Keep recovery refs.** Do not delete the safety or integration branches until the merged tree has been used successfully and the remote is updated.

## Resolution rules for the integrator

- Never use whole-file `--ours` or `--theirs` on the six high-conflict product files.
- Preserve phase-b's schema v2/22-table migration; do not retain stale live test expectations of 20 tables.
- Preserve the live explicit standard-pack allowlist: optional `runaway` remains excluded unless separately composed; phase-b's shots v2 remains inside the already-selected shots pack.
- Preserve one canonical database writer, owner lock, and migration registry across bridge/sweeper/live UX.
- Treat test conflicts as contract decisions, not cleanup noise. A test deleted solely to make the merge green is a regression unless the corresponding contract was intentionally retired.
- Resolve Oracle artifacts separately from product code so bookkeeping choices cannot hide product conflict resolution.

## Evidence commands

All were read-only:

```text
git status --short
git branch -a -vv --no-abbrev
git worktree list --porcelain
git merge-base HEAD origin/phase-b
git merge-base --is-ancestor HEAD origin/phase-b
git merge-base --is-ancestor origin/phase-b HEAD
git rev-list --left-right --count HEAD...origin/phase-b
git diff --name-status <merge-base>..origin/phase-b
git diff --numstat HEAD -- <overlap paths>
git diff --numstat <merge-base>..origin/phase-b -- <overlap paths>
git merge-tree <merge-base> HEAD origin/phase-b
git hash-object .oracle/findings/stacked-render-proof.txt
git rev-parse origin/phase-b:.oracle/findings/stacked-render-proof.txt
```

No branch, index, stash, ref, worktree, or product file was changed by this audit.
