# Explore E6: boot manifest ownership and digest scope
Read .oracle/northstar.md + .oracle/agent_goal.md first. No boot manifest exists yet.
Question: who emits the executor-build manifest (application composition root vs local_bridge_server), where does it live under the managed root, and what does the registry digest cover (REGISTRY entries? conformance fixtures? both?)? Investigate serve composition root (_dispatch_serve), capabilities.py REGISTRY, receipts/service.py provenance fields.
Report: <300 words with file:line evidence + ONE recommended design.
