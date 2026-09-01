# Shot Generation-to-Render Bridge

## Status

Proposal prompted by the 2026-09-01 Astrid Intro shots 02–04 review cycle.

This document describes the missing bridge between Astrid's shot-owned prompt
bindings, generation runs, generated media, editorial promotion, dependent
media, canonical timelines, and review renders. It is a follow-on to the active
`.otto` project `timeline-text-workstream-20260831`; it does not change that
project's frozen scope.

## Summary

Astrid already has most of the required parts:

- immutable media and media relations;
- kernel-owned projects, shots, timelines, tasks, and runs;
- generation manifests containing resolved inputs and model settings;
- canonical references for characters, layouts, and other concepts;
- shot items for primary visuals, transitions, voiceovers, and derivatives;
- content-addressed render plates, review proxies, timeline snapshots, and
  render provenance;
- the `.otto` text-binding workstream, which adds stable shot-owned prompt,
  voiceover-script, and transcript bindings over immutable text media.

What is missing is one explicit workflow that connects those parts:

```text
shot
  -> prompt binding version
  -> generation run and ordered references
  -> generated candidate media
  -> human-approved promotion
  -> dependency invalidation and selective rebuild
  -> new canonical timeline version
  -> verified review render
```

With this bridge, a request such as “regenerate shot 02 with the same prompt,
but use this new character reference” becomes unambiguous and repeatable. An
agent should not need filenames, conversation history, or project-specific
database knowledge to complete it.

## Implementation stance: narrow bridge, generous north star

This is a north-star design document, not a requirement to implement every
section in one delivery. The first implementation must be deliberately small.
Its purpose is to connect existing Astrid authorities, not introduce another
subsystem.

Version one has exactly three responsibilities:

1. Freeze shot context in an existing generation task: shot and target role,
   prompt binding ID/head/hash, ordered reference IDs/hashes, parent media, and
   the generator's ordinary resolved settings.
2. Attach generation outputs as candidates and provide one atomic,
   expected-head-protected promotion operation.
3. After promotion, derive a stale-dependency report from existing shot items,
   media relations, recipes, and content hashes; rebuild deterministic plates
   and proxies, while reporting generative transitions for explicit review.

Version one should **not** add:

- a new generation aggregate, ledger, or authority;
- a general dependency-graph database;
- persistent `stale` or workflow-status state machines;
- a large family of convenience CLI verbs;
- automatic promotion or unapproved generative spending;
- universal continuity propagation across later shots;
- a migration of every historical project or generation.

The recipe shown later in this document is initially an immutable object in
the existing generation task specification and manifest. It is not a proposal
for a new table or service. Dependency state is initially computed on demand
from frozen descriptors and existing relations, not stored independently.

The remaining sections describe desirable behavior and safety boundaries so a
narrow implementation grows in the right direction. They must not be used to
inflate the first slice.

## Problem observed in the Astrid Intro

The shots 02–04 replacement cycle exposed a split between strong downstream
lineage and weak generation replay.

### What was preserved correctly

- Each promoted image is a content-addressed media item.
- Each primary shot item records the image hash, reference media IDs, parent
  variant, prompt-file path, generator label, and promotion status.
- Ordered `uses_as_input` relations connect the outputs to the layout,
  character, and previous-slide references.
- `variant_of` relations retain the superseded images.
- Captioned plates derive from exact primary item IDs and image hashes.
- Numbered review proxies derive from exact plate item IDs and hashes.
- The canonical numbered timeline pins the resulting media bytes.
- The final render pins the canonical timeline version and an immutable
  timeline/assets snapshot.

### What was not preserved cleanly

- The exact image prompt was referenced by a mutable filesystem path, not by
  an immutable binding ID, head, media ID, and content hash.
- The prompt text and hash were not part of the Codex ImageGen output's
  kernel-owned generation record.
- Exact tool/model version, request identity, and available generation
  settings were not associated with the promoted image.
- Shot-level compatibility metadata retained the superseded storyboard prompt,
  while the promoted primary item pointed at the new prompt file.
- Promotion and downstream refresh required several manual API calls.
- The opening transition continued to end on the superseded shot-02 image.
- There was no single command that could regenerate a candidate from the
  current recipe, promote it, rebuild stale dependencies, render, verify, and
  open the result.

The result was recoverable because the files and references still existed,
but it was not a clean replayable workflow.

## Relationship to `timeline-text-workstream-20260831`

The `.otto` project is the correct foundation. It adds:

- stable shot-owned text-binding identity;
- immutable prompt bytes and content hashes;
- event-stream history and receipt-backed replacement;
- friendly binding discovery;
- single and batch checkout, status, diff, apply, set, and rebind operations.

That resolves the prompt-authority problem. A stale prompt in project JSON or
shot compatibility metadata no longer needs to be authoritative.

The workstream deliberately defers:

- binding-aware generation adapters;
- automatic generation or render hydration;
- a first-class generation aggregate;
- implicit promotion;
- an end-to-end regeneration command;
- live migration of the Astrid Intro;
- dependency-driven transition regeneration.

This proposal begins at that explicit boundary. It should consume the text
binding contract after the `.otto` workstream is accepted and integrated, not
fork or duplicate it.

## Desired user experience

The workflow should separate candidate creation from approval.

### Generate candidates

Illustrative agent request:

```text
Regenerate shot 02 using its current prompt and references.
Make four candidates and do not change the current cut.
```

Expected behavior:

1. Resolve the shot and its current prompt binding.
2. Freeze the binding ID, head, text media ID, and prompt hash.
3. Resolve ordered reference media and hashes.
4. Resolve or require an explicit generator recipe.
5. Admit a normal Astrid generation run.
6. Import every output into managed media.
7. Relate every candidate to the prompt, references, parent variant, and run.
8. Attach candidates without replacing the current primary visual.
9. Return a reviewable candidate set and provenance summary.

### Promote one candidate

Illustrative agent request:

```text
Promote candidate 3 for shot 02 and refresh the numbered review timeline.
```

Expected behavior:

1. Verify that the candidate, shot, project, recipe, and generation run agree.
2. Atomically replace the shot's singular primary visual.
3. Retain the old primary as history or a superseded candidate.
4. Mark downstream media that no longer matches its frozen input descriptors.
5. Rebuild only affected derivatives.
6. Save a new canonical timeline version using the rebuilt media.
7. Report any dependent asset that cannot be regenerated automatically.

### Render and open

Illustrative agent request:

```text
Render the refreshed numbered timeline, verify it, and open it.
```

Expected behavior:

1. Pin the exact timeline version.
2. Render with a fresh output identity.
3. Verify the video and audio streams.
4. Verify output-to-input provenance and expected shot hashes.
5. Spot-check the changed shot windows.
6. Open the finished video in the local viewer.

These may be exposed as separate commands or as one orchestrated agent
workflow. The separate phases must remain observable and resumable.

## Proposed workflow surface

Astrid must retain its existing eight-family gateway. The bridge should live
under an existing nested surface or as an orchestrator backed by normal
kernel runs and tasks. It must not create a ninth top-level command family.

The preferred version-one surface is a thin coordinator plus the existing
generation, shot, timeline, and render services. Only candidate attachment and
atomic promotion require new shot-domain behavior. Listing candidates can use
the existing shot read model; timeline saving and rendering already exist.

The coordinator may expose three user-level phases without requiring three
new persistent workflow states:

```text
regenerate shot
  -> existing generation run with frozen shot context
  -> attach outputs as candidates

promote candidate
  -> atomic primary replacement
  -> return a derived stale-dependency report

refresh timeline
  -> rebuild deterministic derivatives
  -> report generative dependencies requiring approval
  -> use the existing timeline save/render path
```

An illustrative future convenience route could coordinate those phases while
preserving each underlying receipt, task, run, and event:

```text
regenerate-shot
  --project astrid-intro
  --shot 02
  --same-recipe
  --reference character=<media-or-reference-id>
  --candidates 4
  --review
```

Promotion should remain explicit by default. A convenience flag may promote
an already selected candidate, but generation alone must never silently alter
the current cut. The illustrative commands in this document describe user
intent, not a requirement to add every spelling to the public CLI.

## Generation recipe

“Use the same prompt” is insufficient. A replayable recipe should freeze the
following values before generation admission:

```json
{
  "schema": "astrid.shot-generation-recipe/v1",
  "project_id": "...",
  "shot_id": "...",
  "target_role": "primary_visual",
  "prompt_binding": {
    "id": "...",
    "head": 3,
    "media_id": "...",
    "content_sha256": "..."
  },
  "generator": {
    "capability_id": "generation.generate_image",
    "model": "...",
    "backend": "...",
    "mode": "...",
    "settings": {}
  },
  "inputs": [
    {
      "ordinal": 0,
      "role": "style_and_layout",
      "reference_id": "...",
      "media_id": "...",
      "content_sha256": "..."
    },
    {
      "ordinal": 1,
      "role": "character",
      "reference_id": "...",
      "media_id": "...",
      "content_sha256": "..."
    }
  ],
  "parent_media_id": "...",
  "parent_content_sha256": "..."
}
```

The authoritative copy should be part of the immutable generation task/run
input and manifest. A file projection may be emitted for review, but it must
not become a second authority.

Provider limitations must be recorded honestly. If a backend exposes no
seed, model revision, or request identifier, the manifest should state that
the field is unavailable and that replay is instruction-equivalent rather
than pixel-deterministic.

## Associations created by the bridge

The bridge should reuse existing kernel entities and media relations rather
than create a parallel provenance ledger.

For each generated candidate it should preserve:

- project and shot identity;
- prompt binding ID and frozen head;
- prompt text media ID and hash;
- generation run and task IDs;
- capability, model, backend, mode, and resolved settings;
- ordered reference IDs, media IDs, roles, and hashes;
- parent or source variant;
- output media ID and hash;
- candidate shot item ID and status;
- creation and promotion receipts.

The output media should retain ordinary `uses_as_input`, `derived_from`, and
`variant_of` relations where they express real media lineage. Binding and run
identity should remain typed metadata or first-class associations owned by the
appropriate existing domain, not be encoded into filenames.

## Promotion contract

Promotion is an editorial decision, not a side effect of generation.

A correct promotion operation should:

- fail closed if the candidate belongs to another project or shot;
- require the expected shot event head or current primary item identity;
- atomically install exactly one primary item for the target role;
- preserve the previous primary and its history;
- record candidate-to-primary state and the promotion receipt;
- perform no timeline or media mutation when replayed with the same key;
- reject an idempotency key reused with different arguments;
- return the exact invalidation set produced by the change.

Rollback should be promotion of a previous valid candidate, not destructive
deletion or restoration from a filename.

## Dependency invalidation

The bridge should compare frozen input descriptors rather than rely on names or
timestamps.

For a replaced primary visual, likely dependants include:

```text
primary visual
  -> captioned render plate
  -> numbered/name review proxy
  -> timeline asset selection
  -> final render

primary visual
  -> incoming/outgoing generated transition endpoint
  -> transition candidate or promoted transition
  -> timeline asset selection
  -> final render

primary visual
  -> later-slide continuity input
  -> optionally suggested regeneration, never silent replacement
```

Each derivative recipe should freeze its source item/media IDs and content
hashes. A derivative is current only when its descriptor matches the active
inputs. Promotion should compute and report the stale set immediately.

Not every dependant should be regenerated automatically:

- deterministic plates and review proxies may rebuild automatically;
- deterministic timeline compilation may run automatically after its assets
  are current;
- generative transitions should normally become an explicit regeneration
  task because they cost time/money and may require review;
- a later image that used the old shot as a continuity reference should be
  reported as potentially stale, not silently regenerated or replaced.

The system should therefore distinguish `stale`, `blocked_on_generation`,
`ready_to_compile`, and `current` states without adding a second authority.

## Review and variant behavior

The bridge should optimize for iterative human feedback:

- generate multiple candidates without touching the cut;
- show prompt, recipe differences, and reference inputs beside each output;
- allow feedback to create a new prompt-binding version or a recipe-only
  override;
- keep rejected candidates as traceable history unless explicitly archived;
- promote exactly one candidate;
- regenerate only the affected dependencies;
- produce a numbered review render with a new output identity;
- preserve a clean, unnumbered master timeline separately.

Prompt edits and recipe changes should remain distinguishable. “Move the mink
below the sign” changes prompt content. “Generate four candidates instead of
one” changes execution policy, not the creative prompt. “Use this new mink
reference” changes ordered recipe inputs, not necessarily prompt text.

## Safety and failure behavior

The bridge should preserve Astrid's existing kernel invariants:

- one kernel authority;
- normal run/task admission for generation and rendering;
- immutable media and task specifications;
- receipt-backed, idempotent domain mutations;
- event-stream history;
- expected-head/version checks;
- managed output verification;
- no direct SQLite editing;
- no silent promotion or synthesis;
- no destructive deletion of previous primaries;
- no hidden reuse of a stale render caused by an unchanged output key.

If generation succeeds but promotion fails, the output remains a candidate and
the workflow can resume. If promotion succeeds but a generative transition is
stale, the current canonical timeline must not falsely claim that the entire
dependency graph is refreshed. It should either render with an explicit stale
dependency warning or wait for transition regeneration according to the
caller's chosen policy.

## Migration of the current Astrid Intro

After the `.otto` text-binding workstream is integrated, the live Intro should
be migrated through public Astrid APIs:

1. Create or update shot prompt bindings for all active prompts.
2. Bind the exact new shots 02–04 prompt bytes, not the superseded storyboard
   prompts.
3. Verify the prompt media hashes against the current prompt files.
4. Backfill generation recipe records for the three existing images with only
   evidence that is actually known.
5. Mark unavailable Codex ImageGen request/model fields as unavailable rather
   than guessing.
6. Associate the promoted primary items with those frozen recipes.
7. Reconcile or de-authoritize stale shot-level compatibility prompt metadata.
8. Rebuild and verify the plate/proxy/timeline chain.
9. Regenerate the shot-01-to-shot-02 transition against the active shot-02
   image and promote it after review.
10. Render, verify, and open a fresh numbered review cut.

Retroactive migration cannot make the original direct Codex tool calls fully
replayable. Its purpose is to establish truthful current authority and ensure
that the next generation uses the complete bridge.

## Version-one acceptance criteria

Version one is complete when this focused path is empirically proven:

1. An existing generation task freezes the exact shot, target role, prompt
   binding ID/head/hash, ordered reference IDs/hashes, parent media, and
   ordinary resolved generator settings.
2. The generation manifest and output media read model make those frozen
   inputs discoverable without consulting filenames or conversation history.
3. Generation attaches one or more candidate shot items without changing the
   active primary visual.
4. Promotion atomically replaces the primary visual with expected-head and
   idempotency protection while retaining the previous item as history.
5. Promotion returns an on-demand invalidation report derived from existing
   descriptors and relations.
6. Deterministic plates and review proxies rebuild when their exact source
   hashes change; a generative transition with an old endpoint is reported as
   requiring explicit regeneration.
7. Existing timeline save/render commands produce and verify a fresh review
   video from the promoted candidate.
8. The complete path is proven on an isolated Astrid Intro copy and resumes
   safely after an interruption.

No additional aggregate, dependency table, persistent workflow state machine,
or broad project migrator is required to satisfy version one.

## North-star acceptance criteria

The bridge is complete when all of the following are empirically proven:

1. A shot's current prompt resolves by binding ID/head/hash without consulting
   storyboard JSON or a mutable prompt path.
2. A generation run freezes the resolved prompt binding and ordered reference
   inputs in its task specification and manifest.
3. Generated output media is traceable to the run, prompt, references, and
   parent variant through public read models.
4. Regeneration produces candidates without changing the active primary.
5. Promotion is atomic, expected-head protected, idempotent, and retains the
   old primary as history.
6. Promotion returns a complete deterministic and generative dependency
   invalidation report.
7. Plates and review proxies rebuild only when their source descriptors are
   stale.
8. A transition whose endpoint image changed cannot be reported as current.
9. Timeline compilation selects only the active/current shot items and creates
   a new version when its assets change.
10. The final render pins that timeline version and preserves a complete
    provenance snapshot.
11. An agent can execute generate -> review -> promote -> refresh -> render ->
    verify -> open without project-specific database access or remembered
    filenames.
12. A failed or interrupted workflow resumes safely from kernel state without
    duplicating promotion or losing generated candidates.

## Non-goals

This bridge should not:

- introduce a second generation or provenance ledger;
- replace the existing task/run lifecycle;
- make filesystem projections authoritative;
- guarantee pixel-identical replay when a provider cannot provide deterministic
  controls;
- automatically approve or promote generative outputs;
- silently spend money on dependent generative transitions;
- silently regenerate later shots that merely used the changed image as a
  continuity reference;
- create a ninth gateway family;
- solve every possible project-specific editorial policy in the first slice.

## Recommended version-one implementation slice

The smallest valuable delivery after the text-binding workstream is:

1. Extend generation admission to accept a frozen shot-generation context:
   shot ID, target role, prompt binding ID/head/hash, ordered reference
   IDs/hashes, and parent media.
2. Emit that context into the existing generation manifest and relate output
   media to the actual inputs.
3. Add candidate attachment and atomic promotion through the Shots service;
   use the existing shot read model for candidate discovery.
4. Compute dependency invalidation on demand for render plates, review
   proxies, transition endpoints, and timeline assets. Do not persist a second
   dependency or workflow-state model.
5. Add a thin resumable coordinator that calls existing services for generate,
   promote, deterministic refresh, render, verify, and open. It reports
   generative dependencies rather than silently running them.
6. Prove the workflow in an isolated Astrid Intro copy, including the stale
   opening-transition case. Do not include broad historical migration in this
   slice.

This slice captures the practical benefit without inventing a universal
document system or a new execution path.
