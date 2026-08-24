# Batch B8 execution record — Setup journal + honest advertisement (T8.1/T8.2/T8.3)

Branch `phase-b`. Date 2026-08-23. Executor stealth/ox-alpha (resumed
instance; prior instance died on a transient provider stream error after
producing the five `astrid/core/model_setup/` modules + boot-replay wiring —
resumed from those bytes, no restart-from-scratch).

## One authority, enforced

The setup journal (`<root>/.astrid/setup/journal.jsonl`) is a **replay log,
never truth**: plain fsync'd JSONL appends, deliberately not product SQLite.
Installed-ness is proven by artifact bytes + signature-verified manifest
stamps + SQLite advertisement. Boot reads the stored stamp + size (stat fast
path); deep re-hash is exclusively `doctor setup`'s job; probes read exactly
one place (`journal.read_stamp`).

## T8.1 Journal state machine ([XHARD])

- `journal.py`: fsync'd appends (file + directory), boot-time replay before
  `derive_database_path` wired into `compose_standard_bridge`
  (`astrid/packs/__init__.py`, after restore-staging recovery).
  `absent→downloading(offset)→verifying→staged→installed(verified)` /
  `corrupt(reason)→repairing`; torn final line tolerated as a crash tail,
  mid-log garbage marks the log `corrupt`.
- Boot reconciliation legs: staged-bytes-present → hash-verify + atomic
  rename + fsync promotion (digest journaled at the `staged` event so the
  promotion can REFUSE drifted staged bytes); part-file present → offset
  refreshed from real bytes (filesystem wins over the journal); installed +
  size drift → flips `corrupt(size_drift)`.
- `acquire.py`: Range-resumable download (chunk-boundary offset journaling),
  typed refusal when the server refuses Range, clean restart on Range-ignore
  (200), hash-mismatch → `corrupt(hash_mismatch)` fail-closed.

## T8.2 Signed versioned manifests + tier discovery + preflight

- `manifest.py`: HMAC-SHA256 signed canonical payload
  `{schema, artifact_id, version, sha256, size, license_identity,
  license_text_sha256, os[], arch[], tier, tier_dependencies,
  min_ram_bytes}`; unknown schema versions and tampered payloads fail
  closed; pinned dev signing key (production rotates out-of-band).
- Tier discovery: OS/arch/RAM compatibility + **tier satisfiability**
  (`gpu` bundles require a declared gpu environment — never CUDA presence
  probing); deterministic tie-break (highest version).
- `preflight.py`: headroom = download × working-factor(2) + output margin;
  typed refusal names the exact shortfall BEFORE any byte moves.

## T8.3 Doctor deep re-hash + repair + probe registrations

- `repair.py`: `doctor setup` = reconcile-first (a hand-corrupted log cannot
  steer repair), then per-artifact deep re-hash against verified manifests,
  targeted re-acquisition of corrupt artifacts via injected setup-mode
  acquire, orphan reporting for unmanifested bytes. Untrusted manifests are
  invisible to repair.
- Doctor CLI: `astrid doctor setup [--source BASE] [--json]` in
  `astrid/core/doctor.py` (read-only checks unchanged; exit 1 on
  corrupt/repair_failed/orphaned).
- Probe registrations per E7 table: `wgp_runtime`,
  **`wgp_weights:<model>`**, `vibecomfy_runtime`,
  **`vc_weights:<template>`** (parameterized resolution in
  `resolve_probe`; import-time registry validation accepts parameterized
  names), `remotion_ready` now composes binaries AND the on-disk Remotion
  adapter bundle (`node_modules/@banodoco/*`). **No probe tests for CUDA.**

## Acceptance evidence (all named fixtures green)

| Fixture | Test |
|---|---|
| Kill-mid-download → Range resume from recorded offset | `test_setup_journal.py::test_kill_mid_download_resumes_from_recorded_offset_with_range` (real child `os._exit(79)` at boundary; origin sees `Range: bytes=1048576-` answered 206) |
| Kill-mid-verify → resume AT EOF, zero redownload | `::test_kill_mid_verify_resumes_at_eof_without_redownload` |
| Kill-mid-rename → completes without network | `::test_kill_mid_rename_completes_without_network` |
| Hash mismatch fail-closed + targeted repair | `::test_hash_mismatch_refuses_fail_closed_then_targeted_repairs` |
| Disk-full before any byte write | `::test_disk_preflight_refuses_before_any_byte_moves` |
| Manifest tamper / unknown version | `test_setup_manifest_preflight.py` |
| Hand-corrupted journal reconciled to filesystem truth | `test_doctor_setup.py::test_hand_corrupted_journal_is_reconciled_to_filesystem_truth` (+ absent/orphaned legs) |
| Deep re-hash catches same-size byte drift; repair re-acquires | `::test_corrupted_bytes_reported_without_network`, `::test_targeted_repair_reacquires_via_setup_mode` |
| Uninstalled capability → missing_prerequisites + one doctor command | `test_setup_probes.py::test_uninstalled_capability_refuses_with_missing_prerequisites` (`CapabilityUnavailable` → bridge maps to `422 capability_unavailable`) |
| Completing setup flips availability, ZERO code changes | `::test_completing_setup_flips_probe_without_code_changes` (same process/code/registry — only manifest+bytes+journal moved) |

Kill fixtures run a REAL threaded HTTP origin with genuine Range/206
support (`tests/v10/_setup_harness.py`) — resume is proven against actual
HTTP semantics, never simulated.

## Validation

- `python3 -m pytest tests/v10 -q` → 1195 passed, 2 skipped.
- `python3 -m pytest tests/integrations/reigh -q` → 292 passed, 12 skipped.
- Scoped `-k "setup or journal or doctor or preflight"` → 42 passed.
- Full batch suite: all remaining failures reproduce identically on the
  stashed clean tree (pre-existing environment legs, none touching B8):
  `tests/packs/rendering/test_timeline_visualize_*` + pack enum recoverability
  (checkout assumptions), ffmpeg compositor off-by-one pixels (codec build),
  `experiment_import` (pre-existing), remotion local-pack assumption.

## Carryover from prior instance

`tests/v10/test_wgp_gate2_contracts.py` one-line fixture fix
(`os.path.abspath(out)` return) committed as-is. `artifacts/m7/performance.json`
timing churn restored (not B8 substance).
