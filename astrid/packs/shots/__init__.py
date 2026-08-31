"""Shots schema pack (in-tree, explicitly registered).

The shots pack owns the normative ``shots`` and ``shot_items`` tables plus
the namespaced ``shot.*`` vocabulary declared in ``schema-pack.yaml`` next
to this module. Every locked shot enum/check/index and kernel-currency
association (``media_id``) is preserved verbatim; the pack never FK's to or
imports the timeline pack.

The generated-client ``timelines shots`` product surface owns shot commands.
The historical repository implementation remains available only through an
explicit legacy/migration import; importing this package for product
discovery never loads its kernel-writer dependencies.
"""

from __future__ import annotations

# Repository symbols are intentionally not re-exported from this package.
# Offline migration/conformance callers must import ``repository`` explicitly;
# product discovery and package imports therefore have no lazy authority hook.
