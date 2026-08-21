"""Session-layer package — retained config/paths only.

The task-mode session machinery (binding, lease, identity, lifecycle, writer)
was retired with the legacy task runtime. This package now holds only the
long-lived config facade (``config``) and filesystem path helpers (``paths``),
which the kernel's preferences layer and the v10 suite still import.
"""
