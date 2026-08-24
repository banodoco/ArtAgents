# Live-agent UX coverage matrix

Updated: 2026-08-24

This campaign evaluates Astrid by giving fresh agents real maker goals and
watching them use the public product. It is not a broad unit-test campaign.
Automated checks are added only after a live journey demonstrates a durable
failure mode.

## Evidence states

- `mapped`: public surface and user-shaped briefs are documented.
- `running`: a fresh Luna is attempting the workflow in an isolated root.
- `observed`: a live report and final-state evidence exist.
- `fixed`: the product/docs were changed at the root cause.
- `replayed`: a different fresh Luna completed the same goal after the fix.
- `hardened`: the live failure has a narrow regression guard where useful.

## Domain matrix

| Domain | Representative live goal | Initial state | Priority |
| --- | --- | --- | --- |
| Orientation and project lifecycle | Discover Astrid, create/update/select/show a project, understand slug vs id and `plan.md` | fixed and replayed (`replay-orientation-errors-3`) | P0 |
| Timeline lifecycle and authority | Create/default/show/save/archive; prove CLI/editor changes share the kernel snapshot, version head, and hash-chained audit | fixed and replayed (`replay-timeline-authority-2`, `live-editor-timeline-events-2`) | P0 |
| Timeline conflict recovery | Preserve two editors' changes after a stale-version failure | fixed and replayed (`replay-timeline-conflict-2`) | P0 |
| Shot curation | Create/add/reorder/remove shot items without deleting project media; recover from invalid permutations | fixed and replayed (`replay-media-reference-shot-2`, `replay-doctor-shots-error-polish-2`) | P0 |
| Media identity and integrity | Import/list/show/verify/relocate/relate; reject undecodable video/audio before mutation; recover from missing or mutated bytes | fixed and replayed (`replay-media-integrity-2`, `replay-media-import-decodability-2`) | P0 |
| References | Create/update/archive/link/associate/set-primary with metadata merge/clear and ambiguity recovery | fixed and replayed (`live-references-shots-composite-3`, `replay-reference-metadata-merge-4`) | P0 |
| Capability discovery | Find the right executor/orchestrator/element from a natural goal without source-grepping | fixed and replayed (`replay-capability-discovery-2`) | P0 |
| Kernel admission and read-back | Invoke a capability, then reconcile SDK result with CLI run/task/events and one canonical ledger | fixed and replayed (`replay-generate-image-3`) | P0 |
| Image generation | Choose model/mode/backend, preflight honestly, create an artifact, find its provenance | fixed and replayed (`replay-generation-local-5`) | P0 |
| Audio generation | Generate music/voice/SFX or fail with an actionable prerequisite and honest manifest | fixed and replayed (`replay-audio-video-preflight-2`) | P1 |
| Video generation | Exercise t2v/i2v/flf requirements, missing credentials, artifacts, metadata, and recovery | fixed and replayed (`replay-audio-video-preflight-2`) | P1 |
| Rendering | Visualize/render canonical version-pinned MP4 and transparent alpha MOV; preserve machine JSON, layering, failures, replay bundle, managed media, and provenance | fixed and repeatedly replayed (`replay-canonical-render-followup-3`, `replay-canonical-render-preflight-4`, `replay-managed-alpha-mov-3`) | P0 |
| Elements and themes | Discover/fork/use effects, animations, transitions, and declared assets | fixed and replayed (`replay-extra-pack-render-2`) | P1 |
| Packs and customization | Distinguish alias/fork/override and complete the supported customization path | fixed and replayed, including cleanup (`replay-render-cleanup-2`) | P1 |
| Task lifecycle | Create/inspect/cancel/retry dependency-gated work without inventing retired verbs | fixed and replayed (`replay-task-dependency-2`, `live-task-run-ledger-regression-6`) | P1 |
| Run lifecycle | Find indirectly created runs; inspect progress/events; cancel/retry/close legally; never expose transient staging roots | fixed and replayed (`replay-retry-envelope-5`, `replay-sdk-staging-contract-2`) | P1 |
| Serve/editor bridge | Start, discover readiness, read/save timeline over HTTP, handle CAS and assets | fixed and replayed (`replay-serve-editor-2`) | P1 |
| Doctor and diagnosis | Distinguish uninitialized, ready, and unhealthy roots without mutation; provide a direct next action | fixed and replayed (`replay-doctor-aggregate-3`, `replay-first-run-selection-isolation-2`, `replay-doctor-shots-error-polish-2`) | P1 |
| Backup and restore | Back up real project/media/timeline state, restore cross-root, and consume immutable old-root registry locators through verified derived rebasing | fixed and replayed (`replay-backup-restore-2`, `replay-restored-visualization-locators-3`) | P0 |
| Contention and handoff | Two agents share a root, distinguish owner contention from CAS, stop/recover cleanly | fixed and replayed (`replay-owner-contention-2`) | P1 |
| Cross-project isolation | Reject or clearly explain foreign IDs and relations without corrupting either project | observed pass with zero mutation (`live-doctor-isolation-1`) | P2 |
| Archive and return | Resume after abandonment/archive with clear visibility and safe recovery | fixed and replayed (`replay-archive-return-2`) | P2 |

## Observation rubric

Each fresh-agent report records:

1. Time and attempts to the first correct public command or SDK call.
2. Help/docs consulted, plus any source or test inspection. Source-diving is a
   severe discoverability failure unless the user's task is extension authoring.
3. Wrong, retired, or guessed verbs and whether the error redirects usefully.
4. Manual ID/path/JSON transformations and opportunities for a safer shortcut.
5. Whether failures preserve state and provide a concrete recovery action.
6. Whether the agent verifies final state from Astrid rather than trusting its
   own narrative.
7. A candid friction classification: discoverability, interpretability,
   safety, ergonomics, latency, or missing capability.

Severity is `F0` blocking/data-risk, `F1` major wrong-turn or source-dive,
`F2` repeated avoidable friction, and `F3` polish.

## Current status

- The post-fix cross-domain maker journey passed at 9.3/10 with no P0/P1;
  every P2 it surfaced was subsequently fixed and independently replayed.
- Canonical timeline render authority, JSON stdout discipline, media clip
  aliases, profile/canvas preflight, deterministic validation, and replay-
  stable failure detail are fixed and independently replayed.
- Transparent alpha-layer MOV now works through direct, project-managed, and
  canonical routes with real ProRes 4444 pixels and durable provenance.
- CLI and editor-bridge writes converge on one kernel timeline stream. Default
  selection is kernel-only; explicit legacy and frozen inputs now declare
  `source_mode` accurately and cannot mutate or outrank kernel state.
- The Phase-B integration replay adds fresh eight-family CLI/SDK, timeline
  event-log/render/restore, and Reigh HTTP/task/gallery acceptance.  It also
  regenerated the real stacked-render proof and adversarially closed timeline,
  backup, setup, trust, and serve-composition authority gaps.
- A final fresh CLI replay proved executor/head-aware idempotency: exact v2
  authority reused one run and artifact set, a v3 save produced a new pinned
  run, durable frozen drill-down succeeded, and temp reconstruction cleanup
  left no residue.
- The final integrated automated counts are recorded in
  `findings/phase-b-combined-integration-verdict.md`; `make check`, focused
  release-contract lanes, and live acceptance are blocking evidence rather
  than the earlier campaign-only changed-area count.
- Evidence corpus: **93 live waves, 58 finding/fix reports, 3 maps**.

The original P0 scout hypotheses about split SDK/CLI ledgers, the missing
capability-handler symbol, FLF end-frame admission, and pack-root propagation
were independently reproduced, fixed, and replayed (or have a replay in
flight). No product fix is marked complete from a scout report alone: the loop
is reproduce with a fresh user brief, fix the smallest root cause, then replay
the unchanged brief with another fresh Luna.
