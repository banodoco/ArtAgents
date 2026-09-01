# Source custody — canonical pack beta

Captured 2026-08-30, Europe/Berlin, before worktree creation.

## Source

- Original checkout: `/Users/peteromalley/Documents/reigh-workspace/Astrid`
- Source branch: `codex/live-ux-pre-phase-b-20260824`
- Immutable source ref/base SHA:
  `7ac50c12e8e4d90988fee603ffdb9896e5628792`
- New worktree:
  `/Users/peteromalley/Documents/reigh-workspace/Astrid-canonical-pack-beta`
- New branch: `megado/canonical-pack-beta`
- Remote: `origin` → `https://github.com/peteromallet/Astrid.git`

## Protected original dirty state

The original checkout contained 570 pre-run status entries plus the newly
prepared `.oracle/prep/` directory. The pre-run baseline included 568 tracked
deletions (547 under `.oracle/`, 21 under `remotion/`), one modified
`storyboards/astrid-intro.storyboard.json`, and untracked `package-lock.json`.

Those changes belong to the user. The run must not modify, restore, stage, or
copy them. Git worktrees cannot safely transplant uncommitted state; the new
worktree therefore starts from the exact source SHA above. Only the canonical
pack run contract is re-established in the new worktree.

## Other protected worktrees at capture

- `/private/tmp/astrid-review-EnfYRv` (detached `63595879…`)
- `/private/tmp/astrid-stage1-review-6767` (detached `6767cb8b…`)
- `/private/tmp/astrid-stage1-review.zRRpbM` (detached `b0b83471…`)
- `/Users/peteromalley/Documents/Astrid-oracle` (`oracle-run`)
- `Astrid-beta-convergence` (`integration/astrid-beta-convergence`)
- `Astrid-live-main` (`main`)
- `Astrid-packification-oracle` (`oracle-packification`)
- `Astrid-stage1-beta` (`megado/astrid-stage1-beta`)
- `Astrid-stage1-convergence2` (`integration/astrid-stage1-product`)
- `Astrid-stage1-cutover` (`feat/stage1-astrid-client-cutover`)
- `Astrid-stage1-host` (`feat/stage1-generic-pack-host`)
- `Astrid-unified-oracle` (`oracle-unified-execution`)

No other worktree may be mutated or treated as authoritative.

## Environment

- Host: `Peters-Laptop.local`
- Darwin 24.4.0, arm64
- Shell: zsh
- Python: 3.11.11

Receipts must record this base SHA, cwd, actual model/provider, command,
timestamps, exit status, input/output digests, and North Star digest. They must
never retain secrets.
