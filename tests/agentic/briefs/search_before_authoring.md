# Brief: search before authoring

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

## The ask

> "I want a tool that can take a video arrangement plus a creative brief
> and produce editorial notes — basically grade the cut against the brief
> and tell me what needs to change. Before you decide to build anything
> new, search the Astrid tool surface to see if it already exists."

The instruction "search first" is part of the task.

## Constraints

- You are working inside the Astrid repo. Everything goes through
  `python3 -m astrid`.
- Attach to project `$SLUG` first.
- Use the discovery commands: `executors search <terms>`,
  `orchestrators search <terms>`, `executors list`, `inspect ...`.
  Try multiple terms (editorial, review, notes, judge, critique, brief,
  arrangement) — don't give up after one query.
- Do NOT scaffold a new executor/orchestrator folder under
  `astrid/packs/...`. Do not run `astrid` create / template / scaffold
  verbs. If you cannot find an existing tool after a *thorough* search,
  stop and report — do not start authoring.
- If you do find a matching tool, inspect it and (where it accepts
  trivial / synthetic inputs) start a run against `$SLUG` so we have
  evidence the discovery led to invocation.
- **Do NOT invoke `python -m astrid.packs.*` directly.** The only canonical CLI surfaces are `astrid executors run <id> ...` and `astrid orchestrators run <id> ...`. Bypassing them disqualifies the run regardless of artifacts produced.

## What success looks like

You searched the executor / orchestrator registry, found
`$TARGET_ORCH`, inspected its STAGE doc, and started it against the
project. No new pack files were created. No scaffolding commands were
run.

## Report back

The report MUST be at least 30 non-blank lines. Each numbered section MUST have at least 2 substantive sentences.

When done, write a narrative report with these four numbered sections:

1. **What you did** — chronological, terse, with the search queries you
   tried and which ones surfaced the tool.
2. **What tools you discovered** — `$TARGET_ORCH` plus any near-miss
   results that came up in your searches.
3. **Discoverability notes** — which search term finally surfaced the
   right tool? Were the `short_description` / `keywords` in the registry
   enough? Did `inspect` give you everything you needed, or did you have
   to read source?
4. **Biggest UX gap** — the single change to the registry, search ranking,
   or skill doc that would most reduce the "agent decides to author new
   instead of reusing" risk.
