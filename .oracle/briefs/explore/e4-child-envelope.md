# Explore E4: orchestrator child-admission envelope shape
Read .oracle/northstar.md + .oracle/agent_goal.md first. Code: astrid/core/integrations/reigh/capabilities.py + bridge_service.py admit_child (exists post-Phase-A).
Question: pin the deterministic child key rule — exactly which fields enter the idempotency key (parent ULID, role, index — NOT attempt number), how the envelope validates against the live parent fence, and what test coverage exists today. Identify gaps B-3 must close for travel/join/edit families.
Report: findings <300 words with file:line evidence + the precise envelope spec to implement/test.
