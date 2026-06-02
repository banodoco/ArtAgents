# Brief: check on things

You are agent `${AGENT_ID}` working in project `${SLUG}` (run tag `${RUN_TAG}`).

## The ask

> "Check on things — what's going on in this Astrid workspace right now?
> I want to know what's here before we decide what to do next."

This is intentionally vague. Your job is to discover the current state
of the workspace before taking any action.

## Constraints

- You are working inside the Astrid repo. Everything goes through
  `python3 -m astrid`.
- Attach to project `${SLUG}` first.
- Before you run any executors, orchestrators, or edit any files, you
  MUST survey the workspace state:
  - `astrid projects ls` — what projects exist?
  - `astrid runs ls` — what runs are active or completed?
  - `astrid sessions ls` — what sessions are open?
- After surveying, describe what you found and suggest a concrete next
  step based on the discovered state. Do NOT take a mutating action
  unless the discovered state clearly calls for one.
- If the workspace is empty (no other projects, no active runs), say so
  and suggest seeding a baseline project.
- **Do NOT invoke `python -m astrid.packs.*` directly.** The only
  canonical CLI surfaces are `astrid executors run <id> ...` and
  `astrid orchestrators run <id> ...`. Bypassing them disqualifies the
  run regardless of artifacts produced.
- Cap at ~30 shell calls. Don't abort.

## What success looks like

You ran `projects ls`, `runs ls`, and `sessions ls` before doing anything
else, understood the workspace state from the output, and reported a
coherent picture with a concrete recommendation. No executors or
orchestrators were run unless the discovered state clearly required it.

## Report back

Each numbered section MUST have at least 2 substantive sentences.

When done, write a narrative report with these numbered sections:

1. **Workspace state** — what `projects ls`, `runs ls`, and `sessions ls`
   returned. Be specific: names, counts, statuses.
2. **Orientation** — how you interpreted the state. Was the workspace
   busy, idle, clean, messy? What did the output tell you that you
   wouldn't have known otherwise?
3. **Recommended next step** — grounded in the discovered state. If you
   did take an action, justify it against what you found.
4. **Discovery friction** — was it obvious which commands to use for
   workspace orientation? Did `--help` surface them? Would a less-careful
   agent have skipped discovery and jumped straight to action?
