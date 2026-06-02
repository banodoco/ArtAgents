# Brief: fix a broken orchestrator

You are agent `${AGENT_ID}` working in project `${SLUG}` (run tag `${RUN_TAG}`).

## The ask

> "The `${TARGET_ORCH}` orchestrator has a compile-breaking DSL bug.
> Run `astrid author check ${TARGET_ORCH}`, read the error, fix the bug,
> and confirm it compiles cleanly."

The orchestrator is in the repo right now. It does not compile. Your
job is to find the bug, apply a minimal fix, and verify.

## Constraints

- You are working inside the Astrid repo. Everything goes through
  `python3 -m astrid`.
- Attach to project `${SLUG}` first.
- Run `astrid author check ${TARGET_ORCH}` BEFORE you touch any files.
  Read the error output carefully — it tells you exactly what's wrong.
- Apply the smallest possible fix. Do NOT rewrite the orchestrator.
  Do NOT delete and re-scaffold. The existing steps must stay intact.
- After your fix, `astrid author check ${TARGET_ORCH}` must exit 0.
- **Do NOT invoke `python -m astrid.packs.*` directly.** The only
  canonical CLI surfaces are `astrid executors run <id> ...` and
  `astrid orchestrators run <id> ...`. Bypassing them disqualifies the
  run regardless of artifacts produced.
- Cap at ~60 shell calls. Don't abort.

## What success looks like

You ran `astrid author check ${TARGET_ORCH}`, saw it fail, read the
error, identified the bug, applied a minimal fix to the DSL file,
reran `astrid author check ${TARGET_ORCH}`, and it passed (exit 0).

## Report back

Each numbered section MUST have at least 2 substantive sentences.

When done, write a narrative report with these numbered sections:

1. **Initial check** — what `astrid author check ${TARGET_ORCH}` reported
   (the exact error message or a close paraphrase).
2. **Diagnosis** — what you identified as the root cause, and how the
   error message led you to the right line/file.
3. **Fix applied** — the exact change you made (show the diff or the
   before/after). Why was this the minimal fix?
4. **Verification** — the result of the second `astrid author check`.
   Did it pass on the first fix attempt, or did you iterate?
5. **Discovery friction** — was the error message clear enough to
   pinpoint the bug? Did you have to read other files to understand
   what "correct" looked like?
6. **Biggest UX gap** — the single change to the `author check` error
   formatting or DSL documentation that would most reduce fix latency.
