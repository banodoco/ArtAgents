# Live agent UX: canonical versus managed timeline authority

Date: 2026-08-24  
Tester: fresh Luna sub-agent  
Method: live public CLI/SDK usage only; no source inspection, database edits,
hand-authored timeline files, or programmatic test suite  
Disposable root: `/private/tmp/astrid-live-dual-timeline.tLk6c5`

## Executive conclusion

The public maker path has one coherent canonical CRUD authority: the kernel
timeline selected by slug, UUID, or ULID. `create`, `save`, `show`, `history`,
`diff`, `archive`, and `unarchive` agreed on its identity and ordered version
history.

However, the complete timeline UX is not yet one authority boundary:

1. A current-state visualization request is cached without the resolved
   timeline version/event head. After saving version 2, and again after an
   archive/unarchive cycle raised the canonical version to 4, the unchanged
   CLI/SDK request returned the old version-1 visualization run with `ok:true`.
2. A visualization of a kernel timeline manufactures a private legacy-style
   event head whose identity changes on every invocation. The snapshot digest
   therefore changes when only the requested presentation format changes.
   That event head is not the canonical timeline history/version.
3. The returned visualization manifest is published only as a root-level
   managed-media CAS locator, while `from_view` requires a path contained by
   the project root. A maker cannot use the successful public result for the
   documented frozen navigation flow.
4. `rendering.render` is file-input-only. It cannot resolve the canonical
   timeline slug/UUID/ULID and does not expose a canonical version pin. Passing
   `timeline="main"` is treated as a checkout-relative filesystem path and
   fails ownership validation after a run has already been admitted.
5. The requested dual-representation collision could not be created through
   documented/public Astrid surfaces. Canonical timeline creation produced no
   project `timelines/` directory. `--timeline-source` is a legacy reader, but
   there is no public managed-timeline writer or canonical export operation.
   I did not hand-create JSON/event logs because that would invalidate this
   live agent-UX test.

This means the safe answer to “where do timeline changes route?” is currently:
canonical CRUD routes through the kernel history, canonical visualization
starts from the kernel row but converts it to an unstable private event-log
projection, and rendering bypasses canonical timeline identity entirely in
favor of a caller-supplied file.

## Journey and exact evidence

### 1. Discover the public surface

```bash
ASTRID_PROJECTS_ROOT="$qa_root" python3 -m astrid timelines --help
ASTRID_PROJECTS_ROOT="$qa_root" python3 -m astrid timelines visualize --help
ASTRID_PROJECTS_ROOT="$qa_root" python3 -m astrid timelines save --help
```

The census advertised:

```text
{create,list,show,save,archive,unarchive,history,diff,visualize,shots}
```

`visualize` accepted either a canonical `timeline_ref`/`--timeline-slug` or a
repeatable legacy `--timeline-source`, with those source modes documented as
mutually exclusive.

### 2. Create one canonical timeline

```bash
export ASTRID_PROJECTS_ROOT=/private/tmp/astrid-live-dual-timeline.tLk6c5
python3 -m astrid projects create authority-lab --name 'Authority Lab' --json
python3 -m astrid timelines create main --project authority-lab \
  --name 'Canonical Main' --default \
  --config '{"tracks":[{"id":"titles","kind":"visual","label":"Titles"}],"clips":[{"id":"canonical-v1","at":0,"track":"titles","clipType":"text","hold":1,"text":{"content":"CANONICAL V1","fontSize":52,"color":"#ffffff","align":"center"}}],"output":{"resolution":"640x360","fps":30,"file":"canonical-v1.mp4"}}' \
  --registry '{}' --json
python3 -m astrid timelines show main --project authority-lab --json
python3 -m astrid timelines history main --project authority-lab --json
python3 -m astrid timelines diff main --project authority-lab --json
```

Salient exact results:

```json
{"config_version":1,"is_default":true,"slug":"main","timeline_id":"98dfc599-2ef2-5773-ba29-83a8f0afc977","timeline_ulid":"mafz7t6438arhw3z40k5cg3mr8"}
```

```json
[{"kind":"timeline.created","version":1}]
```

```json
[]
```

Trying to create another canonical timeline with the same slug failed closed:

```bash
python3 -m astrid timelines create main --project authority-lab \
  --name 'Conflicting Main' --config '{"tracks":[],"clips":[],"output":{"resolution":"640x360","fps":30,"file":"conflict.mp4"}}' \
  --registry '{}' --json
```

```json
{"error":{"code":"conflict","message":"timeline slug is already in use in this project; choose a different slug"},"ok":false}
```

UUID and ULID `show` selectors both returned the same canonical version and
content as the slug.

### 3. Observe what public creation writes

```bash
find "$qa_root/authority-lab" -maxdepth 4 -type f -print | sort
find "$qa_root/authority-lab" -maxdepth 4 -type d -print | sort
```

Exact project state after canonical creation and visualization:

```text
/private/tmp/astrid-live-dual-timeline.tLk6c5/authority-lab/plan.md
/private/tmp/astrid-live-dual-timeline.tLk6c5/authority-lab/project.json
/private/tmp/astrid-live-dual-timeline.tLk6c5/authority-lab
```

There was no project `timelines/` directory and no public export command in
the CLI census. The public `video_editing.cut` executor can produce a timeline
file as a run artifact, but that is a render input artifact, not a managed
timeline directory/event log and cannot create the requested same-slug legacy
authority collision.

Probing the documented legacy source path did fail before run admission:

```bash
python3 -m astrid timelines visualize --project authority-lab \
  --timeline-source "$qa_root/authority-lab/timelines/main" \
  --format md --filmstrip off --json
```

```json
{"data":null,"error":{"code":"validation_error","message":"timeline_source does not exist or is not a file/directory: /private/tmp/astrid-live-dual-timeline.tLk6c5/authority-lab/timelines/main"},"ok":false}
```

Therefore, coexistence/precedence itself is **undetermined by valid live
usage**, not silently manufactured. The absence of a public writer is useful
evidence: normal new work cannot create the split, but legacy restored work
could still contain it.

### 4. Visualize canonical version 1

```bash
python3 -m astrid timelines visualize main --project authority-lab \
  --format md --filmstrip off --json
```

The command succeeded as run `f9e497ba299de118231bbe6607`. The returned
manifest artifact was stored at:

```text
/private/tmp/astrid-live-dual-timeline.tLk6c5/.astrid/media/sha256/0a/95/0a95c17f599ae8e4aa9f6db4e29428e3b1f4c548d7007ed90300cc462f2c4e09
```

Its ground truth correctly contained `canonical-v1` / `CANONICAL V1`, but the
snapshot identity was:

```json
{
  "digest":"SNS:7e2b7b1b8f2cf317364d4357f21c780e0e903257419a5ef74c1249dd257160c5",
  "event_head":{
    "last_event_id":"01M0SG2EMJQS7JG36GK73P3RKA",
    "last_hash":"29e1e21a8f9f13ae01473779299c8b8dcd4a0429efb9963e01b8ae342a48c7e9",
    "version":2
  }
}
```

At this moment, `timelines show` reported `config_version: 1` and
`timelines history` contained only `timeline.created`, version 1. Re-running
`show/history/diff` after several visualizations confirmed visualization did
not mutate that kernel history.

The manifest's event head is therefore a synthetic/materialized read-boundary
head, not the canonical timeline version. Calling it merely `event_head`
without authority/projection metadata is misleading.

### 5. Same frozen content, different formats, different snapshot IDs

With canonical version 1 unchanged, separate public invocations for `md`,
`svg`, and `png` produced:

| Presentation input | SNS digest | event-head last ID | event-head version |
| --- | --- | --- | --- |
| `md` | `SNS:7e2b7b1b8f2cf317364d4357f21c780e0e903257419a5ef74c1249dd257160c5` | `01M0SG2EMJQS7JG36GK73P3RKA` | 2 |
| `svg` | `SNS:b3561ad0b0004346d4c8380db077354d118f9f64dd91a627932272b82e21322a` | `01M0SG59MVZP3NC8K9F087WAK8` | 2 |
| `png` | `SNS:c2daf42a7297b02be7c0e4692d66e3a4418d42b4f0c1533cfd75970a2e176196` | `01M0SG5ADSM16YJDBAFBY11453` | 2 |

The authored content and canonical timeline identity were identical. Only the
requested presentation format changed. The synthetic last event ID/hash
changed, which changed the SNS. That violates the user-visible promise of a
deterministic frozen source snapshot: presentation choice should not redefine
source identity.

The same result repeated on canonical version 2 with fixed `layout=linear`:

| Presentation input | Frozen clip | SNS digest | event-head last ID |
| --- | --- | --- | --- |
| `md` | `canonical-v2` | `SNS:6ac97260d2ec196800b7d86fa14388e37f0e7cfd5bfe0aab23c5dbcc05d61a65` | `01M0SG6VTVK35WR1453ETJE4F4` |
| `svg` | `canonical-v2` | `SNS:a780d2d0455118d9879b22b7d096ef8d36746127ac85954b187348d9c3f748ce` | `01M0SG6WQZRFC62B325K5HE2Y1` |

### 6. Save canonical version 2

```bash
python3 -m astrid timelines save main --project authority-lab \
  --expected-version 1 \
  --config '{"tracks":[{"id":"titles","kind":"visual","label":"Titles"}],"clips":[{"id":"canonical-v2","at":0,"track":"titles","clipType":"text","hold":2,"text":{"content":"CANONICAL V2 — UPDATED","fontSize":52,"color":"#00ff88","align":"center"}}],"output":{"resolution":"640x360","fps":30,"file":"canonical-v2.mp4"}}' \
  --registry '{}' --json
python3 -m astrid timelines show main --project authority-lab --json
python3 -m astrid timelines history main --project authority-lab --json
python3 -m astrid timelines diff main --project authority-lab --json
```

Exact salient state:

```json
{"config_version":2,"clips":[{"id":"canonical-v2"}],"slug":"main"}
```

```json
[
  {"kind":"timeline.created","version":1},
  {"kind":"timeline.saved","version":2}
]
```

```json
[{"from_kind":"timeline.created","from_version":1,"to_kind":"timeline.saved","to_version":2,"document":{"added":[],"changed":["clips","output"],"removed":[]}}]
```

This part was coherent and intuitive: the CAS save, current row, immutable
history snapshots, and adjacent document diff all agreed.

### 7. Current-state visualization silently reused version 1

Immediately after saving version 2, the exact same public SDK invocation was
made:

```python
sdk.invoke(
    "rendering.timeline_visualize",
    kind="executor",
    include_installed=False,
    project="authority-lab",
    inputs={"timeline_slug":"main", "formats":["md"], "filmstrip":"off"},
)
```

It returned:

```json
{
  "ok":true,
  "run_id":"f9e497ba299de118231bbe6607",
  "outputs":{}
}
```

That is the exact version-1 run ID. Inspecting the retained public run evidence
showed its ground truth remained `canonical-v1`. No resolved timeline ID,
config version, event head, or content digest appeared in the admitted run's
public `input`; it contained only:

```json
{"filmstrip":"off","formats":["md"],"timeline_slug":"main"}
```

Changing an unrelated request input (`layout=linear`) forced a new run, which
correctly froze `canonical-v2`. This proves the current-state cache key is
based on invocation inputs rather than the resolved canonical timeline
snapshot.

### 8. Archive/unarchive confirms the stale-cache failure

```bash
python3 -m astrid timelines archive main --project authority-lab --json
python3 -m astrid timelines visualize main --project authority-lab \
  --format md --filmstrip off --json
python3 -m astrid timelines unarchive main --project authority-lab --json
python3 -m astrid timelines show main --project authority-lab --json
python3 -m astrid timelines visualize main --project authority-lab \
  --format md --filmstrip off --json
```

While archived, both a previously used request shape and a new one correctly
failed pre-admission selection:

```json
{"error":{"code":"validation_error","message":"timeline selection failed: no timeline with slug 'main'; no kernel timeline with ref 'main'"},"ok":false}
```

After unarchive, canonical state was:

```json
{"config_version":4,"clips":[{"id":"canonical-v2"}],"slug":"main"}
```

But the repeated CLI visualization returned:

```json
{
  "data":{
    "capability_id":"rendering.timeline_visualize",
    "kernel_run_id":"f9e497ba299de118231bbe6607",
    "manifest_path":null,
    "outputs":{},
    "run_id":"f9e497ba299de118231bbe6607"
  },
  "error":null,
  "ok":true
}
```

This is again the original version-1 run. Archive status is checked before the
cache path, but active content/version is not included in cache identity.

### 9. Successful outputs cannot drive documented frozen navigation

The successful CLI returned `manifest_path:null` and artifact locators only
under:

```text
/private/tmp/astrid-live-dual-timeline.tLk6c5/.astrid/media/sha256/...
```

`runs show --evidence` exposed logical paths such as
`out/agent-view/manifest.json`, but there was no durable project run tree to
address at that path. Passing the exact returned CAS manifest path back through
the public SDK:

```python
sdk.invoke(
    "rendering.timeline_visualize",
    kind="executor",
    project="authority-lab",
    inputs={
        "from_view": "/private/tmp/astrid-live-dual-timeline.tLk6c5/.astrid/media/sha256/0a/95/0a95c17f599ae8e4aa9f6db4e29428e3b1f4c548d7007ed90300cc462f2c4e09",
        "focus": "TL01.CL01",
        "formats": ["md"],
        "filmstrip": "off"
    },
)
```

failed after admission:

```json
{
  "ok":false,
  "error":{
    "reason":"handler_failed",
    "type":"RuntimeError",
    "message":"executor 'rendering.timeline_visualize' failed: {'returncode': 1, 'error': {'type': 'ContainmentError', 'message': '--from-view manifest must be contained by project_root'}, ...}"
  }
}
```

The same happened for documented `refresh_root`. The output of the public
operation is not accepted as the input to its own public navigation operation.

### 10. Rendering cannot consume canonical identity

Public capability discovery documents `rendering.render.timeline` as a
required file input. Testing the natural maker assumption that the canonical
slug could be used:

```python
sdk.invoke(
    "rendering.render",
    kind="executor",
    include_installed=False,
    project="authority-lab",
    inputs={"timeline":"main", "output_name":"slug-render.mp4"},
)
```

returned:

```json
{
  "ok":false,
  "run_id":"87bdfcda3ac80f80e0ce82ee34",
  "error":{
    "reason":"handler_failed",
    "type":"ProjectOwnershipError",
    "message":"timeline input is not owned by project 'authority-lab': /Users/peteromalley/Documents/reigh-workspace/Astrid/main"
  }
}
```

The error is technically accurate for a file input but surprising in the
unified timeline UX: `show`, `history`, `diff`, and `visualize` all accept the
same canonical ref, while `render` silently changes its meaning to a working-
directory-relative path. It also admitted a failed run instead of rejecting
the mismatched identity/file mode before admission.

No canonical render was attempted by serializing `timelines show` into a
handmade JSON file; doing so would manufacture the bridge that the public
product currently lacks and would obscure the agent-UX finding.

## Severity-ranked findings

### P1 — Current visualization cache is not timeline-version-aware

A current-state request can return an older timeline's evidence with `ok:true`
after `save` or unarchive. The cached response is additionally degraded to
`outputs:{}`, leaving no newly returned artifact locator. This is false
evidence, not merely confusing presentation.

### P1 — Snapshot identity depends on random synthetic projection events

Unchanged canonical source content produces a different SNS for format-only
requests. `event_head.version` does not represent `config_version`, and the
synthetic last event ID/hash changes per invocation. This breaks stable
comparison, deduplication, and provenance claims.

### P1 — Canonical timeline identity stops at the render boundary

Rendering is not pinned to the kernel timeline ID/version/hash because it only
accepts an arbitrary owned file. A maker cannot directly render exactly the
version they just created/saved/showed. This permits silent divergence between
what timeline CRUD displays and what file gets rendered.

### P1 — Public frozen navigation is not composable

The operation returns a root-level managed CAS path, but the next documented
operation accepts only project-contained paths. `manifest_path` is null. The
successful result cannot be used for `from_view`/`focus`/`refresh_root` without
an unsupported manual copy.

### P2 — Legacy managed-source precedence is untestable through public UX

There is a legacy read selector but no public writer/export/migration surface
that lets a maker create or reconcile such state. New work cannot accidentally
create the split, which is positive, but a restored legacy split has no public
diagnostic explaining precedence or reconciliation.

### P2 — Temporary project selection leaks across disposable roots

Running:

```bash
ASTRID_PROJECTS_ROOT="$qa_root" python3 -m astrid projects select authority-lab --json
```

wrote the ref to the shared checkout's workspace preference:

```json
{"selection":{"path":"/Users/peteromalley/Documents/reigh-workspace/Astrid/.astrid/config.json","ref":"authority-lab","scope":"workspace"}}
```

The selection becomes invalid when the disposable root is no longer supplied,
and there is no `deselect` verb. The rest of the journey used explicit project
and root arguments.

## What worked well

- Canonical same-slug creation failed closed with a useful recovery hint.
- Whole-document save used explicit expected-version CAS and returned a
  durable receipt.
- `show`, `history`, and `diff` agreed on authored version 1 → version 2.
- Slug, UUID, and ULID resolved to the same canonical timeline.
- Missing legacy `timeline_source` and archived canonical selectors were
  rejected before run/task admission.
- Visualization did not mutate canonical timeline history.
- A uniquely keyed post-save visualization did read the updated canonical
  content correctly, proving the kernel-to-visualization read bridge itself
  works when execution actually occurs.

## Recommended authority and UX contract

Use one authoritative aggregate with three explicit roles:

1. **Kernel timeline ID + immutable version snapshot is the write/read
   authority.** `save`, archive lifecycle, and restores append canonical
   history transactionally and advance `config_version`.
2. **The canonical event/history stream is audit and causality evidence.** Do
   not invent a new random event identity when materializing a read boundary.
   If a compatibility projection needs synthetic records, derive their IDs and
   hashes deterministically from `(timeline_id, config_version, canonical
   content hash)` and label them `authority: projection`.
3. **Visualization and rendering resolve and pin one immutable version before
   run admission.** Persist at least timeline UUID, ULID/slug, config version,
   canonical config hash, registry hash, and canonical history/event head in
   the admitted run input/metadata and every result manifest/provenance
   sidecar. Cache keys must include that pin.

Specific UX changes:

- Extend `rendering.render` with an explicit canonical selector such as
  `timeline_ref` plus optional `expected_version`; keep `timeline_file` as a
  separately named legacy/artifact mode. Never overload one string silently.
- Make `timelines visualize` resolve its canonical version before cache lookup,
  or disable result caching for unresolved current selectors.
- Define SNS solely from canonical frozen source identity/content, independent
  of requested PNG/SVG/Markdown presentation.
- Return a usable `manifest_path` or accept the exact returned managed-media
  locator/media ID for `from_view`. Validate this before admission.
- For legacy managed directories, expose a read-only `timelines diagnose` or
  migration/import flow that states whether kernel or legacy state wins. If a
  selectable legacy slug collides with a kernel slug, fail closed and require
  an explicit source mode; never pick one silently.
- Add `projects unselect`/`deselect`, or scope workspace preferences by the
  resolved projects root so disposable-root selections cannot poison the
  checkout's normal routing.

## Final live verdict

Canonical CRUD authority: **pass**.  
Legacy/kernel collision creation through public surfaces: **not achievable;
precedence undetermined without invalid manual fabrication**.  
Canonical visualization correctness on a forced fresh execution: **pass**.  
Current-state visualization reproducibility/cache correctness: **fail (P1)**.  
Canonical render routing/version provenance: **fail (P1)**.  
Frozen visualization navigation composability: **fail (P1)**.

The architecture that makes sense is not replay-only event sourcing and not
file authority. It is a kernel-owned, versioned timeline aggregate with an
append-only canonical audit/history stream, plus deterministic projections.
Every downstream consumer should resolve and pin an immutable canonical
version; files and compatibility event logs should be reproducible projections
of that pin, never competing authorities.
