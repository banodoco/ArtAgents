---
name: timeline
description: >
  Create and maintain canonical project timelines with whole-document CAS
  saves, event-backed archive recovery, deterministic history/diff reads, and
  timeline evidence/rendering entrypoints.
---

# Timeline

Use the timeline pack for the canonical whole-document timeline attached to a
project. A timeline has an immutable slug, a document `config`, a document
`registry`, and an integer content version. Timeline identity aliases and
archive state are resolved by the repository/event read path; do not add
convenience state beside it.

## Public CLI

The product family is available through the eight-family gateway. Every verb
makes one typed SDK service call and `--json` prints the stable five-key
(`ok`, `data`, `error`, `receipt`, `idempotency_key`) envelope.

```bash
# Create, list, and inspect a timeline.
python3 -m astrid timelines create --project demo primary --name "Primary" --json
python3 -m astrid timelines list --project demo --json
python3 -m astrid timelines show --project demo primary --json

# Whole-document compare-and-swap save. Both JSON objects are required.
python3 -m astrid timelines save --project demo primary \
  --config '{"tracks":[],"clips":[]}' \
  --registry '{"assets":{}}' --expected-version 1 --json

# Archive, recover, and inspect the append-only history.
python3 -m astrid timelines archive --project demo primary --json
python3 -m astrid timelines unarchive --project demo primary --json
python3 -m astrid timelines history --project demo primary --json
python3 -m astrid timelines diff --project demo primary --json
```

`--project` accepts an id or slug and may be omitted when a project selection
exists. `show`, `history`, and `diff` accept the timeline UUID, lowercase ULID,
or immutable slug. Ordinary `list` hides archived timelines; use
`list --include-archived` when recovering one.

A save must use the version returned by the latest read. A stale
`--expected-version` is rejected as `stale_version` before mutation. Archived
timelines reject saves until unarchived; archive does not change document
content. Idempotency keys are optional: the SDK generates and returns one for
mutations, and retries with the same request/key replay the committed receipt.

## Timeline evidence and render surfaces

`visualize` invokes `rendering.timeline_visualize` through the public SDK and
publishes a durable evidence pack. Start with Markdown and no filmstrip when no
verified rendered-video source is available. `render` invokes the managed
canonical renderer and supports an optional exact version pin.

```bash
python3 -m astrid timelines visualize primary --project demo \
  --format md --filmstrip off --json
python3 -m astrid timelines render primary --project demo \
  --expected-version 1 --backend rendering.remotion \
  --output-name primary.mp4 --json
```

Visualization accepts an optional timeline selector (the positional ref or
`--timeline-slug`), `--all`, `--timeline-source`, `--layout`, `--format`,
`--filmstrip`, focus selectors (`--range`, `--at`, `--clip`, `--asset`), and
frozen-view navigation (`--from-view`, `--focus`, `--refresh-root`). The
project-managed run and output manifests remain the durable evidence; do not
manually rewrite them.

## Python SDK

Use one context-managed `AstridClient` for project and timeline operations.
The client owns the shared writer, repository, event stream, and receipt
services; the timeline service holds no independent database connection.

```python
from astrid.sdk.client import AstridClient

with AstridClient.open(projects_root="./projects") as client:
    created = client.timelines.create(
        project="demo", slug="primary", name="Primary",
        config={"tracks": [], "clips": []}, registry={"assets": {}},
    )
    saved = client.timelines.save(
        "demo", "primary",
        config={"tracks": [], "clips": []},
        registry={"assets": {}}, expected_version=1,
    )
    current = client.timelines.show("demo", "primary")
    history = client.timelines.history("demo", "primary")
```

The service methods are `create`, `list`, `show`, `save`, `archive`,
`unarchive`, `history`, and `diff`. `create` accepts `set_default=True`; `list`
accepts `include_archived=True`. `save` replaces the complete config and
registry, not a partial field delta.

## Database ownership and vocabulary

The pack owns the `timelines` table through the pack-relative migration
`migrations/0001_initial.sql`. Migration SQL is the authority for the physical
schema; this guide intentionally does not restate DDL. Product code uses the
shared `DatabaseWriter`/`UnitOfWork` and `TimelineRepository`, never direct SQL
from the CLI or SDK.

The canonical timeline stream is `timeline.timeline`. Declared command kinds
are `timeline.create`, `timeline.save`, `timeline.archive`,
`timeline.unarchive`, and `timeline.replace_config`. Declared event kinds are
`timeline.created`, `timeline.saved`, `timeline.archived`,
`timeline.unarchived`, and `timeline.config_replaced`. `history` and `diff` are
read projections of the ordered lifecycle events; they are not extra writes.

## Pack boundary

Timeline rendering and visualization are delegated to the `rendering` pack.
Reusable project-level shots are owned by the `shots` pack and reached at the
nested `timelines shots` mount. Timeline config may refer to shot ids, but
shot commands do not implicitly attach or delete timeline records. Keep
migration, repository, bridge, CLI, and event behavior under this pack's
manifest-owned resources.
