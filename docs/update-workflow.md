# Update Workflow

How to detect, review, and act on local edits to forked capabilities.

## Detecting Local Edits

After forking a capability and making changes, use the dirty check commands to
see what diverges from the original:

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

The inspect commands also expose edit state in the `_capability` block:

```bash
python3 -m astrid executors inspect local.render --json
# → "_capability": { "local_edit_state": "dirty", ... }
```

## Clean vs Dirty vs Forked States

| State | What it means | How to reach it |
|---|---|---|
| **Clean (original)** | Shipped with Astrid, never forked | Default for all builtin/external/seinfeld capabilities |
| **Clean (fork)** | Forked but unmodified since fork time | Fork, then don't edit |
| **Dirty** | Forked and modified locally | Fork, then edit files |
| **Conflict** | Forked, upstream has a newer version | Not yet implemented (deferred) |

A capability with empty `forked_from` (never forked) always reports `"clean"`.

## How Detection Works

Implemented in `astrid/core/dirty.py`. Two strategies, tried in order:

### 1. Git-Backed Detection (Preferred)

If the capability directory lives inside a git worktree, Astrid runs
`git status --porcelain` scoped to that directory. Any uncommitted changes
(modified, added, deleted files) make the capability dirty.

- **Pros:** Fast, respects `.gitignore`, handles renames, accurate
- **Cons:** Only works inside git repos

### 2. Hash-Based Fallback

If git is not available (or fails), Astrid falls back to comparing current
file SHA-256 hashes against those stored in `.astrid_fork_state.json` at fork
time. This file is written by the fork command and lives in the capability's
root directory.

The fallback:
- Walks all regular files in the capability directory (excluding `.git` and
  `.astrid_fork_state.json` itself)
- Computes SHA-256 for each file
- Compares against stored hashes
- Any mismatch → dirty

If no `.astrid_fork_state.json` exists (e.g., the capability was created
manually, not via fork), the state defaults to `"clean"`.

## Promoting In-Place Edits to Forks

If you've edited a shipped capability in place (not recommended, but it
happens), you can promote those edits to a proper fork:

```bash
# Fork the edited capability into your local pack, preserving changes
python3 -m astrid executors fork builtin.render --overwrite
```

The `--overwrite` flag replaces any existing fork. Without it, the fork command
refuses to overwrite.

**Better workflow:** Fork first, then edit the fork. This keeps the original
pristine and makes dirty detection meaningful.

## Using Overrides to Prefer a Fork

Once you have a fork, tell the system to use it:

```bash
# Route builtin.render → local.render
python3 -m astrid executors override set builtin.render local.render

# List active overrides
python3 -m astrid executors override list

# Remove when done
python3 -m astrid executors override remove builtin.render
```

Overrides are persisted in `astrid/packs/local/.overrides.json` and survive
restarts. The `OverrideStore` is thread-safe.

## Workflow: Review Before Promote

```bash
# 1. Check what's dirty
python3 -m astrid executors dirty list

# 2. Inspect the changes
python3 -m astrid executors inspect local.render --json | python3 -m json.tool

# 3. If happy, set the override to make it the default
python3 -m astrid executors override set builtin.render local.render

# 4. Verify the override is active
python3 -m astrid executors override list
```

## Workflow: Revert a Dirty Fork

```bash
# 1. Remove the override (if set)
python3 -m astrid executors override remove builtin.render

# 2. Delete the fork directory
rm -rf astrid/packs/local/executors/render/

# 3. Re-fork from the original
python3 -m astrid executors fork builtin.render
```

## Deferred Work

The following are not yet implemented:
- **No remote registry:** Fork state is local-only. No sharing or syncing of
  forks between machines.
- **No dependency isolation:** Forking an orchestrator does not automatically
  isolate its child capabilities from upstream changes unless you use `--deep`.
- **No semantic merge:** If upstream changes after you fork, there's no tooling
  to merge those changes into your fork. The `conflict` edit state exists in
  the schema but is not computed.
- **No upstream version tracking:** The `upstream_version` field in fork state
  is recorded but not compared against current upstream versions.
