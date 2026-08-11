# North Star: Pluggable Timeline Renderers

Any trusted Astrid pack can add a timeline render backend without editing
Astrid core. A render planner can select and compose compatible backends
deterministically; every full render and segment crosses a validated,
backend-neutral media contract; final assembly is explicit; and provenance
explains exactly which backend rendered what and why.

The public `rendering.render` capability remains stable. Existing Remotion,
FFmpeg, and hybrid workflows continue to work throughout migration. The
timeline document remains renderer-neutral, and neither timeline data nor CLI
input may introduce arbitrary import paths that bypass pack discovery,
permissions, precedence, or overrides.

The finished architecture must make the third renderer unremarkable: installing
a trusted pack, declaring its backend and capabilities, and selecting it by
qualified ID is sufficient for both full-timeline and eligible hybrid-segment
rendering. No Astrid source edit or concrete-backend branch is required.

For a renderer author, the golden path is a four-file scaffold—pack manifest,
renderer manifest, render implementation, and contract test—with ordinary
authors editing only the renderer manifest and render implementation. Astrid
owns discovery, asset materialization, permissioned process execution, output
probing and normalization, audio passthrough/muxing, cleanup, provenance,
contract tests, and replayable diagnostics. Python helpers are optional
convenience over a stable, language-neutral, versioned request/result protocol.

V1 deliberately composes complete temporal segments rather than overlapping
layers. That constraint must not become a dead end: render results may carry
optional named attachments such as alpha, depth, frame sequences, audio stems,
or native project files, and finalization is an explicit replaceable contract.
Backends with cross-window state can claim a larger window or the whole
timeline.
