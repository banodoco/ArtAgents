# Reshape review — findings & decision backlog

**Status:** review complete, partially folded into `idea.md`. This is the durable record of a multi-agent review of the codebase + the `idea.md` reshape plan, run 2026-05-23.

**How produced:** 15 DeepSeek-V4-Pro subagents across 4 fan-out batches — (1) defect review by perspective, (2) high-abstraction architecture lenses, (3) clean-codebase lenses (abstraction errors / conceptual duplication / dead weight / source-of-truth / surface proliferation) — then a critical-synthesis pass with fact-checking. North star: **clean codebase, minimal duplication, minimal conceptual replication.** Raw agent reports were ephemeral (`/tmp/astrid_review/`); only the verified conclusions are kept here.

> **Critical-lens caveat (load-bearing):** DeepSeek is the weaker model and produced confident-but-wrong claims (it once hallucinated a `reshape/` git branch; it claimed the `returncode` sidecar is "written by nobody" — false, packs write it). Every item below marked ✅ was grep-verified against the tree. Trust the diagnoses, route the prescriptions through the right sprint.

---

## 1. Already folded into `idea.md` (done — don't redo)

- **Timeline unified on `TimelineConfig`.** The two-timeline mess (Banodoco `TimelineConfig` render shape vs `core/timeline`'s `{kind, asset_id, start, duration}` projection, no bridge) is resolved in the plan: one format end-to-end; the event log projects into `TimelineConfig`; the parallel clip shape + false "mirrors" docstring deleted. Threaded through mental-model diagram, load-bearing decisions, out-of-scope carve-out, and S2 body+deliverables.
- **S0 gained:** CI bring-up (no `.github/workflows/` exists today), pack-trust-boundary as a brief locked-decision, a hygiene/validation pass.
- **S3 gained:** three current `gate.py` bugs as regression tests the rewrite must pass (iteration double-count; hardcoded `step_version=1` after supersede; non-atomic feedback write).
- **Profile section** retranslated to current rubric names (`solo/directed/partnered/premium/apex`, robustness `full/thorough`); ghost `4a/4b` numbering fixed to `S5a/S5b`.
- **Banodoco extraction from `core/`** recorded as a deliberate V1 deferral (single-consumer; revisit when a 2nd domain consumer is real) — with the timeline-format unification as the one carved-out exception.

---

## 2. Verified findings scoreboard

| Finding | Verdict |
|---|---|
| `clip_extract/run.py` copied across **7 packs** (~600 dup lines; one copy missing the entrypoint guard) | ✅ exactly 7 |
| `PerformerPort`/`PerformerOutput` = `Port`/`Output` aliases, **0 consumers** outside `contracts/` | ✅ |
| `agent`/`actor`/`human` identity taxonomy fork (`human:`→`actor` in `plan.py`) | ✅ |
| `astrid/elements/__init__.py` `sys.modules` shim — no production consumers | ✅ |
| `astrid/threads/cli.py` (203 lines) unreachable — no `thread` dispatch in `pipeline.py` | ✅ |
| `remote-artifact` adapter ≈ `local` + fetch (shared `Popen`/`os.kill`/`_read_cost_sidecar`) | ✅ near-identical |
| `publish-youtube` **and** `upload-youtube` → same `upload.youtube.run` module | ✅ |
| Two `EventLogError` classes, same name, different modules (`core/task/events.py` + `core/timeline/eventlog/types.py`) | ✅ |
| `returncode` sidecar "read as authoritative, written by nobody" → **delete it** | ❌ FALSE — packs write it; it's the detached-completion contract. Keep. |
| `timelines` verb count (33/38/58) | counting artifact; surface is rewritten by S2/S5b anyway |

---

## 3. Bucket 1 — Free wins (verified, ~zero design risk, orthogonal to reshape)

Slot these into the **S0 hygiene pass**. All grep-verified above.

- Delete `PerformerPort`/`PerformerOutput` (6 lines, 0 consumers) + their `__all__`/re-export entries.
- Delete `astrid/threads/cli.py` + `tests/test_threads_cli.py` (unreachable; threads *internals* stay — they're load-bearing for pack runners).
- Delete `astrid/elements/__init__.py` shim (no prod consumers; CLI already routes to `core.element.cli`).
- Delete the unread `astrid_version` field from `packs/schemas/v1/pack.json`.
- Delete one of `publish-youtube`/`upload-youtube` (clone verbs to same module).
- Remove the legacy `--video`/`--brief` positional hype shortcuts (`_run_default_brief_orchestrator`).
- **Dedup `clip_extract` 7→1** shared module (`astrid/packs/_shared/`); biggest LOC win + fixes the missing-guard drift.
- Route the 7 `_utc_now_iso` copies + 30+ raw `json.loads(read_text())` sites through one helper / the existing `read_json`.

---

## 4. Bucket 2 — Confirms/sharpens the reshape (design notes, not separate work)

- **`orchestrators run` ⟹ `start`+`next`** (one dispatch model) — this *is* idea.md's "canonical orchestrators emit `plan.json` + go through the gate" (S5a). Same destination; the `--video`/`--brief` shortcuts disappear with it.
- **`remote-artifact` = `local` + a `produces.fetch` declaration**, not a third parallel adapter (verified ~97% shared code). Design it this way in S5a → resolves the "3 adapters, are they distinct?" question (it's really 2).
- **Two `EventLogError` + dual event log** (`events.jsonl` + `assembly.jsonl`): same "the second event log has no lease/append discipline" thread. Design input for the timeline-log work — share the transport/hash-chain/base-error layer; keep event *vocabulary* separate.
- **`step_version=1` bug** already captured as an S3 regression test.

---

## 5. Bucket 3 — Open decisions (need an explicit call; each overturns a written `idea.md` decision)

Recurring theme: **stop carrying multi-user / multi-path generality in a single-user tool.**

1. ✅ **RESOLVED (folded into idea.md).** Collapse the identity taxonomy — unify on `agent` / `human`. idea.md now collapses to four forms `system | agent:<id> | human:<name> | any-human`: `any-agent` deleted (→ `system`), `actor` ack-kind renamed to `human` (`AckRule.kind` → `Literal["agent","human"]`, `--actor` flag → `--human`), `any-human` kept (genuinely used by exhaust-override). One-shot migration is now an S3 deliverable.
2. **`session` composite only** — delete the provision/exec/teardown trio (idea.md ships both; "~100 lines, build both" is the tell). Add the trio when `scene_render` proves it wants a hot pod.
3. **`BaseRegistry[T]`** — collapse the 3–4 near-identical registries (executor/orchestrator/element/model, ~1070 dup lines). Caveat: they may diverge in S5a.
4. **Merge `AliasResolver` + `OverrideStore`** into one ordered resolution chain (overrides → aliases → canonical).
5. **leaf-template / plan-template** — is a plan-template more than "a function that adds a step subtree"? The S3 spike is set to discover this; decide whether the authoring duality (= old executor/orchestrator split, renamed) earns its keep or collapses. Also: explicitly delete `astrid/orchestrate/` so it doesn't survive as a 3rd authoring surface.
6. ✅ **RESOLVED (folded into idea.md).** Elements are *not* a third work-capability kind — verified `core/element/` is render-layer primitives (effects/animations/transitions = `component.tsx` + `element.yaml`) that a `TimelineConfig` references. idea.md now scopes them explicitly onto the render/timeline axis (S2), orthogonal to leaf/plan-templates. Deliberate scoping, not a hole.
7. ✅ **RESOLVED (folded into idea.md).** `plan.json` vs the event log — idea.md now makes the initial plan the `plan_initialized` **genesis event** of `events.jsonl`; `plan.json` is a cached projection (log wins on disagreement), and `astrid events verify` covers the plan from byte zero. S3 deliverable + migration seeds the genesis event into existing runs.
8. **Config duplication** — `~/.astrid/config.json` + `.astrid/config.json`; collapse to one location keyed by project slug.

---

## 6. Bucket 4 — Discounted (don't act / don't relitigate)

- `returncode` sidecar deletion (D#1): false premise — packs write it as the detached-completion contract.
- Exact `timelines` verb count: counting artifact; S2/S5b rewrite that surface.
- "Schema bump bricks history" (earlier batch): superseded by idea.md's deliberate "migrate everything, no shims" single-user decision.
- "Name the `Capability` supertype" (earlier batch): superseded by idea.md's collapse to one runtime step type + leaf/plan templates.

---

## 6b. Batch 5 — pristine-code sweep (5 agents, 2026-05-23, all grep-verified)

Five DeepSeek-Pro agents, one per app area (tests/CI, error-handling, CLI surface, packs/schemas, module boundaries), each told what was already covered/found. Markedly higher signal than batches 1–4. Every item below was re-verified by hand against the tree.

**Folded into `idea.md` (done):**

- ✅ **Orchestrator JSON Schema is fiction** — `schemas/v1/_defs.json` requires `runtime.type`+`entrypoint`; every manifest + the parser (`orchestrator/schema.py:_parse_runtime`) use `runtime.kind`+`command`/`module`/`function`. `orchestrator.json` requires `schema_version`; **all 10** builtin orchestrator manifests omit it. They escape only via the `content:` validator hole. ⇒ S0: closing the hole is *gated on* fixing the schema first, else CI reds out on every orchestrator. (Folded into S0 hygiene.)
- ✅ **`manual.py` poll: missing `status` ⇒ `done`** (`poll()` returns `done if completion.get("status") != "failed"` ⇒ `None != "failed"` ⇒ advances cursor past an unfinished step). Now bug-4 regression test in S3; adapters resolve missing/unknown status to `failed`.
- ✅ **`lifecycle_ack.py:193` reads `writer_epoch` under `except Exception: pass # best-effort`** — corrupt `lease.json` silently no-ops the stale-ack fence, contradicting S1's "CAS is the actual fence." Now an S1 fail-closed requirement.
- ✅ **Non-atomic adapter sidecar writes** (`dispatch.json`/`completion.json`/`remote_state.json` via bare `write_text`) → S3 routes them through tmp+rename.
- ✅ **`remote_artifact.py:117` tee-handle closed in `finally` while daemon thread still writes** (thread's `except: pass` eats the errors, drops all but line 1) → noted as the S5a clean-impl target.
- ✅ **More dedup** (extends Bucket 1): `_utc_now` ×6 across pack `run.py`; `_read_env_value`/`_candidate_env_files` ×3 + packs importing env helpers from `generate_image_openai.run`; `probe_duration` ×2 (ffprobe). → S0.
- ✅ **`REPO_ROOT` defects**: `core/element/cli.py` defaults `project_root=REPO_ROOT` while executor/orchestrator siblings use `Path.cwd()` (breaks non-repo-root / pip-install invocation); `core/executor/install.py` re-derives a local `REPO_ROOT` that actually = the *package* dir (venvs land in the package tree). → S0.
- ✅ **Test hygiene** (extends S0): unregistered `slow` marker + dead self-skip at `test_text_card_render.py`; `performance_smoke` registered only in nested `tests/timeline/conftest.py`; can't-fail allowlist test (asserts only one stderr string absent); over-mocked remotion-registry test; copy-pasted `_mint_session`/`_setup_project` across ≥5 session test files → existing conftest fixture.

**Logged, deliberately NOT folded (design notes / lower-stakes / rewrite absorbs them):**

- **`pipeline.py` god-module** (~912 lines: session-gate + 30-branch dispatch + adapter subprocess-wait + RunPod dispatch + default-brief orchestrator). Real, but the reshape rewrites most of these blocks anyway; revisit as a natural split during S3/S4 rather than a standalone refactor. *Don't* pre-refactor a file that's about to be cut up.
- **No JSON schemas for on-disk pipeline artifacts** (`pool.json`, `arrangement.json`, `triage.json`, …). True, but adding a schema per intermediate artifact is arguably the speculative-generality the north star warns against for a single-user tool — defer until a second consumer or a real corruption bites.
- **CLI coherence**: `--json` stored under 3 dest names (`use_json`/`json_out`/`json`); `timelines ls` lacks `--json`; `_parse_input_values` diverged across executor/orchestrator CLIs; cross-module private import `_print_invocation_example`; stale entrypoint `--help` omitting ~20 verbs; dead `astrid thread show @active` hints; `runpod sweep` hand-rolled argv vs `ensure-storage` argparse. Mostly cheap fixes, but the session/timeline/step surfaces are being rewritten — sweep the survivors during those sprints, not up front. (Dead `thread` hints + help staleness are the only ones worth a quick S0/S1 pass.)
- **`load_orchestrator_manifest` is json-only while the static validator accepts YAML** — agent's own least-sure; no YAML orchestrator manifest exists today. Park it.
- **`metadata.runtime_module` vs `runtime.module`** — same concept, two locations; fold into the orchestrator-schema rewrite when it happens.

**Discounted:** none false this batch — verification rate was 100% on the items checked (vs ≥2 false in batches 1–4). The per-area framing + "verify with file:line" instruction visibly raised precision.

## 6c. Batch 6 — load-bearing verification fleet (8 agents, 2026-05-23)

Goal: get from "mostly robust" to ~90% by *verifying the assumptions that, if wrong, invalidate a sprint* — not finding more defects. Eight DeepSeek-Pro agents; three with `terminal` ran live spikes. Everything load-bearing was re-verified by hand afterward. **Meta-finding: idea.md's "current state" snapshots are stale in ≥3 places — real work is described as TODO that's already shipped (locked append, runpod-lifecycle v0.3, vibecomfy split). The plan over-scopes S1/S4.**

| # | Load-bearing assumption | Verdict | Verified |
|---|---|---|---|
| **A1** | flock honors cross-process exclusive locks on APFS | ✅ **GREEN** — ran 5-process append race, 100 lines, zero torn writes; `LOCK_NB` contention raises `BlockingIOError` | re-confirmed (schema of test sound) |
| **A2** | `ASTRID_SESSION_ID` survives every subprocess path | ✅ **GREEN** — all 8 `env=` spawn sites use `{**os.environ}`; live read-back = `spike-test` | re-confirmed |
| **A3** | lease/CAS critical section is race-free | 🟡 **core SOUND, 3 plumbing holes** — `append_event_locked` (`events.py:94`) already exists & is race-free; but `cmd_ack` retry/iterate (`lifecycle_ack.py:357,425`) call legacy unlocked `append_event` (read-only session can append, bypass writer check); takeover warm-check TOCTOU (`cli.py:587`→`595`); dead fail-open epoch read (`lifecycle_ack.py:190`) | ✅ `append_event_locked`+flock confirmed at `events.py:94,131` |
| **A4** | event projection → valid `TimelineConfig` reigh-app renders | 🟡 **NO-UNTIL, one bounded blocker** — version drift NONE (installed == vendored, byte-identical); **`clip.track` is REQUIRED and unproducible** (vocab has `track.added`/`removed` but no clip→track binding); the other ~12 "CANNOT" fields are *optional* render features, not blockers | ✅ schema `TimelineClip required=['id','at','track']`; `validate_timeline` fails without `track` |
| **A5** | hype expressible in new step model | 🟡 **YES-WITH-CHANGES** — no cross-sibling fan-out needed (the feared risk is absent; hype's fan-out is within-step `repeat.for_each`); but `repeat.until` condition grammar is unspecified and group-step-repeat is undefined — the editor loop needs both. Decide before schema locks | (design gap, not code) |
| **B1** | vibecomfy runner ~80% cleanly splittable | ✅ **GREEN, already done** — split executed, ~78/22, shim ~258 lines. Two nits: `PodGuard` bakes `VIBECOMFY_…` env default; shim passes 4 kwargs `ship_and_run_detached` may not accept (live `TypeError`? or stale on disk) | ✅ create_network_volume @ `api.py:507` |
| **B2** | runpod-lifecycle API matches S4 | ✅ **GREEN-er than planned** — at v0.3.0; entire v0.2 deliverable list (guard/shipping/runner, volume-create, storage methods, `terminate_after_exec`) already shipped. Drop the storage-creation "gap." Live pricing exists; pinned fallback table must be pack-side | ✅ |
| **B3** | on-disk inventory complete ("no shims" is safe) | 🔴 **INCOMPLETE** — 3 uncovered kinds: `audit/ledger.jsonl` (a *separate* `astrid/audit/` provenance subsystem = a **third** append-only log), `hype.plan.json` (hype's own plan artifact), `_llm_debug/`. All silently dropped by current migration scope | ✅ `astrid/audit/{context,graph}.py` write `asset.created`/`node.created` to `ledger.jsonl` |

**Folded into `idea.md` (done):** A3 → S1 reframed (lock exists; work = route ack through it + kill legacy path + fix takeover TOCTOU + delete dead read). A4 → S2 hard-prerequisite (emit `track`; add clip→track binding; version-drift=none; optional tail deferred). A5 → S3 must specify `repeat.until` grammar + group-repeat before lock. B3 → S0 inventory expanded + new load-bearing "three logs" decision (keep audit ledger separate but migrate + give it transport discipline). B1/B2 → S4 re-baselined as "confirm shipped + build the pack/sweeper," storage-gap dropped, shim-signature check flagged.

**Confidence after this batch:** the *catastrophic-if-wrong* foundations (flock, env, the concurrency primitive) are GREEN and measured. The three sprint-shaping gaps (track, repeat-grammar, audit-ledger) are all **fixable-in-plan and now enumerated** — none are "this can't work." Residual risk is execution variance + the optional-field render tail (only bites when those features are used). ≈90% on "foundations sound + known gaps closed"; the last 10% is what only the soak retires.

## 7. Meta

- **The reshape is aimed correctly.** Bucket 2 shows the agents kept independently rediscovering idea.md's own direction — reassuring, not redundant.
- **The real net-new value:** (a) the verified deletion/dedup cluster (§3, pure profit), and (b) the recurring theme that single-user generality (`any-agent`, the adapter trio, multi-config, the registry/resolver duplication) is the main thing still being carried that the north star says to drop (§5).
- **Process note:** subagents did the byproduct-heavy reading; fact-checking their confident claims caught ≥2 false ones. Keep that discipline — trust the X-ray, verify before the surgery.

---

## 8. Megaplan-chain holistic sense-check (2026-05-24, Opus + Codex jury)

Two independent reviewers (Claude Opus via Agent, Codex GPT-5.5 via `codex exec`) read the chain spec + 7 briefs + idea.md. **Both returned "ship with named changes."** Strong convergence:

| Finding | Opus | Codex | Action taken |
|---|---|---|---|
| chain.yaml diverged from idea.md profile table | ✓ | ✓ | **Reconciled** — idea.md updated to S3=apex, S0=directed/full; S2/S4 reverted to directed (matches idea.md). |
| S0 under-tiered — bundles chain-gating orchestrator-schema fix at solo/light | ✓ | ✓ | **S0 → directed/full** (kept one milestone, not split — user decision). |
| S3 is the right & only apex | ✓ | ✓ | Kept apex. |
| Audit-ledger (3rd log) has no owning sprint | ✓ | ✓ | **Assigned to S3** (transport + migration); S1 anti-scope updated to build the helper generically. |
| Rollback is snapshot-only (no restore rehearsal) | ✓ | ✓ | **S0 migration-gate harness** added (copy + inventory diff + idempotency + restore drill). |
| S3 hype spike under-exercises the schema (transcribe→cut→render never hits the editor-review `repeat.until`-on-group loop) | — | ✓ (sharpest catch) | **S3 spike now requires a minimal editor-review loop.** |
| remote-artifact may ship with no exercised client | — | ✓ | **S5a requires one concrete RunPod remote-artifact smoke** regardless of hype's default path. |
| Branch-drift policy for ~11-13wk reshape/ branch | — | ✓ | **chain.yaml: main frozen + re-merge+regress on hotfix.** |
| Soak-failure recovery path not in executable spec | ✓ | — | **chain.yaml: patch-milestone + reset-soak-clock documented.** |

Net: every convergent finding folded. The one divergence-from-user-instruction (S2/S4 partnered→directed) was surfaced and the user chose to follow the 2-juror convergence (revert), consistent with the default-lower posture.
