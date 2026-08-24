# Replay: ULID and timeline-source compatibility (live agent UX)

Date: 2026-08-24 (Europe/Berlin)  
Method: black-box public `python3 -m astrid` CLI plus durable visualization
manifests; no source, tests, or product edits  
Fresh disposable projects root: `/private/tmp/astrid-ulid-source-fpw7Wc`  
Verdict: **PASS — lowercase canonical identity, uppercase frozen-v1
compatibility identity, and source authority remain distinct and navigable.**

## Acceptance summary

| Contract | Result |
| --- | --- |
| Fresh `create`, `list`, and `show` expose one byte-equal lowercase ULID | Pass |
| Kernel visualization adds exact lowercase canonical identity | Pass |
| Existing `resolved_timelines` and snapshot ULIDs stay uppercase | Pass |
| Explicit legacy visualization identifies `source_mode: legacy` | Pass |
| Explicit legacy canonical identity is lowercase and exact | Pass |
| Frozen navigation identifies `source_mode: frozen` and preserves parent identity | Pass |
| Real pre-change manifest without additive field remains navigable | Pass |
| Public help distinguishes explicit source path from emitted compatibility field | Pass |

## Fresh kernel identity replay

I created project `ulid-demo` and timeline `compat` through the public CLI. The
timeline create response returned:

```text
UUID: 81a97651-7e86-56bc-8ab0-34cfd97f4240
ULID: 8w4cqy3m9q8anefy1gy6fkynmy
```

`timelines list --project ulid-demo --json` and both slug and ULID forms of
`timelines show` returned the same lowercase ULID byte-for-byte. This is the
agent-facing identity; it did not require case normalization or a UUID lookup.

The project-scoped visualization succeeded as run
`d9350d4d2d1b8979057d22111b` and published the durable manifest:

```text
/private/tmp/astrid-ulid-source-fpw7Wc/.astrid/media/sha256/dd/b1/
ddb1d82fccd76d939153493c6a4f193ea43cd8eaadf5d8a2b1f7485ba06d05c7
```

The manifest’s identity projections were:

```text
inputs.source_mode:                                kernel
inputs.canonical_timeline_identities[0].ulid:      8w4cqy3m9q8anefy1gy6fkynmy
inputs.resolved_timelines[0].ulid:                 8W4CQY3M9Q8ANEFY1GY6FKYNMY
snapshots[0].timeline.ulid:                        8W4CQY3M9Q8ANEFY1GY6FKYNMY
```

The canonical field equals the CLI value exactly. The two established
visualization-v1 fields remain uppercase, and their UUID, slug, `TL01`, and
qualified reference are unchanged. No compatibility field was normalized in
place.

## Explicit legacy source

To exercise the public legacy path boundary in the fresh project, I copied the
documented `tests/fixtures/timeline_visualize/desert_slice` fixture unchanged
into the disposable project’s managed `timelines/` directory. This is test
data setup only; the fixture and product were not edited. The explicit command
was:

```bash
ASTRID_PROJECTS_ROOT=/private/tmp/astrid-ulid-source-fpw7Wc \
python3 -m astrid timelines visualize --project ulid-demo \
  --timeline-source \
  /private/tmp/astrid-ulid-source-fpw7Wc/ulid-demo/timelines/01KYPVKMW5STB4W6FE05ED8242/assembly.jsonl \
  --format md --filmstrip off --json
```

It succeeded as run `3c0dbee9453c7641e148eac70b` and published:

```text
/private/tmp/astrid-ulid-source-fpw7Wc/.astrid/media/sha256/6b/5e/
6b5e51ff9a7fe35bf2500ee147602357c5067177a21b7e85801d1308a66c9a35
```

The manifest proved that the raw CLI path is not silently copied into the
historical `timeline_source` field:

```text
inputs.source_mode:                                legacy
inputs.timeline_source:                             ["ulid-demo"]
inputs.canonical_timeline_identities[0].ulid:      01kypvkmw5stb4w6fe05ed8242
inputs.resolved_timelines[0].ulid:                 01KYPVKMW5STB4W6FE05ED8242
snapshots[0].timeline.ulid:                        01KYPVKMW5STB4W6FE05ED8242
```

Thus the authority is explicit (`source_mode`), the project-slug compatibility
value remains readable, and the new lowercase identity is an exact comparison
surface. The old uppercase identity remains immutable.

## Frozen navigation

I navigated both fresh manifests with `--from-view ... --focus TL01`.

The kernel child succeeded as run `8be092837188a60b37de2ae356` and retained:

```text
source_mode: frozen
canonical ULID: 8w4cqy3m9q8anefy1gy6fkynmy
compatibility ULID: 8W4CQY3M9Q8ANEFY1GY6FKYNMY
```

The explicit-legacy child succeeded as run `5460153d9055d7fcdbb2fc3e3e` and
retained:

```text
source_mode: frozen
canonical ULID: 01kypvkmw5stb4w6fe05ed8242
compatibility ULID: 01KYPVKMW5STB4W6FE05ED8242
```

Both children preserved the parent `from_view` path and the parent’s UUID,
slug, stable reference, qualified reference, and snapshot identity. Frozen
navigation did not re-resolve the source as a new kernel timeline or rewrite
the parent manifest.

## Pre-change manifest compatibility

I replayed a real durable manifest from the earlier explicit-legacy wave, not a
hand-edited synthetic JSON object:

```text
/private/tmp/astrid-legacy-source-replay-3.F8E0Cz/.astrid/media/sha256/0a/c2/
0ac2808914919bfe88b3f9c285ced3bafd6aca8d832adaec09559f095e76809e
```

Before and after replay, the parent had no
`inputs.canonical_timeline_identities` field, retained
`source_mode: legacy`, and retained uppercase
`01KYPVKMW5STB4W6FE05ED8242`. Public frozen navigation accepted it with:

```bash
ASTRID_PROJECTS_ROOT=/private/tmp/astrid-legacy-source-replay-3.F8E0Cz \
python3 -m astrid timelines visualize --project boundary-lab \
  --from-view '<old manifest above>' --focus TL01 \
  --format md --filmstrip off --json
```

The command exited 0 as run `9ecda8c9267d32747e6aede109`; the child added the
lowercase canonical projection while preserving the old uppercase identity.
This demonstrates optional-field read compatibility on a real pre-change pack.

## Help and agent friction

`timelines visualize --help` explicitly describes `--timeline-source` as an
“Explicit legacy managed timeline directory/file” and separately says that in
result manifests `inputs.timeline_source` remains a project-slug compatibility
field; it directs the agent to `source_mode` and resolved identities for
authority/provenance. `--from-view` is separately described as a prior
visualization manifest for frozen navigation.

The only remaining minor friction is that agents must inspect the durable
manifest to see the exact lowercase/uppercase pair; the CLI intentionally does
not duplicate all provenance projections in its short envelope. This is
appropriate for an evidence-producing command and is documented by help.

## Final verdict

**PASS, 9.8/10.** No P0, P1, or P2 defect was found. The compatibility surface
is additive and safe: lowercase ULIDs match kernel create/list/show output,
uppercase v1 fields remain byte-stable, explicit legacy versus kernel versus
frozen authority is explicit, and old manifests without the new field remain
usable.
