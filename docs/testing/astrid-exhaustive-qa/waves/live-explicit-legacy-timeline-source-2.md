# Live explicit legacy timeline-source compatibility wave 2

Date: 2026-08-24  
Method: live public CLI compatibility-boundary replay  
Final verdict: **PASS after one P2 provenance fix**

## Goal

Prove that a caller can explicitly inspect a contained legacy filesystem
`assembly.jsonl` even when a divergent canonical kernel timeline has the same
display slug, without letting the filesystem representation shadow normal
kernel selection or mutate either authority.

## Disposable boundary and fixture provenance

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-legacy-boundary.QoFLzh/projects
project=boundary-lab
```

Product state was created only through the public CLI. For the explicitly
permitted legacy fixture setup, the repository's documented visualization
sample was copied byte-for-byte:

```text
source: tests/fixtures/timeline_visualize/desert_slice/
target: <project>/timelines/01KYPVKMW5STB4W6FE05ED8242/
files: assembly.identity.json, assembly.jsonl, assembly.json,
       assembly.head.json, display.json, registry.json, clips_tracks.json
assembly events: 159
```

No fixture content was rewritten. SHA-256 hashes of every copied file were
captured before interaction and compared again after all visualizations.

## Deliberate authority collision

The public CLI created a divergent canonical default timeline using the same
apparent slug as the fixture:

```bash
python3 -m astrid timelines create plant-growth-storyboard \
  --project boundary-lab --name 'Canonical Kernel Storyboard' --default \
  --config '<one canonical text clip>' --registry '{"assets":{}}' --json
```

Canonical identity/content:

```text
UUID: 34af4a64-e620-5562-8795-8cca5acdae02
ULID: K1T5FYW5BTWM90EP6GNPR5PN00
version: 1
clip: canonical-kernel-only
text: CANONICAL KERNEL AUTHORITY
```

Legacy identity/content:

```text
UUID: ed70ef66-43da-4182-9f14-69361c6c5e10
ULID: 01KYPVKMW5STB4W6FE05ED8242
event-head version: 159
clips: plant-frame-1 ... plant-frame-4, toccata-fugue
```

Both identities report slug `plant-growth-storyboard`, making UUID/ULID/head
provenance essential.

## Before-fix replay

Explicit legacy command:

```bash
python3 -m astrid timelines visualize --project boundary-lab \
  --timeline-source \
  '<project>/timelines/01KYPVKMW5STB4W6FE05ED8242/assembly.jsonl' \
  --format md --filmstrip off --json
```

The compatibility reader itself worked. Run `56d2e1cbc01691bb2c6fbdeb3d`
selected the legacy UUID/ULID, frozen head version 159, and legacy content.
However, the manifest incorrectly reported:

```json
"source_mode": "project"
```

That was ambiguous in precisely the dual-representation case being tested.
The historical `timeline_source:["boundary-lab"]` field also contains a
project slug rather than the explicit assembly locator, so it could not repair
the ambiguity by itself.

Severity: **P2 provenance/agent ergonomics**. Content selection was correct and
read-only, but an agent could not reliably tell which authority was frozen.

## Bounded correction

Leaf evidence manifests now propagate the actual selection boundary:

- `source_mode:"kernel"` for canonical current-state selection;
- `source_mode:"legacy"` only when explicit `timeline_source` was supplied;
- `source_mode:"frozen"` for navigation from a prior view.

`resolved_project` and `resolved_timelines` remain the exact identity record.
The old `source_mode:"project"` spelling stays accepted by the optional v1
schema field, and the historical `timeline_source` field is unchanged, so
existing frozen packs remain valid without byte rewriting.

The executor's public stage documentation now explains these values and says
the older field is compatibility-only.

## After-fix explicit legacy proof

A fresh request identity (`--layout linear`) avoided replaying the immutable
pre-fix output:

```bash
python3 -m astrid timelines visualize --project boundary-lab \
  --timeline-source \
  '<project>/timelines/01KYPVKMW5STB4W6FE05ED8242/assembly.jsonl' \
  --layout linear --format md --filmstrip off --json
```

Run: `3cdced609016543c2c4ae075a9`.

Manifest authority/provenance:

```json
{
  "source_mode": "legacy",
  "resolved_project": {
    "id": "b53a9e73-42ac-5eca-a9d8-d933980705ff",
    "slug": "boundary-lab"
  },
  "resolved_timelines": [{
    "qualified_ref": "TL01",
    "stable_id": "TL01",
    "uuid": "ed70ef66-43da-4182-9f14-69361c6c5e10",
    "ulid": "01KYPVKMW5STB4W6FE05ED8242",
    "slug": "plant-growth-storyboard"
  }]
}
```

Frozen event head:

```json
{
  "version": 159,
  "last_event_id": "01KZS6CCD73SYEC924B5XR12XG",
  "last_hash": "6f6de92702ef683d44b6bd52da32383f34488ea44db4113cadf95ec60ef8535d"
}
```

Ground truth contained the legacy plant-frame clips, not the canonical text
clip. An identical explicit request returned the same run, task, attempt, and
durable manifest, proving exact replay retained the corrected provenance.

## Kernel precedence with no flag

The same public command without `--timeline-source` was then run:

```bash
python3 -m astrid timelines visualize --project boundary-lab \
  --layout linear --format md --filmstrip off --json
```

Run: `8b829f3aadb61c9ef4623541d5`.

It selected only the canonical default:

```json
{
  "source_mode": "kernel",
  "resolved_timelines": [{
    "uuid": "34af4a64-e620-5562-8795-8cca5acdae02",
    "ulid": "K1T5FYW5BTWM90EP6GNPR5PN00",
    "slug": "plant-growth-storyboard"
  }]
}
```

Its event head was canonical version 1 and ground truth contained exactly
`canonical-kernel-only` / `CANONICAL KERNEL AUTHORITY`. The co-located legacy
directory never participated in selector-free/default resolution.

## Read-only and mutation evidence

Before and after explicit legacy visualization plus selector-free kernel
visualization:

```text
timelines show data equal: true
timelines history data equal: true
timelines diff data equal: true
kernel config version: 1 -> 1
kernel history: [(1, timeline.created)] -> unchanged
legacy file SHA-256 set: byte-identical
```

Thus visualization added ordinary run/task ledger records but appended no
canonical timeline events, changed no canonical projection, and wrote no
legacy timeline file.

## Foreign source rejection

The same fixture was copied outside the owning project and supplied explicitly:

```bash
python3 -m astrid timelines visualize --project boundary-lab \
  --timeline-source '/tmp/.../foreign-desert-slice/assembly.jsonl' \
  --layout linear --format md --filmstrip off --json
```

It failed with exit 1:

```text
timeline input is not owned by project 'boundary-lab':
/private/tmp/astrid-legacy-boundary.QoFLzh/foreign-desert-slice/assembly.jsonl
```

All run/task/attempt IDs were null, and public run count stayed **4 -> 4**.
Ownership rejection therefore occurs before admission.

## Narrow verification

```text
29 focused visualization manifest/schema checks passed
```

The added guard proves an explicitly supplied `legacy` mode is serialized and
schema-valid. Existing v1 packs with absent mode or the earlier `project` value
remain accepted.

## Agent friction verdict

After the correction, the boundary is intuitive and safe:

- the explicit flag is required to opt into filesystem authority;
- the resulting pack says `legacy` and pins the exact UUID/ULID/head;
- omitting the flag deterministically means canonical kernel authority;
- the reader is non-mutating on both sides;
- an outside-project path fails before ledger admission.

Remaining low-level quirk: `timeline_source:[project_slug]` is historically
misnamed, but it is frozen compatibility data. The additive authority and
resolved-identity fields now provide the unambiguous surface without breaking
old evidence packs.

