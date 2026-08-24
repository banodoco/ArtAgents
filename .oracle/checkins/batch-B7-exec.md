# Batch B7 execution record — Wan2GP binding + five gates (T7.1/T7.2)

Branch `phase-b`. Date 2026-08-23. Executor stealth/ox-alpha.
Box is CPU-only: every CUDA-dependent leg is a documented skip-with-reason,
never a silent drop.

## T7.1 Vendor the submodule first

- Vendored banodoco/Wan2GP at the pinned SHA
  `181bb71a21008032e4771e11663f33e4489c4512` (branch `reigh-sprint-3`)
  into `<workspace>/vendor/Wan2GP` — sibling of the existing
  `vendor/VibeComfy`, matching the probe's default resolution path.
- **`wgp_config.json` key schema reconstructed against the pinned bytes**
  (`astrid/core/integrations/reigh/wgp_bridge.py::DEFAULT_SERVER_CONFIG`,
  35 keys from the pinned `wgp.py` default literal) and verified
  mechanically by AST re-derivation from those bytes
  (`verify_config_schema_against_pin` ⇒ zero drift, named test).
- Upstream base recorded: `git merge-base <pin> origin/main` =
  `664b26e1dfbae94b4945b76fd9f882e3387a16de` (fork fully rebased).

## T7.2 Five-gate pipeline — each gate a named test

New modules (all in `astrid/core/integrations/reigh/`, flat like
`vibecomfy_binding.py`):

| Module | Authority |
|---|---|
| `wgp_patches.py` | The five documented global patches as DATA (`phase_config`, `svi2pro`, `sliding_window`, `sliding_window_defaults`, `svi_empty_frames_mode`), each with a pinned-bytes anchor that must match exactly once; lock-scoped apply/restore incl. absent-attribute restore |
| `wgp_bridge.py` | The in-process cwd/sys.path contract preserved byte-for-byte: path insert → chdir → `sys.argv=["worker.py"]` → env spoofs → `import wgp` → config-rewrite-only overrides; full finally-restore; typed refusals |
| `wgp_build.py` | The SOLE build manifest `{wan2gp_sha, upstream_base, patchset_hash, worker_contract_version, checkpoint_hashes}`; atomic tmp+os.replace swap; one-deep prior retention; explicit rollback |
| `wgp_conversion.py` | Declarative `TASK_TYPE_TO_MODEL` preset table + doc-03 param whitelist + t2i `video_length=1` forcing + LoRA materialization hook |
| `wgp_binding.py` | `WgpTaskHandler` — second `TaskHandler` implementation under `BINDING_WGP`; build fence before anything; provenance stamp |
| `wgp_gates.py` | The gate runners + platform table + corpus runner |

1. **Gate ① hermetic rebase** (`test_wgp_gate1_hermetic_rebase.py`, 8
   green): HEAD==pin, clean tree, all five anchors match exactly once
   (drift rejects mechanically), schema zero-drift, tree digest stable.
2. **Gate ② contracts** (`test_wgp_gate2_contracts.py`, 7 green +
   1 skip): cwd/argv/env facts recorded at import time by a stub tree;
   overrides land on live `server_config` AND only `wgp_config.json`;
   off-schema override refuses; full restore after body exception.
   *Skip:* real-tree `import wgp` needs mmgp/torch (CUDA-class stack) —
   skipped with reason.
3. **Gate ③ platforms** (`test_wgp_gate3_platforms.py`, 5 green):
   declarative per-platform plans; Darwin-arm64 `decord` stub story;
   linux-x86_64 locks `uv sync --extra cuda124`. *Skip:* real sync =
   CUDA/network leg, opt-in on a GPU runner.
4. **Gate ④ conversion fixtures** (`test_wgp_gate4_conversion.py`, 8
   green): four golden fixtures replay byte-identical (whitelist drop,
   preset defaulting, explicit-model precedence, video_length forcing,
   legacy key mapping); URL-backed LoRA refuses until the B8 setup
   journal exists.
5. **Gate ⑤ corpus** (`test_wgp_gate5_corpus.py`, 3 green + blocked
   legs): CPU-feasible shape assertions over the fixed-seed corpus green;
   every semantic-diff leg recorded `blocked(CUDA)` carrying the phase
   stop-condition note.

## Rollout + rollback drill ([XHARD])

- `rollout_swap(store, manifest, drain=..., gates_evidence=...)`: refuses
  unless five-gate evidence is complete AND the caller-owned drain
  closure reports zero live WGP attempts — silent swaps are structurally
  impossible; identical-manifest swaps refuse typed.
- **Named drill test**
  `test_rollback_drill_n_plus_one_accepted_then_back_to_n`: build N
  installed → N+1 accepted through the gated rollout → explicit
  `rollback_to_prior()` restores N exactly (digest equality); retention
  survives the drill in both directions. Plus refusals: work-in-flight,
  missing gate evidence, no prior, malformed manifest, temp litter check.

## Binding registered behind the same capability contract

`resolve_task_handler("wgp")` yields `WgpTaskHandler`; double
registration of a different factory refuses (one authority per binding).
`_probe_wgp_runtime` now checks the REAL vendored bytes (`wgp.py` +
`defaults/`) instead of the never-present `worker.py`; probe returns
`(True, [])` against the vendored pin. Fake-runtime fixtures in
`tests/integrations/reigh/conftest.py`, `test_family_journeys.py`,
`test_orchestrator_interleaving.py`, and
`tests/packs/reigh/test_capability_conformance.py` follow the same
contract (this resolved 59 fixture-drift ids to green after vendoring
flipped the probe honestly).

## Provenance stamped

Every WGP result manifest stamps
`inputs.provenance = {kind: wgp.build_manifest, sha256: <digest>,
wan2gp_sha, worker_contract_version}` — completion provenance records
the manifest that ran (doc 26), asserted against the store digest in a
named test.

## Validation

- Scoped: `pytest tests/v10 -q -k "wgp or wan"` → 46 passed, 2 skipped
  (both documented CUDA legs).
- Affected groups post-fixture-fix: `tests/integrations/reigh +
  tests/packs/reigh` → 344 passed, 12 skipped; journeys+interleaving →
  40 passed.
- Full suite (`tests/v10 tests/integrations/reigh tests/packs`):
  2925 passed, 84 failed / 95 errors — failure-id diff vs the B-0
  ledger shows exactly 59 new ids, ALL caused by the honest probe
  cutover hitting stale fake fixtures, all now green (verified per
  file). Remaining failures are pre-existing B-0 drift (121 scoped
  baseline ids).

## Commits on phase-b

6acab677 (vendor + primitives), 123f5835 (gates + drill),
439f5e30 (binding tests + pipeline driver),
1b42665a (fixture contract cutover).
