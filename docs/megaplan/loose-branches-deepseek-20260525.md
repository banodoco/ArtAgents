# Loose Branch DeepSeek Investigation - 2026-05-25

## Rationale

This records the read-only DeepSeek fan-out used to refine the Astrid loose-branch cleanup survey. The first pass found no dirty current checkout state, no stashes, and no dirty Astrid worktrees. The remaining ambiguity was mostly whether several large or stale branches were valuable, superseded, or safe to delete.

## Provenance

Fan-out run:

- Briefs: `/tmp/astrid-loose-branches-deepseek-20260525-114852/briefs`
- Results: `/tmp/astrid-loose-branches-deepseek-20260525-114852/results`
- Model: `deepseek:deepseek-v4-pro`
- Toolsets: `terminal,file`
- Tasks: 5/5 succeeded

Primary result files:

- `01-reshape-main.txt`
- `02-pack-system-pr8-port.txt`
- `03-git-backed-packs-chain.txt`
- `04-open-pr-and-locked-worktree.txt`
- `05-nonbranch-loose-state.txt`

## Verdicts

| Work | Current state | Verdict | Reason |
| --- | --- | --- | --- |
| `reshape` | local+remote, current checkout, `15/0` vs `main`, `cherry +12` | PR-then-merge | Coherent sprint integration branch; `git merge-tree` has zero conflict markers against `main`; large diff is dominated by generated-artifact cleanup and test/system changes that should run through CI. |
| `reshape-s5a-hype-port` | local+remote, PR #35 merged into `reshape`, `0/2` vs `reshape`, `cherry +0` | delete after preserving `reshape` | Fully consumed by `reshape`; no unique patch remains against its true base. |
| `pack-system-pr8-port` | local-only clean worktree, `1/0` vs `main`, `cherry +1` | PR-then-merge | Single large but coherent port of PR #8 operational substrate; zero merge-tree conflict markers against `main`; preserves installed-pack infrastructure, pack restructure, tests, and example pack work. |
| `origin/megaplan/git-backed-packs/sprint-02-resolver-runtime` | remote-only draft PR #8 | keep until `pack-system-pr8-port` lands, then close/delete as superseded | PR #8 remains the remote provenance/source until the curated port is merged. |
| `megaplan/git-backed-packs-chain-setup` | local+remote, PR #27 merged but `2/5` vs `main`, docs-only | delete, do not cherry-pick as-is | The two remaining commits are a stale PR #8 port spec and a partially stale consolidation-plan addendum. If archival docs are wanted, write an updated addendum instead of cherry-picking. |
| `feature/per-project-plan-md` | local+remote open PR #26, clean locked agent worktree, `1/74` vs `main` | rebase/update PR, then merge | Additive `plan.md` project scaffold remains absent from both `main` and `reshape`; only one small conflict in `_core/skill/SKILL.md`. |
| `.claude/worktrees/agent-ac695704cdc5ac656` | locked clean worktree for PR #26 | remove only after PR #26 lands or is closed | No uncommitted work, but it pins the branch and should follow the PR decision. |
| `/Users/peteromalley/Documents/.megaplan-worktrees/pr8-ref` | clean detached worktree at PR #8 tip | remove after PR #8 is closed/deleted | No unique local work; tip is reachable from `origin/megaplan/git-backed-packs/sprint-02-resolver-runtime`. |

## Corrections To First Survey

- `.gitmodules` exists and declares `astrid/packs/seinfeld/ai_toolkit/upstream` from `https://github.com/ostris/ai-toolkit.git`. It is a third-party dependency, not same-origin loose Astrid work.
- The dirty sibling `/Users/peteromalley/Documents/reigh-workspace/astrid-projects` is a different repo (`banodoco/reigh-workspace`) and is out of scope for Astrid branch cleanup.
- The detached `pr8-ref` worktree is not unique local work; it is a convenience checkout of the remote PR #8 tip.
- The 192 unreachable commits look like routine rebase/amend/megaplan checkpoint noise. Snapshot their subjects before any aggressive `git gc --prune=now` if recovery confidence is needed.

## Recommended Execution Order

1. Open PR `reshape` -> `main`; merge when CI passes.
2. Delete `reshape-s5a-hype-port` local and remote after `reshape` is protected by PR/merge.
3. Open PR `pack-system-pr8-port` -> `main`; merge when validated.
4. Close PR #8 and delete `origin/megaplan/git-backed-packs/sprint-02-resolver-runtime` only after the port lands.
5. Delete `megaplan/git-backed-packs-chain-setup` local and remote. Write a fresh archival addendum only if desired.
6. Rebase/update PR #26 (`feature/per-project-plan-md`), resolve the `_core/skill/SKILL.md` conflict, merge, then remove its locked worktree and delete local/remote branch.
7. Remove clean redundant worktrees (`pack-system-run`, `pr8-ref`, and spent branch worktrees) after their branch decisions complete.

## Cross-Checks Run Locally

- `main <- reshape`: `0/15`, `cherry +12`, `merge-tree` conflict markers `0`
- `reshape <- reshape-s5a-hype-port`: `2/0`, `cherry +0`, `merge-tree` conflict markers `0`
- `main <- pack-system-pr8-port`: `0/1`, `cherry +1`, `merge-tree` conflict markers `0`
- `main <- feature/per-project-plan-md`: `74/1`, `cherry +1`, `merge-tree` conflict markers `1`
- `main <- megaplan/git-backed-packs-chain-setup`: `5/2`, `cherry +2`, `merge-tree` conflict markers `0`
