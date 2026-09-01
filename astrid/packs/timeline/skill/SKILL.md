---
name: timeline
short_description: Edit shot-owned timeline text and carry it through a verified render.
description: >
  Use for the timeline text workstream: discover shots and their bounded
  prompt, voiceover-script, and transcript bindings, revise them through the
  checkout or direct commands, then rebuild and verify a rendered timeline.
---

# Timeline text workstream

This is the agent-facing path for editing authored text used by a timeline.
The text is shot-owned: a binding belongs to one project and shot, not to a
timeline, and there is deliberately no timeline filter. A timeline may refer
to reusable shots in its own document config, while `timelines shots` and
`timelines text` provide the discoverable project-level views.

## Discover the project and shots

Start with the read-only census and health check, then inspect the active
shots. Use `--include-archived` only when recovering an archived record.

```bash
python3 -m astrid --help
python3 -m astrid doctor --json
python3 -m astrid timelines list --project <project> --json
python3 -m astrid timelines shots list --project <project> --json
python3 -m astrid timelines shots show <shot-id> --project <project> --json
```

Discover text by an exact binding id or by a bounded selector. Friendly
selectors fail closed with candidates when a project has more than one
matching slotted prompt. `prompt`, `voiceover_script`, and `transcript` are
the only kinds. Ordinary bindings have no slot; the verified alternate
`ex_glitch` prompt uses the narrow `regen-glitch` slot.

```bash
python3 -m astrid timelines text list --project <project> \
  --shot <shot-id> --kind transcript --json
python3 -m astrid timelines text list --binding <binding-id> --json
python3 -m astrid timelines text list --project <project> --all-project --json
```

## Revise one or many bindings

Checkout creates ordinary UTF-8 files plus a machine manifest. Files and the
manifest are projections, never authority. Review a checkout before applying
it; `status` reports changed files and `diff` shows the proposed bytes.

```bash
python3 -m astrid timelines text checkout --project <project> \
  --shot <shot-id> --kind transcript --out ./text-checkout --json
python3 -m astrid timelines text status ./text-checkout --json
python3 -m astrid timelines text diff ./text-checkout --json
python3 -m astrid timelines text apply ./text-checkout --json
```

Apply validates every selected binding head and the frozen caller bytes before
opening the mutation. The batch is all-or-nothing: a stale head, ownership
failure, invalid UTF-8, or candidate conflict leaves every binding unchanged.
Unchanged files perform no mutation. A changed command is receipt-backed and
an exact retry replays its receipt; a valid no-op returns without consuming an
idempotency key or writing a receipt.

For a complete replacement without a checkout, use `set`. It creates only a
missing binding from the complete natural tuple (project, shot, kind, and
optional slot), or replaces an existing binding at its expected stream head.
Use `rebind` only to select an existing same-project immutable text media row;
it never creates a binding and rejects head zero. Both are receipt-backed
domain commands, not capability invocations.

```bash
python3 -m astrid timelines text set --project <project> \
  --shot <shot-id> --kind voiceover_script --expected-head <head> \
  --text "New authored script" --json
python3 -m astrid timelines text set --binding <binding-id> \
  --expected-head <head> --file ./script.txt --json
python3 -m astrid timelines text rebind --binding <binding-id> \
  --expected-head <head> --media <text-media-id> --json
```

Caller input is bounded and UTF-8-validated, frozen, and hashed before the
UnitOfWork. Persisted media is checked again: malformed stored text is an
`integrity_error`, while a desired non-text candidate retains the public
validation/conflict taxonomy. Core media is read through the active-UoW
repository; the text-binding path does not use `prepare_media_file()` and
does not add direct Core-media SQL. Immutable text media uses mandatory
canonical managed digest paths. Previous media and the binding event stream
remain the history; there is no revisions table, cached head, or second
authority.

## Resolve prompts and run existing generation

Resolve the binding first and pass its literal text to an existing generation
command. Generation tasks retain literal resolved inputs; they do not
implicitly hydrate a binding. A prompt edit therefore changes no existing task
spec until an agent explicitly submits a new generation task.

```bash
python3 -m astrid timelines text list --binding <prompt-binding-id> --json
python3 -m astrid tasks create --project <project> \
  --capability <qualified-generation-capability> \
  --spec '{"prompt":"<resolved prompt text>"}' --json
python3 -m astrid runs show <run-id> --project <project> --json --evidence
```

Voiceover-script editing does not synthesize or replace audible WAV media.
Use the existing explicit synthesis task and promotion workflow when a new
recording is wanted, then associate/promote that immutable media explicitly.
The current promoted WAV remains the audio source until that explicit step.

## Rebuild, render, and verify

Rebuild the timeline document with its existing media clips and any baked
caption derivatives. Captions are derived media: the caption plate uses the
transcript binding bytes as input, and the output-to-input lineage is recorded
with the media relation. The renderer does not hydrate text bindings or
silently synthesize media.

```bash
python3 -m astrid timelines show <timeline-ref> --project <project> --json
python3 -m astrid timelines save <timeline-ref> --project <project> \
  --config '{"tracks":[],"clips":[]}' --registry '{"assets":{}}' \
  --expected-version <version> --json
python3 -m astrid timelines render <timeline-ref> --project <project> \
  --expected-version <version> --backend <qualified-renderer> --json
python3 -m astrid runs show <render-run-id> --project <project> --json --evidence
python3 -m astrid media verify <output-media-id> --project <project> \
  --realm managed_local --json
```

The Intro proof uses a media-only FFmpeg composition. It retains the approved
push-3s opening, including the ASTRID logo pixels embedded in that media. It
does not add a separate ASTRID wordmark text clip or overlay. Verify both
video and audio streams with `ffprobe`, and verify output-to-input hashes and
the unchanged promoted WAV identity before opening the result in the local
media viewer or file browser.

## Boundaries and deferred work

- Text mutations are ordinary receipt-backed domain commands in the active
  UnitOfWork; they do not create runs, tasks, capability adapters, or a
  parallel execution ledger.
- The source-tree skill and default `_core` registry sync are supported with
  `python3 -m astrid.skills.cli`; wheel distribution and HTTP bridge routes
  for this workstream are deferred.
- Automatic generation/render binding hydration, a universal document model,
  timeline-owned bindings, GUI/editor support, a generation ledger, and raw
  SQLite editing are deferred.
- The existing generation, voiceover synthesis/promotion, timeline rebuild,
  and canonical FFmpeg/render commands remain explicit steps. This skill does
  not claim a new adapter or a Remotion text compositor.
