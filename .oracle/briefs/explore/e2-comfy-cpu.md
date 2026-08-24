# Explore E2: ComfyUI CPU-mode viability on this CPU-only box
Read .oracle/northstar.md + .oracle/agent_goal.md first. This box has NO GPU.
Question: which tiny/deterministic ComfyUI workflows actually complete under ComfyUI CPU mode here vs needing a stub executor shim? Investigate vibecomfy CLI flags for CPU/device selection, whether a SaveImage-only or text-transform workflow can run without model weights, startup time, and what the minimal deterministic workflow looks like.
Report: ranked findings <300 words with evidence; verdict — real subprocess binding satisfiable on this box (yes/no + how).
