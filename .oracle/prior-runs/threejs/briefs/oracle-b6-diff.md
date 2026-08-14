# Oracle Batch 6 — full-epic tracked-diff audit (research + commands)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle
Run base: b1c5f53c. HEAD: fc0c3cee. Previous checkpoint: 8723ca05.
Do not edit any files.

Prove T6.7 / T6.8 and T6.2: the complete feature diff has no `astrid/core/` production edit, no generated artifact, and no broad convention edits except what a gate required.

## Commands

```bash
cd /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle

echo '=== EPIC FILES ==='
git diff --name-status b1c5f53c..HEAD

echo '=== CORE (must be empty) ==='
git diff --name-only b1c5f53c..HEAD -- astrid/core/
git diff --name-only 8723ca05..HEAD -- astrid/core/

echo '=== BATCH 6 FILES ==='
git diff --name-status 8723ca05..HEAD

echo '=== FORBIDDEN ARTIFACTS IN EPIC ==='
git diff --name-only b1c5f53c..HEAD | rg -i 'node_modules|package-lock|\.mp4$|\.png$|\.wav$|browser|chromium|out/|build/|dist/|\.lock$|model\.py|extracted|diagnostic' || true

echo '=== BROAD DOCS / CONVENTIONS TOUCHED ==='
git diff --name-only b1c5f53c..HEAD -- README.md CHANGELOG.md STAGE.md docs/ Agents.md AGENTS.md tests/cli tests/test_package astrid/packs/_core

echo '=== STATUS ==='
git status --short
git check-ignore -v remotion/node_modules remotion/out remotion/build dist 2>/dev/null || true

echo '=== COMMITS ==='
git log --oneline b1c5f53c..HEAD
```

Also list whether `remotion/package-lock.json` is in the epic (it SHOULD be — committed lockfile is required, not a generated artifact to reject). Distinguish lockfile (required) from `node_modules` (forbidden).

Confirm no second lock, second Node project, `model.py`, capture stack.

Working tree: untracked `.codex/`, `.vscode/`, mp3 after `git rm --cached` is EXPECTED and OK. Untracked `.oracle/briefs` leftovers from prior oracle dispatches are OK. Flag anything that looks like a generated media/bundle that should have been cleaned.

## Output (<250 words)

```
EPIC_CORE: empty | <paths>
BATCH_CORE: empty | <paths>
EPIC_FILE_COUNT: N
BATCH6_FILES: <list>
FORBIDDEN: none | <paths>
LOCKFILE_PRESENT: yes | no
SECOND_STACK: none | <what>
T6.2_BROAD_DOCS: none | <paths>
WORKTREE: clean-enough | dirty <what matters>
COMMITS: <oneline list>
ISSUES: none | numbered checkpoint-failing problems only
NOTES: non-blocking
```

Take a position. Do not hedge.
