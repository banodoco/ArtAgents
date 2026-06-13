"""Arnold host package — the gateway-side StepwiseDriver operator.

This package contains the Astrid-side host glue that bridges the existing
task-engine lifecycle (start / next / ack / status / abort / hook) to
Arnold's ``StepwiseDriver`` protocol and shape registry when ``--engine
arnold`` is selected.

Design constraints (settled — do not re-litigate):

* **SD1:** Arnold cursor files live under the Astrid run directory
  (``RuntimeEnvelope.artifact_root``); no second checkpoint store is
  introduced.
* **SD2:** Shape selection uses explicit workflow IDs: ``we.refine_image``,
  ``we.best_of_4``, ``text_analysis.summarize``.  These are an Arnold host
  allowlist, not generic orchestrator migration.
* **SD3:** Human resume wire format is ``{decision: {action, notes,
  state_patch}, produces_reverify: {artifacts, inputs}}``.  CLI sugar like
  ``--decision approve|reject`` normalizes into the wire format.

**Import boundary:** This ``__init__.py`` must remain free of Arnold
imports — even a lazy import would contaminate the core startup path.
Submodules that *do* require Arnold (``compat``, ``driver``, ``envelope``,
``invocation``, ``hooks``) import it lazily inside function bodies or at
the point of first use.  The shapes, registry, render, and CLI modules use
only the host-internal abstractions and never import Arnold directly.
"""

from __future__ import annotations

# ── Package version ───────────────────────────────────────────────────────────

__version__ = "0.1.0"

# ── Public re-exports (no Arnold imports) ─────────────────────────────────────
# These symbols are exposed so that gateway routing and lifecycle modules can
# import from a single host facade without touching Arnold-aware submodules.

from astrid.core.integrations.arnold.host.registry import (
    ShapeRegistry,
    get_host_shape_registry,
)
from astrid.core.integrations.arnold.host.shapes import (
    WE_BEST_OF_4_ID,
    WE_REFINE_IMAGE_ID,
    TEXT_ANALYSIS_SUMMARIZE_ID,
    ALLOWLISTED_SHAPE_IDS,
)

__all__ = [
    "ShapeRegistry",
    "get_host_shape_registry",
    "WE_BEST_OF_4_ID",
    "WE_REFINE_IMAGE_ID",
    "TEXT_ANALYSIS_SUMMARIZE_ID",
    "ALLOWLISTED_SHAPE_IDS",
]
