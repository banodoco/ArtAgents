---
name: vibecomfy-edit
description: Apply a typed VibeComfy delta batch to an admitted ComfyUI UI workflow.
---

# VibeComfy edit

Invoke `vibecomfy.edit` as an executor capability with a UI workflow and a
typed operations document. The only accepted operations are `edit_node`,
`add_node`, `remove_node`, `upsert_link`, `remove_link`, and `set_node_mode`,
wrapped by one atomic `edit_batch`. The Python-like output is inspection only;
arbitrary Python is never accepted as mutation input.
