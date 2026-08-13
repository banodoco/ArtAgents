# Task — Batch 7 oracle rework (8 blocking issues)

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Situation

The Batch 7 oracle (read-only Grok 4.6 review, `.oracle/checkins/batch-7.md`)
returned NOT PASS with 8 blocking issues. Fix ALL of them. The epic is
"Pluggable Timeline Renderers" — a public renderer contract, dependency
inversion, qualified-ID discovery, provenance, SDK, scaffold, replay.

## Issues to fix

### 1. Replay CLI never documented (blocking)

`python3 -m astrid renderers replay` / `python3 -m astrid replay` is missing
from the author docs. Add the `replay` verb to:
- `docs/packs/aliases-vs-forks-vs-overrides.md` (the CLI verb list at
  ~line 282 — currently `create|list|inspect|validate|smoke`, add `replay`);
- `astrid/core/gateway/help.py` (~line 93) — the renderers help text;
- the golden-path recaps in `docs/guides/debugging.md` (~137-145) and the
  rendering `SKILL.md` (~244-252) — extend them past `smoke` to include
  `replay`; and
- `docs/contracts/render-backend-v1.md` — document the `replay` verb with a
  worked example (bundle capture → `replay <bundle-dir>` → drift
  acknowledgement).
Also `astrid/packs/rendering/skill/STAGE.md` does not exist; the updated
`executors/render/STAGE.md` was touched instead — ensure the docs that DO
exist cover replay. Check `docs/reference/sdk.md` too: it documents
`render/support` but not `replay` — add a short section.

### 2. Async/remote/compositing not all deferred (blocking)

The frozen contract only defers "asynchronous remote jobs". Add explicit
deferral statements for ALL THREE: async jobs, remote infrastructure, and
layer compositing — in `docs/contracts/render-backend-v1.md` (the V1 scope
section) and the guides. State: V1 is synchronous local execution only;
asynchronous job scheduling, remote render infrastructure, and layer
compositing are explicitly deferred beyond V1 and are NOT part of the V1
renderer contract.

### 3. Replay bundle incomplete (blocking)

`astrid/core/rendering/replay.py::write_replay_bundle` persists only
`bundle.json` + `request.json` + `inputs/<sha>`. Add to `bundle.json`:
- `support_report` (when the invocation captured one),
- `source_pack`/`trust` identity (candidate pack id, source_kind,
  eligibility/trust method — pass them in `ReplayBundle.metadata` from the
  service),
- `backend_config` (the request's backend_config),
- result hashes (when a partial result was written, record its sha256 and
  copy it under `partial-result-<sha>.json` instead of inlining raw bytes).
Extend `ReplayBundle` with optional fields: `support_report`,
`result_path`/`result_sha256`; update `write_replay_bundle` to write
`partial_result` as a localized hashed file (`partial/<sha256>`) and record
the descriptor. Keep the bundle self-contained and host-path-free.

### 4. Redaction gaps (blocking)

- `request.json` (the localized wire request) may carry secrets in
  `backend_config` / `metadata` — redact it with the transport's redaction
  helpers before writing (reuse `_redact_metadata` on the localized
  payload).
- `partial_result` must be redacted too (it is backend-authored and may
  echo secrets).
- Host paths in copied inputs: a copied `theme.json` (or any JSON input)
  may contain absolute host paths (e.g. `"file": "/Users/.../x.mp4"`).
  After copying each input under `inputs/<sha>`, rewrite JSON inputs so
  absolute host paths under common keys (`file`, `path`, `timeline_path`,
  `assets_registry_path`, `theme`) are replaced with bundle-relative
  references when the referenced file is also an input, else redacted as
  `<host-path>`. (Simplest correct: for JSON inputs, deep-walk and replace
  any string that is an absolute path under the repo/home roots with the
  basename or `<host-path>`; do NOT rewrite non-path strings.)

### 5. Capture excludes support (blocking)

`_REPLAY_VERBS` in `astrid/core/rendering/service.py` is
`{"render", "finalize", "plan"}`. Support failures must ALSO produce replay
bundles (a support call can fail with a backend bug). Add `"support"` to
`_REPLAY_VERBS`. Ensure `_InvocationContext` records support invocations too
(check where `_last_invocation` is set — it is set in `_run_command`, which
all verbs go through; verify support uses `_run_command`).

### 6. Request digest pins wrong object (blocking)

`_build_replay_bundle` computes `request_digest=compute_request_digest(request.to_dict())`
on the ORIGINAL request (absolute paths), but `write_replay_bundle` writes a
LOCALIZED `request.json` (bundle-relative paths). Replay then hashes the
localized file and refuses a mismatch. Fix: the bundle's `request_digest`
must be the digest of the LOCALIZED request payload (what replay will
verify). Compute it in `write_replay_bundle` after localization and store it
in `bundle.json` (overriding the passed-in value), OR localize first and
hash the localized dict in the service. Make the on-disk
`bundle.json["request_digest"]` == sha256-consistent digest of the on-disk
`request.json` bytes as replay computes it. Keep `test_replay.py` green —
it builds bundles with `compute_request_digest(payload)` where the payload
uses `inputs/<digest>` paths ALREADY localized; make the two consistent.

### 7. test_freeze FakeTransport-only + audit misses profile.py/Root (blocking)

- `tests/core/rendering/test_freeze.py` uses only `FakeTransport` for the
  built-in paths. Add at least ONE real-service path (use the real
  `rendering.ffmpeg` via `CommandTransport` + a tiny generated timeline,
  like `tests/core/rendering/test_service.py::test_real_ffmpeg_renders_through_generic_service`
  already does) asserting exactly one video + one committed sidecar, and
  one real failure path (missing binary → no sidecar, temps cleaned).
- `tests/core/rendering/test_generic_code_audit.py` scans nine
  `astrid/core/rendering` files but misses `profile.py` and the top-level
  `astrid/` root. Extend the scan to include `profile.py` and assert the
  top-level package root (`astrid/__init__.py` and `astrid/sdk/`) also
  contain no concrete backend names outside allowlisted compatibility.

### 8. verification.md + tags inaccuracies (blocking)

- `.oracle/verification.md` claims "7778 passed / 62 failed — all
  pre-existing" but also "tags C0..C7" which is FALSE: there is no Batch 7
  freeze tag, and loose tags like `C2-batch1-done` are unbound from
  sessions. Fix the record: tag the current HEAD `C8-batch7-done`, and
  record the REAL per-gate evidence (the numbers you can reproduce with the
  commands in this task — do NOT fabricate; run what you can, mark
  unreproducible gates as "not re-run in rework; see prior record").
- `verification.md` says "Full suite (CI mirror)" is `pytest -q -m "not
  integration and not opt_in"` but the frozen acceptance wants `make ci`
  recorded. Add a `make ci` row (run it if it completes in reasonable time;
  it is heavy — if it exceeds ~20 min, record the individual gates that
  make it up: check, editable, wheel, ci-mirror).
- The Remotion parity note must distinguish chromium-denial skips from real
  renders (the parity tests treat `MachPortRendezvousServer` denial as
  success-with-skip — record that explicitly).

## Acceptance

- `pytest -q tests/core/rendering` passes (except the documented
  pre-existing model-trends env failure).
- `pytest -q tests/core/rendering/test_replay.py test_replay_bundle.py`
  passes with the new bundle fields.
- `pytest -q tests/core/rendering/test_generic_code_audit.py test_freeze.py`
  passes with the extended scope.
- `bash tests/verify_docs_commands.sh` passes; grep the docs for `replay`
  coverage and the three deferral statements.
- `.oracle/verification.md` corrected; `git tag C8-batch7-done` applied.

Do NOT modify `contracts.py`, `schemas/`, the backends, the facade, or
`astrid/sdk/rendering.py` (SDK docs yes, SDK code no). Preserve all existing
work. Report: files changed, test results, evidence for each of the 8.
