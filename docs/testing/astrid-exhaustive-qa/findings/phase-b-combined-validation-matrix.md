# Phase-B + live-agent UX validation matrix

Date: 2026-08-24  
Scope: the resolved integration of current `main`, `origin/phase-b`, and the
live-agent UX campaign  
Method: staged gates followed by fresh-agent, user-shaped journeys

## Purpose and decision rule

The supplied merge recipe is a useful starting smoke test, but it is not a
complete acceptance plan for this repository. The refs are divergent, the
merge has product conflicts, and phase B adds a second set of lifecycle,
bridge, setup, generation, and gallery contracts. A green `pytest` run is
necessary but cannot establish that a new agent can use Astrid without source
diving or that CLI, SDK, HTTP, and the kernel agree.

Promote the integration only when:

- every blocking automated gate below is green;
- every P0/P1 live journey has a fresh-agent pass and durable evidence;
- failures are typed, state-preserving, and actionable;
- every mutation can be read back from the canonical surface it claims to
  update; and
- there are no transient staging paths, split databases, implicit legacy
  authorities, duplicate child admissions, or unverified managed bytes in the
  observed evidence.

Do not push, tag, or delete the phase branch as part of these gates. Preserve
the safety branch and the generated evidence until the combined result has
been reviewed.

## Evidence protocol for live waves

Give each fresh Luna one brief, not a checklist of implementation details. The
agent may use `python3 -m astrid --help`, family help, the SDK discovery API,
the selected capability's `STAGE.md`, and public HTTP routes. It must not grep
source or call `run.py` directly. Each wave records:

1. the isolated `ASTRID_PROJECTS_ROOT`, exact commands/SDK calls, and elapsed
   time to first correct action;
2. wrong or retired verbs, guessed IDs, manual JSON/path transformations, and
   any source dive;
3. response envelopes, receipts, IDs, versions, event heads, artifact
   locators, and the final read-back (not just the agent's narrative);
4. whether a failed or stale operation changed zero rows/bytes/events and
   whether recovery was obvious; and
5. the friction category: discoverability, interpretability, safety,
   ergonomics, latency, or missing capability.

Use a fresh root for each wave. For a multi-surface journey, the same root is
intentional: it proves convergence. A disposable setup is sufficient for
offline product journeys:

```bash
QA_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/astrid-phase-b-qa.XXXXXX")
export ASTRID_PROJECTS_ROOT="$QA_ROOT/projects"
mkdir -p "$ASTRID_PROJECTS_ROOT"
python3 -m astrid doctor --projects-root "$ASTRID_PROJECTS_ROOT" --json
```

Keep source media outside the project root until import admission succeeds.
When an actual video/audio fixture is needed, verify `ffprobe` is installed;
do not substitute a Git-LFS pointer for a decodable fixture.

## Gate 0 — integration identity and reproducibility

Run from the clean integration worktree, before any live wave:

```bash
git status --short
git log --graph --decorate --oneline -30
git merge-base --is-ancestor main HEAD
git merge-base --is-ancestor origin/phase-b HEAD
python3 -m compileall -q astrid tests scripts
git diff --check
```

Pass means the integration contains both ref tips, has no unresolved index,
and records the merge and live-UX replay commits separately enough to audit.
The original dirty worktree's unrelated files must remain on its safety
snapshot, not silently enter this result.

## Gate 1 — side-effect-free census, boot, and schema

These checks catch composition and CLI regressions before any expensive test:

```bash
python3 -m astrid --version
python3 -m astrid --help
python3 -m astrid help
for family in projects timelines media tasks runs serve doctor backup; do
  python3 -m astrid "$family" --help >/dev/null
done
python3 -m astrid doctor --projects-root "$ASTRID_PROJECTS_ROOT" --json
python3 -m pytest -q \
  tests/v10/test_boot_manifest.py \
  tests/v10/test_catalog_migrations.py \
  tests/v10/test_registry.py \
  tests/v10/test_standard_application.py \
  tests/v10/test_shared_service_authority.py \
  tests/v10/test_writer_uow.py
```

Help must not create `.astrid/astrid.sqlite3`; a pristine doctor response must
be `uninitialized`, `ok: true`, with a concrete next action. After the first
product command, schema versions, migration ownership, foreign keys, WAL,
and the single writer/owner lock must be healthy. On the phase-B schema,
assert the expected 22-table catalog rather than retaining the old 20-table
expectation.

## Gate 2 — phase-B focused automated suites

Run the phase-B contract families in separable groups so a failure identifies
the integration boundary. These are deterministic guards, not substitutes for
the live waves below.

### Kernel lifecycle, crash, and concurrency

```bash
python3 -m pytest -q \
  tests/v10/test_crash_atomicity.py \
  tests/v10/test_phase_a_fault_matrix.py \
  tests/v10/test_writer_uow.py \
  tests/v10/test_multi_task_journey.py \
  tests/v10/test_orchestrator_interleaving.py \
  tests/v10/test_lease_expiry_sweeper.py \
  tests/v10/test_shared_service_authority.py
```

Require atomic publication boundaries, no half-published managed bytes,
fenced leases/heartbeats, no duplicate child rows under retry/interleaving,
and terminal parent/child state that cannot be relabelled by an old fence.

### Reigh bridge, trust, task attempts, gallery, and capabilities

```bash
python3 -m pytest -q \
  tests/integrations/reigh/test_capabilities.py \
  tests/integrations/reigh/test_local_trust_gate.py \
  tests/integrations/reigh/test_multipart_parser.py \
  tests/integrations/reigh/test_workflow_digest_fence.py \
  tests/integrations/reigh/test_task_routes.py \
  tests/integrations/reigh/test_gallery_routes.py \
  tests/integrations/reigh/test_journey_phase_a.py \
  tests/integrations/reigh/test_local_bridge_server.py \
  tests/packs/reigh/test_capability_conformance.py
```

Require the 19 retained public capability IDs plus the render/custom-workflow
rows, exact child-only gate symmetry, boot-scoped trust token, Host/DNS and
no-token rejection, bounded multipart parsing, idempotent completion, wrong
fence/poisoned-byte rejection, gallery paging/filter/detail, managed media
`GET`/`HEAD`/Range/ETag, and project scoping. Keep route discovery and the
existing editor save/assets assertions while resolving the branch conflict.

### Setup, acquisition, generation, and rollout

```bash
python3 -m pytest -q \
  tests/v10/test_setup_journal.py \
  tests/v10/test_setup_manifest_preflight.py \
  tests/v10/test_setup_probes.py \
  tests/v10/test_generation_repository.py \
  tests/v10/test_vibecomfy_binding.py \
  tests/v10/test_wgp_binding.py \
  tests/v10/test_wgp_gate1_hermetic_rebase.py \
  tests/v10/test_wgp_gate2_contracts.py \
  tests/v10/test_wgp_gate3_platforms.py \
  tests/v10/test_wgp_gate4_conversion.py \
  tests/v10/test_wgp_gate5_corpus.py \
  tests/v10/test_wgp_rollout_drill.py
```

Require signed-manifest and license identity verification, no CUDA-only tier
guessing, exact disk shortfall, journal reconciliation from bytes rather than
journal claims, safe acquisition failure, generation/variant persistence,
VibeComfy/Wan2GP binding honesty, fixture conversion stability, and explicit
N+1 acceptance/rollback only with all five gates and a drained queue.

### Timeline registry merge and existing pack contracts

```bash
python3 -m pytest -q \
  tests/v10/test_timeline_registry_merge.py \
  tests/v10/test_shot_repository.py \
  tests/v10/test_reference_lifecycle.py \
  tests/v10/test_m4_contracts.py \
  tests/v10/test_m7_bridge_contention.py \
  tests/v10/test_m7_hardening.py \
  tests/v10/test_m8_installed_contract.py \
  tests/v10/test_m8_installed_journey.py
```

Require completion-time registry merge to be additive, preserve the document
byte-for-byte, emit one `timeline.registry_merged` event only when keys are
new, and return the new head for the next editor CAS. Archived/foreign/no-op
merges must be typed and write nothing. The 22-table registry/pack ownership,
installed contract, and bridge contention guards must remain intact.

Then run the attachment's broad selector as a smoke aggregate (after the
focused groups have classified failures):

```bash
python3 -m pytest tests/v10 tests/integrations/reigh tests/packs -x -q
```

The aggregate is useful for coverage, but `-x` is diagnostic only; it is not a
reason to skip the focused groups or to delete a conflicting test.

## Gate 3 — repository quality and packaged surfaces

Run the maintained project gates once the focused suites are green:

```bash
make check
make m4-gate
make m7-gate
make m8-gate
```

If Remotion dependencies are intentionally absent, record the honest skip and
run the real render lane in a workspace with `remotion/node_modules`. Do not
call a skipped typecheck a pass. `m8-gate` without an installed evidence bundle
is a diagnostic only; it must not publish a ship artifact.

For the render proof, regenerate (do not choose between) the two historical
`.oracle/findings/stacked-render-proof.txt` files after the integration. Verify
the output codec/pixel format, frame count, dimensions, layer order, sampled
pixels/text, provenance, and cleanup from the actual integrated Remotion
configuration.

## Gate 4 — one compact live-agent journey across all eight families

Use one fresh Luna on a new root. The journey is intentionally compact: each
operation proves a distinct contract, and the final read-back crosses a
surface boundary. The agent should narrate friction only after attempting the
task.

| Family | User-shaped brief and required evidence | One adversarial turn (not a second happy-path wave) |
|---|---|---|
| `doctor` | “Tell me whether this root is ready, then make it usable.” Run pristine `doctor --json`, create a project, and re-run doctor. Record `uninitialized → ready`, checks, schema, canonical DB path, and next action. | Corrupt/mismatch a disposable setup artifact or journal, then use explicit `doctor setup`; verify it re-hashes/reconciles from bytes, reports orphan/missing/corrupt state, and never lets a journal claim override reality. |
| `projects` | “Start a project and leave me able to resume it.” Create, show/read `plan.md`, update name/settings, `select`, `current`, list; omit `--project` once to prove workspace routing. | Use a foreign/unknown slug or isolated root; expect a typed failure and zero cross-project mutation. |
| `timelines` + `timelines shots` | “Create a primary timeline, add two clips/shots, revise it, pause it, then resume.” Create/default, save v1/v2, show, history, diff, visualize, archive/unarchive, and shot list/create/show/add/reorder/remove. Capture snapshot version, stream head/hash, receipt, event kinds, and visualization source identity. | Make a stale CAS save from an old version and try an archived render/save. Verify current version/recovery guidance, no write on failure, and that unarchive is safe to repeat. |
| `media` + `media references` | “Bring in a real image/video, verify it, move its managed location, and attach it to a reusable reference.” Import/list/show/verify/relocate/relate; create/update/reference metadata merge and `{}` clear; associate/link/set-primary/list/show. Record exact project-scoped identity and digest. | Import a deliberately undecodable video/audio pointer; delete/mutate a source before verify; try foreign/ambiguous reference. Require pre-admission rejection or typed integrity failure with no phantom row/event/bytes. |
| `tasks` | “Queue a timeline evidence task and understand what is blocked or failed.” Create with a real capability/spec, list/show/events, and inspect dependency/readiness state. Use only current verbs, never retired `attach/next/start/ack`. | Submit malformed capability/spec or an unsatisfiable dependency; verify concise pointer/recovery evidence, no accidental run, and no hidden filesystem task store. |
| `runs` | “Find the run created by that invocation and operate it safely.” List/show with derived child progress and evidence, inspect events, then cancel or retry an eligible failed child. Reconcile SDK/result, kernel rows, receipt, attempts, and durable artifacts. | Replay a terminal or stale operation; verify it cannot be relabelled and no `run_root`/temporary staging path appears in output. |
| `serve` | “Use the local editor bridge to inspect and save the timeline.” Start on an ephemeral port with `--no-open-editor`, `GET /health`, `GET /routes`, list/load, save with exact expected version/idempotency key, fetch an asset. Compare bridge save with CLI show/history/visualize. | Repeat the same key, send stale CAS, omit/forge trust token, spoof Host, and issue a `HEAD`/Range request. Verify typed 403/409 responses, no duplicate event, and safe ownership handoff after shutdown. |
| `backup` | “Move this project to a fresh root and keep it usable.” Create a portable backup, restore cross-root, run doctor, list/show project/media/timeline, visualize/render, and read events. Record rebased destination CAS locators and preserved provenance. | Remove/mutate a source or backup snapshot before create/restore; require fail-before-publication and no damage to the live destination. |

The agent must complete the journey using public CLI/SDK/HTTP surfaces. A
successful command is not enough: compare at least one mutation through two
read surfaces (CLI versus bridge or SDK versus CLI) and verify the canonical
kernel snapshot plus immutable event history. Do not repeat the already closed
timeline-authority, alpha-MOV, JSON-noise, or staging-cleanup waves as separate
full campaigns; fold those assertions into this single journey's render,
visualize, and run read-back.

## Gate 5 — phase-B live bridge and generation wave

Use a second fresh Luna and a clean root because these flows exercise the
worker-facing trust boundary rather than ordinary editor ergonomics. Provide
the natural brief: “As a local worker, discover a supported generation family,
admit one parent, claim it, heartbeat, admit its planned children, complete one
with multipart bytes, and inspect the resulting gallery item.”

The agent must discover the capability rather than memorize IDs, then prove:

- public family admission succeeds only for an available configured binding;
- browser/public requests cannot directly admit child-only capabilities;
- a valid parent attempt envelope is required for child admission;
- claim, heartbeat, completion, failure, retry, and lease expiry respect the
  attempt/lease/status-version fence;
- lost completion acknowledgement is idempotently replayable, while wrong
  fences, poisoned bytes, malformed multipart, and cross-project IDs fail
  closed;
- generation and variant rows appear in the gallery with bounded paging,
  starred filtering, project-scoped detail, and primary-variant summaries;
- managed content serves correct bytes, Range, ETag, and HEAD semantics; and
- workflow digest/model binding errors state the missing prerequisite instead
  of silently falling back to another backend.

This wave is not a duplicate of the editor bridge wave: it is the only live
journey that treats the bridge as a worker protocol and tests the phase-B
trust/attempt/child/generation boundary end to end.

## Gate 6 — setup/acquisition and renderer reality

Use a third fresh Luna, with optional runtimes absent first and present only in
a separately declared environment. Brief: “Prepare the required image/video
generation runtime, explain what is missing, then render a small timeline with
one registered element and an alpha layer.”

The agent should use discovery and the selected `STAGE.md`, attempt an honest
local preflight, and record whether missing credentials/runtime/template/disk
capacity is identified before admission. With available fixtures, exercise
one standard MP4 render, one registered external element/declared asset, and
one explicitly alpha-stamped ProRes 4444 MOV. Verify:

- canonical `timeline_ref` and expected-version pinning, not an accidental
  file/legacy route;
- profile/canvas compatibility and concise pre-admission failures;
- durable CAS artifact/provenance paths only, no deleted staging root;
- visibly executed element asset with correct layer order; and
- real media output metadata, alpha pixels for the MOV, and clean temporary
  directories after completion.

Do not spend another wave re-proving ordinary opaque MP4 aliases or JSON
stdout if the combined journey already captures them; replay only a failure
with a new agent and unchanged brief.

## Gate 7 — final evidence and handoff

After all waves:

```bash
python3 -m astrid doctor --projects-root "$ASTRID_PROJECTS_ROOT" --json
git diff --check
git status --short
```

Publish a combined report containing the merge SHA, focused-gate summaries,
live wave IDs, exact roots/commands, render/backup artifact hashes, known
optional skips, and any remaining P2/P3 friction. A fix is only closed when a
different fresh agent replays the unchanged brief. Keep any open F0/F1,
unknown authority, unbounded failure, or data-loss issue blocking promotion.

## Non-redundancy rules

- One compact eight-family journey owns ordinary CLI/SDK ergonomics and
  cross-surface authority evidence.
- One worker-protocol journey owns Reigh trust, attempts, child admission,
  gallery, and managed-content semantics.
- One setup/render journey owns model manifests, binding honesty, real
  renderer output, alpha, elements, and cleanup.
- Focused pytest groups map to phase-B implementation boundaries; they are
  not repeated as live stories.
- Existing live reports remain evidence for already closed regressions. Only
  replay them if merge reconciliation touches their authority or lifecycle
  path, or if the combined journey discovers a regression.
