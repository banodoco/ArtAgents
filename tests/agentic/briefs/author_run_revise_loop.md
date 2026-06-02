# Brief: build an orchestrator, run it, fix it

You are agent `${AGENT_ID}` working in project `${SLUG}` (run tag `${RUN_TAG}`).

## The ask

> "Build a simple orchestrator that takes a text input file containing
> a list of numbers (one per line), computes the sum, and writes the
> result to a JSON file. Run it against a test input. If the output is
> wrong, fix the orchestrator and rerun until correct."

You must author, run, observe, revise, and rerun — the full feedback
loop. The first version is expected to have a subtle bug you'll catch
at runtime.

## Constraints

- You are working inside the Astrid repo. Everything goes through
  `python3 -m astrid`.
- Attach to project `${SLUG}` first.
- Create a test input file in the project: a text file with numbers
  (e.g., `10`, `20`, `30`) — the correct sum should be 60.
- Author a new DSL orchestrator in a pack of your choice. Use the
  canonical authoring surface (`astrid author new`, `astrid author check`).
- Run it via `astrid orchestrators run <id>` against the test input.
- If the output JSON does not contain the correct sum (60), revise the
  DSL and rerun. Do NOT declare success on a wrong output.
- The orchestrator must compile cleanly (`astrid author check` exit 0)
  before each run.
- **Do NOT invoke `python -m astrid.packs.*` directly.** The only
  canonical CLI surfaces are `astrid executors run <id> ...` and
  `astrid orchestrators run <id> ...`. Bypassing them disqualifies the
  run regardless of artifacts produced.
- Cap at ~80 shell calls. Don't abort.

## What success looks like

You authored a new orchestrator, ran it, observed wrong output,
diagnosed the bug, revised the DSL, reran, and the second run produced
the correct sum (60) in the output JSON. The full author→run→revise→
rerun loop completed.

## Report back

Each numbered section MUST have at least 2 substantive sentences.

When done, write a narrative report with these numbered sections:

1. **What you built** — the qualified orchestrator id, pack, file path,
   and the step shape. What was the intended behavior?
2. **First run** — what input you used, what output was produced, and
   whether it was correct. Be specific about the wrong value.
3. **Diagnosis** — what was the bug? How did the wrong output lead you
   to the root cause?
4. **Revision** — the exact DSL change you made. Show the diff.
5. **Second run** — the output of the rerun. Was it correct this time?
6. **Loop friction** — what made the author→run→revise→rerun loop slow
   or confusing? Was it easy to see the run output and map it back to
   the DSL? Would a less-careful agent have shipped the wrong version?
