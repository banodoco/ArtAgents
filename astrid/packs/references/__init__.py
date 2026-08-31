"""References schema pack (in-tree, explicitly registered).

The references pack owns the normative ``project_references``,
``media_references``, and ``reference_links`` tables plus the namespaced
``reference.*`` vocabulary declared in ``schema-pack.yaml`` next to this
module. Every locked reference enum/check/index and kernel-currency
association (``media_id``, ``context_task_id``) is preserved verbatim.

The generated-client ``media references`` product surface owns reference
commands. The historical repository implementation remains available only
through an explicit legacy/migration import; importing this package for
product discovery never loads its kernel-writer dependencies.
"""

from __future__ import annotations

# Repository symbols are intentionally not re-exported from this package.
# Offline migration/conformance callers must import ``repository`` explicitly;
# product discovery and package imports therefore have no lazy authority hook.
