# Loose-work consolidation plan

**Date:** 2026-05-23
**Author:** cleanup-loose-branches session (Claude) + DeepSeek V4 Pro investigation agents
**Repo:** `/Users/peteromalley/Documents/reigh-workspace/Astrid`
**Goal:** land *everything valuable* onto `main`, then delete everything else **with positive evidence** — no middle ground, no silent drops.

---

## 1. Why this plan exists

A routine "clean up loose branches" pass surfaced something bigger than branch hygiene: the most
advanced work in this repo exists only as **uncommitted state across several worktrees**, while the
branch list is mostly *residual* refs from completed megaplan epics. The danger was inverted from what
it looked like — the risk isn't stale branches, it's unprotected dirty trees.

To get to full confidence (rather than guess), the investigation was fanned out to five read-only
DeepSeek V4 Pro agents (four parallel + one follow-up), each briefed on one area with a hard
read-only guardrail. Their findings are folded in below and corrected two of my own earlier
mis-reads (see §6).

---

## 2. The landscape (what's actually going on)

Three megaplan epics and assorted loose work overlap here:

- **timeline-event-sourcing** — base branch `megaplan/git-backed-packs-chain-setup`. **Complete**
  (all 10 milestones m1…m9 merged into that base via PRs #9–#23). **Not yet integrated into `main`.**
- **builtin-training** — **fully done**, 6/6 milestones merged onto `main` (PRs #18–#25; `main` HEAD =
  `41debce`). Its leftover branch + worktree are residual.
- **pack-system** — in-flight, 6 milestones M0–M5. The real implementation is **100% uncommitted** in
  one worktree (`pack-system-run`). Two other worktrees carry *unrelated* churn that merely shares the
  same commit tip.
- **git-backed-packs (old sprints)** — predecessor of pack-system. sprint-00/01 landed on `main`;
  sprint-02 is an open draft (PR #8) carrying a large committed alternative implementation. **(supersession
  verdict pending — see §5.)**

`main` and `chain-setup` have **diverged**: `main` carries builtin-training (6 commits) that
`chain-setup` lacks; `chain-setup` carries timeline (32 commits) that `main` lacks. Neither contains
the other.

---

## 3. Everything valuable → where it lands

| # | Valuable work | Current state | Lands as |
|---|---|---|---|
| 1 | **pack-system epic M0–M5** (CapabilityHandle/Provenance/alias_resolver, enriched PackDefinition, discovery CLI, fork/override/update modules, docs, tests) — **tests GREEN: 305 passed, 0 failed; committable as-is** | uncommitted in worktree `pack-system-run` (B) | commit → PR |
| 2 | **New content packs** (`comfy_t2i_ds1`, `file_summarizer`, `media`, `text_digest`, `text_review`) + agentic test infra — conform to B's contract; only placeholder `description`/`agent.purpose` to fill (~5 min each); `external/pack.yaml` needs `schema_version: 1`. NB: B's own M3 marks the scaffold packs `visibility: hidden` (intentional examples, not deletions) | uncommitted in main checkout (dup in `pack-system` worktree, subset in `state-mutation-coverage` worktree) | commit on `chain-setup` |
| 3 | **`feature/per-project-plan-md`** — adds `plan.md` on project creation + skill docs | 1 commit, no PR | PR → `main` |
| 4 | **Timeline epic** (10/10 milestones) | on `origin/chain-setup` | PR `chain-setup → main` |
| 5 | **Stashes {0} seinfeld dataset-upload · {1} video_understand `--response-schema`** | stashed | verify not already on chain-setup, then port the unique parts. **{4} is REGRESSIVE — drop, do not port** (chain-setup's seinfeld pack is many sprints ahead; see §4) |
| 6 | **PR #8 = the *entire* git-backed-packs chain, sprints 00–09** (resolver runtime, local + git install, builder scaffolding, agent index, elements example, legacy-migration proof, portfolio rationalization) — far more than "sprint-02". Unique assets: `pack_store.py`, `install.py`, `gitignore.py`, `agent_index.py`, the executed directory restructure, example packs, parity/install tests | committed on remote draft branch (all sprints accumulated on the cloud box) | **port INTO B** (§5), then close PR #8 |

Cross-checked that this is the *complete* valuable set: submodule `seinfeld/ai_toolkit/upstream` is
clean/vendored; no GitHub Codespaces; no other clones of this repo on disk; no megaplan cloud workspace;
no tags/notes; 259 unreachable orphan commits show no signal of lost work.

---

## 4. Everything else → delete (only after §3 lands, each with per-item approval)

All deletions below are backed by positive evidence: content is preserved either on `main` (squash-merge)
or on `chain-setup` (which itself is preserved until it lands on `main`).

**Worktrees (clean, zero loss):**
- `Astrid-builtin-training-chain` — stale `main` checkout; epic done.
- `Astrid-m8` — PR #20 merged.
- `.claude/worktrees/agent-ac695704cdc5ac656` — stale lock (agent pid dead), clean. Remove after #3 lands.
- `pack-system` (A) — byte-identical duplicate of the main checkout (`git diff HEAD` hash `dc9db6a`), zero unique content.
- `state-mutation-coverage` — its dirty tree is a strict subset of the main checkout (verified: every untracked file also present and byte-identical).

**Local branches** (content on `main` or `chain-setup`):
`astrid-state-mutation-coverage`, `epic/timeline/m6a-astrid-supabase-contract`,
`epic/timeline/m8-migration-tests`, `worktree-agent-ac695704cdc5ac656`,
`megaplan/builtin-training-m0-contracts`, and — *after #1 is committed* — the now-redundant
`pack-system` / `pack-system-run` refs.

**Remote branches:**
`origin/epic/timeline/m6a-…`, `origin/epic/timeline/m9-…`,
`origin/megaplan/git-backed-packs/sprint-00-architecture-gate`,
`origin/megaplan/builtin-training-m0-contracts`. Plus `origin/…/sprint-02-resolver-runtime`
— but **only after** its unique assets are ported into B per §5 (it is *port-then-close*, not a blind delete).

**Stashes:** drop `{2}` (covered by {1}), `{3}` (exact dup of {1}), `{5}` (`_grid_prompt` already on main),
`{6}` (README decoration already on main), and **`{4}` — regressive**: it's the seinfeld pack at skeleton
stage; `chain-setup` is many sprints ahead (5 built-out executors, reviewer UI, vocab compiler, enriched
orchestrator manifests). Porting it would *revert* newer work; the only identical bits (schemas, vocabulary,
pack.yaml) are already on `chain-setup`.

**Never touch:** `main`, `chain-setup` (timeline integration surface), and any in-progress work not
explicitly cleared above.

---

## 5. PR #8 (git-backed-packs chain) — supersession verdict

**STATUS: RESOLVED. Verdict — NOT superseded. Port its operational assets into B, then close PR #8 (do not just delete).**

> **Scope correction (archaeology):** the branch is mislabeled `sprint-02-resolver-runtime` but actually
> carries the **entire git-backed-packs chain, sprints 00–09**, accumulated on the cloud box
> (resolver runtime → local install → git install → builder scaffolding → agent index → elements example →
> legacy-migration proof → portfolio rationalization). It is a large, *completed* effort, not a half-sprint.

> **Integration is sized (agent ①):** porting B's identity layer onto sprint-02's executed restructure is
> **~2–3 days**, with **no architectural incompatibility** and **schemas that coexist**. ~11 substantive
> conflicts (the 4 `pack.yaml`s + 12 core registry/CLI/schema files) + ~20 trivial path rewrites. The
> bottleneck is a 12-file line-by-line registry merge (~1 day). B's own tests are already green, so the
> merge has a solid validation baseline. See §8 for the ordered task-list pointer.

The two pack efforts are **complementary, not competing — different layers of the same system:**

- **sprint-02 = operational substrate**: how packs get onto disk and how we discover what's there
  (install, restructure, validate, inventory, agent indexing).
- **pack-system (B) = identity & governance layer**: what a capability *is*, where it came from, and how
  to customize it safely (capability identity, aliases, provenance, forks, overrides, update reconciliation).

B is the **keeper architecture** (cleaner 6-milestone vision vs 10-sprint sprawl, richer identity model,
sits on a newer merge-base). sprint-02's operational code should be ported **into** B, not the reverse.

### Unique value in sprint-02 that would be LOST if simply deleted

| Asset | Why it's unique |
|---|---|
| `astrid/core/pack_store.py` | Full installed-pack store: revisions, active symlinks, file locking, rollback. No equivalent in B or main. **Crown jewel.** |
| `astrid/packs/install.py` | `packs install/uninstall/update/rollback` CLI, Git-URL support, trust summaries, dry-run. No equivalent. |
| `astrid/packs/gitignore.py` | copytree filter — needed by install infra. |
| `astrid/packs/agent_index.py` | Deterministic machine-readable pack index for agents (B's discovery is a *different* mechanism). |
| `astrid/core/orchestrator/plan_v2.py` | Shared TypedDict plan-template helpers (port if orchestrators still use plan-v2). |
| `astrid/core/orchestrator/runtime.py` | Resolver-backed runtime module resolution. |
| `astrid/core/executor/folder.py` | Folder-based executor discovery. |
| **Executed directory restructure** | builtin → `executors/<slug>/` + `orchestrators/<slug>/`, upload/seinfeld likewise. **This is exactly what B's M3 only *plans*** — B can inherit the done state instead of re-executing. |
| `examples/packs/media/`, `examples/packs/minimal/` | Reference pack examples. |
| Strict JSON schemas (`_defs/element/executor/orchestrator/pack.json`) | Richer validation layer; merge with or sit alongside B's dataclass contracts. |
| Parity/install tests (`test_portfolio_parity.py`, `test_git_pack_install.py`, `test_pack_install.py`, `test_public_id_resolution.py`) | Prove every shipped pack resolves/validates/inspects identically. |

### What B already does better (discard sprint-02's versions)

Alias resolution (B's `alias_resolver.py`, transitive + cycle detection) · capability identity
(B's `CapabilityHandle`/`Provenance`/`AliasRecord`/`SafetyDeclaration`) · fork/override/dirty/update
(B's `dirty.py`/`override.py`/`update.py`/`git_util.py`).

### Action

**Port-then-close.** Bring sprint-02's operational assets (priority: `pack_store.py` + `install.py` +
`gitignore.py` → adopt the restructure as M3 ground truth → `agent_index.py` → schemas →
`plan_v2.py`/`runtime.py`/`folder.py` → tests) **into B's worktree**, then **close PR #8** and delete its
remote branch. This is a real integration task (sprint-02's substrate under B's identity layer), best done
as part of finishing the pack-system epic — not a quick cherry-pick.

---

## 6. Epic scope ledger — done / incomplete / deferred (archaeology)

The intended-scope record (chain.yaml, EPIC.md, briefs, `wakeup-note.md`, `docs/future-work.md`,
`.megaplan/tickets/`) was read to separate **incomplete** (meant to ship, didn't) from **deferred**
(intentionally out of scope). Note: local plan-state JSON is mostly absent/stale — these chains ran on a
Railway cloud box, which is the real source of truth.

| Epic | Status | Still owes (incomplete) | Deferred (intentional) |
|---|---|---|---|
| **timeline-event-sourcing** | 10/10 milestones merged into `origin/chain-setup` | local `chain-setup` 6 behind origin; `chain-setup → main` integration (1 conflict) | Supabase SQL/RPC + reigh-app write-path + realtime UI; continuous sync; event RBAC; compaction; streaming; cross-project composition |
| **builtin-training** | 6/6 merged to `main` — **DONE** | nothing | nothing |
| **pack-system** | M0–M5 implemented (uncommitted, tests green) | commit B; **M3 cleanup not executed** (delete 4 comfy wrappers + hide 4 scaffold packs); port PR #8 substrate; merge-test against restructure | remote registry; dependency isolation; LLM semantic merge; builtin-training placement; timeline/thread integration |
| **git-backed-packs** | sprints 00–09 all committed on the PR #8 cloud branch | port operational assets into B, then close PR #8 | optional sandboxed run mode (devcontainer/Docker) |

**M3 nuance (agent ③):** B's M3 and sprint-02's restructure **diverge** — they're different milestones, not
duplicates. sprint-02 did *layout nesting* (`executors/<slug>/` + `orchestrators/<slug>/`); B's M3 is
*cleanup* (delete comfy wrappers, hide scaffold packs, alias) layered on top. So M3 **cannot** be marked
"done by inheritance" — but the layouts are compatible; adopt sprint-02's as the substrate, then apply B's
cleanup (~1 day).

**14 open `.megaplan/tickets/` (all pack-architecture)** — the design backlog feeding pack-system, e.g.:
two divergent orchestrator-resolution paths for the same id; custom flat-YAML parser in `pack.py` is a
footgun; `hype.py` vs `hype/` collision with no deprecation path; `pack.yaml` schema anemic (0/6 packs use
`metadata`); "should `pack` exist at all as an abstraction?"; `discover_packs` silently skips manifest-less
dirs; high-ceremony orchestrator authoring. These should be triaged as the pack-system epic is finished —
several are already addressed by B's uncommitted work.

Also noted: `docs/megaplan/agentic-state-mutation-coverage.md` is a **planned-but-not-started** sprint (the
origin of the `astrid-state-mutation-coverage` branch); its commits are already on `chain-setup`, so the
branch/worktree are still safe to delete per §4.

---

## 7. Corrections this investigation forced (intellectual honesty)

The deep-dive overturned two of my earlier surface reads — recorded here so the reasoning is auditable:

1. **"pack-system is barely started."** Wrong. The `pack-system-run` worktree implements **all of
   M0–M5** (just uncommitted). My earlier read mistook the *duplicated churn* in two other worktrees for
   the epic and concluded little had happened.
2. **"Three worktrees are independently building the epic in parallel."** Wrong. Only `pack-system-run`
   carries epic work. `pack-system` is a byte-exact copy of the main checkout, and `state-mutation-coverage`
   is a subset of it — both carry unrelated agentic-test churn, not pack-system code.

A third agent claim was also corrected by direct check: `state-mutation-coverage`'s untracked files are
**not** unique (they are a subset of the main checkout), so dropping that worktree needs **no salvage**.

Later passes forced two more:
4. **"Stash {4} is a port-then-drop keeper."** Wrong — it's **regressive**; `chain-setup`'s seinfeld pack is
   many sprints ahead. Drop it.
5. **"PR #8 is sprint-02 (resolver runtime)."** Understated — it's the **whole git-backed-packs chain
   (sprints 00–09)** accumulated on the cloud box; far more operational value than the name implies.
6. **"pack-system B may have test gaps / M3 is just un-derisked."** Resolved: B's tests are **green (305/0)**
   and the integration is a **sized 2–3 day** task, not a vague risk. M3's cleanup is genuinely unexecuted
   though (not "done by inheritance").

---

## 8. Execution order (lowest blast radius, preserve-before-delete)

**Phase A — preserve (no deletions):**
1. Commit `pack-system-run`'s M0–M5 work to its branch (or a fresh topic branch). Tests are green; first
   refresh the stale `M5_TEST_STATUS.md` (it undercounts and wrongly calls `test_canonical_aliases.py` a ghost).
2. Commit the main checkout's new content packs + agentic test infra on `chain-setup`. Fill the placeholder
   `description`/`agent.purpose` fields and add `schema_version: 1` to `external/pack.yaml` first.
3. Open PR for `feature/per-project-plan-md` → `main`.
4. Port the unique parts of stashes `{0}`/`{1}` onto `chain-setup` (verify not already present first).
   **Drop `{4}` — regressive, do not port.**
5. Fast-forward local `chain-setup` to `origin` (currently 6 behind: missing m8 + m9).

**Phase B — integrate:**
6. PR `chain-setup → main`. Five touched files auto-resolve; manually resolve `runpod/run.py`
   (~15 lines: keep `main`'s SSH/SCP functions + `chain-setup`'s `guard_canonical_entrypoint`).
7. Rebase pack-system work onto the updated `main`.
8. **Port PR #8's operational assets into B** (per §5; sized ~2–3 days by agent ①). Ordered task-list:
   (a) accept sprint-02's `astrid/packs/` restructure as-is; (b) delete `iteration/clip_extract`; (c) merge
   the 4 `pack.yaml`s; (d) merge `schemas/v1/element.json`; (e) the 12-file core registry/CLI/schema
   line-by-line merge (the ~1-day bottleneck); (f) drop in B's 5 new modules + sprint-02's 3 new modules;
   (g) apply B's M3 cleanup (delete comfy wrappers, hide scaffold packs); (h) run B's green suite to validate.
   Then **close PR #8**. This is the natural way to *finish* the pack-system epic — sequence it with #1/#7.

**Phase C — delete (each item, explicit approval):**
9. Remove clean worktrees → delete merged local branches → delete remote branches (including
   `sprint-02` *only after* its assets are ported in #8) → drop superseded stashes.
10. Verify: `git branch`, `git branch -r`, `git worktree list`, `git status` all clean.

---

## 9. Confidence & open questions

After two fan-out rounds + the supersession + the clarity sweep, the earlier ambiguity is **largely resolved.**

**Confident:**
- The ledger — what's where, what's safe to delete (ancestry / `cherry +0` / byte-identical hashes / subset
  checks all verified).
- Timeline complete (10/10) and integrates with **one** conflict (`runpod/run.py`); builtin-training done.
- pack-system B is **test-green (305/0) and committable as-is**.
- PR #8 = the whole git-backed-packs chain; **NOT superseded**; port-then-close.
- B ⨉ PR#8 integration is **sized: ~2–3 days, no architectural incompatibility, schemas coexist**, with an
  ordered task-list (§8 step 8). The 12-file registry merge is the ~1-day bottleneck.
- Content packs conform (trivial field fills); stash `{4}` is regressive (drop).

**Residual unknowns (small, and now bounded):**
1. **The registry merge (§8 step-8e) still has to be *done*** — read-only analysis proves it's tractable and
   sized, but only the actual 12-file merge + green-test run proves it compiles. This is implementation
   (Codex / Claude `Agent` in a throwaway worktree), not more survey.
2. **M3 cleanup is genuinely unexecuted** — deletions/hides are ~1 day of real work, not inherited.
3. **Stashes `{0}`/`{1}`** — verify the unique parts aren't already on `chain-setup` before porting (low stakes).
4. **Timeline Supabase backend is a contract-only stub** — *intentionally deferred* (companion reigh-app work),
   not a defect in scope. See §6.

**Net:** the deletes are go; "land everything valuable" is now a concrete, sized task-list rather than an
open question. The only thing left that read-only investigation can't settle is the act of doing the 12-file
merge — everything pointing at it says it's a 2–3 day job.

## 10. Provenance

Investigation agents (DeepSeek V4 Pro, read-only/scoped, via `subagent-launcher` fan-out):

*Round 1 (`/tmp/cleanup_out/`):* `01_pack_lineage`, `02_timeline_integration`, `03_stashes_loose`,
`04_branch_ledger`.
*Round 2 (`/tmp/cleanup_out2/`):* `sprint02_supersession` — PR #8 unique-value verdict (§5).
*Round 3 — clarity sweep (`/tmp/cleanup_out3/`):* `1_reconciliation` (B ⨉ sprint-02 sizing),
`2_test_suite` (B green 305/0), `3_m3_gap` (M3 diverges, not inherited), `4_packs_and_stash` (content-pack
conformance + stash {4} regressive), `5_plan_archaeology` (epic scope ledger, deferred list, 14 tickets).

Each brief carried a hard read-only guardrail; the test-suite agent ran scoped pytest only. Several agent
claims were cross-checked with direct commands (see §7 corrections). Raw outputs preserved at the paths above.
