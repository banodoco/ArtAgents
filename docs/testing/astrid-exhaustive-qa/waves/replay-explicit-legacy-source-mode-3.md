# Replay 3: explicit legacy timeline-source provenance boundary

Date: 2026-08-24 (Europe/Berlin)  
Method: black-box live agent UX through the public `python3 -m astrid` CLI,
plus the explicitly permitted byte-for-byte copy of the documented legacy
fixture; no SDK calls, source inspection, tests, database edits, fixture edits,
or product changes  
Disposable projects root:
`/private/tmp/astrid-legacy-source-replay-3.F8E0Cz`  
Verdict: **PASS — explicit legacy, implicit kernel, and frozen-view authority
are distinct, correctly identified, immutable, and ownership-fenced.**

## Acceptance summary

| Contract | Result |
| --- | --- |
| Divergent canonical timeline and legacy assembly may share one slug | Pass |
| Explicit `--timeline-source` selects only the legacy assembly | Pass |
| Explicit result declares `source_mode:"legacy"` | Pass |
| Explicit result pins exact legacy UUID, ULID, and version-159 head | Pass |
| Omitting `--timeline-source` selects only the canonical timeline | Pass |
| Canonical result declares `source_mode:"kernel"` | Pass |
| Canonical result pins canonical UUID and version-1 head | Pass |
| `--from-view` without refresh declares `source_mode:"frozen"` | Pass |
| Frozen navigation retains the original legacy identity and snapshot | Pass |
| Canonical `show` and `history` data remain unchanged | Pass |
| All seven legacy fixture files remain byte-identical | Pass |
| Outside-project legacy source is rejected before admission | Pass |

## 1. Fresh boundary and deliberate same-slug divergence

The project was created through the public CLI:

```bash
legacy_root=$(mktemp -d /private/tmp/astrid-legacy-source-replay-3.XXXXXX)
ASTRID_PROJECTS_ROOT="$legacy_root" \
python3 -m astrid projects create boundary-lab \
  --name 'Legacy Boundary Lab' --json
```

The returned project identity was:

```text
project slug: boundary-lab
project id:   deaba6f3-fe5d-5067-9d2e-151e9c2c2aba
project path: /private/tmp/astrid-legacy-source-replay-3.F8E0Cz/boundary-lab
```

The documented fixture was copied without changing its contents:

```bash
mkdir -p \
  "$legacy_root/boundary-lab/timelines/01KYPVKMW5STB4W6FE05ED8242"
cp -R tests/fixtures/timeline_visualize/desert_slice/. \
  "$legacy_root/boundary-lab/timelines/01KYPVKMW5STB4W6FE05ED8242/"
```

Its legacy identity is:

```text
slug:          plant-growth-storyboard
UUID:          ed70ef66-43da-4182-9f14-69361c6c5e10
ULID:          01KYPVKMW5STB4W6FE05ED8242
head version:  159
last event:    01KZS6CCD73SYEC924B5XR12XG
last hash:     6f6de92702ef683d44b6bd52da32383f34488ea44db4113cadf95ec60ef8535d
clips:         plant-frame-1, plant-frame-2, plant-frame-3,
               plant-frame-4, toccata-fugue
```

A deliberately different canonical timeline was then created under the same
slug using only the public timeline command:

```bash
ASTRID_PROJECTS_ROOT="$legacy_root" \
python3 -m astrid timelines create plant-growth-storyboard \
  --project boundary-lab --name 'Canonical Kernel Storyboard' --default \
  --config '{"theme_overrides":{"visual":{"canvas":{"width":640,"height":360,"fps":30}}},"tracks":[{"id":"canonical-track","kind":"visual","label":"Canonical"}],"clips":[{"id":"canonical-kernel-only","at":0,"track":"canonical-track","clipType":"text","hold":2,"text":{"content":"CANONICAL KERNEL AUTHORITY","fontSize":48,"color":"#ffffff","align":"center"}}]}' \
  --registry '{"assets":{}}' --json
```

Canonical identity/content:

```text
UUID:           3e6d52bd-ffd7-54af-bb81-749c127f752b
ULID from show: xsnbgyph3wcejnvq9tdhsgny4k
config version: 1
clip:           canonical-kernel-only
text:           CANONICAL KERNEL AUTHORITY
```

Before visualization, `timelines history` contained exactly one
`timeline.created` event at version 1 and `runs list` was empty.

## 2. Explicit legacy selection

Exact live command:

```bash
ASTRID_PROJECTS_ROOT="$legacy_root" \
python3 -m astrid timelines visualize \
  --project boundary-lab \
  --timeline-source \
  "$legacy_root/boundary-lab/timelines/01KYPVKMW5STB4W6FE05ED8242/assembly.jsonl" \
  --layout linear --format md --filmstrip off --json
```

The command succeeded and admitted one normal visualization run:

```text
run:      dc4b7e4e3ccdde76cd28c63060
task:     765fb0e205371a9b0c1b1f9bf7
attempt:  01m0sr9175wds3244t4nfc0tc3
manifest content hash:
          0ac2808914919bfe88b3f9c285ced3bafd6aca8d832adaec09559f095e76809e
```

The durable public manifest recorded the authority boundary and exact legacy
identity:

```json
{
  "source_mode": "legacy",
  "resolved_project": {
    "id": "deaba6f3-fe5d-5067-9d2e-151e9c2c2aba",
    "slug": "boundary-lab"
  },
  "resolved_timelines": [{
    "qualified_ref": "TL01",
    "stable_id": "TL01",
    "slug": "plant-growth-storyboard",
    "ulid": "01KYPVKMW5STB4W6FE05ED8242",
    "uuid": "ed70ef66-43da-4182-9f14-69361c6c5e10"
  }]
}
```

The diagnostics snapshot pinned the legacy event head exactly:

```json
{
  "digest": "SNS:2d9f0100d9658e1204561e3d298032ac156c7a85c1fcaaa9cc6165bcc611f4b6",
  "event_head": {
    "last_event_id": "01KZS6CCD73SYEC924B5XR12XG",
    "last_hash": "6f6de92702ef683d44b6bd52da32383f34488ea44db4113cadf95ec60ef8535d",
    "version": 159
  }
}
```

`ground-truth.json` contained the five fixture clips and legacy timeline UUID.
It did not contain `canonical-kernel-only`. The five media-missing diagnostics
are expected for this assembly-only repository fixture; they do not affect the
authority proof.

## 3. Kernel selection when `--timeline-source` is omitted

Exact live command:

```bash
ASTRID_PROJECTS_ROOT="$legacy_root" \
python3 -m astrid timelines visualize \
  --project boundary-lab \
  --timeline-slug plant-growth-storyboard \
  --layout linear --format md --filmstrip off --json
```

This command deliberately supplied the canonical slug selector but no legacy
source flag. It succeeded as run `3f78d2b7aab82eb50246a7b779` and emitted
manifest hash
`53de4e68c674c07501ccfabe33a11838a60df39a785fe334f95462be2f3866bd`.

Manifest provenance was canonical:

```json
{
  "source_mode": "kernel",
  "resolved_timelines": [{
    "qualified_ref": "TL01",
    "stable_id": "TL01",
    "slug": "plant-growth-storyboard",
    "ulid": "XSNBGYPH3WCEJNVQ9TDHSGNY4K",
    "uuid": "3e6d52bd-ffd7-54af-bb81-749c127f752b"
  }]
}
```

The diagnostics snapshot pinned canonical version 1:

```json
{
  "digest": "SNS:7f5e47a38dc4e0260a832cce15e88d965d1c443bc9c1e30e7f2bb6ce74bf7050",
  "event_head": {
    "last_event_id": "6T73SYXC8VJ3272PPTPZ7V1VJD",
    "last_hash": "9558820303dbeebfba927e1244d0af3673e0b6045a8cd50b6e65f6e4e3ddbd59",
    "version": 1
  }
}
```

`ground-truth.json` contained exactly one clip,
`canonical-kernel-only`, with text `CANONICAL KERNEL AUTHORITY`. It contained
none of the legacy fixture clips. Therefore a co-located legacy directory does
not shadow slug-based canonical resolution; explicit `--timeline-source` is
the only opt-in to that compatibility authority.

## 4. Frozen navigation preserves the selected snapshot

The explicit legacy manifest was navigated without requesting a root refresh:

```bash
ASTRID_PROJECTS_ROOT="$legacy_root" \
python3 -m astrid timelines visualize \
  --project boundary-lab \
  --from-view \
  "$legacy_root/.astrid/media/sha256/0a/c2/0ac2808914919bfe88b3f9c285ced3bafd6aca8d832adaec09559f095e76809e" \
  --focus TL01 --layout linear --format md --filmstrip off --json
```

Run `40430685492f861634d95d415a` succeeded. Its manifest declared:

```json
{
  "source_mode": "frozen",
  "focus": "TL01",
  "resolved_timelines": [{
    "slug": "plant-growth-storyboard",
    "ulid": "01KYPVKMW5STB4W6FE05ED8242",
    "uuid": "ed70ef66-43da-4182-9f14-69361c6c5e10"
  }]
}
```

The frozen view reused the exact legacy SNS digest, version-159 event head,
ground-truth content hash, and five legacy clips. It did not silently resolve
the matching slug against current kernel state. This is the desired
reproducibility contract for follow-up navigation.

## 5. Outside-project source is rejected before admission

The same documented fixture was copied to
`$legacy_root/foreign-desert-slice`, which is under the disposable root but
outside the selected project's owned tree. Immediately before the negative
request, public `runs list` contained the three successful runs above.

Exact negative command:

```bash
ASTRID_PROJECTS_ROOT="$legacy_root" \
python3 -m astrid timelines visualize \
  --project boundary-lab \
  --timeline-source \
  "$legacy_root/foreign-desert-slice/assembly.jsonl" \
  --layout linear --format md --filmstrip off --json
```

It exited 1 with this stable JSON error:

```json
{
  "data": null,
  "error": {
    "code": "validation_error",
    "message": "timeline input is not owned by project 'boundary-lab': /private/tmp/astrid-legacy-source-replay-3.F8E0Cz/foreign-desert-slice/assembly.jsonl",
    "details": {
      "kernel_attempt_id": null,
      "kernel_run_id": null,
      "kernel_task_id": null,
      "run_id": null,
      "sdk_category": "validation",
      "sdk_error": "CapabilityValidationError"
    }
  },
  "ok": false,
  "receipt": null
}
```

Public run count remained **3 -> 3**. The rejection therefore happens before
run/task/attempt admission and gives an agent both the violated ownership
rule and the offending locator.

## 6. Read-only and byte-immutability proof

Canonical state was captured before the first visualization and after the
negative request using:

```bash
python3 -m astrid timelines show plant-growth-storyboard \
  --project boundary-lab --json
python3 -m astrid timelines history plant-growth-storyboard \
  --project boundary-lab --json
```

Semantic comparison of each JSON envelope's `data` yielded:

```json
{
  "show_data_equal": true,
  "history_data_equal": true
}
```

The canonical config remained version 1, and history remained the single
version-1 `timeline.created` event. Visualization created only the expected
run/task ledger activity.

The contained legacy fixture was hashed before any visualization and after
all positive and negative requests. Both sets were exactly:

```text
08362412733da920015fcb46b5021c6778dea996d6bfa4f8f4787b02da64a699  assembly.head.json
8815268081bb7c3198cd2d480a40c6e6c4cabaa3d1bd09746cf9b5ba720930f9  assembly.identity.json
fc76778abfc8e27f78e1c3bc1db2bd48919640237696c84f512d26acb4acd45b  assembly.json
33584544030ee4e0de3e10b775294e1edcacbc8822096915dfc93f7a3c1a6611  assembly.jsonl
c603d8c51b715703f8683c0c57f3ebd5a11565031b9dfee6819ed36d90015f21  clips_tracks.json
eb5c1a0a483401dbaeee50b787fec027a851c6bfb32d92d42ed0d94d67350721  display.json
403e411ac4e63e27bece56407525a61feb62171aa13920dfa484babf6309c51c  registry.json
```

Byte comparison returned `fixture_hashes_equal: true`.

## Provenance and agent-UX assessment

The authority contract is now sound and discoverable in the durable output:

- `legacy` means the caller explicitly opted into a contained assembly;
- `kernel` means Astrid resolved current canonical timeline state;
- `frozen` means Astrid navigated immutable evidence from a prior view;
- `resolved_project`, `resolved_timelines`, the SNS digest, and the event head
  are the authoritative identity/version record;
- filesystem authority cannot win accidentally merely because its slug
  matches a canonical timeline;
- foreign paths fail before admission.

Two low-severity presentation quirks remain:

1. **P3, compatibility naming:** every manifest still reports
   `timeline_source:["boundary-lab"]`. This historical field contains the
   project slug, not the explicit assembly locator, and is therefore
   misleading when read alone. `source_mode` plus `resolved_timelines` fully
   disambiguates the result, so this is not a correctness issue.
2. **P3, ULID normalization:** `timelines create/show` rendered the canonical
   ULID in lowercase (`xsnb...`), while visualization normalized the same ULID
   to uppercase (`XSNB...`). ULIDs are case-insensitive and the UUID matches
   exactly, but agents doing naive string equality may interpret this as an
   identity mismatch.

## Recommended durable contract

Keep the current explicit authority rules as normative:

1. No legacy filesystem lookup without explicit `--timeline-source`.
2. `source_mode` must always describe the actual materialization boundary:
   `legacy`, `kernel`, or `frozen`.
3. Every evidence pack must carry normalized resolved UUID/ULID plus the
   exact event head and SNS digest; downstream agents should compare those
   fields rather than the compatibility `timeline_source` field.
4. Frozen navigation must retain the prior snapshot unless a caller
   explicitly requests refresh.
5. Ownership validation must remain pre-admission with null kernel IDs.

For future additive polish, either deprecate/rename the compatibility
`timeline_source` field in a new manifest schema or document it adjacent to
every public example, and normalize ULID casing consistently across public
CLI and manifest surfaces.
