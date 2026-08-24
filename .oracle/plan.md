# Phase B Build Plan — megado run (v2, revised against explorer evidence)

**Grounding note (updated, material):** v1 reported the cited inputs missing. They are now present: `docs-corpus/` (01–30) exists on this branch; **`docs-corpus/31-forward-map.md` and `grok/*` remain absent** — `agent_goal.md` (B-1..B-6 summary) + `docs-corpus/27-build-spec.md` (now including §9 Phase-B scope, line 343–349, which carries the five-gate definition verbatim) serve as the workstream authority. Seven explorer findings (`.oracle/findings/e1..e7`) resolve every open design question from v1 §2/§3. One v1 error corrected: the executor seam is the package **`astrid/core/task_executor/`** (`service.py`, `TaskHandler` protocol), not a flat `task_executor.py`.

---

## 1. Tasklist covering the ENTIRE agent goal

Existing seams (verified): registry `astrid/core/integrations/reigh/capabilities.py` (24 entries, three binding constants, `CapabilityEntry.template: tuple[path, sha256]` declared but never populated); admission/fences `bridge_service.py` (`admit` R1, `admit_child` T8 with live deterministic key `reigh.orch:v1:{parent_task_id}:{role}:{index}` at :674, fenced claim :828, heartbeat :953, complete :1096 via `multipart.py`); routes `local_bridge_server.py` (transport-only, constructor-injected); handler seam `astrid/core/task_executor/service.py` (`TaskHandler` protocol); port-injection logic `core/generation/backends/vibecomfy.py`; persistence `packs/shots/generation_repository.py` + migrations 0001/0002; conformance `packs/shots/conformance.py`; probes `AVAILABILITY_PROBES = {"always_available": λTrue}`; sidecar-journal precedent `core/backup/operations.py` (`_RestoreJournal`, `write_json_atomic`, boot replay); composition root `core/gateway/dispatch.py:_dispatch_serve` → `compose_standard_bridge()`.

| # | ID / title | Files | DC | Deps | Acceptance check |
|---|---|---|---|---|---|
| 1 | **B-0 Baseline lock** — suite state + the two documented collection errors archived | none (run only) | 6 | – | full `pytest tests -q` output ledgered |
| 2 | **B-1a Pin the data, not the code**: vendor shipped workflows as **Comfy API-format JSON in-repo** (E1: digesting external `ready_templates/*.py` emitters is unverifiable — models.yaml pins are stale against current bytes, `template_hash` has zero comparison code anywhere); populate the dead `CapabilityEntry.template` field with canonical-bytes SHA-256; admission snapshots workflow bytes into attempt params/spec_json provenance (pattern: `bridge_service.py:1136-1160`); **commit-SHA-pin the `vibecomfy @ git+…` requirement** (currently floating HEAD) and provision the pinned checkout via the existing `core/execution/executor/install.py` clone-with-`commit_sha` primitive (E2: `find_repo_root()` refuses wheel installs) | new `astrid/core/integrations/reigh/workflows/*.json`; `capabilities.py`; `bridge_service.admit`; requirements pins | 1 | 1 | tampered workflow file ⇒ execution fails closed before any byte write; no floating ref remains in any requirements file |
| 3 | **B-1b Generic VibeComfy handler** behind the `TaskHandler` protocol: load vendored workflow JSON, verify SHA-256 against `entry.template[1]`, inject typed ports (prompt/image/mask/seed/size per `required_inputs`) reusing `backends/vibecomfy.py` injection logic, spawn `{python} -m vibecomfy.cli run wf.json --runtime embedded` with `cwd=<pinned checkout>` (**E2 verdict: real subprocess on CPU works — no stub shim; auto device fallback suffices**) | `astrid/core/integrations/reigh/bindings/vibecomfy_binding.py` (new); registration in `task_executor/service.py` | 1 | 2 | digest mismatch refuses to run; typed-port injection covers t2i/i2i/edit shapes; CPU smoke run deterministic across 3 invocations (~13 s warm, decoded-pixel SHA stable) |
| 4 | **B-1c End-to-end journey (DC-1)** + **custom-workflow YAML path** (27 §3.3, Phase-B scope item v1 missed): trimmed YAML `{id, ports, workflow_path, digest, output_policy}` → admission snapshots + hashes bytes → `local.<slug>` capability feeding the *same* generic handler; no runtime Python/plugin loading, no promotion service. Journey vehicle: weightless `EmptyImage→SaveImage` workflow through the real subprocess (satisfies "deterministic workflow acceptable on CPU"; weighted z_image/qwen journeys validate via B-5 probes, not generation here) | journey test in `tests/v10/test_multi_task_journey.py` pattern; `local_bridge_server.py`; YAML loader in binding module | 1 | 2–3 | journey green end-to-end (R1 → claim → real subprocess → multipart complete → generation row + media atomic); custom-YAML round-trip exercises identical handler; **DC-1 satisfied with zero exceptions** |
| 5 | **B-2 Capability fan-out** (~15 capabilities): validators + conformance fixture per capability covering accepted input, completion-manifest file count/media shape, required provenance, error-category mapping, **and truthful-unavailability when a prerequisite is removed** (27 §3.6 — the unavailability leg is contractual, not extra) | `capabilities.py` (`FAMILY_VALIDATORS` extension); `packs/shots/conformance.py`; fixtures under `tests/v10/` | 2 | 4 | fixture per capability green incl. unavailability leg; import-time registry validation still compiler-enforced (**review boundary after this task**) |
| 6 | **B-3a Child-gate closure** (E4: the deterministic key **already exists and is already attempt-independent** — `bridge_service.py:674`; work shifts from design to proof): tests for replay coordinator (201→200 same-key; parent retry N+1 resolves to the *same* child row; zero duplicates), every fence branch (expired lease 409, non-running parent 409, wrong slug 404, unknown parent/attempt, forged executor/lease/status_version 403), cross-parent/cross-role key isolation, duplicate `(role,index)` concurrent admission ⇒ single row, `dependant_on` → hard-dep wiring. Registry consistency fixes: `travel_stitch`/`join_clips_orchestrator` gain `child_only=True` (aligning with :414-433); **edit family stays childless** — the 27 §3.1 allowlist is exhaustive and contains no `edit_*` child, so `edit_video_orchestrator` completes explicitly without child admission (surfaced at review boundary) | `tests/integrations/reigh/test_task_routes.py` extensions; `capabilities.py` two-line fix | 3 | 5 | every fence branch asserted; replay determinism across attempts proven |
| 7 | **B-3b Transition table + interleaving suite**: checked parent/child transitions; adversary scheduler proving zero duplicates + exactly-one parent-terminal across crash/retry/race schedules | new `tests/v10/test_orchestrator_interleaving.py` | 3 | 6 | DC-3 invariant half; deterministic schedule enumeration |
| 8 | **B-3c Port travel/join families** onto gated child admission end-to-end; edit family ported as single-attempt orchestrator with explicit parent terminal | orchestrator runner module + bridge routes | 3 | 7 | journey test per family; DC-3 (**review boundary after B-3**) |
| 9 | **B-4 Wan2GP binding + five gates** (gates now concrete from 27 §9:349, E3): ① hermetic rebase — fork rebased at pinned SHA `181bb71a…`, `wgp_patches.py` applies clean, submodule bump reproducible; ② path/import/config contract tests — `ensure_wan2gp_on_path`, `cwd=Wan2GP/`, `sys.argv=["worker.py"]`, `import wgp`, config rewrite only, `server_config` overrides; ③ dependency resolution per platform incl. `decord`/`smplfitter` stub story; ④ conversion fixtures byte-identical (param whitelist, `video_length=1` forcing, LoRA download, defaults); ⑤ fixed-seed output-shape + semantic-diff corpus (human review outside tolerance). Rollout drains WGP work, swaps sole build manifest `{wan2gp_sha, upstream_base, patchset_hash, worker_contract_version, checkpoint hashes}`, retains prior build. Prerequisite: **vendor the submodule first** — `wgp_config.json` key schema exists nowhere and is reconstructible only against the pinned SHA. Encode `TASK_TYPE_TO_MODEL` preset mapping declaratively | submodule vendored at `181bb71a…`; `bindings/wgp_binding.py`; pipeline driver + drill test | 4 | 4 | gates ①–④ run mechanically green on CPU; rollback drill N+1 accepted ⇒ roll back to N proven; gate ⑤ shape assertions where CPU-feasible, semantic baselines recorded `blocked` (CUDA) per stop conditions (**review boundary after B-3 precedes**) |
| 10 | **B-5 Setup journal + honest advertisement** (placement **resolved: sidecar file, never SQLite** — E5: 27 §6.1 decides it explicitly, setup runs pre-DB so a migration would force creating the product DB during legitimate absence, and `core/backup/operations.py` provides the proven primitive to clone). Journal at `<root>/.astrid/setup/journal.jsonl`, fsync'd appends, boot-time replay before `derive_database_path`; state machine `absent→downloading(offset)→verifying→staged→installed(verified)` / `corrupt(reason)→repairing`; signed versioned distribution manifest (hash, size, license identity/text hash, OS/arch, tier deps); tier discovery; Range resume; disk preflight (download+working+output headroom); `doctor` deep re-hash + targeted repair + journal reconciliation from filesystem reality. Probes per E7 table below — **never test for CUDA** | new `astrid/core/model_setup/` (journal, manifest, preflight); `core/doctor.py`; `capabilities.py` probe registrations | 5 | 2 | kill-mid-download/verify/rename fixtures green incl. resume; hash-mismatch, disk-full, repair fixtures green; uninstalled capability advertises unavailable, `422 capability_unavailable` naming `missing_prerequisites` + one actionable command (**review boundary after B-5**) |
| 11 | **B-6 Conformance completion + boot manifest** (ownership/digest **resolved**, E6): new `astrid/core/integrations/reigh/boot_manifest.py` — pure `compute_registry_digest(REGISTRY, fixtures)` over canonical JSON of derived entry fields `{capability_id → definition_version, binding, output_policy, probe}` **plus** per-capability fixture digests (registry-only misses fixture drift; fixtures-only misses admission-semantics drift); emitted by `_dispatch_serve` after `compose_standard_bridge()`, before server creation — **not** `local_bridge_server` (transport-only by construction); lives at `${ASTRID_PROJECTS_ROOT}/.astrid/boot-manifest.json` beside `astrid.sqlite3`; secret-free. Startup recomputes and fails closed (exit 1, typed message). Completion provenance names the manifest hash in the attempt-completion result — **`CommandReceipt`'s frozen 9-key set is not extended** | `boot_manifest.py` (new); `dispatch.py`; `packs/shots/conformance.py` | 6 | 5, 9, 10 | manifest stamped at boot; mutated registry or fixture ⇒ startup refuses |
| 12 | **Phase exit verification**: full suite green minus B-0 ledger; checkpoints committed; `phase-b` pushed to origin; never merged to main | none | 6 | 11 | DC-6 |

**Probe predicate table (E7, folds into tasks 5/10):** five composable primitives instead of 24 bespoke probes; per-entry probe = binding-runtime ∧ weights/template predicate.

| Probe | Predicate |
|---|---|
| `wgp_runtime` | pinned Wan2GP tree present + import smoke + `decord`/`smplfitter` importable |
| `wgp_weights:<model>` | journal stamp `installed(verified)` for that ckpt hash set |
| `vibecomfy_runtime` | vibecomfy pkg importable from pinned checkout + ComfyUI reachable + declared custom nodes present |
| `vc_weights:<template>` | template sha256 matches vendored bytes + checkpoint stamps verified |
| `remotion_ready` | node binary + Remotion bundle + ffmpeg on PATH |

Signature change: probe returns `(ok, missing: list[str])`; `check_available` emits `missing_prerequisites` naming exact artifacts plus one `doctor setup` command. Entries stay registered and advertised-gated — completing setup flips them available with **zero code changes**.

## 2. Areas resolved / new areas to explore

**Resolved by findings (were v1 §2 items 1–7):**
1. Digest-pinning mechanism (E1) → task 2. Anti-pattern explicitly rejected: *digesting code* — external `.py` emitters with stale unpinned hashes and no comparison code anywhere is unverifiable ceremony; digesting in-repo data bytes is checkable offline and feeds B-6 for free.
2. CPU-mode viability (E2) → **verdict: viable, real subprocess, no shim.** DC-1 closes with zero recorded exceptions. Residual hazards folded into task 3 acceptance: CPU-torch/torchvision must be version-matched from the `+cpu` index (mixing fails `nms does not exist`), `comfyui==0.260` AppMana pin, harmless audio-node import noise to filter from logs.
3. Five WGP gates (E3 + 27 §9) → task 9, enumerated mechanically.
4. Child-key/envelope spec (E4) → **already implemented** (`reigh.orch:v1:{parent}:{role}:{index}`, attempt-independent by construction); B-3 becomes proof-work, shrinking estimate.
5. Setup-journal placement (E5) → sidecar replay log; rationale: contract-decided (27 §6.1), mechanically forced by pre-DB existence, proven precedent exists, preserves one-authority (truth = artifact bytes + manifest stamps + SQLite advertisement).
6. Boot manifest ownership/digest scope (E6) → composition-root-emitted; dual-scope digest; receipt set untouched.
7. Probe honesty (E7) → installation-stamp gating, never hardware; table above.

**New areas worth exploring (in dependency order):**
1. **Worker process skeleton (27 §6)**: "one local worker process beside `serve`, one bridge client, one claim loop" — server routes exist; the client-side process does not. Scope what `task_client.py`/`worker_jwt.py` already give before B-1c; risk of silently inventing an executor framework — keep it a boring loop.
2. **Pinned-checkout provisioning**: reuse `core/execution/executor/install.py` (`commit_sha` clone, content-addressed `.astrid/venvs/.../digest/repo`) vs. a new minimal cloner. Prefer reuse; it already names install targets with `expected_executor_id`.
3. **`wgp_config.json` schema reconstruction** once the submodule is vendored — hard prerequisite for WGP gate ②; do it as the first B-4 step, not mid-pipeline.
4. **Gate-⑤ corpus feasibility without CUDA**: decide early which shape assertions run on CPU and record the semantic-baseline remainder `blocked`, so B-4's done-criterion is precise rather than discovered late.
5. **Stamp fast-path vs deep re-hash interplay**: boot uses stored verification stamp + size; `doctor` re-hashes. One exploration to pin where stamps live (journal vs sibling stamp files) so probes read one place.

**Potential issues:** floating vibecomfy HEAD means vendored workflow digests must be validated against the pinned commit *before* being trusted (pin first, then vendor); submodule vendoring may conflict with repo-size/pack hygiene; `decord` wheel gaps on some platforms (known hazard, Darwin-arm64 worst); edit-family-childless reading of the contract should be confirmed at the B-3 review boundary since `agent_goal.md` names "edit" among ported families.

## 3. Open questions

**Closed:**
1. ~~Missing authoritative inputs~~ — `docs-corpus/` present; `27-build-spec.md` §9 supplies the Phase-B scope and five gates directly. (`31-forward-map.md` and `grok/*` still absent; superseded by 27 §9 + agent goal — no longer plan-changing.)
2. ~~Does DC-1 permit a deterministic workflow?~~ — Yes, and stronger: a real weightless graph through the real ComfyUI engine is proven on this box (E2), so no stub question even arises.
3. ~~Are the five gates defined or deliverable?~~ — Defined: 27 §9 line 349; E3 operationalized them.

**Remaining (non-plan-changing, tracked):** gate-⑤ semantic baselines (CUDA-blocked, stop-condition record); exact `wcp_config`→`wgp_config.json` key set (resolved by vendoring in task 9); edit-orchestrator-childless interpretation (review-boundary confirmation).

## 4. Effort estimate (update)

- B-1 (tasks 2–4): **~4–5 d** (↑ from 3–4: vendoring + custom-YAML path added; offset by E2 removing all CPU-viability unknowns)
- B-2 (task 5): **~3 d** (unchanged; fixtures now include the contractual unavailability leg)
- B-3 (tasks 6–8): **~4–6 d** (↓ from 5–7: key/envelope/fences exist; work is tests + two registry lines + porting)
- B-4 (task 9): **~4–6 d** (± : submodule vendoring and config reconstruction added; gate definitions now concrete remove design risk)
- B-5 (task 10): **~4 d** (↓ from 4–5: no migration; journal clones a proven primitive)
- B-6 + exit (tasks 11–12): **~2–3 d**

Total ≈ **21–27 focused engineering-days (~4.5–5.5 weeks single-human)** — same band as v1, redistributed; huge-run determination stays YES; review boundaries unchanged (post-B-2/B-3/B-5). Risk migrated from *missing upstream documents* (closed) to *WGP submodule reconstruction* (bounded: pinned SHA known, vendoring mechanical).

## 5. North Star check

- **One authority**: setup journal deliberately *not* SQLite and *not* truth — installed-ness is proven by artifact bytes + manifest stamps; doctor rebuilds journal state from filesystem. Boot manifest is derived, secret-free, sibling to `astrid.sqlite3`. Zero new structured-authority surfaces; zero migrations beyond existing v2.
- **Correctness by primitives, each with a named test**: digest fence (tampered-file fail-closed, task 2), lease/status_version fences (every branch enumerated, task 6), replay determinism (task 6), crash-resume (kill-mid-append/download/verify/rename fixtures, task 10), CAS atomicity (journey, task 4), rollback (drill, task 9).
- **Invisible failure default**: probes return `missing_prerequisites` + actionable command rather than failing silently or lying available; B-6 fails startup closed on drift; adversary suite proves orphan-or-replay, never mixed state.
- **Growth by declaration**: ~15 capabilities land as REGISTRY rows + validator/fixture data; `TASK_TYPE_TO_MODEL` and probe composition are tables, not executors; custom workflows feed the same generic handler with no plugin loading.
- **Honest latency**: polling budgets (2 s/10 s/30 s) untouched; claim loop unchanged; no transport-coupled correctness.

**Named anti-patterns explicitly rejected this revision:**
1. *Second authority* — rejected SQLite setup journal (would contradict 27 §6.1 and force premature product-DB creation) and any mirror of installation state.
2. *Digest-the-code pinning* — rejected external `.py`-emitter hashing with stale pins and no comparator (ceremony without consumer); replaced with in-repo data-byte digests verified at admission and boot.
3. *Cloud fallback / silent swap* — rejected CUDA-presence probes (would permanently disable the catalog on the sanctioned CPU path) and any network-at-task-execution path (27 §6.1: outbound networking is setup-mode-only).
4. *Speculative machinery* — rejected a handler-registry abstraction (three concrete bindings suffice), `CommandReceipt` extension, and a promotion service for custom workflows.
5. *Abstraction that can't name its option* — the only new seams are the `TaskHandler` implementation (option preserved: B-4 immediately exercises the second binding) and the sidecar-journal primitive (option: backup-restore already proves the replay pattern in production shape).

Cadence unchanged: small batches, writer-queue-only mutations, commits at checkpoints, push `phase-b` at phase completion, docs-of-record updated at each review boundary.
[launch_hermes_agent] done in 360.2s (exit=0)
0

## v3 folds (STABLE - applied)
- N1 receipt premise false: every completion UoW appends core.task.completed + >=1 core.media.imported unconditionally -> receipts always valid; registry merge conditional (skip legal).
- CPU-mode DC-1 path: synthetic SaveImage-only workflow through the real subprocess binding.
- WGP five gates defined: hermetic rebase build, contract tests, platform resolution, conversion fixtures, seeded corpus + semantic diff.
- Setup journal = sidecar replay log NOT product SQLite; boot manifest emitted at serve composition root covering REGISTRY + fixtures digest.
