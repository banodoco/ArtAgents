# Explore E7: availability-probe truthfulness on a GPU-less box
Read .oracle/northstar.md + .oracle/agent_goal.md first. AVAILABILITY_PROBES are currently trivially true.
Question: define per-binding probe predicates that stay HONEST on a CPU-only box without permanently disabling the catalog — what does each capability family actually require at runtime (model weights present? comfy nodes? decord?), what can run CPU-only, and how should probes report partial availability (e.g. weights missing -> hidden with setup hint)?
Investigate: capabilities.py probe seam, vibecomfy/wgp runtime requirements, model download conventions.
Report: <300 words with evidence + recommended probe predicates table.
