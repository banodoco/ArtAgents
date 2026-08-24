# Explore E1: VibeComfy scratchpad format + digest pinning
Read .oracle/northstar.md + .oracle/agent_goal.md first. Repo: this worktree (branch phase-b).
Question: for template-digest pinning of Comfy workflows — what exactly gets digested (ready-template YAML? resolved workflow JSON? both)? Do templates live in this repo or in the external vibecomfy package? Can pins be verified offline?
Investigate: the vibecomfy dependency (comfy_wrap requirements GitHub pin), packs/executors using it, any scratchpad/template code, tests.
Report: ranked findings <300 words with file:line evidence + recommended pinning mechanism for B-1.
