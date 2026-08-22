# Explore E5: setup-journal placement vs product SQLite (North-Star-sensitive)
Read .oracle/northstar.md + .oracle/agent_goal.md first.
Question: where should the model-acquisition setup journal live — inside product SQLite (new migration/table) or as a sidecar journal file (replay log, not authority)? North Star says one SQLite file is the only STRUCTURED truth; setup must work BEFORE the product DB exists. Investigate existing journal/file patterns in core/io/, boot sequence, doctor. Recommend ONE placement with rationale.
Report: <300 words with evidence + recommendation.
