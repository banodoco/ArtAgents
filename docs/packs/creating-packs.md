# Creating Astrid Packs

This guide covers the active strict-v2 pack workflow. A pack is one directory
with one authoritative `pack.yaml`; capabilities, optional database ownership,
agent guidance, and pack-relative resources are declared there.

## Quick start

```bash
python3 -m astrid.core.pack.cli new my_video_tools
cd my_video_tools
python3 -m astrid.core.pack.cli validate .
```

The scaffold must be completed with a strict v2 declaration before it is
loaded. Add component directories under the declared content roots, each with
its component manifest and `run.py` entrypoint. The pack validator checks the
layout without importing or executing pack code.

## Canonical layout

```text
my_video_tools/
  pack.yaml
  skill/
    SKILL.md
  executors/
    transcribe/
      executor.yaml
      run.py
      STAGE.md
  orchestrators/
    make_highlight_reel/
      orchestrator.yaml
      run.py
      STAGE.md
  elements/
    effects/<id>/
      element.yaml
      component.tsx
```

`content.executors`, `content.orchestrators`, and `content.elements` in
`pack.yaml` name the roots. The catalog uses those declarations; it does not
infer pack identity or ownership from arbitrary directory names.

## Strict v2 manifest

The complete manifest grammar is
[`astrid/core/pack/schemas/v2/pack.json`](../../astrid/core/pack/schemas/v2/pack.json).
The minimum valid declaration is:

```yaml
schema_version: 2
id: my_video_tools
name: My Video Tools
version: 1.0.0
description: Tools for preparing and rendering video.
status: active
visibility: visible
domain: media
stability: stable
support: project
capabilities:
  - transcribe_audio
agent:
  purpose: Turn source media into a transcript.
  do_not_use_for: Final video rendering.
  normal_entrypoints:
    - my_video_tools.transcribe
documentation:
  kind: skill
  path: skill/SKILL.md
content:
  executors: executors
```

A declaration must use `schema_version: 2`, a lowercase pack id, a release
version, and at least one contribution (`capabilities`, `content`,
`extensions`, `documentation`, `database`, or `resources`). Alternate pack
filenames, schema-less/flat YAML, unknown fields, and missing identity are
invalid. There is no v1 pack reader and no compatibility form.

Component manifests remain the typed contracts for executor, orchestrator, and
element implementations. Rendering extension manifests remain under their
existing rendering schema. The pack manifest owns the pack identity and
resource/documentation references; component manifests own component details.

## Database-bearing packs

Trusted bundled packs may declare SQLite ownership:

```yaml
database:
  default_enabled: false
  depends_on:
    - pack: core
      min_migration: 1
  migrations:
    - version: 1
      name: initial
      path: migrations/0001_initial.sql
      tables: [my_records]
  stream_types: []
  event_kinds: []
  command_kinds: []
  repositories: [MyRecordRepository]
  conformance: []
  cli_mounts: {}
  bridge_mounts: []
```

Migration SQL is the authority for DDL, columns, constraints, indexes, and
transformations. The manifest declares ownership and migration identity; it
must not duplicate SQL. `path` is relative to this pack root and resolves
through the canonical resource handle. A dependency uses a pack id and a
positive minimum migration head.

External packs remain capability-only during beta. An external database block
fails closed before SQL or resource resolution.

## Resources and documentation

Use `documentation.path` for the pack's structured agent guidance. Use
`resources` only for standalone runtime/service files not already represented
by a content root or extension declaration:

```yaml
resources:
  - path: templates/default.json
    kind: runtime
```

All declared paths are pack-relative and must resolve to regular files or
owned content directories without symlink escapes. Required agent context,
migrations, rendering extension manifests, and standalone resources are
included in the source and wheel closure check. Every bundled product pack
ships `skill/SKILL.md`; `_core/skill/SKILL.md` publishes the generated census
and routes agents to each owner.

## Inspect and validate

```bash
python3 -m astrid.core.pack.cli validate /path/to/pack
python3 -m astrid.core.pack.cli inspect my_video_tools
python3 -m astrid.core.pack.cli inspect my_video_tools --json
python3 -m astrid.core.pack.cli list
python3 -m astrid.core.pack.cli status
python3 -m scripts.reshape.package_closure .
```

Inspection is catalog-backed and shows canonical identity, source,
capabilities, database ownership/head, documentation, and resolved resources.
Do not construct a separate standard registry or reread raw manifests in an
operation consumer.

## Bundled versus external packs

The bundled catalog is the fixed beta product set. Its default database
composition is derived from entries with `database.default_enabled: true`; the
Runaway pack is explicitly composable but disabled by default. External
capability packs can be discovered through the supported install/discovery
seams, but cannot contribute database migrations in beta.

Pack code executes with the user's process permissions. Permission and secret
fields disclose expected access; they are not a sandbox. Keep network, file,
subprocess, accelerator, and service declarations accurate.

## Agent guidance checklist

`skill/SKILL.md` should begin with structured front matter and explain:

- what the pack does and its normal entrypoints;
- when an agent should and should not use it;
- required inputs, outputs, permissions, and secrets;
- related pack skills and canonical capability ids;
- pack-relative runtime resources when relevant.

Never teach alternate manifest filenames, schema-less forms, fixed database
lists, or a second database authority. Historical design notes are not active
authoring instructions.
