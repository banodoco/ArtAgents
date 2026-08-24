# Phase-B conflict-resolution strategy

Read-only review of the clean `HEAD`/`origin/phase-b` merge prediction and the
current live-UX worktree. References at review time:

- merge base: `dd1bbe3a872eb4adfaa644c7a377e9ab32bad160`
- current `HEAD`: `d8335c9a59499bff48841bdb068780f19c8c3036`
- phase-B tip: `c8b68b994eae6ca50c33fd395d2207a377515c7e`
- clean merge prediction: 12 conflicted files (six Oracle/bookkeeping files and
  six product/test files)

This is a semantic guide for the integrator. It is not a recommendation to
resolve a conflict with whole-file `--ours` or `--theirs`.

## Executive resolution rule

Merge Phase B as a history unit, resolve the six committed product/test
conflicts, then replay the live snapshot. The live snapshot is newer in the
operator-facing contracts (canonical DB precedence, archive recovery, typed
errors, close/ownership ergonomics), while Phase B is newer in setup/model
acquisition, trust-token/task/gallery routes, lease expiry, generation
settlement, and registry-merge completion. The final tree must carry both
sets of behavior.

One important integration correction is required during resolution: Phase B's
serve error path returns after a boot-manifest failure without closing the
already-composed writer/owner. The combined composition must close on every
post-composition failure, including boot-manifest mismatch, and must release
the owner only after stopping the sweeper and closing the writer.

## Six committed product/test conflicts

### `astrid/core/gateway/dispatch.py`

Keep the live changes to the SIGTERM/SIGINT shutdown thread and
`StandardBridgeComposition.close()`. Add Phase B's boot-manifest
verify/stamp before HTTP server creation and retain the lease-expiry sweeper
shutdown. Put the boot-manifest operation inside the same `try/finally` that
owns the composition; a failed stamp must not leak the writer or exclusive
owner lock. The final close order is: request server shutdown without
deadlocking the serving thread, stop sweeper, close writer, release owner.

Focused tests:

- `astrid --help`/unknown-command help remains DB-free;
- a valid boot manifest starts the bridge and advertises the final route set;
- a mutated registry/conformance fixture fails closed before bind and a second
  composition can acquire the store immediately afterward;
- SIGTERM (and KeyboardInterrupt) exits without deadlock and releases the
  owner lock; a subsequent `compose_standard_bridge()` succeeds;
- ownership failure keeps the typed `store_owned`/retryable guidance and points
  callers to `/routes`/HTTP while serve owns the store.

### `astrid/core/repositories/tasks.py`

This is a genuine contract union, not a textual choice. Retain the live
completion relaxation: evidence outputs can have no media identity, an
optional non-empty `result` summary can complete a task with zero outputs,
and the read model/receipt/event must round-trip that summary. Add Phase B's
`PublishedMedia` digest fence, optional `generation_request` settlement, and
optional `registry_merge` settlement. Keep every operation in the caller's
single UoW and make generation/registry failures roll the task, media,
outputs, events, and receipt back together.

The final `TaskCompleteReadModel` needs all optional fields (`result`,
`generation`, and `timeline_head`) in `to_dict`/`from_mapping`; the completed
event should expose the summary and the receipt should replay the complete
shape. Do not let Phase B's added fields accidentally drop evidence outputs or
the live `result` field when resolving the conflict.

Focused tests:

- media + evidence outputs together: ordinals, one primary, nullable evidence
  identity, completed event and receipt are identical after replay;
- zero-output completion with a non-empty summary succeeds and idempotently
  replays; zero-output/no-summary still rejects;
- a `PublishedMedia` with a mismatched digest rejects before any mutation;
- generation creation receives the primary media id and is atomic with task
  completion; generation repository failure leaves no terminal task or media;
- registry merge is additive, preserves editor-owned keys, returns the new
  timeline head, and is atomic with completion; its internal event has no
  independent receipt;
- stale/losing attempt, retry, dependency-unblock, event-chain, receipt, and
  run-projection tests remain green under every optional combination.

### `astrid/packs/__init__.py`

Retain the live owner-lock acquisition and actionable `ServiceUnavailableError`
details, then add Phase B's setup-journal replay before database open and its
`LeaseExpirySweeper` over the same writer. Keep one canonical writer and one
lock. Extend `StandardBridgeComposition` with a single idempotent `close()`
that stops the sweeper before closing the writer and only then releases the
lock. Construction failures after lock acquisition must stop any started
sweeper, close a partially opened writer, and release the lock.

The setup journal is a boot/recovery log, not a product authority: replay it
before composing the database, and do not let it create a second store.

Focused tests:

- a dangling setup journal is reconciled before writer open and does not create
  a product DB on its own;
- two compositions for one root fail closed with typed, actionable ownership
  guidance;
- a short-interval sweeper expires an overdue attempt through the shared writer
  and never writes through a second connection;
- close is idempotent, stops/join the sweeper, closes the writer, releases the
  lock, and permits a fresh composition;
- injected startup/composition failure releases the owner and leaves no daemon
  thread or locked store.

### `tests/integrations/reigh/test_local_bridge_server.py`

Retain the live fixture's `composition.close()` use, and carry over Phase B's
request-token helpers and persistence/WAL poison regression. The test server
fixture must send the per-boot token on every mutation, clear it at teardown,
and close the complete composition rather than only its writer. Keep the
Phase-B assertions that two HTTP saves create two durable events/receipts and
that a poisoned writer returns a truthful 500 with zero durable changes.

Focused tests:

- fixture teardown permits immediate re-acquisition of the root lock;
- mutation without `X-Astrid-Request-Token` or with the wrong token is 403,
  while GET/HEAD and OPTIONS retain their intended behavior;
- exact loopback `Host` is enforced, and CORS advertises the token and
  idempotency headers;
- `/routes`, canonical timeline save, asset GET/HEAD/range, and Phase-B task,
  generation, media-content, and gallery routes all coexist;
- two saves are durable and a foreign WAL replacement cannot produce a false
  success.

### `tests/packs/test_generate_image_openai.py`

The two branch variants encode the same intended credential contract (process
environment wins; a dotenv file is consulted only when explicitly supplied),
so deduplicate them into one clear test set. Retain an explicit named-env-file
case and a missing-key case; do not reintroduce cwd `.env` scavenging. Align
the assertions with the final `credentials_scope` implementation and avoid
duplicated test names/comments from the two branches.

Focused tests:

- process environment wins over an explicitly named env file;
- named env file supplies a key only when the process environment is absent;
- an implicit cwd `.env` is ignored;
- missing/empty credentials return the typed failure without leaking values.

### `tests/v10/test_m8_installed_journey.py`

Merge the installed-journey harness changes additively. Mutation HTTP calls
must carry Phase B's request token. The repository-only authority assertion
must allow the live `project.json` binding projection and Phase B's sanctioned
`.astrid/boot-manifest.json`, while rejecting other JSON/JSONL authority
artifacts. Keep the Phase-B backup scratch cleanup so later lanes do not see a
false leftover, and keep the live assertion that the kernel remains the
authority.

Focused tests:

- the complete ten-item journey obtains and sends the boot token;
- concurrent saves still satisfy the CAS/receipt contract;
- only `project.json` and `.astrid/boot-manifest.json` are allowed derived
  receipts; arbitrary sidecars/JSONL fail the authority assertion;
- deleting backup scratch does not hide a failed backup, and the journey still
  checks its evidence before cleanup.

## Six high-conflict live overlaps

These are the six paths where replaying the current dirty UX snapshot requires
semantic reconciliation beyond the committed branch merge.

### `astrid/core/doctor.py`

Keep the live read-only doctor contract: `uninitialized`/`ready`/`unhealthy`,
canonical-vs-legacy DB authority selection, managed/external locator integrity,
and truthful `next_action`. Add Phase B's explicit `doctor setup [--source]`
deep verification/repair and journal reconciliation as a separate mutation
mode. Plain `doctor` must remain read-only and must never acquire a writer or
perform model repair; only `doctor setup` may do so and must report repair
failure honestly. Ensure setup-mode parsing does not alter the stable plain
doctor JSON envelope.

Focused tests:

- pristine root: exit 0, `state=uninitialized`, actionable next action, no DB;
- canonical DB wins over a legacy `kernel.sqlite3`, with the expected warning;
- mutated managed/external bytes fail read-only doctor with bounded details;
- `doctor setup --json` verifies/repairs artifacts and reconciles a journal;
- setup without `--source` never performs outbound acquisition; corrupt repair
  returns nonzero and a typed report;
- snapshots before/after plain doctor are byte-identical.

### `astrid/core/integrations/reigh/local_bridge_server.py`

Carry Phase B's local-trust posture, task admission/claim/poll, gallery and
managed-media content routes, private-directory/token boot handling, and
typed task errors. Add the live `/routes` discovery document, persisted save
schema, asset registry aliases, GET/HEAD/range semantics, and canonical writer
injection. Route discovery must describe the entire final surface and the
token/idempotency requirements. All mutations must pass the trust gate before
the canonical SDK/repository writer; no transport path may open a second
writer or bypass the project-scoped DB authority.

Preserve these invariants while resolving route-level overlaps:

- `/projects/{project}/timelines/{timeline}/assets/{registry_key}` resolves the
  registry key to its locator/media identity; it is not interchangeable with
  Phase B's `/projects/{project}/media/{id}/content` route;
- GET/HEAD must never require the mutation token, while POST/PUT/task routes
  must require it and an idempotency key where declared;
- save schema/CAS errors are typed and occur before run/task admission;
- private token files and media paths are constrained to the managed root.

Focused tests:

- route census is complete and JSON-stable;
- token/host/CORS matrix for GET, HEAD, OPTIONS, save, task, and registry
  mutation;
- registry-key alias resolution, traversal/absolute-path rejection, verified
  media bytes, range, ETag, and HEAD bodylessness;
- task/generation/gallery routes exercise typed 4xx/409/500 mapping;
- canonical save creates exactly one timeline event/receipt and stale CAS
  changes zero rows.

### `astrid/core/repositories/tasks.py`

Apply the union described above. The main risk is silently losing one optional
contract while resolving the overlapping completion method. Validate the full
cross-product of media/evidence/result plus Phase-B generation/registry
settlement, and assert rollback at every post-materialization failure point.

### `astrid/packs/__init__.py`

Apply the union described above. The main risk is using `writer.close()` alone,
which leaves the live owner lock, or using `composition.close()` without first
stopping Phase B's sweeper. Test deterministic shutdown and failed-start cleanup
explicitly.

### `astrid/packs/timeline/repository.py`

Keep the live timeline identity/validation, archive/unarchive, inclusive list,
history/diff, canonical DB read models, and typed error ergonomics. Add Phase
B's internal `merge_registry` operation and `timeline.registry_merged` event.
The merge is completion-internal: additive only, never clobbering editor keys,
does not alter `document_json`, uses an exact head CAS, returns the resulting
head, and records no standalone receipt.

Important semantic correction: Phase B's merge implementation fences by the
presence of any historical `timeline.archived` event. The live repository has
an unarchive transition, so the integrated merge must use the latest archive /
unarchive event (`_archive_state`) just like save. A timeline that was archived
then unarchived must be mergeable again. Include registry-merge in lifecycle
history/diff only if the product contract wants internal placement visible;
otherwise keep it in the canonical event stream while documenting that
user-facing content history intentionally excludes placement-only events. In
either case, the stream head and render/visualize pins must observe the merge.

Focused tests:

- active timeline merge adds new assets, preserves existing editor keys, leaves
  document bytes unchanged, advances one stream/project head, and emits one
  hash-chained `timeline.registry_merged` event with no receipt;
- all-existing entries are a no-op at the same head;
- stale head/concurrent save is fenced and does not partially merge;
- archived timeline rejects merge, then archived→unarchived timeline accepts
  it;
- a completion failure rolls back media, generation, registry projection,
  event, and task together;
- `history`, `diff`, `show`, render, and visualize use the resulting canonical
  head/hash according to the decided visibility rule.

## Oracle/bookkeeping conflicts

`.oracle/agent_goal.md`, `.oracle/custody.md`, `.oracle/northstar.md`,
`.oracle/plan-v1.txt`, `.oracle/tasklist.md`, and
`.oracle/findings/_report.json` are independent run records, not product
source. Neither branch's complete file can be selected as the integrated
truth: doing so would erase the other run's scope and provenance (and the
Phase-B report contains stale `/workspace` paths).

Recommended resolution:

1. Preserve both input records under clearly namespaced archival paths or in a
   merge evidence document, retaining their source refs and original dates.
2. Generate a fresh root Oracle/integration record whose objective combines
   Phase-B capability/setup/trust work with the live single-authority/timeline
   UX contract, and whose custody section lists the protected dirty worktree.
3. Regenerate `_report.json` for the integration run rather than mechanically
   merging counters, PIDs, output directories, or task arrays. No stale
   `/workspace` path should remain in the active root report.
4. Make the new tasklist explicit about the merge order and gates; link this
   strategy report and the graph/overlap audits. Do not let bookkeeping edits
   hide a product conflict or claim that either original run's done criteria
   alone proves the combined tree.

Bookkeeping checks are: valid JSON for `_report.json`, source refs for both
input runs, no stale active output paths, `git diff --check`, and a final
product test run independent of Oracle metadata.

## Minimum combined gate after resolution

Run the focused tests above before the broad suite. Then run the Phase-B gate
(`tests/v10`, `tests/integrations/reigh`, `tests/packs`), the live changed-area
suite, `python3 -m compileall -q astrid`, `git diff --check`, and a real serve
smoke with health, `/routes`, one tokened mutation, clean shutdown, and
post-shutdown owner re-acquisition. Regenerate the stacked-render proof only
after the integrated renderer/configuration is final.
