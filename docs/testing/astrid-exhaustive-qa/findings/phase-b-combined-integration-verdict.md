# Phase-B + live-agent UX integration verdict

Date: 2026-08-24

## Scope and merge decision

The supplied fast-forward recipe was not safe against the current refs:
`main` and `origin/phase-b` had diverged.  The integration therefore used a
dedicated worktree and an explicit merge commit, then replayed the exhaustive
live-agent UX campaign on top.  Both ref tips remain ancestors of the result.
The original worktree and its unrelated local work were not used as a merge
scratchpad.

The historical `WIP: preserve exhaustive live agent UX campaign` commit is an
intentional safety checkpoint, not the release verdict: it preserves the
pre-merge campaign byte-for-byte so the later merge-resolution and hardening
commits remain auditable.  Rewriting it now would discard useful ancestry and
invalidate all subsequent reviewed commit IDs.

## Adversarial fixes made after integration

The combined review and live waves found and repaired contract gaps that were
not visible on either branch alone:

- boot-manifest, owner-lock, writer, WAL-replacement, setup-journal, and
  setup-path fail-closed boundaries;
- Reigh route discovery/composition, Host/token/OPTIONS trust, task bridge,
  gallery/media transport, and typed failure behavior;
- task cancellation/completion fencing, grouped retry eligibility, and run
  event/retry operator guidance;
- canonical CAS locator admission, backup symlink rejection, portable
  external-media rebasing, and restore provenance;
- timeline registry merge, event-chain verification, stale materialization
  rejection, archive state, and render/visualize hash-head observation;
- renderer process transport preserving virtual-environment executables,
  real Remotion parity, and regenerated stacked-layer pixel evidence;
- schema compatibility, pack composition, installed-wheel behavior, import
  boundaries, and deterministic MIME derivation across Python/host databases.

The sense-check wave specifically found four authority escape hatches:
tampered timeline streams could leave a stale materialization readable,
backup/restore accepted unsafe symlinks, setup staging could traverse a
symlinked temp directory, and Reigh `OPTIONS` skipped Host validation.  All
now reject the unsafe state and have focused regressions.

The final contract battle found and repaired a second set of release blockers:
managed frozen-pack cleanup could delete an arbitrary user-owned directory
whose ancestor merely had Astrid's temp prefix; failed verification leaked
reconstruction trees; replay reported the currently installed executor rather
than the admitted version; and timeline authority was hashed for idempotency
but not rechecked at execution. Temp deletion is now restricted to exact
process-created inode identities, verification failures reclaim their trees,
executor definition identity is persisted and fenced before execution, and
kernel heads, legacy event-log bytes, and frozen manifest/SNS/focus are checked
inside the actual visualization runner. Legacy schema-v1 project indexes
without child digests remain readable, while new indexes bind each child and
duplicate identities or explicit null/mismatched digests fail closed.
Cleanup and cache-repair replacement probes also move/replace the target during
the critical section and prove the replacement sentinel survives. Recursion is
FD-relative within the verified private temp root; Astrid does not claim to
defend against a hostile same-UID process deliberately injecting a new child
inside that random mode-0700 root during the unlink syscall, because POSIX has
no inode-conditioned unlink operation. That actor is outside Astrid's local
same-user trust perimeter.

The final undefined-name and agent-UX battle then found several dormant or
merge-only defects: missing runtime imports in manifest hashing, atomic JSON
errors, RunPod teardown, refine, thumbnail, and hype paths; a trusted-view
record that was declared like a dataclass but could not be constructed; a
gateway frozen-view cleanup leak; an unregistered first-party `runaway`
schema pack; legacy retries that could skip executor-definition fencing; and
generated navigation commands that omitted their required project. These are
now repaired. Public visualization preflight also rejects empty sources,
invalid enum/numeric values, mutually exclusive selectors, invalid frozen
focus/refresh combinations, incompatible filmstrip inputs, malformed project
slugs, and `--out` before kernel admission. Independent Luna re-audits found
no remaining P0/P1 authority, cache-safety, manifest, managed-media, or public
agent-UX release risk.

## Live product evidence

- The fresh eight-family CLI/SDK journey exercised projects, timelines,
  media, tasks, runs, serve, doctor, backup, references, and shots on a
  disposable root.  Lifecycle, contention, failure recovery, and portable
  restore passed.
- The timeline-specific journey created, added, removed, moved, archived,
  unarchived, visualized, rendered, restarted, and restored state.  Seven
  canonical hash-chained timeline events replayed to the same terminal event
  ID/hash and config digest.  The materialized document behaved as a
  projection; mutations routed through the event log and CAS head.
- The Phase-B HTTP journey exercised health/routes, Host/token/OPTIONS trust,
  CAS conflict preservation, task claim/heartbeat/failure, gallery, media
  GET/HEAD/Range/ETag, and restart persistence.  It exposed and fixed the
  missing task-bridge composition in CLI `serve`.
- The real stacked render ran after integration: H.264, 24 frames at 320x180,
  AAC, `rendering.layer-stack` to `rendering.ffmpeg-compositor`, correct z
  order, transparent overlay, and sampled-pixel proof.
- A final public-CLI authority replay saved a fresh kernel timeline at v2,
  visualized it, exactly replayed the same run/task/artifacts, saved v3, and
  observed a new run and pack pinned to the v3 event/hash. Durable
  `--from-view` navigation then succeeded with no rehydration temp tree left.
- The final live serve gate started the integrated bridge on port 17400,
  returned `{"ok": true}` from `/health`, and shut down cleanly.

Durable wave reports:

- `waves/live-eight-family-agent-ux-acceptance-2026-08-24.md`
- `waves/replay-timeline-eventlog-live-6.md`
- `waves/phase-b-live-http-cli-acceptance-2026-08-24.md`
- `.oracle/findings/stacked-render-proof.txt`

## Automated evidence

- `make check`: passed, including structure, doctor, Ruff and mypy baselines,
  import-cycle admission, real Remotion TypeScript checking, and 18 renderer
  parity cases.
- The attachment's exact combined kernel/bridge/pack slice passed on the
  integrated tree with a host-calibrated per-test timeout: **3,331 passed,
  59 skipped, 172 subtests passed**, zero failures, in 29m58s. The sole warning
  was the expected legacy-selector auto-routing notice from the audio-render
  compatibility test.
- The final-tip changed-contract sweep passed **544 tests with 1 skipped** in
  5m21s after the last Luna battle fixes. It covers every timeline-visualize
  module plus handler/version fencing, gateway frozen-view cleanup, atomic I/O,
  first-party pack inventory, and the public timeline CLI.
- The final-tip undefined-name sweep (`F821/F822/F823`) passed across all
  production and test Python, `compileall` passed, and `git diff --check` was
  clean.
- The installed-wheel smoke passed from an isolated environment, covering
  version/help, doctor JSON, packaged resources, the expected missing-resource
  failure, and protection against imports leaking back to the checkout. Its
  wrapper was also made safe under macOS Bash 3.2 with `set -u`.
- Focused reconciliation and adversarial lanes: hundreds of checks passed
  across bridge/WAL, media, backup/setup, task/timeline, CLI/SDK, v10 release,
  installed-wheel, renderer, and authority contracts.
- M7 dogfood plus external portability/hardening: 11 passed after teaching the
  snapshot to ignore only intentional physical locator rebasing and restore
  provenance.
- Real layer-stack module: 13 passed; proof test was not skipped.
- The attachment aggregate found and fixed host-dependent YAML MIME behavior.
- The prescribed aggregate reached 539 passing tests with no semantic failure
  before the installed-wheel factoring test's three nested kernel subprocesses
  exceeded pytest's strict 120-second host timeout. The installed journey was
  rerun separately with a 600-second allowance and passed 2 tests in 179.53s.
- With both installed-wheel stress cases separated, the aggregate advanced to
  691 passed and 1 skipped before the independent 100+ crash fault matrix hit
  the same global 120-second pytest timeout. That exact fault matrix had
  already passed alone in 117 seconds; its assertions did not fail.
- The extended 100+ crash Phase-A fault matrix passed once in isolation at
  117 seconds.  Under heavy concurrent host load it reached pytest's strict
  120-second wall-clock guard; this is recorded as timing contention, not a
  semantic assertion failure.

Earlier host-timeout observations below are retained as audit history; the
successful 3,331-test combined run supersedes them as the promotion result.

## Timeline authority verdict

Timeline writes should route through the canonical event log and version/CAS
head.  `assembly.json` is a derived, validated materialization for consumers;
it must never become a second mutable authority.  The integrated behavior now
matches that model: mutations append verified events, reads observe the head,
stale writes change nothing, repair rejects corrupt history, and backup/restore
preserves replay identity.

## Promotion rule

The integrated branch is ready to push after its clean-tree check. Remote
push, source-branch cleanup, and the historical archive tag are intentionally
outside this integration operation.
