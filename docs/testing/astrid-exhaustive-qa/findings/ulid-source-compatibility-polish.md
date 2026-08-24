# ULID and timeline-source compatibility polish

Date: 2026-08-24 (Europe/Berlin)  
Severity: **P3 agent ergonomics / provenance presentation**  
Status: **fixed and live-replayed**  
Disposable live root: `/private/tmp/astrid-ulid-source-polish.HYSdPr`

## Outcome

Astrid now gives agents an exact, comparison-safe timeline identity without
rewriting the immutable timeline-visualize v1 identity fields:

- public kernel timeline `create`, `list`, and `show` keep their canonical
  lowercase Crockford ULID spelling;
- existing `resolved_timelines` and snapshot identity ULIDs stay uppercase as
  required by the frozen v1 visualization schema;
- every newly emitted manifest adds optional
  `inputs.canonical_timeline_identities`, with the same UUID, slug, stable ref,
  and qualified ref but a lowercase ULID matching the public kernel DTO;
- an old frozen manifest that lacks the additive field remains valid and can
  be navigated; the child preserves the old identity and adds the comparison
  projection;
- public help and manifest documentation now distinguish the explicit
  CLI/SDK `timeline_source` path from the historical manifest
  `inputs.timeline_source:[project_slug]` compatibility field.

No existing field was removed or silently normalized.

## Original live friction

The preceding explicit-legacy boundary replay found two correct-but-confusing
public representations.

First, a canonical kernel timeline returned a lowercase ULID from
`timelines create/show` while the evidence manifest returned its uppercase
equivalent:

```text
CLI show:                       xsnbgyph3wcejnvq9tdhsgny4k
manifest resolved/snapshot:    XSNBGYPH3WCEJNVQ9TDHSGNY4K
```

ULIDs are case-insensitive, but a normal agent string comparison reports these
as different identities. Simply lowercasing `resolved_timelines` or snapshot
fields was not safe: timeline-visualize v1 schemas require uppercase ULIDs,
and immutable frozen packs already use that spelling.

Second, the manifest field named `timeline_source` is not the raw explicit
legacy source path. It is frozen v1 compatibility data containing the project
slug:

```json
"timeline_source": ["boundary-lab"]
```

The corrected `source_mode`, `resolved_project`, and `resolved_timelines`
fields already make authority precise, but `timelines visualize --help` did
not warn agents that the identically named input and emitted compatibility
field have different meanings.

## Chosen compatibility contract

The kernel's source documentation and live DTOs establish lowercase as the
canonical user-facing v10 ULID spelling. Frozen visualization v1 establishes
uppercase as its immutable schema spelling. The fix represents both rather
than choosing one by mutation.

New manifests carry:

```json
{
  "inputs": {
    "source_mode": "kernel",
    "timeline_source": ["identity-lab"],
    "resolved_timelines": [{
      "stable_id": "TL01",
      "qualified_ref": "TL01",
      "uuid": "ff9d0db9-d5ec-5e17-aaef-ed1bd3b87e56",
      "ulid": "8JWSZ5EVE9SC4HP7046TKK5ZWP",
      "slug": "plant-growth-storyboard"
    }],
    "canonical_timeline_identities": [{
      "stable_id": "TL01",
      "qualified_ref": "TL01",
      "uuid": "ff9d0db9-d5ec-5e17-aaef-ed1bd3b87e56",
      "ulid": "8jwsz5eve9sc4hp7046tkk5zwp",
      "slug": "plant-growth-storyboard"
    }]
  }
}
```

Agent comparison rule:

1. Use `source_mode` to identify `kernel`, explicit `legacy`, or `frozen`
   authority.
2. Use `canonical_timeline_identities` when comparing a new manifest with
   public kernel CLI/SDK DTOs.
3. For an older manifest lacking that optional field, compare UUID exactly
   and ULID case-insensitively.
4. Never infer the raw legacy path or source authority from the compatibility
   `inputs.timeline_source` field.

## Implementation

### Additive identity projection

`evidence_pack.py` now derives `canonical_timeline_identities` from the exact
frozen timeline identity and lowercases only the copied ULID. The source
snapshot and `resolved_timelines` are untouched.

The manifest schema adds this field as optional. A dedicated closed shared
definition enforces:

- lowercase 26-character Crockford base32 ULID;
- exact lowercase UUID shape;
- the same stable/qualified timeline refs and slug shape.

The existing uppercase `$defs.ulid` description now explicitly calls out the
frozen-v1 compatibility spelling. A separate `kernel_ulid` definition names
the lowercase user-facing form.

### Help and docs

`astrid timelines visualize --help` now renders:

```text
--timeline-source TIMELINE_SOURCE
    Explicit legacy managed timeline directory/file; repeat for multiple
    sources. In result manifests, inputs.timeline_source remains a project-slug
    compatibility field; inspect source_mode and resolved identities for
    authority/provenance.
```

The executor input description, `STAGE.md`, manifest schema descriptions, and
the agent-navigation architecture reference repeat this distinction and
document the ULID comparison rule. The historical field remains present.

## Fresh live replay

### Setup

```bash
polish_root=$(mktemp -d /private/tmp/astrid-ulid-source-polish.XXXXXX)
ASTRID_PROJECTS_ROOT="$polish_root" \
python3 -m astrid projects create identity-lab \
  --name 'Identity Lab' --json

mkdir -p \
  "$polish_root/identity-lab/timelines/01KYPVKMW5STB4W6FE05ED8242"
cp -R tests/fixtures/timeline_visualize/desert_slice/. \
  "$polish_root/identity-lab/timelines/01KYPVKMW5STB4W6FE05ED8242/"

ASTRID_PROJECTS_ROOT="$polish_root" \
python3 -m astrid timelines create plant-growth-storyboard \
  --project identity-lab --name 'Kernel Identity' --default \
  --config '<one kernel-only text clip>' \
  --registry '{"assets":{}}' --json
```

Canonical kernel identity:

```text
UUID: ff9d0db9-d5ec-5e17-aaef-ed1bd3b87e56
ULID: 8jwsz5eve9sc4hp7046tkk5zwp
```

### Kernel create/list/show spelling

Exact reads:

```bash
python3 -m astrid timelines show plant-growth-storyboard \
  --project identity-lab --json
python3 -m astrid timelines list --project identity-lab --json
```

`create`, `show`, and `list` all returned exactly:

```text
8jwsz5eve9sc4hp7046tkk5zwp
```

The values were byte-equal, establishing lowercase as the stable public
kernel spelling.

### Canonical kernel visualization

```bash
python3 -m astrid timelines visualize \
  --project identity-lab \
  --timeline-slug plant-growth-storyboard \
  --layout linear --format md --filmstrip off --json
```

Run `991530062ec36233e1b2ca0e75` succeeded. Its manifest proved:

```text
source_mode:                         kernel
CLI/show ULID:                       8jwsz5eve9sc4hp7046tkk5zwp
canonical_timeline_identities ULID:  8jwsz5eve9sc4hp7046tkk5zwp
resolved_timelines ULID:             8JWSZ5EVE9SC4HP7046TKK5ZWP
snapshot timeline ULID:              8JWSZ5EVE9SC4HP7046TKK5ZWP
canonical field equals CLI:          true
```

Thus the new comparison surface is exact while the frozen fields retain their
required bytes.

### Explicit legacy visualization

```bash
python3 -m astrid timelines visualize \
  --project identity-lab \
  --timeline-source \
  "$polish_root/identity-lab/timelines/01KYPVKMW5STB4W6FE05ED8242/assembly.jsonl" \
  --layout linear --format md --filmstrip off --json
```

Run `a2c61945e8435e69fdf84e847f` succeeded:

```text
source_mode:                         legacy
resolved/snapshot ULID:              01KYPVKMW5STB4W6FE05ED8242
canonical_timeline_identities ULID:  01kypvkmw5stb4w6fe05ed8242
timeline_source compatibility value: ["identity-lab"]
```

The raw explicit locator is intentionally not copied into the immutable v1
compatibility field. Authority and exact identity remain unambiguous through
`source_mode` and the resolved fields.

### Frozen navigation

The legacy manifest was navigated through the public CLI:

```bash
python3 -m astrid timelines visualize \
  --project identity-lab --from-view '<legacy durable manifest>' \
  --focus TL01 --layout linear --format md --filmstrip off --json
```

Run `1e208eb113cfde1b3f693d30d6` succeeded:

```text
source_mode:                         frozen
parent uppercase identity preserved: true
canonical_timeline_identities ULID:  01kypvkmw5stb4w6fe05ed8242
```

No frozen identity was normalized in place.

## Pre-change frozen-pack compatibility proof

The public CLI also navigated the real durable legacy manifest created by the
preceding replay before this field existed:

```text
/private/tmp/astrid-legacy-source-replay-3.F8E0Cz/.astrid/media/sha256/
0a/c2/0ac2808914919bfe88b3f9c285ced3bafd6aca8d832adaec09559f095e76809e
```

No manifest bytes were edited. The parent had no
`canonical_timeline_identities` field. Current public `--from-view` accepted
it and succeeded as run `2cccf8ef5feb0a1a32eb723d68`:

```json
{
  "parent_has_additive_field": false,
  "replay_succeeded": true,
  "identity_preserved": true,
  "child_has_additive_field": true
}
```

This demonstrates real old-pack read compatibility, not merely schema
compatibility.

## Focused guards

```bash
pytest -q \
  tests/packs/rendering/test_timeline_visualize_pack.py \
  tests/core/timeline/test_timeline_visualize_schemas.py \
  tests/v10/test_domain_cli_projects_timelines.py \
  -k 'timeline_visualize or visualize_help'
```

Result:

```text
40 passed, 74 deselected in 54.11s
```

The guards prove:

- new packs publish the lowercase comparison identity;
- the schema rejects uppercase ULIDs in the additive user-facing field;
- the legacy optional-field omission still validates;
- old uppercase resolved/snapshot identities remain valid;
- CLI help retains the explicit-input/compatibility-field warning.

`git diff --check` also passed for every touched source, schema, documentation,
and guard file.

## Final agent-UX verdict

**PASS.** The product no longer asks agents to remember an undocumented ULID
case-normalization rule or guess what `timeline_source` means in a manifest.
The safe compatibility choice is additive: lowercase is the canonical public
comparison spelling, uppercase frozen identities remain immutable, and the
old project-slug compatibility field stays readable without being mistaken
for source authority.
