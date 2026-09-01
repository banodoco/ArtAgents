---
name: runaway
description: >
  Compose optional Runaway timing storage and insert receipt-backed transition
  batches with deterministic prompts, contiguous ordinals, and sharded runs.
---

# Runaway

Runaway is an optional database-only pack for timing transitions. It is
explicitly composable but disabled from the default application composition.
It has no user-facing CLI mount, typed public SDK service, capability executor,
or pack-owned event stream. Do not infer its presence from a database or add it
to the default composition implicitly.

## Composition boundary

Compose the pack through the same explicit registry/application injection used
by the database owner. A bound application must include the pack before opening
or writing a project database that has its migration applied. Keep one shared
writer, receipt service, and registry for the operation; do not open a second
SQLite writer or hand-edit the database.

The executable API is `RunawayRepository` in
`astrid.packs.runaway.repository`. It receives the caller's `UnitOfWork` and
`ReceiptService`; it owns no writer or transaction of its own. Pack-aware
application code uses the repository directly:

```python
from astrid.core.store.uow import UnitOfWork
from astrid.packs.runaway import RunawayRepository

repo = RunawayRepository(receipts=receipts)  # shared application service
result = UnitOfWork(writer).run(
    lambda uow: repo.create(
        uow,
        project_id=project_id,
        run_id=run_id,
        transitions=[
            {
                "ordinal": 0,
                "start_ms": 0,
                "duration_ms": 500,
                "prompt": "rose neon piano chord, hard cut",
                "metadata": {"segment": "S01"},
            }
        ],
    )
)
```

For reads, use a read-only connection and the repository's transaction-free
methods:

```python
with writer.read_only_connection() as conn:
    transitions = repo.list(conn, project_id=project_id, run_id=run_id)
```

The create result is a frozen `RunawayCreateReadModel` containing project/run
identity, ordered transition ids, first and last ordinals, and its timestamp.
Read models are the supported inspection shape; there is no raw SQL surface.

## Transition contract

Each transition is a mapping with `ordinal`, `start_ms`, `duration_ms`, and a
non-empty `prompt`; optional fields are `metadata`, `task_id`, and `id`.
Repository validation requires:

- non-negative integer ordinals and start times;
- positive durations;
- unique, contiguous ordinals within a batch;
- when appending to a run, the batch starts at the next ordinal after the
  existing run data;
- task ids are unique per run, exist, and belong to the same project;
- explicit transition ids do not collide; generated ids are lowercase ULIDs;
- project and run exist, and the run belongs to that project;
- metadata is canonicalizable before insertion.

Creation inserts the batch atomically and records one receipt using command kind
`runaway.create`. Without an explicit key, the default key is
`runaway:create:{run_id}`. An identical retry returns the stored result with no
new rows; a changed request under the same key fails as an idempotency mismatch.

Runs with more than 256 transitions may shard across continuation runs. The
stored rows retain each shard's `run_id` while ordinals remain globally
contiguous. Append the next batch with a distinct idempotency key when the
operation is intentionally a new batch.

## Deterministic prompts

`build_prompt`, `prompts_for_manifest`, and `sample_prompts` are pure helpers
for the Runaway timing design. The template is:

```text
{colour_name} neon piano chord, hard cut, 48fps, complementary colour {next_colour}, {timing_mode}, {segment_id}
```

`prompts_for_manifest` follows the input transition order and uses the next
transition's colour, with `hold` for the final transition. `sample_prompts`
returns the first ten generated prompts. These helpers perform no I/O and do
not replace repository validation.

## Database ownership and resources

The pack owns `runaway_transitions` through the pack-relative migration
`migrations/0001_initial.sql`. Migration SQL is authoritative for the physical
schema; this guide deliberately does not duplicate DDL. The pack references
kernel project, run, and task identities but does not own their tables.

The declared command is `runaway.create`; the pack declares no stream types,
events, CLI mounts, or bridge mounts. Its direct resources are the migration,
`repository.py`, `prompts.py`, and the pack's structured skill. Keep all
migration/resource resolution relative to this pack root.

## Recovery and boundaries

A missing project/run, foreign run, invalid transition batch, duplicate task or
ordinal, or receipt mismatch is a typed repository failure and must leave the
batch uncommitted. To inspect or recover, use the owning application/database
composition and the repository read models. Do not add a public CLI command,
write transition rows outside `RunawayRepository`, or restore the removed
historical demo as a runtime dependency.
