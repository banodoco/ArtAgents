"""Pure event-to-display projection used for migrated event fixtures.

Runtime event storage and versioning live behind the generated workspace
client.  Astrid deliberately exposes no backend, append request, stream-ref,
or filesystem selector contract from this package.
"""
from .projector import DisplayProjection, project_display

__all__ = [
    "DisplayProjection",
    "project_display",
]
