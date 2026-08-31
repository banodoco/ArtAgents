"""Executor-host model manifests and acquisition helpers.

Modules:

- :mod:`manifest` — signed versioned distribution manifests + tier
  discovery and artifact-id validation.
- :mod:`preflight` — disk headroom (download + working + output).
- :mod:`acquire` — host-owned Range-resumable acquisition.

These helpers are executor-host infrastructure only. They never open the
workspace, write a product sidecar, or advertise model availability. The host
owns the materialized bytes and verifies their manifest digest before use.
"""

__all__: tuple[str, ...] = ()
