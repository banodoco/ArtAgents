# Astrid formalization-gap audit — adjudicated synthesis (2026-06-04)

Method: 6 DeepSeek domain sweeps + 2 Codex high-level frames; Claude adjudication. Exemplar pattern: invariant → choke point → conformance test (the run-ledger fix).

## TIER A — live bugs found incidentally (fix now, don't wait for an epic)
1. **`step_failed` missing from 2 of 4 terminal-kind sets** (d6#1): `derive_cursor` (gate_cursor.py:216) and `_leaf_progress` (operator_view.py:84) omit step_failed; `_run_is_complete` (run_state.py:105) includes it. Consequence: after a step_failed, run reports complete but the gate never advances — RUN STALLS. Likely explains known agentic-suite stall symptoms. Fix: shared frozen STEP_TERMINAL_KINDS + subset conformance test.
2. **Syntactically invalid recovery commands** (d3#4): claim.py:183-188 tells agents `astrid sessions takeover --project X` — no such flag exists (positional arg). gateway.py:191-201 prose says attach, recovery_command says status. Fix: correct both + conformance test that shell-validates every recovery_command.
3. **`ASTRID_AUTHOR_TEST` constant is literally `"ASTRID...TEST"`** (d2): subprocess_env.py:19 copy-paste artifact; external setters of the real name silently no-op.
4. **Two cryptographically incompatible hash chains** (d6#3): timeline embeds prev_hash in JSON (serialize.py:64-69), task prepends raw string (events.py:827-829). Same `sha256:` prefix, different algorithms. Fix: extract shared compute_event_hash; document winner.

## TIER B — next epic: OUTPUT/RESULT CONTRACT (strongest convergence: codex1 #1 risk + codex2 'predictability=folklore' + d5 family-by-family evidence)
Invariant: every executor writing artifacts emits a self-describing manifest (schema_version, kind, echoed inputs, content-hashed outputs, created).
Evidence: generation = excellent (manifest v2, golden tests, PNG tEXt); understanding = zero contract, 3 executors × 3 ad-hoc stdout shapes (video/visual/audio_understand run.py:296/456/491); editorial = bare lists / bespoke version markers; training = third versioning dialect (last_run.json). register_outputs opt-in, unused by 60% of families. CLI `--json` returns raw payload while SDK returns typed envelope (sdk.py:1715 vs executor/cli.py:632).
Fix-shape: one `write_manifest()` in astrid.contracts; one result-envelope schema shared CLI/SDK; conformance test enumerating every executor family. Composes with run-ledger m1 (ledger entry points at the manifest).
DISCARDED from codex2's version: full AgentUXEnvelope across all five surfaces (boil-the-ocean); mandatory effects/rollback/idempotency_key on every capability (architect maximalism — a single retry_safe bool captures most value).

## TIER C — epic or fat ticket: AGENT CLI CONTRACT (d3; critical × cheap)
1. `astrid next` — THE primary agent verb — has no `--json`; agents regex prose (operator_view.py:601-1047). Discovery verbs all have --json; lifecycle verbs none (class split).
2. stdout/stderr discipline never codified (preamble interleaved with actionable output on stdout).
3. `sys.exit(1)` bypasses AstridError at 8 sites in claim.py; argparse SystemExit renders as degraded "this is a bug"; RecoverableArgumentParser adopted by only 6 of ~15 surfaces.
Fix-shape: --json on lifecycle verbs; exit_with_error choke point; stream-discipline contract + conformance (`astrid next --json` emits valid JSON; no unstructured stdout prose).

## TIER D — medium epic: IDENTITY & RESOLUTION UNIFICATION (d1 + d2)
1. run.json TWO dialects confirmed from identity angle (d1#1): loose validate_run_id (paths.py:50) vs strict require_ulid (threads); two build_run_record functions, same filename. NOTE: run-ledger m1 contract documents the dialects; unification remains deferred (threads contract-locked).
2. Timeline triple identity (d1#2): field `timeline_id` means ULID in Session, UUID in identity sidecar; 3 translation fns, 5 call sites in session/cli.py; no single resolve_timeline(). Fix: rename fields (timeline_ulid/timeline_uuid) + one resolver + bidirectional conformance test. Migration needed — schedule deliberately.
3. FOUR independent "which project am I in?" resolution paths (d2#3): binding.py two variants, cmd_next reimplementation, gateway auto-bind. Explains today's session bug class. Fix: one resolve_bound_project() with fixed precedence; per-verb exceptions become parameters.
4. Env-var catalog (d2#1): constants defined in duplicate (ASTRID_HOME_ENV, ASTRID_SESSION_ID_ENV ×2 modules), some vars have no constant; no doc. Fix: env_vars.py + docs/env-vars.md + 3-assertion conformance test. CHEAP — could go in Tier A batch.
5. Dual role derivation (d2#4): session.role vs lease disagree post-takeover; status lies. Declare lease authoritative; 1-hour fix.

## TIER E — pairs with security-model work: EVENT-LOG TRUST (d6)
1. Hash-chain verification opt-in, never on hot read (gate.py:347 feeds unverified events into derive_cursor). read_events_verified() default + allowlist conformance.
2. Timeline append has NO writer auth (local_fs.py:55-131 public; actor = unverified metadata; repair_erasure unaudited) vs task WriterContext gate (writer.py:180-238). Undermines provenance premise. TimelineWriterContext mirroring task pattern.

## Smaller dispositions
- graph.consumes/provides = dead formalism (d4#2: validated as non-empty strings only; one orphaned reader in hype). DECIDE: deprecate (my lean) or make load-bearing. Don't leave decorative.
- run.py entrypoint contract = folklore (d4#1: main vs run_sdk split, --out semantics vary). Fold into the EXISTING pack-system epic (pack-contract.md already targets this — don't double-plan).
- STAGE.md warning→error + heading template (d4#3): comfy_wrap shipped without one; agent index degrades. Trivial promote.
- Duplicate _require_uuid_str (d1#3): 1-hour chore.
- Capability catalog visibility (codex1 #3): already on pack-system roadmap; no new plan needed.
- Resource lifecycle invariant (codex1 #12): parked — no evidenced drift cost.

## Well-formalized (anti-scope — do not touch)
SDK boundary/platform-contract; session lease epoch CAS; RunStatus enum (the exemplar); unbound-allowlist tuple; RecoverableArgumentParser shape (extend adoption, don't redesign); requires_timeline; model/pack/thread/agent ID validation; generation manifest contract (generalize, don't change).

## Suggested sequencing
1. Tier A bug batch (+ env catalog, role authority, UUID dedup) — one solo/bare megaplan or direct fixes.
2. Output/Result contract epic — after run-ledger m1 merges (it provides the ledger the manifests hang off).
3. Agent CLI contract — independent, cheap, high agent-UX leverage; can run parallel to 2.
4. Identity unification — deliberate migration planning; after 2/3.
5. Event-log trust — bundle with the security-model milestone already on the platform roadmap.
