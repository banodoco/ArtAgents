# Software-Engineering-Agent Composition Sketch

Status: **illustrative packaged-artifact and source-composition proof** (v10
GA item 12 / Phase 1). Scope: documents how a second agent reuses the
unchanged 14-table kernel with its own in-tree packs. It is not SWE product
scope, not a commitment to any pack's DDL or API, and not a dynamic plugin
loader.

## 1. The composition

A software-engineering agent is composed as the **unchanged kernel** plus its
own in-tree packs:

```text
unchanged 14-table kernel
+ workspace pack
+ changeset pack
+ review pack
```

The kernel is reused exactly as declared by `CORE_MIGRATIONS`
(`astrid/core/migrations/catalog.py`); no kernel table is added, renamed, or
dropped, and no kernel table is given a pack-specific meaning through DDL.

## 2. Kernel inventory (locked by the factoring check)

The composition reuses the audited 14-table kernel. Its kernel inventory is
transcribed verbatim from `CORE_MIGRATIONS` and locked by
`scripts/reshape/check_pack_factoring.py`: the check parses the block below,
derives the audited inventory from `CORE_MIGRATIONS`, and fails if the sketch
adds or omits any kernel table. The sketch therefore **cannot silently add a
kernel table** (for example a pack-specific foreign-key target, a new asset
table beside `media`, or a domain column-shaped table).

Kernel inventory (reused unchanged from CORE_MIGRATIONS):

```text
schema_migrations, projects, event_streams, events, command_receipts,
runs, evidence_items, tasks, task_dependencies, execution_attempts,
task_outputs, media, media_locations, media_relations
```

## 3. What each pack owns

All software-engineering domain state lives in pack tables; the kernel
continues to own execution, exact assets, ordered history, atomicity, and
evidence through its existing currencies (`projects`, `runs`, `tasks`,
`task_dependencies`, `execution_attempts`, `task_outputs`, `media`,
`event_streams`, `events`, `command_receipts`, `evidence_items`).

| Pack | Owns (illustrative) | Kernel currencies it uses |
| --- | --- | --- |
| **workspace** | repository/worktree and workspace context, scoped to a kernel `projects` row as its isolation boundary | `projects`, `media` (exact source files), `tasks`, `runs` |
| **changeset** | the domain meaning of a proposed source change: grouped diffs, affected files, patch/version lineage, and the selected primary artifact | `media` (source and diff bytes), `tasks` / `execution_attempts` (edit tasks), `task_outputs` (ordered outputs), `events` (pack aggregate stream) |
| **review** | comments, decisions, and review state, with evidence and exact diff/report assets attached through the kernel | `runs` / `evidence_items` (findings), `media` (reports, screenshots), `events` + `command_receipts` (retry-safe review decisions) |

## 4. Kernel meaning map

The mapping is structural, not linguistic: meaning can vary while the kernel
contract stays unchanged.

| Kernel part | Astrid / creative-video meaning now | Illustrative software-engineering meaning |
| --- | --- | --- |
| `projects` | A film, sequence, campaign, or other creative body of work | A bounded engineering workspace or initiative (product UI may say "workspace") |
| `runs` | A generation batch, render operation, or synchronous understanding result | A CI-style run, code search, refactor campaign, or test matrix |
| `tasks` / `task_dependencies` | Generation, rendering, analysis, probing; gated on prerequisite assets | File edits, code generation, tests, builds, searches; edit-before-verify edges and test matrices |
| `execution_attempts` | Fences provider-backed workers; stale attempts cannot materialize | Fences coding/CI workers; stale retries cannot publish edits or results |
| `task_outputs` | Ordered generated images, videos, manifests, and selected primary results | Ordered patches, source files, logs, reports, and a selected primary artifact |
| `media` / `media_locations` / `media_relations` | Exact bytes: footage, generated images, prompts-as-text, reports | Exact bytes: source files, diffs, patches, build logs, coverage data, screenshots; generated-from / patch / report-for lineage |
| `evidence_items` | Visual-quality findings, understanding summaries, warnings | Test outcomes, lint findings, review observations, benchmark results |
| `event_streams` / `events` / `command_receipts` | Orders aggregate changes; retry-safe mutations | Orders workspace changes, changeset revisions, review decisions; retry-safe edits and tool commands |

## 5. An illustrative journey

1. A user command creates a run and a bounded edit task under one atomic
   receipt.
2. A fenced attempt reads exact source media and produces exact changed-source
   and diff media.
3. A verification fan-out creates test and lint tasks with explicit
   dependencies and stable ordinals.
4. Test logs and reports become task-output media; summarized findings become
   evidence on the run.
5. The changeset pack projects the proposed change using `task_id` and
   `media_id`; the review pack records review decisions as registered events.
6. An identical retry returns the original receipt; a conflicting retry fails
   before mutation; a stale attempt cannot publish over the winner.

Nothing in this journey requires a new kernel column, a kernel foreign key, or
a new kernel table. Pack-specific state stays in pack tables.

## 6. What this sketch is explicitly not

- **Not a dynamic plugin platform.** There is no dynamic loader, no
  discovery, no install/uninstall path, and no runtime dependency solver.
  The composition is a compile-time, in-tree source composition: the same
  boundary discipline `register_standard_schema_packs` already uses for the
  Astrid packs.
- **Not a new kernel primitive.** If a real SWE implementation needs a table
  for an essentially domain-specific concept, the concept belongs in a pack.
  A genuinely universal missing primitive must be demonstrated across at
  least two compositions and evolved through the normal migration discipline.
- **Not an Astrid pack.** The workspace, changeset, and review packs are a
  separate composition; they are never registered in the Astrid standard
  tuple and never imported by kernel code.

## 7. How the check enforces it

`scripts/reshape/check_pack_factoring.py` verifies on every run that

1. the sketch's declared kernel inventory (section 2 above) equals exactly the
   inventory derived from `CORE_MIGRATIONS` -- any added table fails as
   "sketch adds kernel table(s) not declared by CORE_MIGRATIONS" and any
   omitted table fails as "sketch omits kernel table(s)";
2. the sketch names its own in-tree packs (`workspace`, `changeset`,
   `review`) and they are disjoint from the Astrid standard packs;
3. the check itself remains a read-only source-composition proof: no
   database is opened, no glob-based discovery runs, and no loader or
   install/uninstall machinery exists.

The focused tests in `tests/v10/test_pack_factoring.py` exercise the positive
binding and the negative controls (an injected extra kernel table and a
dropped kernel table both fail), so the sketch cannot silently grow the
kernel.

## 8. Packaged artifact-root proof (m8 GA gate)

The packaged factoring lane begins with exactly one built wheel and unpacks it
into a throwaway artifact root. For each of `timeline`, `shots`, and
`references`, the lane removes that pack directory and edits only the explicit
standard registration tuple in the temporary root. The wheel and checkout are
never edited.

For every reduced root, the lane proves all of the following before accepting
the composition:

1. `astrid` imports from the reduced artifact root, not the checkout;
2. the frozen registry contains the kernel plus only the two remaining pack
   tables, stream/event/command/repository/mount vocabulary, and no omitted
   pack vocabulary;
3. a fresh migrated database has exactly those tables, with foreign keys
   pointing only to the kernel or the owning pack;
4. the kernel and every remaining pack service use one explicit database
   writer, with repositories remaining writer-free; and
5. the complete fixed kernel test lane remains green against that reduced
   root.

This is an artifact-root composition proof, not a loader contract. The
software-engineering composition above remains the unchanged 14-table kernel
plus its own `workspace`, `changeset`, and `review` packs, and the inventory
binding in section 2 remains normative.
