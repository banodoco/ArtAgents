# Program runbook — the autonomous loop reads THIS first

Forward-looking "current state → exact next action → stopping condition" for the whole program.
Survives compaction. The hourly `/loop` and any resuming instance should read this top-to-bottom, do the
**next unchecked action**, update the checkbox + the "STATUS" line, and (if the epic is running) run the
babysit cycle. Backward-looking detail lives in `RESTRUCTURE-PROGRESS.md`; infra fixes in memory.

## STATUS (update this line every time you act)
2026-06-10: **Restructure DONE + pushed** (24→6 cycles). **EPIC LAUNCHED & RUNNING** (actions 1–4 done).
The capability-waist chain is driving in worktree `~/Documents/.megaplan-worktrees/capwaist` (branch `capwaist`,
forked from `astrid-capability-waist`@`c2e593f`), `--no-push` LOCAL-COMMIT mode, vendor=claude, native Shannon.
Log: `/tmp/capwaist-chain.log`. **02:42 babysit:** s0 advanced plan→critique→revise→**execute** cleanly;
**Shannon capture VALIDATED** (no TUI-scrape stall — no transcript-read fix needed). s0 now executing.
**NEXT: at next fire, check the s0 HARD-GATE outcome** — if gate PASS, chain auto-advances to s1 (keep
babysitting); if gate FAIL (s0's stop-and-replan condition: scoped-config can't be made clean) → that's an
architectural go/no-go → STOP and surface to operator, do not force.

## The program (3 user goals, in order)
1. ✅ Execute `RESTRUCTURE-PLAN.md` directly (no megaplan) — DONE, at the cycle floor of 6.
2. ⬜ Run the **capability-waist megaplan epic** (`docs/migration/capability-waist/chain.yaml`) on top.
3. ⬜ Hourly `/loop` babysits the epic and unblocks anything — incl. fixing the megaplan repo at depth.

## STANDING MANDATES (operator, do not violate)
- **Fix every issue at the DEEPEST level — no band-aids.** (esp. the Shannon output-capture fix below.)
- **Don't ask questions** — use judgment, push to completion.
- **vendor = claude** for the epic (override the chain's `vendor: codex`; Codex rate-limited until Jun 11).
- Commit **explicit paths, never `git add -A`**. Work on `astrid-capability-waist` (the epic's base_branch).
- Hard architectural go/no-go calls (e.g. epic S0 HARD GATE fails, S4 says "split if it bloats") → STOP and
  surface to the operator. The loop unblocks mechanical/environmental snags, not architecture decisions.

## NEXT ACTIONS (ordered — do the first unchecked one)

- [ ] **1. Push the restructure.** `git -C <repo> push -u origin astrid-capability-waist`. (Backs up 24→6 work.
      Do NOT merge to main yet — main merge is the very last step, after the epic.)
- [ ] **2. Reconcile the autonomous epic chain.** The autonomous version (no human gates) lives on the
      `capability-waist-epic` worktree (`/Users/peteromalley/Documents/.megaplan-worktrees/capability-waist`,
      3 commits ahead: `61dd83e`/`001286d`/`bf4cf93` "Make the epic fully autonomous"). Bring those onto
      `astrid-capability-waist` (cherry-pick or merge the chain.yaml/briefs changes) so the chain we run is the
      autonomous one with `vendor: claude`. Verify `docs/migration/capability-waist/chain.yaml` has no human gates
      and vendor=claude (override if not).
- [ ] **3. Pre-empt the Shannon output-capture failure (DEEPEST fix).** Before/at launch, validate then apply the
      fix in `megaplan/vendor/shannon/index.ts`: keep DRIVING the interactive TUI but READ the result from
      `~/.claude/projects/<hash>/<session-id>.jsonl` (Shannon owns `--session-id`) instead of scraping the rendered
      pane. Validate first: confirm that `.jsonl` flushes promptly+completely in interactive mode (tail it during a
      live run). See memory `reference-megaplan-shannon-under-load` for the full diagnosis + knobs. PYTHONPATH-pin
      `~/Documents/megaplan`; patch the VENDORED shannon (not ~/Documents/shannon or npm global).
- [ ] **4. Launch the epic.** `PYENV_VERSION=3.11.11 megaplan chain start --spec docs/migration/capability-waist/chain.yaml`
      (from the repo; confirm base_branch=astrid-capability-waist). Milestones s0→s5; s0 is a HARD GATE.
- [ ] **5. Babysit to completion** (the recurring loop body — see below).
- [ ] **6. STOPPING: when the chain is `done`** — tear down the loop (omit ScheduleWakeup), merge
      `astrid-capability-waist` → `main`, push main, write the completion report, persist outcome to memory.

## LIVE CHAIN SPECIFICS (as launched 2026-06-10)
- Worktree: `~/Documents/.megaplan-worktrees/capwaist` (branch `capwaist`). Log: `/tmp/capwaist-chain.log`.
- Status (read-only): `MEGAPLAN_SHANNON_CLAUDE_CONFIG_MODE=native PYENV_VERSION=3.11.11 megaplan chain status --spec docs/migration/capability-waist/chain.yaml` (run from the main Astrid checkout).
- Process check: `pgrep -fl 'chain start --spec docs/migration/capability-waist'`. Plan dirs: `~/Documents/.megaplan-worktrees/capwaist/.megaplan/plans/`.
- **RE-DRIVE if the process died but the chain isn't done** (resumes from persisted state; does NOT recreate the worktree):
  `cd /Users/peteromalley/Documents/reigh-workspace/Astrid && MEGAPLAN_SHANNON_CLAUDE_CONFIG_MODE=native PYENV_VERSION=3.11.11 megaplan chain start --spec docs/migration/capability-waist/chain.yaml --project-dir ~/Documents/.megaplan-worktrees/capwaist --no-push` (run in background). Do NOT re-pass `--in-worktree` (worktree already exists). Do NOT use `--fresh` (would discard progress).
- Integration model: `--no-push` → each milestone commits LOCALLY onto `capwaist`. At the END, push `capwaist` and merge it (with the restructure) into `main`.
- Contention: the arnold chain (`/private/tmp/arnold-target`, vendor=codex, rate-limited) may also be live — heavy concurrent Shannon/claude load is the documented failure mode. Don't kill arnold (operator's). If our Shannon phases stall under load, that's a signal to apply the transcript-read fix (action 3), not to raise timeouts.

## BABYSIT CYCLE (run this body each hourly fire while the epic is live)
1. **Status:** the megaplan CLIs may be approval-gated in autonomous fires — prefer reading JSON directly:
   newest `.megaplan/plans/<outcome-*>/state.json` + `events.ndjson` mtime; `pgrep -fl 'megaplan|codex|shannon'`;
   growing `execution_batch_*.json` count + `git status` file count. (codex/shannon phases don't stream events —
   silence ≠ dead; judge by rollout mtime / batch count.)
2. **If blocked:** diagnose the actual error (read the plan dir logs / `plan_v*_raw.txt`). Fix at the deepest level —
   including editing the **megaplan repo itself** (`~/Documents/megaplan`, vendored shannon, engine). Common ones:
   Shannon capture (apply action 3), DeepSeek SSE stall (HERMES_STREAM_CONTENT_STALL_TIMEOUT), readiness window.
   See memories: `reference-megaplan-shannon-under-load`, `reference_megaplan_deepseek_sse_stall`, `reference_codex_worker_liveness`.
3. **Parity oracles:** the epic is strangler/parity-gated. If an oracle flags a real divergence → investigate; if it's
   an architectural go/no-go → STOP and surface to operator (don't force).
4. **Advance & log:** update the STATUS line + check off completed milestones. Re-arm the hourly ScheduleWakeup.

## Known non-blocking failures (do NOT chase as restructure bugs)
- `astrid/packs/local` + `astrid/packs/external`: untracked, gitignored LOCAL pack dirs (operator's WIP, predate this
  work). They trip `test_no_unexpected_pack_ids_ship` + first-party-packs validation. **Do not delete them.** Environmental.
- `dataset_build/*` (~30): missing fixture dir `docs/megaplan/epics/builtin-training/contracts/fixtures/`. Pre-existing.
- `test_m5b_baseline_public_surface` / `test_structure_contracts` / `test_platform_contract` / `test_onboarding_parity`
  (doc-name checks): pre-existing doc-file gaps on this branch (verified failing at pre-restructure baseline 601f47d).
- Triage method: run a failing test at the `/tmp/astrid-baseline` worktree (601f47d). Fails there too ⇒ pre-existing.

## POINTERS
- Cycle gate: `python3 -m scripts.reshape.import_cycles --baseline scripts/reshape/baselines/import_cycles.json` (floor 6).
- Architecture: `docs/architecture/import-tiers.md`. Restructure detail: `docs/migration/RESTRUCTURE-PROGRESS.md`.
- Epic briefs: `docs/migration/capability-waist/briefs/s0..s5`. Chain: `docs/migration/capability-waist/chain.yaml`.
