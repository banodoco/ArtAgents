# Durable Timeline Visualization — Completion Record

Status: **completed and merged**.

The original two-milestone visualization epic shipped in `ca8c9cd2`
(`feat: timeline_visualize VLM navigation epic (B1-B10, oracle-validated)`) and
has since been integrated with Astrid's kernel timeline authority.

The pre-build briefs, dirty-worktree launch instructions, and duplicated
architecture-plan copy are not restored as an active `.megaplan` chain.
Astrid treats that directory as local/runtime state, the work has landed, and
the current architecture is documented below. Git history before `7c42c8d8`
retains the original planning source.

## Achieved North Star

A VLM-capable Astrid agent can run one stable command and understand a
project's temporal structure, spatial layering, visual progression, source
media, and text/speech evidence through an evidence pack designed for machine
navigation, without mutating the source timeline or inventing parallel
authority.

Proportional and readable-linear views share the same normalized model and
geometry. Stable qualified IDs connect numbered images to concise structure,
versioned ground truth, diagnostics, exact media, transcript evidence, and
executable actions. A frozen lineage fixes authoritative event-log state and
content hashes; children never silently read newer project state, and only
`refresh_root` returns to current state.

## Authority correction

The shipped managed path is event-log authoritative and read-only:

```text
kernel timeline event stream
        -> replay and verify head/identity
        -> frozen normalized inspection model
        -> shared layout model
        -> deterministic evidence pack
```

Visualization never repairs `assembly.json`, trusts a stale projection
sidecar, or writes timeline state. Explicit legacy input is a declared
compatibility mode; frozen navigation reads only the prior hash-ledgered pack.

## Shipped outcome

- `astrid timelines visualize` invokes `rendering.timeline_visualize` and
  produces deterministic, read-only agent evidence packs.
- Frozen roots and children retain event-head, registry, media, transcript,
  model, and artifact hashes.
- Time-scaled and readable-linear PNG/SVG pages share one semantic and geometry
  model.
- Evidence packs include TL/SH/RG/CL/AS/TS/SP identities, executable actions,
  exact-original integrity states, transcript/speech mapping, diagnostics,
  ground truth, and view geometry.
- Image-only, stdout-discovery, adversarial-integrity, and 24-clip Park24 live
  gates passed.

## Evidence map

| Intended capability | Current authority |
|---|---|
| Managed command and executor | `astrid/packs/timeline/cli.py`, `astrid/core/gateway/project.py`, `astrid/packs/rendering/executors/timeline_visualize/` |
| Event-log replay and immutable snapshots | `frozen.py`, `snapshot_digest.py`, kernel timeline repositories and authority tests |
| Qualified IDs and navigation actions | `ids.py`, `navigation.py`, `schemas/action-index.json` |
| Shared model and deterministic PNG/SVG | `model.py`, `layout.py`, `render_png.py`, `render_svg.py` |
| Exact-original and derived-media integrity | `assets.py`, `thumbnails.py`, `schemas/asset-index.json` |
| Transcript source and mapped speech evidence | `transcript_attach.py`, `transcripts.py`, `schemas/transcript-index.json` |
| Pack hashes, schemas, validation, diagnostics | `evidence_pack.py`, `emit.py`, `validate.py`, `schemas/` |
| Live and hermetic proof | `docs/architecture/timeline-visualization-release-evidence.md`, `tests/packs/rendering/test_timeline_visualize_*.py` |

## Shipped v1 boundaries

- Cold selectors cover project, timeline, shot, range, clip, asset, and
  timestamp. TS/SP are frozen-view targets reached through emitted actions.
- The qualified-ref grammar is TL/SH/RG/CL/AS/TS/SP. Tracks, transitions,
  effects, warnings, pages, and frame samples remain facts, geometry, or
  diagnostics rather than independent identity namespaces.
- `timeline_source` is compatibility data, not managed authority. Kernel
  source mode, resolved identities, event heads, and frozen hashes carry
  provenance.
- Direct capability inspection/invocation uses the Python SDK; the retired
  `astrid executors ...` family is not resurrected.

The current navigation contract is
`docs/architecture/timeline-visualization-agent-navigation.md`; the historical
design is `docs/architecture/timeline-visualization-plan.md`; the release
evidence records 495 hermetic passes, image-only 66/66 exact answers, three
fresh discovery journeys, and the Park24 journey passing three times. Possible
cold TS/SP selectors or new ID namespaces require a separate usability case,
not a replay of this epic.
