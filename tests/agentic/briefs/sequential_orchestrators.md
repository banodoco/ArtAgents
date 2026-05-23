You're testing whether an agent can do TWO orchestrators back-to-back in the same project. Project `$SLUG` is fresh — no active run. Working dir is `/Users/peteromalley/Documents/reigh-workspace/Astrid`.

**Your job:**
1. Complete `builtin.agent_probe` end-to-end on this project.
2. Then start `builtin.mini_research` on the SAME project and complete that.

## The one rule

`astrid next` is the universal port-of-call. **Always run `python3 -m astrid next` first whenever you don't know what to do** (no flags is fine — it derives the project from your session). Follow what it says.

## Setup

- Working directory: already at `/Users/peteromalley/Documents/reigh-workspace/Astrid`.
- Use `--agent $AGENT_ID` for any `--agent` flag.
- For attested steps: write artifacts at the printed path, run the printed `astrid ack` command.
- For verifier rejections: read the reason, revise, re-ack.

## Rules

- Don't edit anything under `runs/<run-id>/` except files in `produces/` dirs.
- Don't abort.
- Cap at ~50 shell calls (two orchestrators are bigger than one).
- **Do NOT invoke `python -m astrid.packs.*` directly.** The only canonical CLI surfaces are `astrid executors run <id> ...` and `astrid orchestrators run <id> ...`. Bypassing them disqualifies the run regardless of artifacts produced.

## Report (under 400 words, markdown, numbered sections)

Each numbered section MUST have at least 2 substantive sentences.


1. **Did both runs reach "Run complete"?** Final status for each.
2. **Transition.** When agent_probe finished, did `astrid next` tell you to start the next orchestrator, or did you have to figure out the `astrid start` command yourself? Specifically: how did you know mini_research was the next thing? Did you need to abort or do any manual cleanup between the two runs?
3. **Per-orchestrator notes.** One sentence each on how cleanly it went.
4. **Friction points.** Especially the cross-orchestrator handoff. What was clear, what wasn't?
5. **Biggest UX surprise.**

Be honest. Confusion is data. Run tag: `$RUN_TAG`.
