# Brief: batch-retime clip segments using a tempo map

You are agent `${AGENT_ID}` working in project `${SLUG}` (run tag `${RUN_TAG}`).

## The ask

> "I need to batch-retime a set of clip segments to a target duration
> using a tempo map. Can Astrid do this?"

This is a plausible video-editing capability, but it may not exist on
the Astrid tool surface. Your job is to search thoroughly and not give
up after the first empty result.

## Constraints

- You are working inside the Astrid repo. Everything goes through
  `python3 -m astrid`.
- Attach to project `${SLUG}` first.
- Search the Astrid tool surface with persistence:
  `astrid executors search <terms>`, `astrid orchestrators search <terms>`,
  `astrid executors list`, `astrid orchestrators list`.
- If your first search returns zero hits, do NOT conclude "nothing
  exists." Rephrase, broaden, or change strategy:
  - Try different keywords: "retime", "tempo", "duration", "clip",
    "segment", "warp", "stretch".
  - Fall back to `astrid executors list` or `astrid orchestrators list`
    to scan the full registry.
  - After at least 2–3 attempts, report what you found honestly.
- If you find a close-but-not-exact match (e.g., a general clip tool
  that doesn't do tempo-based retiming), explain the gap.
- If nothing exists, say so. Do NOT fabricate a tool id or claim a
  near-miss is a match.
- **Do NOT invoke `python -m astrid.packs.*` directly.** The only
  canonical CLI surfaces are `astrid executors run <id> ...` and
  `astrid orchestrators run <id> ...`. Bypassing them disqualifies the
  run regardless of artifacts produced.
- Cap at ~40 shell calls. Don't abort.

## What success looks like

You tried at least 2–3 different search formulations, didn't give up
after the first empty result, and reported an honest conclusion about
whether Astrid has this capability — including any near-misses and
what the gap is.

## Report back

Each numbered section MUST have at least 2 substantive sentences.

When done, write a narrative report with these numbered sections:

1. **Search process** — every query you tried, in order, with result
   counts. Which terms returned zero? Which returned near-misses?
2. **Fallback strategy** — did you broaden terms, switch to `list`, or
   try a different discovery surface? What worked better?
3. **Conclusion** — does Astrid have this capability? If not, what's
   the closest existing tool and what's the gap?
4. **Resilience note** — if you had stopped after the first empty
   search, what would you have missed? What near-miss would a less-
   persistent agent have overlooked?
