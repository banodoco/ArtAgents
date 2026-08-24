# Live UX wave: serve ownership contention and safe handoff

Date: 2026-08-23  
Surface: public `python3 -m astrid` CLI and public serve HTTP routes  
Mode: live agent usage (no programmatic tests, no source/test inspection)  
Project root: `/tmp/astrid-live-owner-tZCcwR` (fresh `mktemp` root)  
Bridge: `127.0.0.1:18987` (checked free before use)

## Goal and verdict

I simulated two editors sharing one Astrid project:

1. Create project `handoff-demo` and default timeline `primary`.
2. Start `astrid serve` as editor A, giving the bridge exclusive database ownership.
3. As editor B, discover the CLI, read the project/timeline over the HTTP bridge,
   attempt a timeline change through the CLI, and observe recovery guidance.
4. Stop editor A cleanly, retry the intended change without duplication, and
   distinguish owner contention from a stale-version conflict.
5. Restart the bridge and verify the final state survives the handoff.

**Verdict: PASS for data safety and handoff; P1 UX failure for CLI owner contention.**

The bridge made its ownership model explicit and HTTP reads worked while it was
running. A direct CLI read or write was rejected without mutation, so there was
no lost work or duplicate timeline version. After a clean shutdown, the same
logical save succeeded and replaying it with the same idempotency key returned
the original receipt without creating another version. A subsequent fresh-key,
stale expected-version save produced a typed `stale_version` envelope, clearly
separating version conflict from ownership contention.

## Setup and initial state

Commands used:

```text
qa_root=$(mktemp -d /tmp/astrid-live-owner-XXXXXX)
ASTRID_PROJECTS_ROOT=$qa_root python3 -m astrid projects create handoff-demo --name 'Handoff Demo' --json
ASTRID_PROJECTS_ROOT=$qa_root python3 -m astrid timelines create primary --project handoff-demo --name 'Primary' --default --json
```

Project creation returned `ok: true`, project sequence 1. Timeline creation
returned `ok: true`, timeline sequence 2, and the initial document was:

```json
{
  "config": {},
  "config_version": 1,
  "is_default": true,
  "name": "Primary",
  "registry": {"assets": {}},
  "slug": "primary"
}
```

I read the generated project `plan.md` after showing the project. It was the
expected empty working-notes skeleton; no ownership handoff instructions were
present there.

## Editor A: serve ownership

I checked `serve --help`, then started:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-owner-tZCcwR \
  python3 -m astrid serve --host 127.0.0.1 --port 18987 \
  --projects-root /tmp/astrid-live-owner-tZCcwR --no-open-editor
```

The live process announced:

```text
Astrid ready — bridge at http://127.0.0.1:18987, editor: not opened
Projects root: /private/tmp/astrid-live-owner-tZCcwR
Database ownership: exclusive to this bridge until shutdown; use the HTTP routes while it is running.
HTTP discovery: GET /routes (machine-readable route and schema document)
HTTP routes: GET /health, GET /projects, GET /projects/{project}/timelines,
GET /projects/{project}/timelines/{timeline}, POST .../save, GET|HEAD .../assets/{registry_key}
Save JSON: {"config": object, "registry": object, "expected_version": integer}
```

This is good operator-facing startup guidance: it names the owner, lifetime,
and the supported bridge surface rather than leaving the second editor to guess.

## Editor B reads and help while A owns the store

The CLI help command did **not** contend because it does not open the store:

```text
python3 -m astrid timelines --help
=> exit 0; help printed normally
```

HTTP discovery and reads also worked, as intended for an editor B using the
bridge:

```text
GET /routes                         => HTTP 200; route/schema document
GET /health                         => HTTP 200; {"ok": true, ...}
GET /projects                       => HTTP 200; handoff-demo
GET /projects/handoff-demo/timelines
  => HTTP 200; primary, default=true
GET /projects/handoff-demo/timelines/primary
  => HTTP 200; config={}, registry={"assets":{}}, config_version=1
```

The bridge's explicit `exclusive_ownership.implication` says to use HTTP for
reads and writes while it runs. That is discoverable from `GET /routes` and the
startup banner.

## Editor B CLI contention reproduction

### Read contention

The same project-list and timeline-show requests through the CLI both exited 1
and emitted **unstructured human text despite `--json`**:

```text
unstructured - this is a bug.
the database is already owned by another process
recovery: retry the command; if it repeats, report this bug
state snapshot: {"argv": ["projects", "list", "--json"],
"entrypoint": "astrid.core.gateway.main", "original_type": "ServiceUnavailableError"}
```

The timeline-show snapshot substituted its own argv. There was no five-key
`ok/data/error/receipt/idempotency_key` JSON envelope for either read.

### Write contention

Editor B attempted one real timeline mutation while A remained live:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-owner-tZCcwR \
  python3 -m astrid timelines save primary --project handoff-demo \
  --config '{"tracks":[{"id":"b-track","clips":[]}],"clips":[]}' \
  --registry '{"assets":{}}' --expected-version 1 --json
```

Observed result (exact output shape):

```text
unstructured - this is a bug.
the database is already owned by another process
recovery: retry the command; if it repeats, report this bug
state snapshot: {"argv": ["timelines", "save", "primary", "--project", "handoff-demo", "--config", "{...}", "--registry", "{\"assets\":{}}", "--expected-version", "1", "--json"], "entrypoint": "astrid.core.gateway.main", "original_type": "ServiceUnavailableError"}
```

Exit code was 1. No receipt, event, version, or partial config was created.
The timeline remained version 1. The attempted payload was intentionally not
retried while A held ownership, avoiding repeated contention noise and avoiding
any ambiguity about whether a write might have landed.

## Safe handoff and idempotent retry

I sent Ctrl-C to the serve session. The process printed `Shutting down...`, the
port became free, and `/health` then failed to connect. This was a clean owner
release; I did not kill any unrelated process.

After shutdown, editor B retried the same intended logical mutation with a
stable explicit idempotency key and the known version-1 snapshot:

```text
... timelines save primary ... --expected-version 1 \
    --idempotency-key owner-recovery-001 --json
```

Result: exit 0, `ok: true`, `config_version: 2`, one `timeline.saved` event,
and `idempotency_key: owner-recovery-001`. The committed config was exactly:

```json
{"clips": [], "tracks": [{"clips": [], "id": "b-track"}]}
```

I immediately replayed the exact command with the same key. Astrid returned the
original timestamp, receipt id, event id, request hash, project sequence `[4,4]`,
and version 2; exit code was 0. There was no version 3 and no duplicate track.

Safe retry rule observed:

- Reuse the same idempotency key for a retry of the same logical request,
  including an ambiguous transport/process handoff.
- After rereading and intentionally changing the request, use a fresh key.
- Do not blindly replay a stale whole-document payload after a version conflict;
  reread, merge, and use the current `config_version`.

## Stale-version distinction

With the bridge stopped and the store available, I submitted a different
payload using a fresh key but the old expected version 1:

```text
... timelines save primary ... --config '{"tracks":[{"id":"stale-track","clips":[]}],"clips":[]}' \
    --expected-version 1 --idempotency-key stale-version-001 --json
```

This was a typed JSON error, not an ownership failure:

```json
{
  "data": null,
  "error": {
    "code": "stale_version",
    "details": {"current_version": 2, "expected_version": 1},
    "message": "timeline save rejected: expected version 1, current version 2; no write occurred. Recovery: show the current timeline, merge your changes into it, then save with its config_version as --expected-version. Reuse the same idempotency key only for the same request; use a fresh key for the merged save."
  },
  "idempotency_key": "stale-version-001",
  "ok": false,
  "receipt": null
}
```

Exit code was 1. This guidance is materially better than the owner-contention
message: it supplies both versions, states no write occurred, names the public
read/merge/save recovery, and explains idempotency. The stale attempt created no
history entry and did not overwrite `b-track`.

## Restart and final evidence

I restarted `astrid serve` on the same now-free port and queried the public HTTP
bridge. Both `/health` and `/projects/handoff-demo/timelines/primary` returned
HTTP 200; the timeline was still version 2 with `b-track`. I then stopped this
second bridge cleanly with Ctrl-C as well.

Final CLI state:

```json
{
  "config": {"clips": [], "tracks": [{"clips": [], "id": "b-track"}]},
  "config_version": 2,
  "registry": {"assets": {}},
  "slug": "primary"
}
```

Final history contained exactly two versions:

```json
[
  {"kind":"timeline.created", "version":1, "config":{}, "registry":{"assets":{}}},
  {"kind":"timeline.saved", "version":2, "config":{"clips":[],"tracks":[{"clips":[],"id":"b-track"}]}, "registry":{"assets":{}}}
]
```

`timelines diff` reported one adjacent transition, version 1 → 2, with
document keys `clips` and `tracks` added. The idempotent replay did not appear
as a third history entry. The stale request did not appear at all, which is
correct for a rejected write but means rejected proposals are not auditable.

## Severity-ranked UX critique

### P0 — none observed

No data loss, silent overwrite, partial write, duplicate version, or duplicate
track occurred. Exclusive ownership, whole-document CAS, and idempotency worked.

### P1 — CLI ownership failure violates the advertised JSON contract

All three CLI operations attempted during bridge ownership (project list,
timeline show, timeline save) ignored `--json` and emitted the literal
`unstructured - this is a bug.` line plus a JSON-looking state snapshot. The
operator cannot reliably parse the failure using the documented five-key
envelope, and the message labels a predictable coordination state as a bug.

Recommended durable fix: map `ServiceUnavailableError` to the normal typed
envelope, for example:

```json
{
  "data": null,
  "error": {
    "code": "store_owned",
    "details": {"owner":"astrid serve", "recovery":"use HTTP bridge or wait for shutdown"},
    "message": "database is owned by the running Astrid bridge; use its HTTP routes for reads/writes, or retry after the bridge shuts down"
  },
  "receipt": null,
  "idempotency_key": "",
  "ok": false
}
```

The exit code can remain 1. Crucially, `--json` should produce JSON only, and
human mode should avoid saying “this is a bug” for expected ownership fencing.

### P1 — retry guidance is too generic and risks unsafe operator behavior

The current text says `recovery: retry the command; if it repeats, report this
bug`. It does not tell the agent to use the HTTP bridge, wait for clean
shutdown, apply backoff, or reuse the same idempotency key. It also does not
distinguish a read (safe to retry) from a write (must preserve the exact key and
payload, then verify state before inventing a new request).

Recommended guidance:

> Store owned by `astrid serve`. Reads/writes through this CLI are blocked. Use
> `GET /routes` and the bridge HTTP routes while it runs, or wait for a clean
> shutdown. For a write, retry the same request with the same idempotency key
> after ownership is released, then verify the returned version. Do not create a
> new key unless you intentionally changed the payload.

If automated retry is desired, specify bounded exponential backoff and a
retryable error code rather than asking the agent to guess.

### P2 — ownership is process-global but editor identity is not surfaced

The banner and `/routes` correctly say `astrid serve`, but there is no editor
label, owner process id, started-at timestamp, or bridge endpoint in the CLI
failure. A second agent cannot tell whether it is contending with the intended
editor A, a stale abandoned server, or an unrelated local bridge.

Recommended addition: include a stable owner session id, PID, endpoint, and
start time in `/health` and the typed `store_owned` error. Keep the existing
public route discovery so the agent can hand off to the owner without opening
the SQLite store directly.

### P2 — rejected owner-contended writes leave no recoverable proposal record

The absence of a history entry is correct for “no write occurred,” but the
public output does not preserve the attempted payload or idempotency key in an
audit/recovery object. If the agent loses its own context after the handoff, it
must reconstruct the intended document manually.

Recommended addition: return a machine-readable rejected-request receipt (not a
timeline version) containing request hash, expected version, and idempotency
key; never apply it automatically. This would make safe post-shutdown replay
and incident explanation easier without polluting committed history.

### P3 — happy-path discovery is strong but split across surfaces

`timelines --help`, `serve --help`, the startup banner, and `GET /routes` are
each useful. However, the CLI help does not warn that product commands contend
with an active bridge, while the bridge correctly tells the user to use HTTP.
Add one sentence to the product-family help and the top-level census so an agent
learns the handoff rule before its first blocked command.

## Agent ergonomics summary

The safe live path is:

```text
create → start serve A → use HTTP for B reads
→ if CLI contends, preserve payload/key and do not invent a new write
→ cleanly stop A → retry same logical request with same idempotency key
→ use current-version/fresh-key semantics for intentional new writes
→ show + history + diff → optionally restart serve and verify via HTTP
```

The underlying ownership/CAS/idempotency design is trustworthy. The highest
value fix is the P1 CLI error-envelope and recovery guidance: this is expected
coordination behavior, not an unstructured bug, and agents need a precise
bridge-vs-shutdown decision plus safe write-retry semantics.
