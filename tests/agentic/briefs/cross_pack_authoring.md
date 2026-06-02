# Brief: build a cross-pack orchestrator

You are agent `${AGENT_ID}` working in project `${SLUG}` (run tag `${RUN_TAG}`).

## The ask

> "Build me a new orchestrator that takes a video, transcribes it with
> `editorial.transcribe`, and then runs `video_editing.hype` on the
> transcript output. The orchestrator should be a DSL-based orchestrator
> under a pack you choose, with a qualified id."

You must discover both executors through the Astrid tool surface, then
author a new orchestrator composing them.

## Constraints

- You are working inside the Astrid repo. Everything goes through
  `python3 -m astrid`.
- Attach to project `${SLUG}` first.
- Use the discovery commands: `astrid executors search <terms>`,
  `astrid orchestrators search <terms>`, `astrid executors list`,
  `astrid orchestrators list`. Search for both the transcribe and hype
  executors before you start authoring.
- Author the new orchestrator using the canonical authoring surface:
  `astrid author new <pack>.<name>` to scaffold, then edit the DSL
  file. Do NOT hand-write YAML or invent non-existent CLI verbs.
- The orchestrator must compile cleanly: `astrid author check <id>`
  must exit 0 before you declare done.
- Do NOT run the orchestrator against real media in live mode. Structural
  mode / `--dry-run` is acceptable. The point is the authoring + compose
  decision, not output quality.
- **Do NOT invoke `python -m astrid.packs.*` directly.** The only
  canonical CLI surfaces are `astrid executors run <id> ...` and
  `astrid orchestrators run <id> ...`. Bypassing them disqualifies the
  run regardless of artifacts produced.
- Cap at ~80 shell calls. Don't abort.

## What success looks like

You discovered `editorial.transcribe` and `video_editing.hype` via
search/list, authored a new DSL orchestrator composing them, ran
`astrid author check` and got exit 0, and reported the qualified id of
your new orchestrator.

## Report back

Each numbered section MUST have at least 2 substantive sentences.

When done, write a narrative report with these numbered sections:

1. **What you discovered** — every executor/orchestrator you found via
   search, which queries surfaced them, and which ones you selected.
2. **What you built** — the qualified orchestrator id, pack, file path,
   and the step shape of each step in the pipeline.
3. **Authoring surface** — which CLI verbs you used to scaffold and
   validate. Did you use `astrid author new`? Did `astrid author check`
   pass on first try? If not, what failed and how did you fix it?
4. **Discovery friction** — was it easy to find executors from two
   different packs? Did the search/`inspect` output make clear that
   `hype` already wraps `transcribe`? Would a less-careful agent have
   composed a redundant pipeline?
5. **Biggest UX gap** — the single change to authoring or discovery that
   would most reduce the risk of an agent hand-scaffolding or inventing
   verbs.
