You're testing the reader-state warning path. Project `$SLUG` already has an active `builtin.agent_probe` run started by ANOTHER actor (the priming step, holding the writer lease). You'll start as a reader.

**Your job:** detect the reader state, take over, and complete the run.

## What to do

1. **First, attach with a DIFFERENT actor identity** so idempotent attach doesn't auto-promote you to the writer:
   ```
   python3 -m astrid attach $SLUG --as agent:$AGENT_ID
   ```
2. Then run `python3 -m astrid next` (no flags). Read what it prints — it should warn you about reader state and give you the exact takeover command.
3. Take over.
4. Complete the run normally.

## The big question to answer

**Did `astrid next` warn you BEFORE the gate rejected you?** Pre-fix, agents would attach, try `astrid ack`, get rejected with "lease epoch mismatch," and only THEN discover they needed to take over. Post-fix, `astrid next` should print the takeover hint immediately on the first call from reader state.

## Setup

- Working dir already `/Users/peteromalley/Documents/reigh-workspace/Astrid`.
- Use `--agent $AGENT_ID` for the actor identity (and any `--agent` flag).
- Don't abort.
- Cap at ~30 calls.
- **Do NOT invoke `python -m astrid.packs.*` directly.** The only canonical CLI surfaces are `astrid executors run <id> ...` and `astrid orchestrators run <id> ...`. Bypassing them disqualifies the run regardless of artifacts produced.

## Report (under 350 words, markdown, numbered sections)

Each numbered section MUST have at least 2 substantive sentences.


1. **Did the run reach "Run complete"?**
2. **Reader-state detection.** When you ran `astrid next` from reader state, did it:
   - (a) print "attached to '$SLUG' as reader" warning?
   - (b) give you the exact `astrid sessions takeover <run-id>` command?
   - Was this BEFORE or AFTER any failed `astrid ack` attempt?
3. **Takeover flow.** After takeover, did `astrid next` immediately show the step instructions correctly?
4. **Friction points.**
5. **Biggest UX surprise.**

Be honest. Run tag: `$RUN_TAG`.
