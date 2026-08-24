# Phase-B merge graph audit

Date: 2026-08-24

Mode: read-only Git graph audit

Repository inspected: `/Users/peteromalley/Documents/reigh-workspace/Astrid`

Verdict: **the supplied direct-merge procedure is unsafe in the current
worktree and its ancestry assumptions are false**

No fetch, checkout, merge, reset, stash, commit, push, branch deletion, or ref
update was performed. The only repository write is this requested report.

## Executive result

- The current branch is `main` at
  `d8335c9a59499bff48841bdb068780f19c8c3036`.
- Local `main` and the locally cached `origin/main` are byte-identical at that
  commit (zero cached ahead/behind).
- There is **no local `phase-b` branch**.
- The locally cached `origin/phase-b` is
  `c8b68b994eae6ca50c33fd395d2207a377515c7e`.
- `origin/phase-b` is not an ancestor of `main`, and `main` is not an ancestor
  of `origin/phase-b`. A fast-forward in either direction is impossible.
- Their merge base is
  `dd1bbe3a872eb4adfaa644c7a377e9ab32bad160`.
- Since that merge base, cached `origin/main` has 25 unique commits and cached
  `origin/phase-b` has 57 unique commits.
- A read-only `git merge-tree` simulation finds 12 conflicted files and 22
  conflict hunks before considering any uncommitted work.
- The current shared worktree is extremely dirty. At the audit snapshot before
  writing this report it had 200 tracked modifications and 181 untracked files
  (381 dirty entries); 53 dirty paths overlap the committed tip-to-tip delta.
- `/workspace` does not exist on this machine. The attachment's assumed
  workspace is not this repository.

Therefore, do not merge, pull, switch branches, reset, stash, or delete a
branch in the current worktree. Preserve the active work first, refresh refs
when authorized, and perform the integration on a new clean integration
worktree/branch.

## Exact ref snapshot

```text
working tree  /Users/peteromalley/Documents/reigh-workspace/Astrid
branch        main
HEAD          d8335c9a59499bff48841bdb068780f19c8c3036
main          d8335c9a59499bff48841bdb068780f19c8c3036
origin/main   d8335c9a59499bff48841bdb068780f19c8c3036
phase-b       <missing>
origin/phase-b c8b68b994eae6ca50c33fd395d2207a377515c7e
remote        origin https://github.com/peteromallet/Astrid.git
```

HEAD subject:

```text
feat(runaway): typed timing with per-transition prompts, run-table FK, old files preserved
```

The cached `origin/main` reflog was last updated by push at
2026-08-23T14:02:21+02:00. The cached `origin/phase-b` ref was fetched at
2026-08-24T14:02:27+02:00. Because this audit was expressly forbidden from
fetching, these are local remote-tracking observations, not a guarantee that
GitHub still exposes the same tips at the time of a later merge.

## Requested commit identities

### `4cf58bec`

```text
full       4cf58beca911208b44d1c3b9174c00fde6a8ba1c
parent     5791ae1c268225b703a0bbbd2a84638c8d5e1091
author     Arnold Fixer <fixer@arnold.local>
date       2026-08-19T21:58:09+00:00
subject    chore(chain): pin astrid-first partnered-codex revision
```

This commit is an ancestor of both `main` and `origin/phase-b`. It is not the
phase-B tip and does not prove that main contains phase B. Distances:

```text
4cf58bec -> common merge base dd1bbe3a: 44 commits
4cf58bec -> origin/main:                 69 commits
4cf58bec -> origin/phase-b:             101 commits
```

Merging `4cf58bec` into current `main` would be a no-op; current `main` already
contains it. It would integrate none of phase B's 57 post-divergence commits.

### `0b69557b`

```text
full       0b69557bfcca417bc32a3f0edff0753bac67712a
parent     3cbb3224d69d2fccbf52877f49df61663f48ad7a
author     POM <peter@omalley.io>
date       2026-08-22T11:46:40+00:00
subject    converge: implement contracted gallery reads + managed-media content route (contract-lens fix)
exact ref  origin/oracle-run
```

`0b69557b` is not contained by `main`. It is contained by `origin/phase-b`, but
it is 22 commits behind the cached phase-B tip. Merging only this SHA would be
a partial integration and must not be described as merging phase B.

## Ancestry proof and counts

Commands and results:

```console
$ git merge-base origin/main origin/phase-b
dd1bbe3a872eb4adfaa644c7a377e9ab32bad160

$ git merge-base --is-ancestor origin/phase-b origin/main
exit 1

$ git merge-base --is-ancestor origin/main origin/phase-b
exit 1

$ git rev-list --left-right --count origin/main...origin/phase-b
25  57

$ git merge-base --is-ancestor 4cf58bec origin/main
exit 0
$ git merge-base --is-ancestor 4cf58bec origin/phase-b
exit 0

$ git merge-base --is-ancestor 0b69557b origin/main
exit 1
$ git merge-base --is-ancestor 0b69557b origin/phase-b
exit 0

$ git rev-list --left-right --count 0b69557b...origin/phase-b
0  22
```

The tip-to-tip tree delta is substantial:

```text
316 files changed, 50,660 insertions(+), 17,817 deletions(-)
```

The phase side has 43 first-parent commits and two merge commits after the
common base; the 57 count is the complete reachable phase-only set. Main has
25 first-parent/main-only commits after the base.

## Read-only merge simulation

This command does not update refs or the index:

```console
$ base=$(git merge-base origin/main origin/phase-b)
$ git merge-tree "$base" origin/main origin/phase-b
```

At the committed tips, it emits 22 conflict-marker pairs across these 12
files:

```text
.oracle/agent_goal.md
.oracle/custody.md
.oracle/findings/_report.json
.oracle/northstar.md
.oracle/plan-v1.txt
.oracle/tasklist.md
astrid/core/gateway/dispatch.py
astrid/core/repositories/tasks.py
astrid/packs/__init__.py
tests/integrations/reigh/test_local_bridge_server.py
tests/packs/test_generate_image_openai.py
tests/v10/test_m8_installed_journey.py
```

The simulation classifies 16 files as changed on both sides and four as added
on both sides. Some merge automatically; the 12 above do not. This is only a
committed-ref forecast. It intentionally excludes the current uncommitted
changes, many of which touch the same subsystems.

## Dirty-tree collision evidence

Before this report was added:

```text
tracked modified entries: 200
untracked files:          181
all dirty entries:        381
dirty paths overlapping origin/main..origin/phase-b: 53
```

The 53 overlapping paths include critical authority and runtime files such as:

```text
astrid/application.py
astrid/core/doctor.py
astrid/core/gateway/dispatch.py
astrid/core/integrations/reigh/local_bridge_server.py
astrid/core/io/media_import.py
astrid/core/kernel/read.py
astrid/core/repositories/media.py
astrid/core/repositories/projects.py
astrid/core/repositories/tasks.py
astrid/core/task_executor/service.py
astrid/packs/__init__.py
astrid/sdk/client.py
astrid/sdk/invocation.py
astrid/sdk/tasks.py
tests/integrations/reigh/test_local_bridge_server.py
tests/v10/test_m6_gate.py
```

Running a merge here could be refused by Git for paths that would be
overwritten. Even if Git allowed it, it would combine phase-B conflict
resolution with 381 unrelated in-progress entries, destroying the ability to
attribute or safely review the integration.

## Attachment assumptions versus this machine

| Assumption/procedure step | Observed reality | Assessment |
|---|---|---|
| Work in `/workspace/...` | `/workspace` is absent; this repo is under `/Users/peteromalley/Documents/reigh-workspace/Astrid` | Wrong environment/path |
| A local `phase-b` exists | Only cached `origin/phase-b` exists | `git merge phase-b` cannot name a local branch here |
| Current branch already contains phase B | Main contains shared ancestor `4cf58bec`, but not `0b69557b` or phase tip `c8b68b99` | False |
| Phase B is a strict descendant of main | Neither tip contains the other | False; two-sided merge required |
| `4cf58bec` identifies phase B | It is a 44-commit-pre-divergence shared ancestor | False; merging it is a no-op |
| `0b69557b` is the final phase commit | It is phase-only but 22 commits behind cached phase tip | False/incomplete |
| Merge can happen in the present checkout | 381 dirty entries, 53 overlapping paths, plus 12 committed-tip conflict files | Unsafe |
| A fast-forward merge is available | Both ancestry checks exit 1 | Impossible at current cached refs |
| Immediate push/delete after merge | Merge needs substantive resolution and validation; refs have not been refreshed in this audit | Unsafe and premature |

## Safe integration procedure

The following is a proposed later procedure, not something performed during
this audit. It requires authorization for network/ref mutations and requires
the current collaborative work to be preserved first.

1. **Do not touch this worktree's branch/index.** Let the active work be
   separated into its intended commits/branches by its owners. Do not use
   `reset --hard` or a blanket shared-worktree stash.
2. **Refresh and re-audit refs.** Once authorized:

   ```bash
   cd /Users/peteromalley/Documents/reigh-workspace/Astrid
   git fetch --prune origin
   git rev-parse origin/main origin/phase-b
   git merge-base origin/main origin/phase-b
   git rev-list --left-right --count origin/main...origin/phase-b
   ```

   If either tip differs from this report, repeat the ancestry and
   `merge-tree` audit before integrating.
3. **Create a separate clean integration worktree and branch** from refreshed
   `origin/main` (choose an unused absolute directory):

   ```bash
   git worktree add -b codex/phase-b-integration \
     /Users/peteromalley/Documents/reigh-workspace/Astrid-phase-b-integration \
     origin/main
   cd /Users/peteromalley/Documents/reigh-workspace/Astrid-phase-b-integration
   test -z "$(git status --porcelain)"
   ```

4. **Merge the actual refreshed phase tip, with inspection before commit:**

   ```bash
   git merge --no-ff --no-commit origin/phase-b
   ```

   Do not substitute `4cf58bec` or `0b69557b`. Resolve each conflict by
   contract/behavior, not by blanket `--ours` or `--theirs`, especially
   `gateway/dispatch.py`, `repositories/tasks.py`, and `packs/__init__.py`.
5. **Run focused tests for every conflict plus the complete Astrid suite.** At
   minimum, include the integration bridge, capability discovery/composition,
   task repository/lifecycle, generation, and installed-journey tests named by
   the conflict list. Inspect `git diff --check`, the merge diff, and the final
   two-parent commit graph.
6. **Commit and push an integration branch, not main:**

   ```bash
   git commit
   git push -u origin codex/phase-b-integration
   ```

   Review/merge that branch through the normal protected workflow. Direct
   `git push origin main` is not a safe mechanical continuation of the
   supplied procedure.
7. **Delete nothing yet.** Only after the reviewed integration is on the
   authoritative main, tests are green, and ancestry proves containment:

   ```bash
   git fetch origin
   git merge-base --is-ancestor origin/phase-b origin/main
   ```

   An exit code of 0 is necessary but deletion still requires explicit owner
   intent. Remote branch deletion is destructive and was not authorized by
   this audit.

## Unsafe commands/variants now

- `cd /workspace/...` — wrong host path.
- `git checkout main` / `git switch main` in this shared dirty worktree — may
  collide with or obscure active changes; it is already on main anyway.
- `git pull origin main` without `--ff-only` — combines fetch and merge and can
  create an unintended merge; this audit did not refresh the remote.
- `git merge phase-b` — no local ref exists.
- `git merge --ff-only origin/phase-b` — ancestry proves it cannot fast-forward.
- `git merge 4cf58bec` — no-op, not phase B.
- `git merge 0b69557b` — partial phase integration, missing 22 commits.
- `git merge origin/phase-b` in the current worktree — committed histories
  already conflict, and 53 phase-delta paths also have uncommitted changes.
- `git reset --hard`, blanket `git stash`, or `git clean` — destructive to
  unrelated shared work.
- immediate `git push origin main` or phase-branch deletion — premature before
  conflict resolution, validation, review, refreshed-ref proof, and explicit
  authority.

## Bottom line

Phase B has **not** already landed on this main. It is a substantial divergent
line whose cached tip is `c8b68b99`, not either SHA highlighted by the
attachment. Integration is feasible, but it is a real reviewed merge project,
not a fast-forward cleanup command. The present shared worktree is the wrong
venue for it.
