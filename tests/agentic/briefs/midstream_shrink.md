# Brief: midstream shrink — the spec changed after you started

You are agent `$AGENT_ID` working in project `$SLUG` (run tag `$RUN_TAG`).

You receive TWO messages from the same user. The second one arrives *after* you
have already started, and it changes the spec. Honor the LATEST spec — and reuse
work you've already done rather than starting over.

---

### Message 1 (initial request)

> "I've got some footage and I want a hype cut — the full treatment, about 60
> seconds. Find the best moments, cut it together, render it. Use the right
> Astrid tool for the job."

### Message 2 (follow-up, after you've started)

> "Actually, make it way shorter — like 15 seconds, and punchier. I don't need
> the full 60-second treatment. Just the tightest, highest-energy cut."

---

## What to do

- You are inside the Astrid repo. Everything goes through `python3 -m astrid`.
  Attach to project `$SLUG` first.
- Discover the canonical hype orchestrator (target: `$TARGET_ORCH`) via
  `python3 -m astrid orchestrators search` or `... orchestrators list` — do NOT
  grep the source tree, and do NOT invoke `python -m astrid.packs.*` directly.
- The **final** output must reflect the SECOND spec (~15 seconds, punchy), not
  the first (~60 seconds). Look for a duration parameter on the orchestrator and
  set it to ~15.
- Re-parameterize, don't restart from zero. If you already kicked off discovery
  (or an invocation) against the 60s spec, adjust parameters for the 15s spec
  and reuse what you can. If you haven't invoked anything yet, just use 15s.
- If no source media is staged, synthesize a short placeholder so you can
  exercise the orchestrator end-to-end.

## Report back

Each numbered section MUST have at least 2 substantive sentences.

1. **What you did.** Chronological and terse — the commands you ran and what they
   told you, covering BOTH the initial 60s-oriented action and the 15s pivot.
2. **How you handled the pivot.** Did you notice the second message? Did you
   re-parameterize an in-flight attempt or start fresh? What did you reuse?
3. **Discoverability.** How did you find `$TARGET_ORCH`, and was the duration
   parameter easy to find?
4. **Biggest friction.** One concrete change that would make a mid-task spec
   pivot easier for the next agent.
