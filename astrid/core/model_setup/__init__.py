"""Sidecar setup journal + honest advertisement (Batch B8, doc 27 §6.1).

Modules:

- :mod:`journal` — the fsync'd replay log, boot-time resolution, and the
  single stamp read probes consult.
- :mod:`manifest` — signed versioned distribution manifests + tier
  discovery.
- :mod:`preflight` — disk headroom (download + working + output).
- :mod:`acquire` — Range-resumable setup-mode acquisition (the only
  sanctioned outbound networking in the product).

One authority: installed-ness is proven by artifact bytes + manifest
stamps + SQLite advertisement; this journal is a replay log, never a
second database.
"""

__all__: tuple[str, ...] = ()
