# Astrid Pack Contract (strict v2)

Astrid has one bundled-pack authority: `pack.yaml` with
`schema_version: 2`. The canonical catalog reads, normalizes, validates, and
projects each declaration once. Capability, database, documentation, and
resource views are typed projections of that catalog.

## Manifest identity

Every bundled product pack has exactly one declaration at
`astrid/packs/<id>/pack.yaml` with:

```yaml
schema_version: 2
id: references
name: References
version: 1.0.0
description: Project, media, and linked references.
documentation:
  kind: skill
  path: skill/SKILL.md
```

`schema_version`, `id`, `name`, and `version` are required. `id` is the owning
namespace; versions use `MAJOR.MINOR.PATCH`. Unknown fields, missing identity,
flat legacy mappings, alternate filenames, and path escapes are rejected.
`pack.yml`, `pack.json`, and `schema-pack.yaml` are not supported.

The complete grammar is the checked-in JSON Schema at
`astrid/core/pack/schemas/v2/pack.json`. The authoritative runtime path is
`BundledCatalog.from_root(...)` and its `CanonicalPackEntry` projections.

## Contribution axes

A pack may contribute any combination of:

- `capabilities` and declared `content` roots for executors, orchestrators, and
  elements;
- `extensions`, including rendering backend/planner/finalizer manifests;
- a bundled-only `database` contribution with migration identity and ownership;
- structured `documentation`, normally `skill/SKILL.md`;
- standalone `resources` with pack-relative paths and kinds.

The YAML database block declares ownership, migration names/versions, tables,
vocabulary, repositories, conformance, CLI mounts, bridge mounts, and positive
dependency migration heads. SQL remains authoritative for columns, constraints,
indexes, and transformations. External packs are capability-only; an external
`database` declaration is rejected before SQL or resource resolution.

All paths are relative to the owning pack root. The catalog resolves every
manifest, documentation file, required context file, migration, extension file,
and standalone runtime resource, rejects symlinks and traversal, and records a
confined `ResourceHandle` with size and SHA-256 for regular files.

## Documentation and discovery

Every user-facing bundled pack ships structured agent guidance at
`skill/SKILL.md`; `_core/skill/SKILL.md` is code-owned kernel guidance and
contains the generated 22-pack census. Agent workflows use the catalog-backed
SDK/CLI discovery and then the owning pack skill. They do not scan pack trees,
reconstruct identity from filenames, or infer database ownership independently.

`python3 -m astrid.core.pack.cli inspect <id>` reports canonical identity, source, capability and
database projections, documentation, and declared resource closure. The root
`astrid help` census remains the eight-family gateway surface; pack capabilities
are not a ninth gateway family.

## Customization

Aliases, forks, and overrides are distinct from bundled ownership:

- aliases are optional v2 pack-level identity mappings;
- forks copy a capability into a user-owned pack with provenance;
- overrides select a preferred capability without changing its canonical id.

Bundled product manifests currently declare no compatibility aliases. Do not
add an alias to preserve an alternate manifest filename or a removed schema-pack
form. Behavioral customization uses a fork or typed override. See
[aliases-vs-forks-vs-overrides.md](aliases-vs-forks-vs-overrides.md).

## Database composition

The standard database projection is derived from bundled catalog entries whose
`database.default_enabled` is true: core plus timeline, shots, and references.
Runaway is a valid database-bearing pack with `default_enabled: false` and can
be selected explicitly through the same projection. `schema_migrations` is the
sole applied-state record; there is no project composition lock or enable/
disable/purge lifecycle in beta.

Application, SDK invocation, read probes, doctor, backup/restore, inspect, and
CLI/bridge seams receive the same operation-owned catalog and frozen database
projection. They must not call a fixed pack tuple or independently parse a
manifest.

## Authoring checklist

1. Create one `pack.yaml` with strict v2 identity.
2. Declare capability/content roots, database ownership (if bundled and
   trusted), documentation, extensions, and standalone resources.
3. Keep every declared path inside the pack root.
4. Add structured `skill/SKILL.md` guidance and link only pack-relative context.
5. Run `python3 -m astrid.core.pack.cli validate <pack-root>`.
6. For bundled changes, run the source resource-closure check and the focused
   installed-artifact packaging tests.

This document describes the active contract. Older design decisions and test
findings are historical records and are not authoring guidance.
