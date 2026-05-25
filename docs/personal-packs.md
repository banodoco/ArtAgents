# Personal Packs

How to scaffold, populate, and manage a personal pack for your own
customizations. Personal packs live alongside shipped packs but are
gitignored by convention — they're yours, not Astrid's.

## Scaffolding a Personal Pack

```bash
# Create a new local pack (gitignored by convention)
python3 -m astrid packs new my_tools

# The pack is created at astrid/packs/my_tools/ with:
#   pack.yaml          — pack manifest
#   executors/          — your executors go here
#   orchestrators/      — your orchestrators go here
#   elements/           — your elements go here
#   AGENTS.md / STAGE.md / README.md  — documentation stubs
```

The `astrid/packs/local/` pack is pre-shipped as the conventional scratch space
and is already in `.gitignore`. Use it for one-off experiments, or create a
named personal pack for organized collections.

## Forking Capabilities Into Your Personal Pack

Copy any shipped capability into your pack for customization:

```bash
# Fork an executor into your local pack
python3 -m astrid executors fork rendering.render

# Fork an orchestrator
python3 -m astrid orchestrators fork video_editing.hype

# Fork an element
python3 -m astrid elements fork effects text-card
```

The forked copy lands in `astrid/packs/local/` with its id rewritten to
`local.<name>`. Provenance is tracked in `.astrid_fork_state.json` so you can
detect local edits later.

Use `--deep` on orchestrator forks to recursively copy all child executors and
orchestrators.

## Overriding Without Editing Originals

Once you have a fork, you can redirect all consumers to use your version:

```bash
# Set the override
python3 -m astrid executors override set rendering.render local.render

# Verify it's active
python3 -m astrid executors override list
```

Now any code, orchestrator, or agent that asks for `rendering.render` (or its
legacy alias `builtin.render`) gets `local.render` instead. The original is
untouched.

To revert:

```bash
python3 -m astrid executors override remove rendering.render
```

## Detecting Local Edits (Dirty Check)

Astrid tracks whether a forked capability has been modified since fork time:

```bash
# Check one capability
python3 -m astrid executors dirty check local.render
python3 -m astrid orchestrators dirty check local.hype
python3 -m astrid elements dirty check effects my-text-card

# List all dirty capabilities
python3 -m astrid executors dirty list
python3 -m astrid orchestrators dirty list
python3 -m astrid elements dirty list
```

### How Detection Works

Two strategies, tried in order (see `astrid/core/dirty.py`):

1. **Git-backed** (preferred): If the capability lives inside a git worktree,
   `git status --porcelain` checks for uncommitted changes. Fast, accurate,
   respects `.gitignore`.

2. **Hash-based fallback**: Compares current SHA-256 file hashes against those
   stored in `.astrid_fork_state.json` at fork time. If any file hash differs,
   the capability is dirty.

If `forked_from` is empty (the capability was never forked), the state is
always `"clean"`.

### Clean vs Dirty vs Forked States

| State | Meaning | `forked_from` | Files match fork state |
|---|---|---|---|
| Clean (original) | Not forked, shipped with Astrid | empty | N/A |
| Clean (fork) | Forked but unmodified | set | Yes |
| Dirty | Forked and modified locally | set | No |
| Conflict | Forked, and upstream has newer version | set | N/A (future) |

The inspect commands show `local_edit_state` in the `_capability` block:

```bash
python3 -m astrid executors inspect local.render --json | grep local_edit_state
```

## Interaction with Updates

When Astrid updates and a shipped capability changes, your forks are unaffected
— they're separate copies. The dirty check helps you identify which forks
diverge from their originals.

**Deferred (not yet implemented):**
- No remote registry for sharing personal packs
- No dependency isolation between packs
- No semantic merge of upstream changes into forks
- No `conflict` state detection (the state exists in the schema but is not
  yet computed)

## Convention: Gitignore

The `astrid/packs/local/` directory is gitignored by default. If you create
additional personal packs (e.g., `astrid/packs/my_tools/`), add them to
`.gitignore`:

```gitignore
astrid/packs/local/
astrid/packs/my_tools/
```

This keeps your experiments out of version control while Astrid discovers them
at runtime.
