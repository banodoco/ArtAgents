# Astrid B12 legacy-source authority forensic (2026-09-01)

## Decision

For the Stage1 B12 live migration, select
`/Users/peteromalley/Documents/reigh-workspace/.local/astrid-projects-extension-demo`
as the authoritative input tree.  Keep both candidate trees unchanged until a
fresh operator source-manifest and writer-stop receipt are issued.  This is a
source-selection decision, not evidence that B12 live activation has already
run.

## Evidence and exact comparison

The comparison was read-only: SQLite was opened in read-only mode, integrity
and foreign-key checks were observed, and file manifests were computed in
temporary space outside both trees.  No Astrid command that creates, migrates,
or rewrites either tree was run.

| measure | `Astrid/projects` (A) | `.local/astrid-projects-extension-demo` (B) | difference B-A |
|---|---:|---:|---:|
| regular files | 4,548 | 28,253 | +23,705 |
| regular-file bytes | 6,081,145,612 | 6,399,869,617 | +318,724,005 |
| SQLite bytes | 13,508,608 | 26,951,680 | +13,443,072 |
| SQLite SHA-256 | `04846473a6969f224316df5c77edb1e7f68ede5bdb71d7c66a6a47d7eee370c7` | `f6ba309adaf59020efd3bd2e442a2f2ee72658b6d2b5b5df89dc751d8ee41ea1` | different |
| projects | 18 | 19 | +1 |
| media / locations | 205 / 205 | 229 / 229 | +24 / +24 |
| timelines | 62 | 64 | +2 |
| generations / variants | 0 / 0 | 56 / 68 | +56 / +68 |
| runs | 567 | 567 | 0 |
| tasks | 70 | 82 | +12 |
| events | 2,684 | 3,149 | +465 |
| event streams | 922 | 961 | +39 |
| command receipts | 2,132 | 2,573 | +441 |
| task outputs | 142 | 166 | +24 |

Both databases report `quick_check=ok` and no foreign-key violations.  All 18
common project IDs, all 205 A media IDs, all 567 run IDs, all 70 A task rows,
all 2,684 A event rows, and all 205 A media-location rows occur in B.  B adds
the later `generations`/`generation_variants` schema and rows, one
`reigh-gallery-acceptance` project, 24 media objects, 12 tasks, 465 events,
and the corresponding receipts/outputs/streams.  The two B-only schema
migrations are `shots/2` and `timeline/2`, both applied 2026-08-27.

The common non-database files are byte-identical except for three `.DS_Store`
hashes (the root, `2rp-launch-video`, and `desert-plant-growth`).  A-only
content is 809 manifest entries / 800,947,680 regular bytes, chiefly
`astrid-intro` (678 entries / 666,712,536 bytes) and
`.astrid-intro-kernel` (130 entries).  B-only content is 24,514 manifest
entries / 1,106,228,613 regular bytes, chiefly
`h3-derope-video` (24,477 regular files / 895,430,743 bytes), plus
`reigh-gallery-acceptance` and two desert-plant-growth files.  A's root DB
has an `h3-derope-video` project row but A has no corresponding directory;
B has both the row and the output/run tree.  Conversely A's `astrid-intro`
tree is a separate nested source layout, not a root-DB project; its runbook
path is the explicit `normalize-nested-source` operation, not B12 root input.

The DB timestamps support B as the later complete state: A DB mtime is
2026-08-23 14:37:22 +0200; B DB mtime is 2026-08-28 02:27:16 +0200.  B's
additional migrations and post-2026-08-27 project/event heads account for the
new data.  Eight common project rows have advanced event heads (and
`music3-cybernetic` also changes its default timeline); this is a later
writer state, not a reason to merge the trees.

There are 62 overlapping timeline IDs.  The recorded overlap review identifies
two substantive document conflicts:
`01KYPVKMW5STB4W6FE05ED8242` and `xnsf53y25kay32ksjacttycqcr`.  In the
current databases all 62 common timeline rows also reflect the later
projection rewrite (notably path asset references becoming `media_id` and
`project_data_json` being projected as null).  Therefore the safe policy is
to select B as a whole and retain A separately; do not union or precedence-
guess timeline rows.

This selection is consistent with the latest convergence evidence: the Sol
sensecheck calls B the “Primary live-data candidate” and says not to infer
disposability from “demo”; the current Stage1 execution note says the real
extension corpus validates at 19 projects, 229 media, 64 timelines, 567 runs,
82 tasks, 3,149 events, and 4,363 owner records.  Older inventory notes called
B an unknown demo/test candidate.  The later exact overlap and lane-9 evidence
resolve that historical uncertainty, while still requiring a new immutable
input manifest at activation.

Evidence files: `/Users/peteromalley/Documents/reigh-workspace/.astrid-convergence/sol-astrid-beta-sensecheck.md`,
`/Users/peteromalley/Documents/reigh-workspace/.astrid-convergence/stage1-execution-current.md`,
`/Users/peteromalley/Documents/reigh-workspace/.oracle/briefs/phase-4-tasklist-sol.md`,
and the target worktree's
`.astrid-convergence/astrid-loose-thread-classification-20260830-v2.md`.
The command contract is
`banodoco-workspace-runtime-stage1-convergence/tools/astrid_migrate/runbook.md`
and its B12 operator implementation is
`banodoco-workspace-runtime-stage1-convergence/tools/astrid_migrate/operator.py`.

## Git, custody, and unresolved risk

Neither candidate is a versioned source tree.  A is data ignored by the dirty
`Astrid` worktree (`codex/live-ux-pre-phase-b-20260824`); B is untracked data
under the dirty umbrella checkout.  Git history therefore supplies no
authoritative content commit or writer ordering for either tree.  The
authority conclusion comes from DB identity/subset evidence, timestamps,
content relationships, and the cited Stage1 docs—not path, name, or size.

B has three escaping symlinks under
`h3-derope-video/runs/final/vo-work/vv-runtime/bin/` (`python3`, `python`, and
`python3.11`; the last targets `~/.local/share/uv/...`).  B12's boundary
checks reject escaping links.  Do not rewrite B in place: obtain a
symlink-safe, independently hashed snapshot only if the operator policy
allows it, then reissue the source manifest and authorizations.  B also has
pre-gallery SQLite backups and a `bridge-boot-secret`; evidence must not copy
secret contents into reports, and custody/permissions must be explicit.

The current filesystem has only 441,470,976 bytes available (`df -k`, 100%
capacity).  The older convergence note's approximately 16 GiB free reading
is stale.  This is an immediate capacity-gate failure, before any live action.

## Capacity and operator command

For B, `source_bytes S=6,399,869,617`, estimated CAS bytes
`C=1,922,677,060`, and an empty-destination estimate
`D=S+C=8,322,546,677`.  With the default B12 safety margin
`M=max(20%*S,10 GiB)=10,737,418,240` and the mandated minimum evidence
allowance `E=1,048,576`, the explicitly requested basic footprint
(source retained + source archive + destination + destination backup + CAS +
rollback active-root bytes `A` + margin + evidence) is:

```
42,105,976,464 + A bytes
```

The full B12 `live.py` preflight additionally reserves candidate and
reactivation copies.  Its filesystem reservation is:

```
50,428,523,141 + 2*A bytes
```

(`A` is the actual active realm-store size, not present in this workspace, so
these are lower bounds).  The full reservation is short by at least
49,987,052,165 bytes at the current free-space reading, even before the
unknown active realm backup.  Do not proceed until a capacity gate reports
the actual active-root size and sufficient verified free space.

After capacity, writer freeze, symlink policy, and fresh authorization gates
pass, the exact live operator shape is (placeholders are intentionally
operator-supplied):

```bash
astrid-live-migrate live-migrate --confirm 'MIGRATE LIVE ASTRID' \
  --source-root /Users/peteromalley/Documents/reigh-workspace/.local/astrid-projects-extension-demo \
  --active-root /absolute/Banodoco/runtime/realms/REALM_ID \
  --support-root /absolute/Banodoco/runtime \
  --archive-root /absolute/migration/source-archive \
  --destination-root /absolute/migration/destination \
  --evidence-root /absolute/migration/migration-evidence-b12 \
  --realm-id REALM_ID \
  --authorization-file /absolute/operator/b12-authorizations.json \
  --writer-stop-receipt /absolute/operator/writer-stop.json
```

The source path must be bound to the newly captured manifest; do not use the
dry-run template's `Astrid-live-main/projects` reference, do not combine A and
B, and do not use the nested `astrid-intro` normalization command for B12.
