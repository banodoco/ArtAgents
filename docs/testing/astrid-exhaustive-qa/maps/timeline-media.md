# Live UX map: timelines, shots, media, references, and editor bridge

Date: 2026-08-23  
Scope: live creative work by fresh agents using the CLI, editor bridge, and
visible/rendered outputs; repository contracts and automated coverage are
secondary regression evidence.  
Isolation rule: every executable wave must set a fresh, unique
`ASTRID_PROJECTS_ROOT` (for example `mktemp -d /tmp/astrid-timeline-media-XXXXXX`).

This is a dispatch map for Luna agents, not a claim that all journeys pass.
The primary question is whether an agent with minimal prior instruction can
make and inspect creative work, recover from mistakes, and feel confident
continuing. Do not coach the first attempt or lead with source/tests. Only
promote a reproduced live problem to an automated regression guard afterward.

## Reference surface map and authority

Use this section after a live brief to orient an observed failure or to choose
the smallest regression guard. It is deliberately secondary to the briefs.

There are three related but distinct surfaces:

| Surface | Entry points | Authority / output |
| --- | --- | --- |
| Product CLI | `python3 -m astrid timelines ...`; nested `timelines shots ...`; `media ...`; nested `media references ...` | One typed SDK call per verb; JSON is the five-key `{ok,data,error,receipt,idempotency_key}` envelope. |
| Typed SDK | `AstridClient.timelines`, `.shots`, `.media`, `.references` | Repository-backed DTOs and typed errors; mutations carry committed receipts, reads do not. |
| Editor bridge | `serve`; `GET/POST /projects/:slug/timelines/...` | Repository-backed HTTP DTOs; receipts and idempotency internals are deliberately secret. |

The kernel SQLite database is at
`$ASTRID_PROJECTS_ROOT/.astrid/astrid.sqlite3`, created lazily. Timeline
document state is projected from the `timeline.timeline` event stream and the
`timelines` projection; archived state is event-backed. Media identity is the
content hash plus a project-scoped media row; locations are replaceable aliases.
Shots and references own their own event streams and tables and may use exact
kernel `media_id` values as the cross-pack currency.

The clean-machine preamble for every wave is:

```bash
qa_root=$(mktemp -d /tmp/astrid-timeline-media-XXXXXX)
export ASTRID_PROJECTS_ROOT="$qa_root"
python3 -m astrid --help
python3 -m astrid doctor --json
python3 -m astrid projects create qa --name "Timeline/media QA" --json
```

The first probe on 2026-08-23 found the repository's default root already
owned by another process. The commands returned an unstructured service error
even for `--help`. A fresh `ASTRID_PROJECTS_ROOT` worked cleanly. Treat
contention behavior as a separate operational wave; never make a campaign
claim from the shared production root.

## Fresh-agent brief and observer protocol

Give the agent only the brief under test plus this note:

> You are working in a fresh Astrid project root. You may use the Astrid CLI,
> local editor/HTTP surface, and ordinary filesystem inspection. Start from
> the app's own help when you need to discover a command. You are trying to
> complete the creative brief, not inspect implementation details. Think
> aloud about what you expect each action to do, note confusing output or
> uncertainty, and recover from mistakes when possible. Do not edit source,
> commit files, access another project's data, or use the shared/default
> projects root. Stop after the brief is complete or after two honest recovery
> attempts and report what blocked you.

The observer records the transcript, commands, stdout/stderr, HTTP requests
and responses, screenshots/rendered artifacts, elapsed time, mistakes, docs or
source opened, recovery attempts, and a satisfaction quote. A final narrative
is not evidence: require a read-back or visible artifact proving the requested
state. Run each brief once with a fresh agent before introducing its deliberate
twist; replay any F2/F3 result with a second fresh agent to distinguish product
friction from an unusual agent choice.

Score each brief 0 (failed) to 3 (smooth) on:

| Dimension | Observe | Friction signal |
| --- | --- | --- |
| Goal understanding | Can the agent translate a creative brief without hidden schema knowledge? | It asks what timeline/shot/reference/primary means or makes an arbitrary choice that changes the result. |
| Surface discovery | Does help/output reveal the next action? | It guesses verbs, tries retired commands, swaps flag/positional order repeatedly, or source-dives before trying the obvious surface. |
| State visibility | Can it retain IDs, versions, order, primary, archive, and verification state? | It loses IDs, cannot inspect shot items, or trusts a receipt without read-back. |
| Mental model | Do registry, realm, role, position, primary, CAS, and layering behave as expected? | It treats save as a patch, locator as identity, remove as media deletion, or last visual track as top. |
| Mistake tolerance | Does a bad request fail safely and explain the next move? | Unstructured error, hidden zero-write behavior, ambiguous status, or no field-level guidance. |
| Recovery | Can it reload, repair, retry, merge, or continue without restarting? | It repeats the same failure, discards good work, or needs source/SQLite inspection. |
| Confidence and satisfaction | Can it explain why the result is correct and would it use Astrid again? | “I think it worked”, fear of retrying, “too much ceremony”, or a long unexplained pause. |

Classify friction as F0 (none), F1 (one recoverable hesitation), F2
(repeated guessing/source-diving/avoidable restart), or F3 (blocked, unsafe,
lost work, or false success). Capture the smallest durable fix: copy,
discoverability, output, guardrail, recovery path, or source bug.

### Brief cards to paste verbatim to fresh Luna agents

These cards intentionally omit command recipes. The observer supplies only the
fresh-root setup above.

#### LTM-01 — Make and find a first timeline (P0)

> Start with an empty Astrid project root. Make a project called “Night Walk”.
> Create a default timeline called “Rough Cut”. Then forget the command output:
> list the project and show the timeline. Leave it in a state another editor
> could pick up.

Observe discovery of projects/timelines, slugs vs IDs/ULIDs, default state, and
an empty document/version. Twist: ask it to show the timeline after it loses
the UUID. Proof is project and timeline read-back, not the receipt alone.

#### LTM-02 — Put a source clip on the timeline (P0)

> Continue the “Night Walk” project. Import the supplied source media fixture.
> Put it on “Rough Cut” so an editor can open or render it. Inspect both the
> timeline and media and explain how you know they point to the intended file.

Observe whether importing and registering are discoverably separate, whether
the agent preserves a stable asset key, and whether it distinguishes
hash/location/verification. Twist: give two similarly named files and require
identity-based selection. Proof is matching registry/media read-back and a
viewable/renderable result.

#### LTM-03 — Make a layered rough cut (P0)

> Make a 10-second rough cut from the available source media. Add a persistent
> brand label, a caption, and one moment-specific callout over the source. Open
> or render it and check that overlays are above the source in the intended
> order. If the first attempt is wrong, repair it without starting over.

Observe schema discovery, timing, missing-asset handling, and whether the agent
finds the key rule that the first visual track is top because visual tracks are
rendered in reverse array order. Proof is sampled frames or a viewer, not a
zero exit code.

#### LTM-04 — Recover a stale two-editor edit (P0)

> Two editors are working on “Rough Cut”. One adds a caption while the other
> changes the source clip. Make both edits from the same loaded version. When
> one edit is rejected as stale, reload, merge both intended changes, and save.
> Do not silently discard either edit.

Observe whether `expected_version`/CAS is discoverable, the error is actionable,
whole-document replacement is understood, and history/diff proves both edits.
Twist: first submit a malformed registry or boolean version. Proof is exactly
one old-head success, one safe conflict, then a merged next version.

#### LTM-05 — Curate and inspect a shot (P0)

> Import three different media files for “Night Walk”. Make a shot named
> “Opening beats”. Add A, B, C; insert a new take before B; reorder to C, A,
> new take, B; remove A. Finally show the shot and verify that A's media still
> exists in the project.

Observe nested-command discovery, distinction among shot/item/media IDs,
position/permutation understanding, and whether remove is understood as a
container edit. Twist: submit an incomplete reorder or foreign item and recover
without changing the shot. Proof is final exact order/positions plus surviving
media. Known gap: SDK has `shots.show`, but nested CLI has no `shots show`; a
CLI-only agent may be unable to perform the final inspection.

#### LTM-06 — Import, relocate, and repair media (P0)

> Import a folder containing nested source, still, and audio files. Find the
> imported items in deterministic order. Verify one, relocate it to a new local
> location, and verify again. Tamper with one file and try to verify it. Recover
> by restoring correct bytes or relocating to a valid copy. Explain which
> identity changed and which did not.

Observe folder fan-out, realm/locator/hash mental model, tamper failure safety,
and error-guided recovery. Twist: include a symlink, empty file, unknown
extension, or nested path. Proof is stable media identity through relocation,
failed tamper verify with no state change, then successful repair.

#### LTM-07 — Build a reusable character reference (P0)

> From the imported media, create a character reference named “Mara” using one
> canonical image. Associate a second image as a depiction, make it the new
> primary canonical image, and show the reference so another editor can use it.
> Keep the original association available.

Observe discovery of the nested references mount and concepts of kind, role,
association ID, and primary. Twist: use a bad role, duplicate, or foreign media
and recover from the error. Proof is two associations with exactly one primary.

#### LTM-08 — Link and archive safely (P0)

> Create “Mara” and “Old Station” references. Link them as related and add one
> directional relationship that makes sense. Archive “Old Station”. Confirm
> what remains in a normal list, an inclusive list, and direct show. Try to add
> another link after archive and recover without recreating it.

Observe symmetric `related_to` vs directional links, soft archive vs deletion,
preserved associations/bytes, and terminal error guidance. Twist: reversed
related link, self-link, or archived endpoint. Proof is retained history/graph
and safe post-archive rejection.

#### LTM-09 — Open the cut through the editor bridge (P0)

> Start the local editor bridge for the project you built. Open “Rough Cut”,
> save one small change, reload it, and open a registered media asset. Check
> the asset at full length and in a range. Restart the bridge and confirm the
> same cut is still there.

Observe serve discovery, health/readiness, wire identity, GET/HEAD/range/ETag,
and missing/HTTP-only/unsafe/unverified asset recovery. Twist: stale save from
another client plus an OPTIONS preflight. Proof is persisted reload, matching
bytes/hash, correct headers, and no receipt leakage. The bridge intentionally
has no shot/reference/media routes; record that as a surface gap if expected.

#### LTM-10 — Recover an inherited broken project (P1)

> You inherited a project with an archived timeline, failed media verification,
> incomplete shot reorder, and a reference whose primary image is wrong. Make
> the project usable for a new cut: identify readable history, repair media,
> finish the shot, and set the correct primary. Do not unarchive or delete
> history.

Observe historical reads vs terminal mutations, partial-failure continuity,
and whether a new active timeline is discoverable as the safe path. F3 if the
agent needs raw database surgery.

#### LTM-11 — Two projects, no cross-contamination (P1)

> Create “Client A” and “Client B”. Import similarly named media into both and
> create one timeline, shot, and reference in each. Intentionally use a Client
> A ID while operating on Client B. Finish one legitimate edit in each and
> prove neither project changed from the foreign operation.

Observe project scoping, safe not-found/validation, and whether names are
mistaken for identity. Proof is independent read-backs and unchanged state on
the rejected side.

#### LTM-12 — Five-minute ambiguous creative brief (P1)

> You have five minutes to make a 15-second social teaser called “Midnight
> Signal” from the available source media. It needs a source, bold caption,
> still or B-roll moment, and final brand card. Choose timing and names. Hand
> back the timeline, viewable/rendered result, and assumptions.

Observe what the agent does first without schema knowledge, time spent on IDs vs
creative work, layer choices, inspection before completion, and whether it would
use Astrid again. This is the highest-signal satisfaction brief.

## Live wave loop

Dispatch LTM-01 through LTM-05 first, uncoached. Then run LTM-06 through LTM-09
for cross-domain and editor behavior, and LTM-10 through LTM-12 for recovery,
isolation, and ambiguity. After each cluster, summarize the top three frictions,
replay affected briefs with fresh agents, and write a sanitized finding before
any fix.

Per-task record:

```text
brief_id, agent_id, isolated_root, revision, prompt verbatim,
commands/HTTP transcript, expected proof, observed proof, elapsed time,
wrong guesses/pauses, help/docs/source files opened, recovery attempts,
F0-F3 scores by rubric dimension, satisfaction quote, severity,
smallest proposed fix, replay status with a second fresh agent
```

## Timeline product surface

### Commands and expected contracts

| Verb | Ordinary task | Expected evidence | Main adversarial/recovery cases |
| --- | --- | --- | --- |
| `create` | Create a named timeline with a slug, optional config/registry, optionally default. | Success envelope; immutable UUID/ULID/slug; `config_version=1`; `is_default`; one receipt/event. | Bad slug, duplicate slug, duplicate key with same payload (replay), same key with changed payload (`idempotency_mismatch`), default replacement, project id vs slug, malformed config/registry. |
| `list` | Find active timelines in project. | Slug-ascending rows with `timeline_id`, ULID, name, default flag; no receipt. | Empty project, archived timeline hidden, cross-project isolation, deterministic ordering, missing project. |
| `show` | Load a timeline by UUID, lowercase Crockford ULID, or immutable slug. | Full config, `registry: {assets: ...}`, version, identity; no receipt. | All address forms, uppercase/invalid ULID, invalid UUID, missing/foreign project, archived direct lookup remains available. |
| `save` | Replace whole document under optimistic CAS. | New full load shape; version increments exactly one; receipt; history event. | Stale version (zero writes, typed `stale_version`), bool/non-integer version via bridge, malformed objects, `registry.assets` not object, retry/mismatch, two writers from same head. |
| `archive` | End a timeline's mutation lifecycle. | Archive result with timestamp and new stream version; one event/receipt; no config change. | Replay, second archive, save after archive (`terminal_state`), list hides it, show/history still work, default remains a potentially stale project setting. |
| `history` | Explain lifecycle. | Ordered `created`, each `saved`, `archived`; document/registry snapshots; archive has null content. | No-save timeline, archived timeline, malformed/corrupt event stream, deterministic ordering. |
| `diff` | Explain adjacent document/asset key changes. | Sorted `added/removed/changed` keys for document and `registry.assets`; archive excluded from content diff. | Nested values changed but same top-level key, registry-only change, no-change save, archive-only history, deleted/added assets. |

Important semantics to assert in every mutation journey:

- Timeline IDs are deterministic for an explicit idempotency key; identical
  retries return the stored result and receipt without new rows. A changed
  request under the same key must reject before any event/projection change.
- `save` is whole-document replacement, not a field patch. The persisted
  registry is normalized to `{assets: ...}`. `expected_version` is the stream
  head (`1` after create, incrementing once per save/archive); an archive
  increments the head even though it does not change document content.
- `list` is active-only. `show`, `history`, and `diff` remain historical reads
  after archive. Archive is terminal for mutations.
- Project default is projected from `projects.settings_json`; creating a new
  default should atomically replace the previous default. Test whether archive
  leaves an unusable default and how an editor recovers.

### Timeline document semantics and render-facing invariants

The bridge/editor document is intentionally loose at the persistence layer,
but render/viewer paths expect the Banodoco timeline shape:

```json
{
  "theme": "...",
  "theme_overrides": {},
  "tracks": [
    {"id": "brand", "kind": "visual"},
    {"id": "captions", "kind": "visual"},
    {"id": "source", "kind": "visual"},
    {"id": "audio", "kind": "audio"}
  ],
  "clips": [
    {"id": "src_1", "at": 0, "track": "source", "clipType": "media", "asset": "source", "hold": 3},
    {"id": "cap_1", "at": 0, "track": "captions", "clipType": "text", "hold": 3, "text": {"content": "Hello"}}
  ]
}
```

The registry is normally a separate `{assets: {key: {file, url, media_id,
content_sha256, type, resolution, fps, duration}}}` object. Verify these
cross-artifact invariants:

- every clip asset key resolves in the persisted registry when the viewer or
  renderer needs media; absent keys produce an honest warning/error, not a
  guessed path;
- media registry entries can resolve through `media_id` or a verified local
  location, while a locator is a path alias and never media identity;
- `tracks` and `clips` IDs are stable and unique; clips reference existing
  tracks; `at`, `hold`, `from`/`to`, and transitions are coherent and do not
  silently change duration;
- source, B-roll, captions/text, brand/CTA, effects, transitions, and audio
  can coexist; empty/missing media, stills, video, audio-only, remote URL, and
  mixed-media assets each produce the documented viewer/render behavior;
- whole-document save preserves unknown editor keys where the loose contract
  permits them, while registry normalization does not drop valid asset fields.

Layering gotcha: visual tracks render in reversed array order, so the **first
visual track in `timeline.tracks` is the top layer**. A first-wave visual task
must create overlapping `brand`, `captions`, `fx`, `broll`, and `source` tracks,
render/view them, and verify the observed order. This is a high-value
ergonomic hazard because a natural “bottom-to-top” list produces the opposite
result. Audio tracks follow visual tracks and are not z-layers.

## Shots nested under `timelines`

The only CLI mount is `python3 -m astrid timelines shots`; there is no top-level
`shots` family and no `shots show` CLI verb. The SDK does have
`client.shots.show(project, shot_id)`. This asymmetry is an observed discovery
and ergonomics gap: after `shots create`/`shots add`, a CLI user cannot inspect
the shot's items except via mutation results or the SDK. First execution should
decide whether this is intentional, document it prominently, or add a read
route (a source change requires a reproduced finding and owner approval).

| Verb | Ordinary task | Expected evidence | Tricky/recovery tasks |
| --- | --- | --- | --- |
| `list` | Find a project's shots. | Stable `sort_key`/id ordering; active rows; no receipt. | Empty project, cross-project ID, concurrent creates, names with whitespace/unicode. |
| `create` | Create an empty shot. | Shot id, name/metadata, empty items, event head 1, receipt. | Empty/whitespace name, non-object metadata, replay/mismatch, project id/slug, duplicate identity. |
| `add` | Insert exact project media into shot, default append or explicit 0-based position. | Item id/media id/position/source frame/metadata, ordered item IDs, event head. | Insert front/middle/end, negative/out-of-range position, bool/non-int, negative source frame, missing media, foreign media, missing/foreign shot, duplicate key and mismatch, concurrent insert. |
| `remove` | Remove an item. | Removed item facts + remaining ordered IDs; event head; receipt. Media row/bytes still show and verify. | Missing/foreign item, repeat removal, remove only item, remove middle and renormalize, idempotent replay/mismatch, archive/media relationship unaffected. |
| `reorder` | Submit exactly one full permutation (`--items` repeatable or comma-separated). | Exact item/media order and normalized positions; one event/receipt. | Omission, duplicate, extra, item from another shot, empty parser value, repeated key mismatch, no-op reorder. |

Shot evidence should always include `client.shots.show` (or a future CLI
equivalent), because list omits items. Verify add/remove are container edits:
they never delete or mutate the kernel media bytes or media row. Verify every
item's `position` and zero-padded `sort_key` are renormalized after an insert,
remove, or reorder.

## Media product surface

### Import, location, identity, and relations

| Verb | Ordinary task | Expected evidence | Adversarial/recovery tasks |
| --- | --- | --- | --- |
| `import` | Import one file or a directory. | One media read model per exact file; content hash, byte size, kind/MIME, metadata, managed location, verified timestamp, receipt. Directory output sorted depth-first with child keys `parent#N`. | Empty file, unknown extension, same bytes at two paths, changed bytes, missing root, directory containing symlinks/managed root/non-regular files, duplicate/replay, failure on one child (per-file atomicity), path outside scope. |
| `list` | Browse project media. | Created-at then ID stable order; full locations/relations as contract. | Empty list, cross-project isolation, large directory, managed/external locations. |
| `show` | Inspect one exact project-scoped media id. | Identity, all locations, relations; no receipt. | Missing/foreign ID, malformed ID, path moved out of band. |
| `verify` | Re-fingerprint a selected `--realm` local location. | Verified timestamp and receipt; no identity change. | Missing realm, multiple locations, missing bytes, tampered bytes (zero writes/events), symlink, concurrent mutation between pre-hash and transaction, replay/mismatch. |
| `relocate` | Replace one realm's locator while preserving media identity. | Same media ID/hash; location alias changed; receipt. | Nonexistent/unsafe/HTTP locator, missing realm, cross-project ID, repeated relocation, verify after relocation, old bytes still present. |
| `relate` | Add one or more typed media relation edges. | Relation IDs/kinds and receipt; `show` reflects edges. | Only frozen kinds (`derived_from`, `variant_of`, `uses_as_input`, `mask_for`, `audio_for`), self edge, duplicate, foreign endpoint, variant parent limit, variant cycle, atomic multi-edge failure, replay/mismatch. |

Media import copies bytes into a sharded managed path by SHA-256 unless an
explicit external realm is used. Content identity and filesystem location are
separate: identical bytes at different paths should deduplicate identity where
the repository contract says so, while a relocation changes only the location
projection. Directory import is a sequence of independent per-file commands,
not one all-or-nothing transaction; a wave must test and report this clearly.

The CLI `relate` help advertises `--from`, `--to`, and one `--kind`; the SDK
service accepts a `relations` sequence. Test the composed CLI shape for one
edge and the SDK shape for atomic multi-edge batches, because documentation
can otherwise imply more/less atomicity than the actual path.

## References nested under `media`

The only CLI mount is `python3 -m astrid media references`; references are
project-scoped and soft-archived.

| Verb | Ordinary task | Expected evidence | Adversarial/recovery tasks |
| --- | --- | --- | --- |
| `create` | Create a `character`, `place`, `object`, `clothing`, or `other` reference with one primary canonical media row. | Reference model, one canonical primary association, event head 1, receipt. | Invalid kind/name/metadata, missing/foreign media, duplicate identity, replay/mismatch. |
| `update` | Change name/description/metadata only. | Kind/project/media associations unchanged; receipt and event. | Empty update, unknown fields, archived reference (`terminal_state`), replay/mismatch, cross-project ID. |
| `associate` | Add one exact media association with `canonical`, `used_as_input`, `depicts`, or `inspired_by` role. | Association id/media/role/ordinal/context/primary flag; reference show includes it. | Duplicate, missing/foreign media, bad role, canonical ordinal rule, `used_as_input` context required and same-project, context role not permitted, archived reference, atomic batch (SDK). |
| `set-primary` | Atomically replace the primary canonical association by association id. | Previous/new primary, exactly one primary, event/receipt. | Target non-canonical, foreign association, missing current primary, archived reference, replay/mismatch, collision-safe ordering. |
| `link` | Link two references with `belongs_to`, `wears`, `located_in`, `associated_with`, or `related_to`. | Link row and event/receipt; directional kinds preserve direction. | Self-link, missing/foreign endpoint, archived endpoint, bad kind/metadata, duplicate; reversed `related_to` converges canonically, reversed directional link mismatches. |
| `list` | Browse active references. | Kind/name/id order; archived hidden unless `--include-archived`; no receipt. | Inclusive archived read, empty result, project isolation. |
| `show` | Inspect full reference including archived state, associations, and links. | Full association/link graph, primary marker, timestamps; no receipt. | Missing/foreign ID, archived direct lookup, links/bytes survive archive. |
| `archive` | Soft-terminally archive one reference. | `archived_at`, preserved association/link/media counts, event/receipt. | Replay, second archive, all later mutations/links rejected, list hiding vs show retention, media bytes still present. |

Frozen vocabularies and invariants are intentionally test targets, not merely
parser details. For every role/kind rejection assert zero new event rows,
unchanged head/projection, and a useful error. For every archived path assert
associations, links, and media remain readable and no cascade occurs.

## Editor HTTP bridge and viewer/asset interactions

The local bridge serves only:

```text
GET   /health
GET   /projects
GET   /projects/:slug/timelines
GET   /projects/:slug/timelines/:ref
POST  /projects/:slug/timelines/:ref/save
GET   /projects/:slug/timelines/:ref/assets/:key
HEAD  /projects/:slug/timelines/:ref/assets/:key
OPTIONS any path (CORS preflight)
```

Bridge task matrix:

1. Cold start: health, empty projects/timelines, invalid project/timeline
   grammar, missing project/timeline, malformed routes. Assert exact status,
   `{error,detail}` body, `Cache-Control: no-store`, and no receipt internals.
2. Provider load/save: load by slug/UUID/ULID, save valid whole document, then
   load again; stale save must be `409 timeline_version_conflict` with current
   `config_version` and zero changes. Invalid body/config/registry/version,
   including JSON `true` as version, must be typed 400. Schema-incompatible
   registry must be typed 422 with `issues[]`, never a connection-close 500.
3. CORS: allowed origins receive exact allow/expose headers; absent/unknown
   origins do not. `OPTIONS` is 204 with zero body. Exercise browser-like
   Content-Type/Origin headers and repeated save after reload.
4. Asset viewer: persist a registry entry tied to a media ID, then exercise
   GET and HEAD full bytes, single ranges (`start-end`, `start-`, `-N`), ETag
   304, oversized-body initial 206, clamped end, unsatisfiable 416, malformed
   or multi-range 400, missing key 404, HTTP-only asset 404 `asset_not_local`,
   unsafe `../`/absolute locator 404, missing/tampered/unverified local bytes
   404. HEAD must match GET status/headers without a body.
5. Restart/retention: stop/restart server and database, then load/save/asset
   requests. Assert the same persisted projection and no sidecar/FSA fallback.
   Two simultaneous saves from one version should produce exactly one success
   and one typed conflict, with no SQLite busy leak.

The bridge has no shots/references/media HTTP routes. A browser editor that
wants shot or reference state must use the product/SDK boundary or a future
adapter; this is an explicit cross-surface gap to test for accidental UI
assumptions.

## Reference composed journeys (after live briefs)

These compact journeys describe expected state transitions for observers and
regression follow-up. They are not substitutes for giving a fresh agent a
brief.

These are the minimum user-shaped journeys for a first broad wave. Each step
records command/HTTP input, output envelope, IDs, receipt/event evidence, and
the next read used to verify persistence.

### A. Build and inspect a timeline

Create project → create default timeline with empty config → list → show by
slug, UUID, ULID → save a source track and media clip with registry → show →
history/diff → load via HTTP → serve a registry asset → render/view overlapping
tracks. Expected: one coherent document, version increments, stable aliases,
asset bytes match content hash, overlay ordering is visible and correct.

### B. Edit under contention and recover

Load version `v`; issue two saves with `expected_version=v`; assert one success
at `v+1`, one typed conflict with current version and no second mutation;
reload, merge/reapply the intended edit, save with the new version; inspect
history/diff and verify no lost fields. Repeat with HTTP and SDK/CLI clients.

### C. Curate a shot from imported media

Import a directory containing source/still/audio fixtures → create shot → add
three media items at end/front/middle → inspect via SDK show → reorder → remove
middle → show media still present and verifiable → list shot/media. Expected:
exact item/media order and normalized positions after each mutation; removed
container item never deletes media bytes.

### D. Build a reference graph

Import two or more media → create character with primary canonical image →
associate another image as `depicts` or context-bearing input → set primary →
create a second reference → make directional and symmetric links → list/show →
archive one endpoint → assert list hides it, show retains it, bytes and links
remain, and new mutations are rejected. Repeat one operation with a replay and
one changed same-key request.

### E. Asset lifecycle with a timeline

Import media → register its media ID in timeline assets → load/serve via bridge
→ relocate/verify → tamper or remove old bytes → serve again. Expected: media
identity unchanged, only verified local bytes served, tampering fails closed,
and registry never silently resolves a stale path.

## Adversarial and recovery task catalogue

Run these against each applicable journey and capture before/after counts of
rows, event heads, project sequence, and receipts (read-only SQL inspection is
acceptable in an isolated test root; mutations must go through CLI/SDK).

- Identity: same explicit idempotency key with identical payload; same key with
  each semantically changed field; omitted key; whitespace/empty key; retry
  after process interruption; replay after server restart.
- Scope: every object addressed by slug, UUID/id, and foreign-project ID;
  missing project vs missing child; uppercase aliases; URL-encoded route
  segments; invalid slug grammar.
- Empty/large data: zero-byte media, empty directory, nested directory,
  symlinks, unreadable file, many assets/clips, very large asset requiring
  initial chunked 206, huge metadata and unknown editor keys.
- Atomicity: malformed input, stale CAS, bad relation batch with one invalid
  member, duplicate order IDs, missing order IDs, foreign order IDs, crash or
  forced exception at each statement boundary in repository conformance tests.
- Lifecycle fences: archive then every mutation; remove then every read;
  relocate then verify; tamper between preflight and commit; archived reference
  as either link endpoint; archived timeline as default.
- Graph rules: media self-edge, duplicate edge, two `variant_of` parents, a
  `variant_of` cycle, all five relation kinds; reference self-link, all five
  link kinds, reversed symmetric and directional requests.
- Presentation: top-overlay track listed last by a naive user; missing asset
  key; missing track; malformed clip timing; audio-only/video-only/still asset;
  HTTP-only and unsafe paths; `HEAD` response unexpectedly carrying bytes;
  stale browser ETag after relocate/verify.

## Existing automated coverage and remaining live gaps

The following automated suites are useful only after a live finding has been
reproduced. They should not be the first campaign wave or be used as evidence
that an uncoached agent experience is smooth.

Strong existing coverage to reuse/promote:

- `tests/sdk/test_timelines.py`: envelope/receipt, deterministic replay and
  mismatch, CAS save, archive terminal behavior, history/diff, project scope.
- `tests/sdk/test_shots.py`: create/add/remove/reorder, position normalization,
  exact permutation rejection, media preservation, replay/mismatch and scope.
- `tests/sdk/test_media.py`: file/directory import ordering, identity, verify
  tamper/replay, relocate, relation vocabulary/self-edge.
- `tests/sdk/test_references.py`: lifecycle, association/primary, symmetric
  links, terminal archive, replay/mismatch and scope.
- `tests/v10/test_media_pipeline.py`: hashing, MIME/kind, directory walk and
  symlink/path safety, staging/publish/verify/GC.
- `tests/v10/test_reference_lifecycle.py`, `test_reference_media.py`,
  `test_reference_links.py`: frozen vocabularies, atomicity, context rules,
  graph rules and archive preservation.
- `tests/v10/test_shot_conformance.py` and `test_reference_conformance.py`:
  replay, mismatch-before-mutation, same-project, writer ownership, hash-chain
  and statement-boundary crash checks.
- `tests/v10/test_domain_cli_projects_timelines.py` and
  `test_domain_cli_media_references.py`: command registration, nested mounts,
  parser and envelope discipline.
- `tests/integrations/reigh/test_local_bridge_server.py` and
  `test_local_bridge_helpers.py`: route/status/error/CORS/Range/HEAD/ETag and
  repository bridge behavior.
- `tests/core/timeline/test_timeline_visualize_*`,
  `tests/packs/rendering/test_timeline_visualize_*`, and rendering fixtures:
  timeline normalization, clips/tracks, scopes, assets, visual layout and
  adversarial evidence packs.

Composed or human-facing gaps likely to expose friction:

- No end-to-end CLI run currently proves create → import → registry → bridge
  asset serving → viewer/render → edit → stale recovery in one isolated root.
- CLI docs/examples are not consistently executable. Observed probe: the
  documented-looking `python3 -m astrid timelines show qa-map primary --json`
  fails because the parser requires `--project qa-map`; the actual form is
  `timelines show --project qa-map primary`. Audit all journey docs for this
  positional/flag ordering problem.
- `timelines shots show` now exposes the SDK's ordered shot read model through
  the nested CLI, including item/media ids, positions, and best-effort media
  names/paths; the live regression is recorded in
  `findings/shots-inspection-ux-fix.md`.
- Product CLI exposes no media/reference/timeline HTTP/UI viewer flow; browser
  tests must cover the bridge directly and record that absence rather than
  assuming feature parity.
- No broad ergonomics rubric measures command discoverability, error-message
  actionability, number of reads needed to obtain IDs, or whether output makes
  order/default/primary/archive state obvious.
- No tested policy is visible for archived default timeline, media import
  partial failure UX, or a failed save merge strategy.
- Layering is documented but needs a user-shaped visual assertion with at least
  three overlapping tracks and a real render/viewer artifact.
- Directory import and SDK multi-edge relation batching are not represented in
  one CLI/HTTP journey; test partial-commit semantics explicitly.
- Serve lifecycle and DB ownership under simultaneous CLI/HTTP clients need a
  long-lived-process test, not only isolated handler fixtures.

## Regression promotion wave (after live UX evidence)

Do not start here. Once a live brief produces a reproducible F2/F3 friction or
correctness defect:

1. Replay the exact brief with a second fresh agent and preserve the raw
   transcript/artifact evidence.
2. Decide whether the smallest fix is wording/help, output/state visibility,
   a safer guardrail, a recovery route, or a source defect.
3. Implement only after the live evidence is written to a wave artifact;
   rerun the original uncoached brief and its deliberate twist.
4. Add one focused automated guard at the lowest stable boundary (CLI, SDK,
   repository, bridge, or rendering) and run that guard as a regression check.
5. Keep the live brief as recurring coverage: a green unit test does not prove
   a fresh agent can discover or trust the workflow.

Promotion priority follows user impact × cross-domain reach × likelihood of
hidden regressions. Typical guards include CLI parser/help alignment, typed
zero-write errors, CAS behavior, project scoping, shot ordering/media
preservation, primary/link rules, bridge status/CORS/Range/HEAD/ETag, and
rendered layering/asset resolution.

### Per-task evidence record

Each execution should retain:

```text
scenario_id, isolated_root, git revision, command/HTTP request,
expected outcome, observed exit/status, stdout/stderr or JSON body,
before/after IDs and versions, event/receipt counts, artifact paths,
human friction note, reproducibility, severity, proposed smallest fix.
```

Do not publish paths, prompts, media, URLs, or credentials to Hivemind from
this campaign. Keep raw runs in the isolated root or ignored campaign
artifacts; only sanitized, generalizable conclusions belong in shared
knowledge after explicit approval.
