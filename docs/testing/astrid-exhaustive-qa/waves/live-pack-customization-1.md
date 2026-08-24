# Live pack customization wave 1 — private gentle-fade animation

Date: 2026-08-23

## Verdict

**Partial success; P1 discoverability/runtime gap.** A new, disposable external
pack can be scaffolded, statically validated, discovered through the public SDK,
and inspected/validated through the public element CLI. The public SDK exposes
the variant as `animations/gentle-fade`, owned by `gentle_fade_pack`, with a
24-frame default versus the built-in `animations/fade` at 12 frames. A timeline
can therefore select it by replacing an entrance/exit `type` value with
`gentle-fade`.

However, the live `rendering.render` facade did not include the extra pack in the
Remotion element registry. It rendered successfully, but the provenance sidecar
contained only the repo-local `text-card` effect root and no
`gentle_fade_pack`/`gentle-fade` resolution evidence. The custom timeline and a
stock-fade timeline produced the same primary-video hash. This is a dangerous
silent fallback/ignore: discovery says the element exists, while the rendering
path gives no error or warning that the requested external animation was not
loaded. Do not treat this workflow as production-safe until render registration
and provenance are fixed.

## Scope and safety

- No tests were run and no source files were inspected for implementation details.
- No files under `astrid/packs/local` or any builtin pack were edited.
- All new pack/project artifacts were created below
  `/tmp/astrid-gentle-fade-pack.Allqk4/`.
- The pack was not installed globally. `packs install --dry-run` was used only
  to inspect the trust summary.
- No override file was created and no existing local override was changed.

## Live commands and observations

### 1. Surface discovery and documentation friction

The canonical Astrid skill and pack-author docs were read first:

- `docs/packs/creating-packs.md`
- `docs/packs/aliases-vs-forks-vs-overrides.md`
- `docs/packs/fork-and-update.md`
- `docs/guides/discovery-for-agents.md`
- `docs/guides/creating-tools.md`
- `docs/reference/env-vars.md`

`python3 -m astrid --help` and `python3 -m astrid help` correctly showed only
the eight product/operational gateway families. `python3 -m astrid packs
--help` was rejected as an unknown gateway family, despite the pack guide's
examples being written as `python3 -m astrid ...`. The working pack-management
surface is the internal module CLI:

```text
python3 -m astrid.core.pack.cli --help
```

This is a meaningful cold-agent UX ambiguity. The pack guide does explain the
internal module CLI later, but the first quick-start command is easy to try
literally and fails with a recovery message listing only the eight gateway
families.

### 2. Create a disposable pack

The supported scaffold command was run in a fresh temporary parent. Because the
checkout is not installed as a site package, running it from `/tmp` required the
checkout on `PYTHONPATH`:

```bash
mkdir -p /tmp/astrid-gentle-fade-pack.Allqk4
cd /tmp/astrid-gentle-fade-pack.Allqk4
PYTHONPATH=/Users/peteromalley/Documents/reigh-workspace/Astrid \
  python3 -m astrid.core.pack.cli new gentle_fade_pack
```

The scaffold created `pack.yaml`, `executors/`, `orchestrators/`,
`elements/`, and `skill/SKILL.md`. The pack manifest was then completed with
external-pack taxonomy, agent purpose, and capability metadata. The only
component added was:

```text
gentle_fade_pack/elements/animations/gentle-fade/
  element.yaml
  component.tsx
```

The manifest declares `kind: animation`, `runtime.adapter: remotion`, clip to
clip/visual ports, and `defaults.durationFrames: 24`. The component is a
Remotion wrapper with a slower fade default.

### 3. Validate the pack and element

Both supported validators passed:

```bash
PYTHONPATH=/Users/peteromalley/Documents/reigh-workspace/Astrid \
  python3 -m astrid.core.pack.cli validate \
  /tmp/astrid-gentle-fade-pack.Allqk4/gentle_fade_pack --warnings
# valid: .../gentle_fade_pack

PYTHONPATH=/Users/peteromalley/Documents/reigh-workspace/Astrid \
  python3 -m astrid.core.element.cli \
  --pack-root /tmp/astrid-gentle-fade-pack.Allqk4 \
  validate animations gentle-fade
# animations/gentle-fade: ok
```

The dry-run installation trust summary also worked and reported one element,
no declared permissions, local trust tier, and the expected disclosure that
installed pack code is not sandboxed. No install was performed:

```bash
PYTHONPATH=/Users/peteromalley/Documents/reigh-workspace/Astrid \
  python3 -m astrid.core.pack.cli install \
  /tmp/astrid-gentle-fade-pack.Allqk4/gentle_fade_pack --dry-run
```

### 4. Discover through public surfaces

The explicit SDK extra-root surface discovered the pack and element:

```python
import astrid.sdk as sdk

root = "/tmp/astrid-gentle-fade-pack.Allqk4"
inventory = sdk.discover(extra_pack_roots=(root,), include_installed=False)
cap = sdk.get_capability(
    "animations/gentle-fade",
    element_kind="animations",
    extra_pack_roots=(root,),
    include_installed=False,
)
```

Observed public DTO facts:

```text
pack id:       gentle_fade_pack
pack source:   extra
element id:    animations/gentle-fade
element pack:  gentle_fade_pack
element source: pack:gentle_fade_pack
default:       {"durationFrames": 24}
component:     .../gentle_fade_pack/elements/animations/gentle-fade/component.tsx
```

The built-in comparison was also resolved through the SDK:

```text
animations/fade       pack=rendering          default durationFrames=12
animations/gentle-fade pack=gentle_fade_pack  default durationFrames=24
```

The element CLI was similarly able to list and inspect the extra pack with
`--pack-root`, and returned `local_edit_state: clean` and the correct source
pack. `ASTRID_PACKS_PATH=/tmp/astrid-gentle-fade-pack.Allqk4` also made
`sdk.discover(include_installed=False)` find the pack.

There is an inconsistency in the pack CLI: with the same `ASTRID_PACKS_PATH`,
`python3 -m astrid.core.pack.cli list --json` did not list the extra pack and
`... pack.cli inspect gentle_fade_pack --json` returned `unknown pack`. Thus
the public SDK and element CLI can discover the extra pack, but the pack CLI's
own list/inspect surface does not honor the documented additional-pack path in
this usage.

### 5. Existing-timeline selection

Timeline element ids are bare and kind-scoped. A clip using the stock animation
should select the variant by changing only the id and, optionally, params:

```json
// before
"entrance": {
  "type": "fade",
  "duration": 0.4
}

// after
"entrance": {
  "type": "gentle-fade",
  "duration": 0.8,
  "params": {"durationFrames": 24}
}
```

The same id is used for an exit wrapper when the timeline's exit field supports
that phase. `examples/hype.timeline.full.json` demonstrates the shape (its
sample clip currently uses `slide-up`, so it is a shape reference rather than a
pre-existing stock-fade instance).

For the live render attempt, a project-owned timeline was created at:

```text
/tmp/astrid-gentle-fade-pack.Allqk4/projects/demo/render.timeline.json
```

It contained a visual text clip with
`entrance.type: "gentle-fade"` and `params.durationFrames: 24`.

### 6. Live render attempt and critical finding

An isolated project was created with the product gateway, and the timeline was
rendered through the public SDK facade:

```python
result = sdk.invoke(
    "rendering.render",
    kind="executor",
    project_root="/tmp/astrid-gentle-fade-pack.Allqk4/projects",
    extra_pack_roots=("/tmp/astrid-gentle-fade-pack.Allqk4",),
    include_installed=False,
    inputs={"timeline": "/tmp/astrid-gentle-fade-pack.Allqk4/projects/demo/render.timeline.json"},
    project="demo",
)
```

The first attempt used a timeline outside the project and correctly returned a
typed `ProjectOwnershipError`. Moving the timeline under the project root
allowed rendering to complete. That ownership requirement is understandable,
but the error does not explain the required relocation when the input was
already explicitly passed to a project-scoped SDK call.

The completed render wrote `hype.mp4` and a provenance sidecar. The sidecar's
Remotion fragment showed:

```text
element_roots: [.../astrid/packs/local/elements/effects/text-card]
source_pack_ids: ["local"]
```

It did not show `gentle_fade_pack`, `gentle-fade`, or an external element root.
The same timeline rendered with `entrance.type: "fade"` and
`durationFrames: 12` produced the same primary video content hash
`e4c456f9eb9043bc49a75e1c35c77199ec6c96722418ef3fbdc494d4ffe0052e` as the
custom-variant render. The custom request returned `ok: true` and no warning.

This is the core P1 issue: public discovery and static element validation say
the extra element is available, but `rendering.render` does not propagate the
extra pack into the Remotion registry/provenance. A caller receives a
successful-looking render with no evidence that the requested custom
animation ran. The explicit SDK `extra_pack_roots` argument and the
`ASTRID_PACKS_PATH` environment variable both failed to make the extra pack
appear in the render provenance in this live run.

## Alias vs fork vs override

| Mechanism | Meaning | Would it solve this goal? |
|---|---|---|
| Alias | A second public id that resolves to the same behavior; declared in the owning pack manifest. Identity/backward-compatibility only. | No. It cannot make fade slower, and element aliases are explicitly deferred. |
| Fork | A user-owned copy of an existing capability/element with provenance back to the source. | Conceptually yes, but the documented fork destination is the fixed repo-local `astrid/packs/local`; no public element-fork command or extra-root fork destination was exposed. I created a new external element instead, leaving the original untouched. |
| Override | A project-local redirection from a canonical id to a preferred replacement, persisted in `astrid/packs/local/.overrides.json`. | It would change the meaning of every request for the stock id, not create a separately selectable `gentle-fade`. It also requires touching the fixed local override store, which was out of scope and intentionally not done. |

The chosen approach is therefore **a new external/private pack element**, not an
alias, fork, or override. It preserves coexistence with `animations/fade` and
does not edit the original. The missing piece is making extra-pack element
registration flow through the render service.

## Severity-ranked UX critique

### P1 — Silent render-time loss of an externally discovered element

`sdk.discover()`/`element.cli --pack-root` report the element, but
`rendering.render` omits it from Remotion registry/provenance and returns
success. This can silently ship output with the wrong animation. Render should
either register explicit extra roots or fail closed with a typed
`element_not_available` error; provenance should record requested and resolved
animation ids/source packs just as it records backend routing.

### P1 — Extra-pack discovery surfaces disagree

The SDK and element CLI honor explicit extra roots, while pack CLI list/inspect
did not honor `ASTRID_PACKS_PATH` in this run. Agents cannot form a reliable
mental model of whether a pack is discoverable. One canonical discovery path
should back all list/inspect/validate surfaces, or each surface should state
its scope clearly.

### P2 — Pack CLI is not on the gateway despite quick-start wording

`python3 -m astrid packs ...` is rejected; the working command is
`python3 -m astrid.core.pack.cli ...`. The docs contain the clarification, but
the first command a cold agent is likely to try fails. Make the gateway route
the pack command or change all examples to the internal module CLI.

### P2 — No public element fork/override workflow for a disposable extra root

The docs explain fork and override concepts, but element customization is
coupled to the fixed repo-local `local` pack and manual `.overrides.json`
editing. There is no public, root-parameterized fork/override operation that
keeps a disposable experiment self-contained. Add an SDK/CLI operation with an
explicit destination root, or document that extra packs support creation and
discovery only, not fork/override lifecycle management.

### P3 — Project ownership error is technically correct but under-explained

Passing an absolute timeline outside the project to a project-scoped render
returned `ProjectOwnershipError`. The recovery should identify the expected
project-owned path or offer a supported import/copy step.

## Rollback and cleanup

No persistent repo state was changed. Cleanup is one scoped, recoverable target:

```bash
rm -rf /tmp/astrid-gentle-fade-pack.Allqk4
```

That removes the disposable pack, isolated project database/media staging,
timelines, render outputs, and provenance artifacts. There is no local-pack
override to remove and no builtin file to restore.

