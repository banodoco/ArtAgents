# Loose-work consolidation plan — Astrid

Date: 2026-08-14. Status: approved (full strategy + preserve-to-archive). Repo: github.com/peteromallet/Astrid, main @ d93ec0ce.

## Rationale

Post-epic cleanup. Remote is already clean (only origin/main; all PRs merged/closed June). Loose work is local: 6 local branches, 8 worktrees, and uncommitted payloads in three of them. The inverted-risk insight: the highest-risk item is a complete, oracle-validated epic (timeline-vlm-plan) sitting on a local branch with no PR, plus its worktree's dirty payload — not the merged branches.

## Landscape

- Completed + merged epics: three.js, Layer Stack (both with residual worktrees/oracle artifacts).
- Active epic: astrid-first (m1-m8, running locally, KEEP — out of scope).
- Complete-but-unmerged epic: timeline-vlm-plan (VLM timeline navigation, B1-B10, R25 oracle PASS).
- Planning venue: oracle-packification (KEEP — active megado execution venue for the packification plan).

## Everything valuable → where it lands

| Work | Current state | Lands as |
|---|---|---|
| timeline-vlm-plan (28 commits) | local branch, no PR, dormant chain | PR-then-merge to main (rebase, resolve 8 conflicts, merge, delete branch) |
| timeline-vlm dirty payload (69 M + 42 ??) | worktree uncommitted | Snapshot to .oracle/prior-runs/timeline-vlm-dirty-<date>/ (churn = nothing lost; divergent pieces preserved for later triage), then remove worktree |
| oracle-run 2 cleanups (dup-stub removal, indent fix) | worktree uncommitted | Commit directly to main |
| layer-plan 61 oracle artifacts | worktree untracked | Archive → .oracle/prior-runs/layer-stack/{briefs,findings,checkins}/ |
| threejs 52 oracle artifacts | worktree untracked | Archive → .oracle/prior-runs/threejs/{briefs,findings}/ |

## Everything else → delete (positive evidence)

| Branch | Evidence |
|---|---|
| agent/provider-independent-experiments | 3 commits byte-identical to main (re-committed via b768588e pre-epic dirty-tree commit); merge conflicts resolve to main |
| layer-plan | merged (cherry +0); only 61 untracked artifacts (archived) |
| oracle-run | merged (cherry +0); dirty files handled (2 landed, 1 discarded as doc-vs-code contradiction + colliding with legacy_hybrid rename) |
| oracle-run-threejs | merged (cherry +0); untracked artifacts archived, junk (mp3/.codex/.vscode) deleted |
| astrid-c5 worktree | detached, clean, HEAD 9d1dfd92 on main — stale temp |

## Per-decision verdicts

- timeline-vlm: LAND. DeepSeek verdict: complete epic, 8-file conflict surface (favor main's gateway/SKILL.md plumbing, keep branch's timeline.py/runner.py; add/add audio-reactive test → main's copy). Sanity-check overlap with main's pluggable-timeline-renderers direction during merge.
- experiments: DELETE (no cherry-pick — nothing unique).
- oracle-run grammar tightening: DISCARD (validator still accepts `_`; contradicts code; superseded by packification's legacy_hybrid → hybrid rename).
- Chain liveness: timeline-visualization chain dormant (static Jul 29 artifacts, no logs/tickets).

## Corrections forced by investigation

- Initial read: "oracle-run dirty diff is Layer Stack-era contract work" → agent proved 2 of 3 files are genuine main defects worth landing, and the doc change is a doc-vs-code contradiction to discard.
- Initial read: "timeline-vlm dirty worktree is the epic's in-progress state" → agent proved the payload is churn (matches main) + unrelated divergent work; the epic itself is committed and complete.

## Execution order (lowest blast radius first)

1. `git worktree prune`
2. Land 2 tiny cleanups on main (surgical edits + commit)
3. Preserve artifacts (copy into .oracle/prior-runs archives, commit; delete approved junk)
4. Snapshot timeline-vlm dirty payload → archive; land timeline-vlm (rebase, resolve 8 conflicts, push, PR, merge, verify tests); delete branch + remove worktree
5. Delete consumed branches + worktrees: experiments, layer-plan, oracle-run, oracle-run-threejs, astrid-c5
6. Verify: git branch, worktree list, status; report

KEEP: main checkout, astrid-first epic, oracle-packification worktree (execution venue), tags, orphans (surface only).

## Provenance

DeepSeek V4 Pro fan-out (3 agents, /tmp/loose-branches-results/): 01-timeline-vlm.txt (LAND verdict), 02-experiments.txt (DELETE verdict), 03-oracle-run-dirty.txt (cherry-pick-parts verdict). Survey: read-only git commands, this session.
