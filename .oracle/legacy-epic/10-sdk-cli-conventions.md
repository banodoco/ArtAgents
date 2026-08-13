# Explore: SDK conventions and CLI insertion points

Project root: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only exploration. Do NOT edit files.

## What to establish

1. Public SDK conventions:
   - `astrid/sdk/generation.py`: how a public SDK module is structured
     (functions? dataclasses? lazy imports?), how it's exported from
     `astrid/__init__.py`, and how `tests/test_sdk_public_surface.py` pins
     the surface (what exactly does it assert about `import astrid`?).
   - `astrid/sdk/results.py` and `astrid/sdk/invocation.py` — patterns for
     result wrappers and invocation helpers.
   - `astrid/sdk/dto.py` if it exists — frozen JSON-safe DTO conventions
     (frozen dataclasses? pydantic?).
   - Are SDK imports lazy (astrid/__init__ must stay lightweight)? Show the
     export mechanism.
2. CLI insertion:
   - `astrid/core/gateway/dispatch.py`: how subcommands are dispatched
     (CommandSpec? registry dict?), how a new top-level verb family like
     `astrid renderers` would be inserted, and where help text lives
     (`gateway/help.py`).
   - How session-binding gates work: which commands require an attached
     project and how that's enforced (the epic wants `astrid renderers` to
     work unbound).
   - `astrid/core/cli/` — where the lifecycle `--engine task|arnold` flag is
     parsed (to avoid colliding with renderer `--engine` values).
   - How existing verbs emit `--json` envelopes (one example, e.g.
     `executors list --json`): the exact JSON shape and error conventions.
3. `astrid/core/modalities` — what it is and whether "renderers" naming
   would collide with modality "render hints" (iteration_video's renderers
   flags).

## Report format

Ranked findings with file:line evidence. Max 350 words. End with:
- Verified facts
- Unknowns
- Risks for adding `astrid renderers` + public SDK
- Suggested approach
