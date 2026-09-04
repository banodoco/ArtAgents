---
name: vibecomfy-inspect
description: Inspect an admitted ComfyUI UI workflow through VibeComfy's readable IR.
---

# VibeComfy inspect

Invoke `vibecomfy.inspect` as an executor capability. It emits
`workflow-ir.py` and `inspection.json`; both are read-only projections. The
input UI JSON remains authoritative and this capability never lands edits.
