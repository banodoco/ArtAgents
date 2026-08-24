# CLI + kernel live-agent UX map

Status: wave-0 live-usage map (2026-08-23). Scope is the gateway, the standard
SQLite application, receipts/events, task/run execution lifecycle, persistence
and operational recovery. The primary unit below is a realistic task handed to
an agent and the observable friction while the agent discovers, performs and
recovers from it; automated tests are regression guards only.

## Agent-facing contract to observe

- The supported gateway is `python3 -m astrid`; the census is five product
  families (`projects`, `timelines`, `media`, `tasks`, `runs`) plus operational
  `serve`, `doctor`, `backup`. `timelines shots` and `media references` are
  nested mounts, never top-level families.
- Product handlers are intended to be thin adapters: parse argv, make exactly
  one typed SDK call, render through `domain_output`. The product `--json`
  contract is exactly `{ok,data,error,receipt,idempotency_key}`; exit codes are
  0 success, 1 typed SDK failure, 2 usage/parse failure.
- The canonical standard database is
  `$ASTRID_PROJECTS_ROOT/.astrid/astrid.sqlite3`. Its first writable open
  applies migrations and PRAGMAs (`foreign_keys=ON`, WAL, NORMAL sync,
  `busy_timeout=5000`). The standard application owns one writer queue and one
  process-lifetime `.lock` file; a second owner must fail closed as
  `unavailable`.
- Every mutation is one `BEGIN IMMEDIATE` unit of work: receipt/idempotency
  gate, semantic validation/fence, projection + event append, receipt write,
  commit. Event streams have per-project and per-stream sequences and a
  hash-chain; a failed command must leave zero rows/heads/receipts changed.
- Task state is `queued|blocked -> running -> succeeded|failed|cancelled`,
  with attempts, status versions, leases and heartbeats fencing executor
  transitions. Failed/expired work can requeue only within attempt budget.
- Runs are created by kernel admission/fan-out, not by a `runs create` CLI
  verb. A run owns ordered child tasks (maximum 256), derives progress from
  child rows, and transitions through group cancel/retry or explicit `close`.
- `run.json` under a project is a write-once/finalize-time projection stamped
  `authority=kernel`; it is not an authority. `doctor` is read-only. Backup and
  restore are staged, validated and journaled.

## Surface census

| Surface | Ordinary journey | Tricky/recovery journey | Evidence to capture |
|---|---|---|---|
| `projects` | create → list/show → update → select | slug/id collision; same-key replay vs changed-request mismatch; invalid slug/name/settings; workspace vs user preference | five-key envelope, receipt, `projects.event_head_seq`, `project.json`/`plan.md`, preference sidecar |
| `timelines` | create (optionally default) → show/list → save → history/diff | stale `--expected-version`; duplicate slug; archive then save/list/show; default replacement; same-key replay/mismatch | config version, active/archive visibility, adjacent history/diff, event/receipt sequence |
| `media` | import file/directory → list/show → verify | duplicate content hash; missing/mutated bytes; wrong realm; relocate identity preservation; cross-project relation; self/duplicate/invalid relation | media rows, location realm/locator/verified time, content hash/size, relation rows, managed-media bytes |
| `media references` | create with canonical media → associate/link → set-primary → update/list/show | frozen kind/role/link vocabulary; archive and inclusive read; primary replacement; used-as-input context-task requirement; cross-project/self link | reference lifecycle, association primary flags/ordinals, link symmetry, archive timestamp, receipts/events |
| `tasks` | create immutable standalone task → list/show/events → cancel queued | malformed JSON/admission; hard/soft dependency gating, self/cross-project/cycle/duplicate edge; retry never-claimed/terminal/exhausted; same-key replay/mismatch | task read model/spec hash/status, dependency rows, attempt rows, ordered `core.task` events, receipt |
| `runs` | capability admission creates run + child; list/show/progress/events; cancel/retry group; close terminal run | zero-child run close; partial child failure; running child cooperative cancel and late-completion fence; explicit subset vs all-failed retry; >256 children; terminal run; stale continuation head/ordinal/dependency | run row + derived progress, ordered child ordinals/statuses, run event stream, evidence IDs, receipt event range |
| nested `timelines shots` | create shot → add media at position → reorder → remove | foreign media; missing/duplicate/omitted permutation; negative/out-of-range position; remove preserves media bytes; replay/mismatch | shot/item rows and order, media still present, receipt/event stream |
| capability SDK/invocation | discover/get capability → invoke with project → kernel admit/claim/start/execute/complete/fail → inspect tasks/runs/events and final projection | missing project; invalid capability/kind; dry-run must not admit; executor failure/lease expiry; replay; output/manifest and run projection reconciliation | `InvocationResult`, kernel run/task/attempt IDs, canonical DB rows, run directory/run.json, event hash verification |
| `doctor` | run on fresh/healthy root | missing DB; too-new/checksum-drift migration; quick-check corruption; FK violation; malformed managed-media tree; orphan staging warning; run while writer owns DB | checks list/status/detail, exit/JSON behavior, no file/row modification |
| `backup` | create destination → restore fresh root → doctor/list | corrupt backup; FK-invalid backup; existing live data without `--force`; interrupted publication/restore journal; repeated create/restore; secret/excluded media files | `backup.json`, staged/journal paths, old-or-complete invariant, restored rows/media, doctor result |
| `serve`/ownership | start bridge, use one client, SIGTERM, restart | explicit missing editor path; second owner/process; startup DB/schema failure; shutdown during queued writer work | readiness line, owner lock, process exit, HTTP status, writer/lock release |

## Live agent task cards

Give an agent only the task prompt and normal repository/CLI access. Observe
whether it discovers the right family, chooses the canonical root, keeps IDs
and keys, checks state before mutating, notices recovery guidance, and verifies
the resulting state. Do not pre-teach the exact command sequence. Capture the
agent transcript, commands, retries, wait time, wrong turns, and the final
database/filesystem/event evidence.

1. **Orient and create a project.** “Start from a clean checkout, determine
   how Astrid stores projects, create a project called `demo`, rename it, and
   show me the final state.” Watch for unnecessary legacy verbs, failure to read
   `--help`, confusion between slug and ID, accidental use of the user’s real
   root, and whether the agent reads `plan.md`/`project.json` as authority.
2. **Build a small timeline.** “Create a default `primary` timeline, save a
   1920×1080 document, then show its history and diff.” Watch whether the agent
   discovers that save needs both whole-document JSON objects and an expected
   version, understands version 1 after create, and can explain the result.
3. **Recover a timeline conflict.** “Two editors changed `primary`; preserve
   both changes and finish with the current version.” Set up one stale save and
   let the agent recover. Watch whether `stale_version` is intelligible, whether
   it reloads before retrying, and whether it accidentally overwrites the other
   editor or reuses an idempotency key for a changed request.
4. **Import and verify media.** “Import the supplied image and a folder of
   assets, verify them, move one to an external locator, and relate the output
   to its source.” Watch path/realm vocabulary discovery, whether a missing or
   mutated source is treated as a read-only integrity failure, and whether the
   agent checks content identity rather than assuming the locator is identity.
5. **Assemble references and shots.** “Create a character reference from the
   imported image, add a second association, make it primary, and put both
   images in a shot in reverse order; remove one.” Watch nested-mount discovery,
   same-project ID handling, permutation semantics, primary terminology, and
   the crucial expectation that removing a shot item does not delete media.
6. **Manage a blocked task.** “Create two tasks where the second waits for the
   first, inspect why it is blocked, cancel the first, and report what happened
   to the second.” Watch whether the agent understands hard vs soft dependency,
   sees that claim/start/heartbeat are executor-owned and not CLI verbs, and
   avoids inventing `next`, `ack`, or plan/step commands.
7. **Recover failed work.** “Run a deterministic local capability that fails
   once, inspect the task/run, retry only eligible work, then verify the final
   result.” Watch whether the agent can find the run created indirectly by
   invocation, distinguish failed/expired from terminal-cancelled work, preserve
   the original evidence, and understand the batch retry subset policy.
8. **Cancel mixed run work.** “Cancel a run containing queued, running and
   terminal children; leave already-finished work intact.” Watch for the missing
   cooperative cancellation and late-completion fence on running work, whether
   group cancel reports already-terminal skips clearly, and whether derived
   progress is trusted
   over stale cached counts.
9. **Diagnose a damaged project.** “Before changing anything, determine whether
   this project is healthy, then recover it from the supplied backup if needed.”
   Watch whether the agent starts with read-only doctor, interprets each check,
   avoids hand-editing SQLite/event files, understands `--force`, and verifies
   old-or-complete recovery after restore.
10. **Operate under contention.** “Use two agents against the same project to
    make concurrent timeline edits, then stop one cleanly and continue with the
    other.” Watch owner-lock messaging, whether the losing agent retries safely,
    whether help itself unexpectedly contends, and whether the surviving agent
    can tell stale-version conflict from unavailable-owner failure.

### UX scoring for each task

Record: time to first correct command; number of wrong/retired commands; number
of times the agent rereads help or source; whether it preserves IDs/keys; number
of retries; whether each retry is safe; whether the agent can state the current
state from `show/events/doctor`; and whether the final explanation matches the
evidence. Classify friction as discoverability (cannot find the verb),
interpretability (cannot understand output/error), safety (unsafe retry or
authority confusion), or ergonomics (too many manual transformations/IDs).

## Lifecycle and observable state model

### Gateway and output

1. `astrid --help`/`help`/`--version` are sessionless documentation paths.
2. A product invocation composes `AstridClient` and the standard application,
   then the family parser dispatches one SDK call. Family `--help` is reached
   after composition, so it can open/migrate the database and contend for the
   owner lock.
3. Typed SDK failures render a five-key envelope on stdout in JSON mode and
   return 1. Argparse failures return 2; top-level unknown commands return an
   `AstridError` on stderr and 2. Human mode emits one identity line on stdout
   for success and one concise error line on stderr for typed failure.
4. Mutation replay with the same `(project, command kind, idempotency key,
   request hash)` returns the original result/receipt and creates no new rows.
   Same key with changed semantic input must fail as `idempotency_mismatch`
   before mutation. A generated key is returned to the caller and must be
   retained if a caller may retry.

### Writer, receipts and event chain

`DatabaseOwnerLock -> DatabaseWriter FIFO queue -> UnitOfWork(BEGIN IMMEDIATE)
-> receipt gate -> pre-write fences -> repository mutation -> event append and
projection/head updates -> receipt -> COMMIT -> read committed receipt`.

Probe both commit and rollback surfaces. For each mutation record: command
kind, caller/generated key, request hash, receipt ID, `project_seq` range,
event IDs, primary stream/head, result payload, and row counts before/after.
Read streams in sequence order and verify event hashes/previous hashes; event
tampering must be detected and never repaired by a read.

### Task/executor lifecycle

Public CLI/SDK exposes create/list/show/cancel/retry/events. Claim/start/
heartbeat/fail/complete are executor-owned kernel operations. Test both the
public adapter and the internal executor seam: operator cancellation of a
running task is cooperative, while executor transitions retain strict
attempt/lease/status-version fences and reject partial fences. Exercise lease
expiry, heartbeat counter/version increments, foreign/stale fences, late
completion races, output materialization, dependency unblocking, and terminal
immutability.

### Run lifecycle

Admission atomically creates one `runs` row, run stream, ordered child tasks,
dependency edges, child streams and one complete receipt. `show` derives
progress fresh from child rows (no persisted cursor). Group cancel/retry uses
shared task predicates and must skip running/terminal children that lack an
executor fence. Zero-child or otherwise resolvable runs require `runs.close`
via the SDK; terminal runs reject further group operations. Continuation is an
internal CAS path: continuation event first, contiguous ordinals, max 256,
then child events and one receipt.

### Persistence and recovery

Canonical state is the SQLite database plus managed-media digest tree. Project
binding files and `plan.md` are convenience/projection files, not authority.
`doctor` opens read-only and reports schema/media/quick-check/FK health. Backup
takes an online snapshot and copies only allowed media; restore validates a
staged copy before an atomic swap and uses a durable journal. Recovery must
land in either the complete old state or the complete new state, never a mixed
state.

## Journey details and adversarial probes

### 1. Bootstrap, project identity and preferences

Ordinary: use a fresh `mktemp -d` root, run doctor, create `demo`, list/show by
slug and ID, update name/settings, select workspace/user preference, then
reopen a new client and verify durability. Check that create writes `plan.md`
and a binding but the kernel row remains authoritative.

Adversarial/recovery: empty or malformed slug/name/settings; duplicate slug;
same key exact replay; same key changed slug/name/settings; unknown slug/ID;
no-op update; two processes composing the same root; close/reopen after a
failed wiring attempt; stale preference path or selected project deleted.

### 2. Timeline document/CAS lifecycle

Ordinary: create `primary`, save complete config plus registry at version 1,
read show/list/history/diff, set/replace default, archive, and verify active
list excludes archived while show/history preserve lifecycle data.

Adversarial/recovery: omit config or registry (usage error), malformed/non-object
JSON, stale and ahead expected versions, retry same key, reuse key with changed
document, save/archive after archive, duplicate slug, concurrent saves from one
head (exactly one winner), and reopen after crash boundary. Confirm stale save
changes zero rows/events/receipts and recovery is show → merge → save current
version.

### 3. Media and nested reference/shot identity

Ordinary: import one existing file and a directory, list/show each, verify
managed location, relocate an external locator, relate two media, create a
reference and a shot, associate/promote media, add/reorder/remove shot items.

Adversarial/recovery: import missing path (must be usage failure before SDK),
same content twice, mutate/delete source before verify, verify wrong realm,
relocate invalid realm/locator, relation self-edge/duplicate/variant-parent
conflict/cross-project target, reference invalid frozen vocabularies and
archive visibility, shot permutation omission/duplicate/extra and foreign
media. Confirm failed integrity checks do not rewrite identity/bytes and shot
remove does not delete kernel media.

### 4. Task admission and execution fences

Ordinary: create a task with a stable spec and optional input manifest,
priority, availability and max attempts; show/list/events; cancel queued work.
Use an internal test handler to claim/start, heartbeat, complete with outputs,
then verify derived run progress and materialized media/evidence.

Adversarial/recovery: hard dependency blocked until predecessor succeeds,
soft dependency never blocks, future/cross-project/self/cyclic/duplicate
dependencies; claim FIFO/priority/availability; double claim; stale/foreign
lease/attempt/status version; heartbeat after expiry; fail requeue vs exhausted
terminal failure; retry only failed/expired eligible work; cancel races with
claim/complete/expiry; completion races select one winner. Every losing fence
must have zero mutation and no losing receipt.

### 5. Run fan-out, group controls and continuation

Ordinary: invoke a deterministic local/test executor with a project, inspect
run/task IDs, list/show/events, observe ordered child progress, then cancel or
retry eligible children and close a zero-child run via SDK.

Adversarial/recovery: 0, 1, 256 and 257 children; same-project earlier-child
dependencies vs later/cross-project dependencies; duplicate idempotency key;
partial failure; explicit retry subset vs omitted all-failed selection; group
cancel with queued, running and terminal children; terminal run operations;
continuation stale head, non-contiguous ordinals, bound overflow, terminal run,
empty chunk and replay. Verify run stream ordering (`created`/`continued` then
child/evidence events), derived counts and receipt event range.

### 6. Capability invocation and authority reconciliation

Ordinary: discover/lookup an in-tree capability, dry-run it (no kernel rows),
then invoke with an explicit project and inspect the kernel and final output
projection. Verify `InvocationResult` IDs and event stream agree with task/run
CLI reads.

Adversarial/recovery: missing/ambiguous/element capability, missing project,
project plus `out` conflict, executor nonzero/handler exception, missing
inputs, lease expiry, malformed output manifest, replay and project-root
selection. Compare all database files under the root and ensure exactly one
authority is used.

### 7. Doctor, backup and owner-lock recovery

Ordinary: doctor fresh root, create project/media, backup, restore to a fresh
root, reopen and doctor/list/show. Repeat backup destination publication and
restore to prove idempotence.

Adversarial/recovery: inspect health while a writer owns DB; missing DB;
quick-check-corrupt DB; FK violation; too-new migration/checksum drift;
malformed managed-media/leftover staging; corrupt/FK-invalid backup; restore
without `--force` onto live data; kill at every backup/restore journal boundary;
SIGTERM serve during work; second owner process. Recovery must be explicit,
read-only diagnosis first, then repeat restore or choose a compatible checkout.

## Evidence protocol for every wave

Use only an isolated root (`probe_root=$(mktemp -d); export
ASTRID_PROJECTS_ROOT="$probe_root"`). Save command argv, exit code, stdout,
stderr, parsed JSON, and a file manifest. For product JSON assert one line,
valid JSON, exactly five keys, receipt null on reads/failures, and correct key
propagation. For each mutation snapshot row counts and event/receipt heads
before/after; use read-only SQLite queries or the public read services, never
edit the DB/event stream directly. Verify event hashes and receipts after every
recovery probe. Keep source media fixtures outside the project root and do not
publish prompts, secrets or personal paths.

## Regression guards (secondary to live usage)

The repository has substantial automated guards for project/task/run
repositories, leases/races, fan-out/close, receipts/event chains, writer
authority/UoW, contention/crash atomicity, media/references/shots/timelines,
backup/restore, and parser/output census. The relevant guards include
`tests/v10/test_task_lifecycle.py`, `test_task_races.py`, `test_fanout.py`,
`test_run_close.py`, `test_receipts_events.py`, `test_writer_authority.py`,
`test_contention.py`, `test_crash_atomicity.py`, `test_backup_restore.py`,
`test_domain_cli_*.py`, and the repository-specific tests. They should be run
only after a live friction or defect is reproduced, then promoted with the
agent task prompt and an evidence oracle.

The live wave needs real subprocess + canonical-root journeys around the
following seams, because parser tests often use fake clients and repository
tests bypass the discovery/navigation burden an agent experiences:

1. one end-to-end matrix for every product verb, nested mount and output mode;
2. SDK `invoke` → canonical DB → CLI `runs/tasks` read-back and final
   projection reconciliation;
3. owner-lock contention from separate processes, including family help and
   serve/doctor/backup interaction;
4. real CLI media/reference/shot setup followed by cross-project and
   integrity-failure recovery;
5. crash/restore probes at the subprocess boundary, not only repository seams.

## First live execution wave (priority order)

| Priority | Agent task | Why first | Pass/fail oracle |
|---|---|---|---|
| P0 | **“Create and invoke.”** Create `demo` through the CLI, invoke one deterministic local capability, and report the run through CLI `runs/tasks/events`. | Validates what an agent actually does across the CLI/SDK boundary and catches split-ledger/handler failures immediately. | exactly one canonical DB; IDs/status/events agree; no parallel `kernel.sqlite3`; no hidden `NameError`; agent can explain failure/recovery. |
| P0 | **“Orient under contention.”** Have two agents start from help, one holding the root, while the other performs project/timeline work and recovers after release. | Lock and help ergonomics affect every domain. | agent distinguishes unavailable from stale-version; recovery is actionable; no unsafe duplicate mutation. |
| P1 | **“Build and merge a timeline.”** Two agents save different changes, then one resolves the conflict. | Highest user-facing lost-update risk. | one winner, one understandable `stale_version`, loser changes zero rows, agent reloads/merges/history-checks. |
| P1 | **“Import, verify, and curate.”** Import assets, induce a missing/mutated source, then use references/shots and report preserved identity. | Cross-domain identity, byte integrity and nested-mount discoverability are easy to misunderstand. | integrity failure is read-only; relation/association scopes are correct; shot removal preserves media; agent explains realm/primary/permutation. |
| P1 | **“Manage blocked and failed work.”** Create dependency-gated tasks, run a deterministic failure, retry eligible work, and report event evidence. | Agents may reach for retired task-mode verbs or retry terminal work unsafely. | agent discovers executor-owned lifecycle boundary, distinguishes blocked/failed/expired/terminal, and retries with preserved IDs/evidence. |
| P2 | **“Cancel a mixed run and close it.”** Cancel queued/running/terminal children, inspect derived progress, and close only when legal. | Exercises hidden run creation, cooperative running cancellation, and late-completion fencing. | terminal work remains intact; running handlers cannot publish after cancel; progress is derived and explained; no premature close or silent data loss. |
| P2 | **“Diagnose and restore.”** Doctor a damaged root, restore a supplied backup, and prove the final state. | Recovery friction is costly even when core state is correct. | doctor is read-only; restore is old-or-complete; agent handles `--force`, journal replay and secret exclusions. |

## Reproduced wave-0 observations

The following were observed in disposable roots and should be promoted to
deterministic regression scenarios:

- Project create with key `p1` replayed the same ID, result, receipt and event;
  changed request under `p1` returned `idempotency_mismatch` (exit 1), and a
  fresh duplicate slug returned `conflict` (exit 1).
- Timeline create starts at `config_version=1`; save at expected 1 returned
  version 2; a second save still expecting 1 returned `stale_version` with no
  receipt; history and diff exposed the two document versions; archive moved it
  to a terminal archived state.
- A standalone queued task produced one `core.task.created` hash-chained
  event; cancel produced one receipt/event, exact replay was idempotent, and a
  new-key terminal cancel returned `terminal_state` without a receipt.
- Healthy doctor returned `python_version`, `data_paths`, `media_paths`,
  `sqlite_quick_check`, `fk_integrity`, and `schema_versions` checks. Backup
  `--json` returned a custom multi-line object (`ok`, `dest_path`, `packs`,
  etc.), not the product five-key envelope; clients need an operational parser.
- Real `astrid.invoke('editorial.validate', kind='executor', project='demo')`
  in a root initialized through the CLI created a second `<root>/kernel.sqlite3`
  beside `.astrid/astrid.sqlite3` and returned `ok=false` with
  `NameError: ExecutorRunRequest is not defined` from the capability handler
  path. This is the P0 authority/lifecycle blocker, not merely a test fixture
  concern.
