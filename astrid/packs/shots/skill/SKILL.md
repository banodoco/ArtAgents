---
name: shots
description: >
  Manage reusable project-level shots and their ordered same-project media
  items through the nested timelines shots CLI mount or typed SDK service.
---

# Shots

Shots are reusable project-level records. The CLI nesting under `timelines` is
a discoverability mount, not an implicit timeline association: shot operations
never take a timeline id. A timeline document may refer to a shot id in its own
config, and removing that reference does not delete the shot.

## Public CLI mount

Reach this pack only through `timelines shots`. Each verb makes one typed SDK
service call. Use `--json` for the stable five-key product envelope.

```bash
python3 -m astrid timelines shots list --project demo --json
python3 -m astrid timelines shots show S_01ABC --project demo --json
python3 -m astrid timelines shots create --project demo --name "Shot 1" --json

# Insert exact same-project media; position is 0-based and defaults to append.
python3 -m astrid timelines shots add S_01ABC --project demo \
  --media M_01ABC --position 0 --json

# Remove only the shot item; the kernel media and bytes remain.
python3 -m astrid timelines shots remove S_01ABC I_01ABC \
  --project demo --json

# Supply the whole item-id permutation; repeat --items or use commas.
python3 -m astrid timelines shots reorder S_01ABC --project demo \
  --items I_02DEF,I_01ABC --json
```

`list` is ordered by shot `sort_key`, then id. `show` returns ordered items,
media ids, positions, and best-effort media name/path details. `create` accepts
`--name` and optional JSON-object `--metadata`. `add` requires `--media` and
accepts `--position`, `--source-frame`, and JSON-object `--metadata`.
`remove` takes a shot id and item id. `reorder` requires the exact complete
permutation: omissions, duplicates, extras, and foreign-shot ids fail before
any write.

All mutation commands accept `--idempotency-key`; when omitted, the SDK
generates and returns one. Repeating an identical request/key replays its
committed receipt without duplicate rows. A media id must exist in the same
project as the shot.

## Python SDK

Use the typed service on a context-managed `AstridClient`; it shares the
project resolver, one `DatabaseWriter`, receipt service, and shot repository
with the other product services.

```python
from astrid.sdk.client import AstridClient

with AstridClient.open(projects_root="./projects") as client:
    shot = client.shots.create(project="demo", name="Shot 1")
    added = client.shots.add_item(
        "demo", shot.data["id"], media_id="M_01ABC", position=0,
    )
    current = client.shots.show("demo", shot.data["id"])
    ordered = client.shots.reorder(
        "demo", shot.data["id"], [added.data["item"]["id"]],
    )
```

The typed methods are `list`, `show`, `create`, `add_item`, `remove_item`, and
`reorder`. Results are `DomainResult` values: inspect `ok`, `data`, `error`,
`receipt`, and `idempotency_key` rather than assuming a mutation succeeded.
`show` may enrich items with media locator details when the composed
application has the media repository available; the shot's authoritative
identity remains its exact `media_id`.

## Database ownership and vocabulary

The pack owns the `shots` and `shot_items` tables through the pack-relative
migration `migrations/0001_initial.sql`. Migration SQL remains authoritative
for the physical schema; this guide does not duplicate DDL. The repository is
`ShotRepository`, and commands run inside the caller's shared
`DatabaseWriter`/`UnitOfWork`; reads use the transaction-free read path.

The aggregate stream is `shot.shot`. Declared commands are `shot.create`,
`shot.add_item`, `shot.remove_item`, and `shot.reorder`. Declared events are
`shot.created`, `shot.item_added`, `shot.item_removed`, and `shot.reordered`.
The pack owns no timeline foreign-key relationship; the nested CLI mount is
only a surface-level route.

## Pack boundary

Media bytes and media identity belong to the kernel `media` family. Timeline
content and timeline rendering belong to the `timeline` and `rendering` packs.
Do not copy media files into this pack or edit its tables outside the repository
and shared writer boundary.
