# Explore: remote project commands (projects list/edit vs reigh executors)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle

Explore the remote `projects list` / `projects edit` surface vs the pack executors that would replace it. Start from:
- astrid/core/cli/project.py + astrid/core/cli/project_handlers.py (remote list/edit parsers + handlers; Reigh DataProvider use)
- astrid/core/integrations/reigh/data_provider.py, timeline_io.py
- astrid/packs/reigh/executors/reigh_data/ (run.py, executor.yaml, STAGE.md) — what reigh.reigh_data does today
- astrid/core/gateway/dispatch.py `reigh-data` verb and _dispatch_executor_main("reigh.reigh_data")
- astrid/core/gateway/__init__.py (verb allowlists — are projects list/edit gated differently?), help.py
- Timeline lookup/mutation flows: astrid/core/cli/timeline_*.py, tasks that call projects list/edit in docs/guides or STAGE.md files
- Tests covering projects list/edit (grep tests/ for 'projects list' / 'projects edit')

Report verified facts with file:line evidence: (1) exact semantics of remote `projects list` and `projects edit` (flags, what they read/write, where — local project store vs Reigh remote); (2) overlap with reigh.reigh_data executor (does reigh_data already do the lookup? the mutation?); (3) what a `reigh.timeline_edit` executor must cover that nothing does today (exact mutation verbs — timeline create/edit/delete? events?); (4) who calls projects list/edit in docs/scripts/STAGE files; (5) which tests pin the current CLI routes. Suggest: what to keep in kernel (generic local project-store commands), what to retire, and the reigh.timeline_edit executor spec. Ranked findings, <300 words.
