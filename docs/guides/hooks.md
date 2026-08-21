# HOOKS — retired

> **Retired.** This document described the Claude Code Stop hook that
> re-injected task-mode rules (`astrid next` preamble + current step) into
> Claude's next turn. The task-mode runtime it served was removed with the
> v10 cutover: session binding, `next`/`ack`, and the filesystem task-run
> store are gone, so there is no task-mode rule stream to re-inject.

Agents orient through the eight-family CLI census and the core skill, not a
stop hook:

```bash
python3 -m astrid --help          # the eight-family census
python3 -m astrid doctor --json   # read-only health check
```

The agent-facing guidance lives in `astrid/packs/_core/skill/SKILL.md`;
human-facing setup lives in [getting-started.md](../getting-started.md).
