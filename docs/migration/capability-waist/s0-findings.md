# S0 Findings — De-risk Spike

**Date:** 2026-06-10
**Spike scope:** Scoped-config seam feasibility (prototype) + Reigh round-trip corpus baseline (permanent)
**RFC:** [`docs/RFC-capability-artifact-waist.md`](../../RFC-capability-artifact-waist.md)
**Migration plan:** [`docs/migration/capability-waist/MIGRATION-PLAN.md`](./MIGRATION-PLAN.md) §4 row S0

---

## 1. Verdict — GREEN

**The scoped-config primitive is feasible.** A `ThemeScope` frozen dataclass + `resolve_theme_dir` resolver, mirroring the *non-fast-path* branch of `catalog.resolve_active_theme` (explicit > env `HYPE_ACTIVE_THEME` > project binding > `None`), successfully replaces the global-state-dependent call at the single chosen seam (`runner.py:416`). All 12 parity tests pass: the new resolver produces identical results to the legacy catalog resolver across the three input domains (explicit, env-only, project-binding), including precedence and edge cases. Subprocess parity is preserved — `ACTIVE_THEME_ENV` remains in `_ASTRID_PROPAGATED_ENV` and `build_child_subprocess_env` continues to propagate `HYPE_ACTIVE_THEME` to children. No import cycle is introduced; `build_pipeline_context` imports cleanly. No regressions in the existing 46 runner tests.

**The Reigh corpus baseline is established.** Six timeline fixtures are discovered across `examples/` and `tests/fixtures/`. Four round-trip byte-identically; two (`iteration_video/assembled/*`) exhibit formatting drift (JSON content preserved, bytes differ in `save_timeline` output). The two drifters are *not* xfail'd yet (Step 2 was skipped — baseline unavailable), but their failure mode is benign and well-diagnosed by the normalized JSON diff fallback. They constitute the corpus baseline's known pre-existing drift, ready for one-time xfail annotation or source normalization in S1.

**Both gates are PASS.** S0 succeeds; the chain advances to S1.

---

## 2. Seam touched

| Seam | File:line | Role |
|---|---|---|
| Implicit-theme resolution call-site (replaced) | `astrid/core/executor/runner.py:416` | `build_pipeline_context` — the load-bearing read of the global; now calls `spike_resolve_theme_dir(ThemeScope(...))` |
| Explicit-branch (`theme_explicit`) | `astrid/core/executor/runner.py:417-426` | **Untouched** — still uses `astrid.core.theme.resolve_theme_dir` directly |
| Legacy ambient global + resolver | `astrid/core/element/catalog.py:32-83` | `_ACTIVE_THEME_DIR` global (32), `set_active_theme` (58-61), `resolve_active_theme` (71-83) — **all untouched** |
| Subprocess propagation contract | `astrid/core/subprocess_env.py:69-85` | `_ASTRID_PROPAGATED_ENV` frozenset (69-84) includes `ACTIVE_THEME_ENV` at line 77 — **untouched** |
| Spike primitive (throwaway) | `astrid/core/_spike/__init__.py` + `astrid/core/_spike/scoped_config_spike.py` | `ThemeScope` frozen dataclass + `resolve_theme_dir` — deleted at S3 |
| Parity test (permanent — renamed/moved at S3) | `tests/core/test_spike_scoped_config_parity.py` | 12 tests covering 3 input domains, precedence, and subprocess propagation |
| Reigh corpus baseline (permanent) | `tests/timeline/test_timeline_roundtrip_corpus.py` | 6 fixtures parametrized, byte-equivalence + normalized JSON diff fallback |

---

## 3. REQUIRED S3 re-plan flags

These are non-negotiable items S3's brief *must* address before beginning implementation:

### 3.1 Global-fastpath omission

The spike resolver deliberately omits `catalog.resolve_active_theme`'s global short-circuit (line 72-73: `if project_slug is None and _ACTIVE_THEME_DIR is not None: return _ACTIVE_THEME_DIR`) and tail-fallback (line 83: `return _ACTIVE_THEME_DIR`). This omission is the *whole point* of scoped resolution — no ambient module-level state. But it means the spike and legacy resolver diverge whenever `_ACTIVE_THEME_DIR` is truthy and `project_slug` is `None` *and* neither `explicit` nor `env` are set.

**S3 must decide one of:**
- (a) Restore the fallback under scoped-config semantics (kernel-owned scope, not module global).
- (b) Formally deprecate the global with a migration window, then remove it.
- (c) Document the behavior change as intentional and accept it.

The parity test autouse-fixture resets `_ACTIVE_THEME_DIR` to `None` before every case specifically to isolate this divergence. Without that reset, the parity comparison silently breaks (legacy fast-path returns a stale global while the spike returns `None`). S3's production parity oracle must handle this transparently.

### 3.2 Upward `_spike/` import direction

The spike module `astrid/core/_spike/scoped_config_spike.py` imports from `astrid.core.theme` (tier 3) and `astrid.core.project.project` (tier 3). It lives at `astrid/core/_spike/` — a sibling of tier-3 directories but deliberately outside the import-tier system. This upward import (`_spike/` → tier-3) is intentional for S0 (throwaway, deleted at S3), but **S3's production primitive must invert this dependency direction**: the kernel scope must own the resolution logic, with `theme` and `project` depending *down* on the scoped-config primitive, not up. The plan_v2 (line 103) calls this out explicitly; the findings confirm it from actual code.

### 3.3 Project-binding import-cycle pressure

The `get_project_theme` call is lazily imported inside `resolve_theme_dir` (`from astrid.core.project.project import get_project_theme` at line 70 of `scoped_config_spike.py`). This mirrors the same lazy-import pattern in `catalog.py:78`. No import cycle was observed at the S0 seam (`runner.py` imports cleanly), but S3's broader rollout across 32+ call-sites may surface cycle pressure. **S3 should audit the import graph** before inlining `get_project_theme` into a shared kernel scope — a lazy import that works at one seam may deadlock when imported from a different package tier.

### 3.4 Project-binding precedence edge case

The spike resolver checks `scope.project_slug` truthiness *after* env, meaning if both `HYPE_ACTIVE_THEME` is set AND `project_slug` is provided, env wins. The legacy `resolve_active_theme` runs the same precedence (env line 74-76 fires before project-binding line 77-82). The parity test `test_precedence_env_beats_project` confirms this. However, **this precedence was not a deliberate design choice** — it fell out of the code order. S3 should make it explicit: is env-means-override correct, or should project-binding take priority in a scoped-config world?

---

## 4. Reigh corpus summary

| Fixture | Status | Detail |
|---|---|---|
| `examples/hype.timeline.full.json` | ✅ PASS | Byte-equivalent round-trip |
| `examples/hype.timeline.json` | ✅ PASS | Byte-equivalent round-trip |
| `tests/fixtures/multitrack_cut/hype.timeline.golden.json` | ✅ PASS | Byte-equivalent round-trip |
| `tests/fixtures/reshape/hype_regression/hype.timeline.json` | ✅ PASS | Byte-equivalent round-trip |
| `tests/fixtures/iteration_video/assembled/hype.timeline.json` | ❌ DRIFT | Formatting drift — JSON content preserved, bytes differ in `save_timeline` output |
| `tests/fixtures/iteration_video/assembled/iteration.timeline.json` | ❌ DRIFT | Formatting drift — JSON content preserved, bytes differ in `save_timeline` output |

- **Total fixtures:** 6 (2 from `examples/`, 4 from `tests/fixtures/`)
- **Byte-equivalent:** 4
- **Formatting drift:** 2 (content-preserving, benign)
- **Content corruption:** 0
- **Test file:** [`tests/timeline/test_timeline_roundtrip_corpus.py`](../../../tests/timeline/test_timeline_roundtrip_corpus.py)

The two drifters have **not** been xfail'd — Step 2 (triage) was skipped because the `baseline_test_failures` was null and the harness deferred the interim no-new-failures checkpoint. These should be dispositioned with `xfail(reason="formatting drift in save_timeline — content preserved; normalize at S1")` before S1 starts, or the source fixtures normalized to match `save_timeline` output format.

---

## 5. Throwaway deletion list (S3)

When S3 lands its production scoped-config primitive, delete the following:

| Artifact | Reason |
|---|---|
| `astrid/core/_spike/` (entire directory) | S0 prototype — replaced by production primitive at S3 per RFC §3 + MIGRATION-PLAN row S3 |
| `astrid/core/_spike/__init__.py` | Directory marker; docstring says "S0-only, deleted at S3" |
| `astrid/core/_spike/scoped_config_spike.py` | `ThemeScope` + `resolve_theme_dir` prototype — replaced by kernel-scope-owned resolver |
| `tests/core/test_spike_scoped_config_parity.py` | Parity test for the throwaway primitive — replace with S3's production parity oracle (or migrate assertions into it) |

**Keep permanently:**
- `tests/timeline/test_timeline_roundtrip_corpus.py` — the Reigh corpus baseline is a permanent CI gate
- `astrid/core/executor/runner.py:416` change — the S3 production primitive re-wires this same seam with the real resolver

---

## 6. GATE status

| Gate | Status | Justification |
|---|---|---|
| **Scoped-config seam** | ✅ **PASS** | `ThemeScope` + `resolve_theme_dir` successfully replaces the implicit global read at `runner.py:416`. All 12 parity tests pass across 3 input domains with correct precedence. Subprocess parity preserved (`HYPE_ACTIVE_THEME` propagation intact). Import canary clean. Zero regressions in existing 46-runner-test suite. Deliberate global-fastpath omission recorded for S3 re-plan (see §3.1). |
| **Reigh baseline** | ✅ **PASS** | Corpus discovered (6 fixtures), non-empty assertion guards at module load, parametrized with readable ids. Four fixtures byte-equivalent; two exhibit benign formatting drift (content preserved). Normalized JSON diff fallback surfaces the exact mismatch mode. Baseline established — ready for CI gating at S1. |

**S0 outcome: both gates PASS → chain advances to S1.**
