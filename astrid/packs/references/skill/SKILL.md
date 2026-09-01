---
name: references
description: >
  Maintain reusable project references, canonical media associations, and
  typed reference links through the media references CLI mount and SDK.
---

# References

The references pack is the combined data, SDK, CLI, and documentation exemplar.
It provides reusable project references with one canonical primary media
association, additional media associations, and typed links between references.
Use exact project-scoped ids whenever possible; an unambiguous exact local name
is also accepted by the service for reference addressing.

## Public CLI mount

Reach this pack only through `media references`; it is not a separate
top-level family. Each verb performs one typed SDK service call. `--json`
returns the stable five-key product envelope.

```bash
# Create an active reference with its primary canonical media.
python3 -m astrid media references create --project demo \
  --kind character --name "Aria" --media M_01ABC --json

# Update only mutable fields; kind and project remain immutable.
python3 -m astrid media references update R_01ABC --project demo \
  --name "Aria (S1)" --json

# Soft archive and recover. Associations and links are preserved.
python3 -m astrid media references archive R_01ABC --project demo --json
python3 -m astrid media references unarchive R_01ABC --project demo --json

# Associate media, create a typed link, and replace the primary association.
python3 -m astrid media references associate R_01ABC --project demo \
  --media M_02DEF --role depicts --json
python3 -m astrid media references link --project demo \
  --from R_01ABC --to R_02DEF --kind belongs_to --json
python3 -m astrid media references set-primary R_01ABC --project demo \
  --media-reference MR_01ABC --json

# Active-only list is the default; inclusive list includes archived rows.
python3 -m astrid media references list --project demo --json
python3 -m astrid media references list --project demo --include-archived --json
python3 -m astrid media references show R_01ABC --project demo --json
```

`create` requires a frozen `--kind`, `--name`, and exact same-project `--media`;
`--description` and JSON-object `--metadata` are optional. `update` accepts a
name, description (including an empty value to clear), or metadata delta.
`associate` requires a frozen role and exact same-project media; `used_as_input`
requires `--context-task`. `link` takes `--from`, `--to`, and a frozen link
kind. `set-primary` takes the exact association id, not a media id.

Mutations accept `--idempotency-key`; absent keys are generated before the
write and returned in the envelope. Identical retries replay the committed
receipt. Archived references remain readable and recoverable, but active
mutations are rejected while archived.

## Frozen vocabularies

The repository and CLI enforce these shared vocabularies:

- reference kinds: `character`, `place`, `object`, `clothing`, `other`;
- media roles: `canonical`, `used_as_input`, `depicts`, `inspired_by`;
- link kinds: `belongs_to`, `wears`, `located_in`, `associated_with`,
  `related_to`.

`related_to` is symmetric and stored in canonical endpoint order. Other link
kinds preserve direction. A reference can have one primary canonical
association; `set-primary` replaces it atomically. Association, provenance,
context-task, same-project, duplicate, and archive rules are repository rules,
not CLI conventions.

## Python SDK

Use one context-managed client for the typed `references` service. The service
shares the application writer, project resolver, receipt service, and
`ReferenceRepository`; it contains no SQL and does not create a second writer.

```python
from astrid.sdk.client import AstridClient

with AstridClient.open(projects_root="./projects") as client:
    created = client.references.create(
        project="demo", kind="character", name="Aria",
        media_id="M_01ABC", metadata={"source": "brief"},
    )
    reference_id = created.data["id"]
    client.references.associate(
        "demo", reference_id, media_id="M_02DEF", role="depicts",
    )
    current = client.references.show("demo", reference_id)
```

The typed methods are `create`, `update`, `archive`, `unarchive`, `associate`,
`set_primary`, `link`, `list`, and `show`. `list` hides archived rows unless
`include_archived=True`; `show` includes archived rows. `show`, `update`,
`archive`, `unarchive`, and `associate` accept an exact id or an exact
project-local name where the service contract permits it. Ambiguous names fail
closed with candidate ids rather than guessing.

## Database ownership and events

The pack owns exactly three tables — `project_references`,
`media_references`, and `reference_links` — through the pack-relative
migration `migrations/0001_initial.sql`. Migration SQL is the physical-schema
authority; this guide intentionally does not duplicate DDL. All writes go
through `ReferenceRepository` inside the shared `DatabaseWriter`/`UnitOfWork`,
and reads use its transaction-free read path.

The aggregate stream is `reference.reference`. Declared commands are
`reference.create`, `reference.update`, `reference.archive`,
`reference.unarchive`, `reference.associate`, `reference.set_primary`, and
`reference.link`. Declared events are `reference.created`,
`reference.updated`, `reference.archived`, `reference.unarchived`,
`reference.media_associated`, `reference.primary_changed`, and
`reference.linked`. Receipt-backed mutations preserve the event and read-model
semantics; archive never deletes associations, links, media rows, or bytes.

## Pack boundary

Media identity and bytes are owned by the kernel media family. References store
exact media ids and repository-validated provenance; they do not copy or
relocate media. Timeline and shot records remain owned by their respective
packs. Keep the nested CLI mount and SDK service as the supported user-facing
surfaces.
