# Explore: first-party inventory provenance (discord_local / seedance_local)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle

Determine why discord_local and seedance_local are absent from the repo while the generated _core skill indexes them. Verified already: `git ls-files astrid/packs | grep -E 'discord_local|seedance_local'` → 0 files; no .gitignore entry matches them. They exist as untracked directories in the MAIN checkout (/Users/peteromalley/Documents/reigh-workspace/Astrid) but not in this worktree. Start from:
- astrid/packs/_core/skill/SKILL.md in THIS worktree: does it mention discord_local/seedance_local? (if the committed version does, quote the lines and the install command it suggests)
- astrid/skills/ registry/state.py + harnesses: how the installed-skills table and harness AGENTS.md blocks are generated — do they derive from live pack discovery (which would include the untracked packs on this machine)?
- astrid/core/pack/discovery.py: source-tree layer — does it walk the filesystem (finding untracked packs) or a tracked index?
- git log --oneline -- astrid/packs/discord_local (any history? probably none); git log -S 'discord_local' -- astrid/ (when did references appear?)
- .gitignore full contents (any pack-ignore patterns)
- Check the main checkout: git -C /Users/peteromalley/Documents/reigh-workspace/Astrid check-ignore -v astrid/packs/discord_local (why is it untracked?)

Report verified facts with file:line evidence: (1) whether committed _core skill references them (quote); (2) mechanism by which they appear in skill listings on this machine (filesystem walk vs index); (3) git history of any reference to them; (4) why they are untracked (check-ignore result or plain never-added). Verdict: are they stale references to remove, or a sign discovery walks the filesystem in a way that must be pinned? Ranked findings, <300 words.
