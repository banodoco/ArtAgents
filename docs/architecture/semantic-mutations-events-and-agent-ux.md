# Semantic Mutations, Events, and Agent UX

Status: proposed holistic implementation plan
Date: 2026-09-04

## Summary

The awkwardness exposed while fixing the Astrid Intro ending is not primarily a
missing `span` command. It is a cross-cutting agent-UX problem:

1. Astrid often exposes storage-shaped mutations instead of intent-shaped
   mutations.
2. The runtime has strong canonical ownership, compare-and-swap protection,
   receipts, and event streams, but those concepts are not presented as one
   coherent editing journey.
3. Some semantic event vocabulary already exists internally, but the public
   runtime write surface does not expose corresponding operations.
4. Documentation describes individual commands, but does not consistently
   teach how an agent inspects, changes, audits, renders, follows, diagnoses,
   and opens one piece of work.
5. Several documentation claims do not match the current executable surface,
   so documentation alone cannot solve the problem.

The general solution is a shared **semantic mutation protocol** implemented by
resource-specific runtime handlers, with domain-specific CLI commands on top.
It should reuse the existing kernel `event_streams`, `events`, and
`command_receipts` architecture rather than introduce another edit log. Every
committed mutation should produce a versioned receipt and one or more meaningful
domain events. Every asynchronous operation should return a task/run handoff
that can be followed to outputs, events, logs, and an openable artifact.

The intended journey is:

```text
resolve -> inspect/review -> dry-run or apply -> diff/history/undo
        -> render -> follow -> diagnose if needed -> open
```

This should be delivered as one holistic agent-command-UX initiative, not as
uncoordinated tickets for `span`, project inference, events, logs, and docs.
Those are different layers of the same promise: an agent can express intent,
observe the authoritative result, and know the next action.

## Motivating case

The ending initially contained a visual that was scoped to an individual shot.
It disappeared at a boundary and was reconstructed for the following beat,
breaking continuity. The desired interaction was approximately:

```bash
# Read-only inspection of the problematic interval.
astrid timelines review main --range 68.097..97.878

# Extend one existing visual clip across the complete interval.
astrid timelines clips span main fx-end_deepseek --until 97.878
```

Today, the first operation mostly exists as:

```bash
astrid timelines visualize main \
  --project astrid-intro \
  --range 68.097..97.878
```

The second does not exist. The only public composition mutation is a
whole-document compare-and-swap save that requires the complete timeline
config, complete registry, and expected version. That made a small structural
edit require carrying and resubmitting the entire document.

The eventual fix had two distinct parts which should remain distinct:

- **Timeline structure:** one clip spans the whole ending, so the renderer
  preserves one component lifecycle across shot boundaries.
- **Element behavior:** the Remotion element implements the internal DeepSeek,
  Codex, Minimax, and music phases.

A semantic `span` operation would have made the first part easy and safe. It
would not, and should not, pretend to author the component's internal visual
behavior.

## Current state and gaps

### Inspection is capable but poorly surfaced

`timelines visualize` already supports a timeline range, timestamp, clip, shot,
asset, context window, neighboring clips, layouts, and filmstrip policies. It
emits a durable evidence pack through a normal runtime run.

The capability is stronger than its discoverability. “Visualize” describes an
implementation; “review this part of the timeline” describes the user's task.
A preferred `timelines review` journey may wrap the same capability, open or
return the primary evidence artifact, and remain explicitly read-only. It must
not imply that an editorial approval decision was recorded unless the user
actually submits one.

### Timeline mutation is storage-shaped

`timelines save` is safe in one important respect: it is a whole-document CAS
operation, so a stale writer cannot silently overwrite a newer document. It is
nevertheless a poor normal editing surface. An agent changing one clip must:

- fetch and retain every unrelated config and registry field;
- edit a nested JSON structure correctly;
- resubmit both complete documents;
- carry the version manually;
- recover and merge the whole document if another writer wins the race.

This is high cognitive load and creates accidental-deletion risk. Whole-document
save should remain an escape hatch for import, migration, and editor snapshot
replacement, not the default way to trim or move a clip.

### The semantic vocabulary exists but is disconnected

Astrid's internal timeline event schema already includes operations such as
`clip.added`, `clip.removed`, `clip.moved`, `clip.retracked`, `clip.retimed`,
`clip.replaced`, `track.added`, `track.removed`, and effect/transition edits.
For example, `clip.retimed` projects onto canonical `at` and `hold` fields and
has inverse-planning support.

The generated workspace client, however, exposes only
`update_timeline_document` for timeline content mutation. The semantic model is
there, but it is not connected to the sole live runtime authority or to the
public SDK/CLI.

### Public audit behavior is currently inconsistent

The live Astrid Intro timeline currently reports `config_version: 7`, but a
public `timelines history` read by exact timeline ID returned only its initial
version-1 record. Public `timelines diff` also failed because the SDK requires
`from_version` and `to_version` while the CLI exposes no corresponding flags.

This is important: documentation says timeline history and diff are the audit
companions to CAS editing, but the current public path cannot demonstrate the
six committed document changes made after creation. The event vocabulary and
older architecture evidence say those changes should be represented, while the
live product read does not expose them. That is an implementation/contract gap,
not something documentation can paper over.

The underlying event substrate is not missing. The kernel already has ordered
aggregate streams, project transaction sequence allocation, command receipts
whose `event_ids` link to committed events, registered stream/event/command
vocabularies, and task/run lifecycle events. The problem is integration and
coverage:

- timeline create/archive/recover and task lifecycle transitions emit events;
- the current generic whole-document timeline update returns a receipt but does
  not append a timeline content event or advance its event stream;
- most shot, reference, and media mutations return receipts without domain
  events;
- the rich `clip.*`, `track.*`, effect, transition, and audio event vocabulary
  in Astrid is currently used as a projection/visualization model, not as the
  live runtime mutation API;
- public event reads emphasize task/run execution events and do not yet provide
  one filterable route across timeline, shot, reference, media, and review
  aggregates.

Therefore the work is not “build event sourcing.” It is “make all semantic
mutations use the event substrate Astrid already deliberately built, then make
the correlations visible to agents.”

### Project routing is inconsistent

Timeline commands currently require `--project`, even though the product also
has runtime project selection and documentation claims that a sole project can
be inferred. A command aimed at an exact canonical resource should not require
the caller to repeat ownership already known by the runtime.

A shared resolver should use this order:

1. explicit `--project` override;
2. owner of an exact globally unique resource ID;
3. runtime-selected current project;
4. a unique project-local slug match or the sole visible project;
5. otherwise fail closed and return candidate projects plus a copy-pasteable
   retry.

Project inference must be one runtime/SDK contract used by all product
families, not slightly different CLI heuristics.

## General semantic mutation model

The public interface should remain specific and readable while sharing one
internal mutation envelope.

| Resource shape | Examples | Natural operations |
| --- | --- | --- |
| Versioned document | timeline, project settings | set fields, apply typed operations, replace snapshot |
| Ordered collection | timeline clips/tracks, shot items | add, remove, move, retime, reorder |
| Relationship graph | media relations, reference associations | associate, link, unlink, set primary |
| State machine | task, run, review decision | cancel, retry, approve, reject |
| Immutable artifact | managed media, render output | import, derive, verify, materialize/open |

The internal request shape should be uniform:

```json
{
  "target": {
    "resource_type": "timeline",
    "ref": "main",
    "project": null
  },
  "expected_version": 7,
  "operations": [
    {
      "kind": "clip.set_interval",
      "selector": {"clip_id": "fx-end_deepseek"},
      "end_exclusive": 97.878
    }
  ],
  "dry_run": false,
  "idempotency_key": "..."
}
```

The runtime must perform one authoritative transaction:

1. resolve exactly one project and target aggregate;
2. read and lock the current head;
3. enforce an explicit version when supplied;
4. resolve every selector exactly once;
5. normalize intent into canonical operations;
6. calculate derived values such as `hold`, including playback speed;
7. apply all operations in memory;
8. validate the complete resulting document and registry;
9. commit the snapshot, ordered semantic events, receipt, and new head
   atomically in the existing runtime event transaction;
10. return a stable result with meaningful next actions.

Do not implement this as a CLI `show` followed by a whole-document `save`.
That would preserve the current race window and make the CLI another domain
authority. The CLI handler should still make one SDK call; the semantic
operation belongs in the runtime.

Do not expose generic JSON Patch as the primary product surface. JSON Patch
cannot explain timeline interval rules, track layering, media ownership,
reference roles, or valid task transitions. Typed operations produce better
validation, diffs, events, undo, help, and agent reasoning.

### Public timeline commands

Friendly commands should compile to the same typed operation protocol:

```bash
astrid timelines clips span main fx-end_deepseek --until 97.878
astrid timelines clips move main fx-end_deepseek --at 68.097
astrid timelines clips trim main pic14 --from 0 --to 8.843
astrid timelines clips set main fx-end_deepseek \
  --param deepSeekSeconds=9.193
astrid timelines tracks add main fx --kind visual --before picture
astrid timelines tracks reorder main --tracks frame,fx,picture,vo
```

“Clip” is intentional terminology. A clip is an instance in a timeline. An
element is the reusable effect/animation/transition implementation referenced
by a clip's `clipType`. A layer is a useful visual metaphor, but it is not
currently an independently owned runtime resource.

For multi-edit work, offer an atomic batch surface:

```bash
astrid timelines edit main --ops edit.json --dry-run
astrid timelines edit main --ops edit.json
```

## Event, receipt, task, and log semantics

These are related but different records. Agent UX should name them clearly.

### 1. Command receipts

A receipt answers: **did the runtime accept and commit this command exactly
once?** It carries the command kind, idempotency key, target, old/new version,
and committed event ID. Replaying the same idempotency key and identical
request returns the same receipt/result. Reusing it for a different request
fails.

Every committed semantic mutation should return a receipt. A dry-run should
not mint a mutation receipt because it changed no canonical state.

### 2. Domain events

A domain event answers: **what canonical state changed, and why?**

Current coverage is uneven:

| Current mutation surface | Receipt | Domain event |
| --- | --- | --- |
| Timeline create | Yes | Timeline-created event |
| Generic whole-document timeline update | Yes | No content event; receipt event list can be empty |
| Timeline archive/recover | Yes | Archive/recovery event |
| Shot item mutations | Yes | Generally no shot domain event |
| Reference and media-relation mutations | Yes | Generally no reference/media domain event |
| Task admission/cancel/retry/completion/failure | Usually yes, with some legacy inconsistencies | Task lifecycle events |
| Run cancel/retry | Idempotent legacy record | Run/task lifecycle events, but incomplete canonical receipt linkage |

This explains the apparent contradiction: Astrid does have a large event-stream
system and some commands definitely log events, but “successful mutation” does
not currently imply “meaningful domain event was appended.” A receipt with an
empty `event_ids` list proves the command was recorded, not that history can
explain the state change.

Preferred policy:

- One atomic user command produces one receipt.
- The receipt references one or more ordered semantic event IDs using the
  existing receipt `event_ids` field and project sequence range.
- A single clip-span operation emits the existing normalized fact
  `clip.retimed`; it does not invent a parallel `timeline.edited` vocabulary.
- An atomic batch emits its normalized semantic events in one unit of work.
  The UI/history groups them by receipt so the user sees one command even when
  the aggregate stream head advances across several facts.
- Each event records actor, source command, receipt/transaction ID, selectors as
  resolved canonical IDs, before/after values or sufficient inverse data, and
  the resulting snapshot hash.
- Projection applies those events to the canonical snapshot in the same runtime
  transaction.
- Semantic edits must not also append a second state-changing
  `timeline.config_replaced` event. Snapshot replacement remains the event for
  the low-level whole-document save path.

This makes history readable:

```text
v7 -> v8  clip fx-end_deepseek retimed
          68.097..77.290 -> 68.097..97.878
          actor: agent/codex
          receipt: txn-...
```

It also enables append-only undo. `undo` does not delete history; it validates
the current head and appends the ordered inverse events linked to the original
receipt/events:

```bash
astrid timelines undo main --receipt txn-...
```

### 3. Task and run events

Task/run events answer: **what happened while asynchronous work executed?**
Rendering currently produces durable milestones such as `task.admitted`,
`task.claimed`, and `task.completed`, including output object digests at
completion. Timeline visualization/review also creates task/run lifecycle
events because it executes a capability, even though it does not mutate the
timeline.

The rules should be explicit:

| Action | Timeline/domain mutation event? | Task/run lifecycle events? |
| --- | --- | --- |
| `timelines review` / `visualize` | No | Yes, when implemented as a capability run |
| `timelines clips span` dry-run | No | No, unless validation is deliberately modeled as a task |
| `timelines clips span` commit | Yes | No for an immediate runtime transaction |
| `timelines render` | No | Yes |
| `tasks follow` | No | No; it reads current state/events |
| `runs open` | No | No canonical mutation; access telemetry may be separate |
| submit an editorial decision | Yes, on a review aggregate | Only if submission itself is asynchronous |

### 4. Existing event substrate: retain and extend it

The canonical design should remain kernel snapshot plus append-only audit:

- `event_streams` provides per-aggregate ordering and CAS heads;
- `events` stores registered, namespaced facts;
- `command_receipts` provides retry identity and links a command to its ordered
  event IDs and project sequence range;
- projection rows provide efficient current state;
- task/run events provide execution lifecycle history;
- evidence objects and logs contain large diagnostic/output material.

The semantic mutation endpoint should be another typed writer into this model,
not a local timeline event file, a CLI-side event store, or an additional
database. Failures and dry-runs commit no receipt, events, projection change, or
head advance. An idempotent replay returns the exact original receipt and event
IDs. A changed request under the same idempotency key fails.

The public read side needs a correspondingly general event route that can be
filtered by project, aggregate type/ID, receipt, transaction/project sequence,
and event kind. `timelines history` can remain the human-friendly aggregate
view, while a lower-level event query exposes exact correlation across
resources and execution.

### 5. Progress and logs

Events should not become an unbounded stdout dump. Durable events are for
meaningful state transitions. Operational evidence needs two additional
surfaces:

- **Structured progress:** current phase, completed work, total work, unit,
  observed rate, heartbeat, queue position when known, and timestamps. This is
  sufficient for `tasks follow` to calculate a defensible ETA. If a runtime
  cannot report a field, the CLI should say why it is unavailable rather than
  inventing a number.
- **Attempt logs:** redacted, paginated logs addressable by task/run and attempt,
  with a durable final log artifact where appropriate. Logs explain failures;
  lifecycle events identify when and where failure occurred.

The Astrid Intro render's public event stream contained admitted, claimed, and
completed milestones, but no structured frame progress, speed, queue position,
ETA inputs, or log link. `tasks follow` can present those absences honestly, but
the runtime/executor must emit the underlying data before the follower can show
more.

## The complete agent journey

An elegant command should never strand the caller after success or failure.

### Inspect

```bash
astrid timelines review main --range 68.097..97.878
```

Example result:

```text
review ready
timeline: main
version: 7
view: view-...
open: astrid timelines review open view-...
edit: astrid timelines clips ...
```

### Mutate

```bash
astrid timelines clips span main fx-end_deepseek --until 97.878
```

Example result:

```text
timeline updated  v7 -> v8
change: fx-end_deepseek  68.097..77.290 -> 68.097..97.878
receipt: txn-...
history: astrid timelines history main --since-version 7
undo: astrid timelines undo main --receipt txn-...
review: astrid timelines review main --range 68.097..97.878
render: astrid timelines render main --expected-version 8 --detach
```

### Execute and follow

```bash
astrid timelines render main --expected-version 8 --detach
astrid tasks follow <task-id>
```

The render admission result should contain the durable task/run IDs and exact
follow command. The follower should show phase, heartbeat, progress, rate,
queue position, and ETA where defensible. On failure it should print event,
log, retry, and inspection commands. On success it should print the output URL
or materialization path, exact open command, and recent completed-task command.

## Documentation is part of the product contract

This is a meta problem because the product surface, event model, and
documentation currently drift independently. The fix needs layered
documentation with one source of truth for each concern.

### Documentation layers

| Layer | Purpose | Required content |
| --- | --- | --- |
| CLI `--help` | Exact executable grammar | arguments, defaults, inference, interval semantics, exit behavior |
| SDK reference | Typed programmatic contract | request/result DTOs, exceptions, receipts, idempotency, CAS |
| Contract/architecture docs | Stable semantics | authority, transactions, events, projections, logs, undo |
| Agent skill | Task routing | which command to use, safe defaults, common recovery, terminology |
| Journey guide | End-to-end learning | inspect -> edit -> render -> follow -> diagnose -> open |
| Live acceptance evidence | Prevent aspirational docs | copy-paste journeys against the real runtime |

CLI help and generated SDK types should be mechanically checked against the
runtime contract. Command tables in skills and guides should be generated or
tested where possible, rather than manually copied into several files.

### Known documentation/agent-UX mismatches to resolve

1. The Astrid skill says a sole runtime project can be inferred, while timeline
   CLI parsers currently require `--project`.
2. Visualization documentation discusses selected-project resolution, while
   its CLI and SDK admission reject a missing project.
3. Timeline history/diff are documented as audit tools, while the live history
   omitted committed config versions and `diff` has no CLI version flags for
   the SDK requirement.
4. Existing docs explain families individually but do not provide one current
   edit-to-output journey with receipts, follow, failure logs, and open.
5. “Element,” “clip,” “track,” “layer,” “shot,” “task,” “run,” “event,”
   “receipt,” and “log” need a concise shared glossary. The earlier workflow
   used “Remotion thing” because the product did not surface the right noun.
6. Successful command output should teach the next step. Agents should not need
   to rediscover `follow`, `events`, `logs`, `retry`, `open`, or `recent` from
   separate help pages.

### Skill hierarchy

Timeline work warrants a dedicated deep skill. The core Astrid skill is already
responsible for gateway setup, product-family routing, and the global command
census; it should not also carry every timing, layering, event, editing, and
rendering detail.

The intended hierarchy is:

```text
astrid (core skill)
  -> summarizes the product families and routes timeline-specific work
  -> astrid-timeline (deep timeline skill)
       -> canonical timeline authority and terminology
       -> inspect/visualize/edit/version/history/event workflow
       -> clip timing, track layering, element/source boundaries
       -> render/follow/diagnose/open workflow
       -> links to detailed contracts and this proposal
```

`typed_timeline.map` remains a narrow executor that maps admitted typed rows
into a timeline JSON artifact. It is not a user workflow and should not be
installed as a competing agent skill. The dedicated timeline skill describes
working with the runtime-owned timeline product itself and can point to the
mapper only when that specific conversion is actually relevant.

The dedicated skill should live at
`astrid/packs/timeline/skill/SKILL.md`. Until semantic edit commands ship, it
must distinguish current commands from proposed commands and warn about known
history/diff and project-routing limitations. Once the product contracts are
fixed, update the skill in the same change rather than leaving transitional
warnings indefinitely. The existing `typed_timeline` skill declaration should
be removed in that implementation change while retaining its executor.

Documentation fixes should follow implementation fixes. Where the executable
contract is missing or contradictory, first repair the runtime/SDK/CLI and add
acceptance tests; then update help, skills, and guides in the same change.

## Implementation sequence

Treat the phases below as workstreams in one project with shared acceptance
journeys. A phase may land separately, but no phase should claim the agent UX is
complete while its adjacent handoff remains missing.

### Phase 1: freeze the operation and event contracts

- Define the shared mutation request/result envelopes.
- Define version, idempotency, dry-run, selector, transaction, and undo
  semantics.
- Decide the single-operation versus batch event shape.
- Define canonical project/resource resolution.
- Fix and test public timeline history/diff before depending on them.

### Phase 2: add runtime and SDK support

- Add a runtime `apply_timeline_operations` transaction.
- Connect it to canonical timeline projection and validation.
- Emit receipt-linked semantic events.
- Add `client.timelines.apply(...)` with typed operation DTOs.
- Retain whole-document save as an explicit replacement operation.

### Phase 3: add the public editing surface

- Add `timelines clips` and `timelines tracks` nested commands.
- Add batch `timelines edit --ops` and `--dry-run`.
- Add receipt-based `timelines undo`.
- Add readable field-level history/diff output.
- Add `timelines review` as a read-only journey over visualization, or improve
  `visualize` enough that a separate verb is unnecessary.

### Phase 4: complete execution observability

- Standardize progress snapshots across executors.
- Expose paginated attempt logs and durable final log artifacts.
- Connect task/run failures to their relevant logs and inputs.
- Ensure render admission and task completion return follow/open/recent
  handoffs.

### Phase 5: repair documentation and lock it with journeys

- Update CLI help, SDK reference, contracts, the core Astrid skill, and CLI
  journeys together.
- Add one golden agent journey based on the ending-continuity case.
- Test every documented command against the runtime-backed parser/client.
- Add a live acceptance case proving events, history, diff, undo, render,
  follow, logs, and open form one navigable chain.

## Definition of done

The meta problem is solved when an agent can:

1. find the correct timeline without redundantly specifying a known project;
2. review a bounded interval and know the exact canonical version reviewed;
3. perform a small intent-shaped edit without carrying the whole document;
4. preview the edit and receive meaningful validation;
5. see the committed edit as a readable, receipt-linked history event;
6. inspect a field-level diff and undo it without erasing history;
7. render the exact resulting version and receive a durable task handle;
8. follow real progress with an ETA when the executor supplies enough data;
9. inspect lifecycle events and redacted logs on failure;
10. open the verified output and discover recent completed work;
11. learn this journey from CLI output and the agent skill without encountering
    contradictions.

That is the reusable solution. `clip span` is simply the first concrete
operation that exposed why the larger contract is needed.
