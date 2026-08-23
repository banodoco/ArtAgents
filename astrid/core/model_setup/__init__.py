"""Sidecar setup journal + honest advertisement (Batch B8, doc 27 §6.1).

Modules:

- :mod:`journal` — the fsync'd replay log, boot-time resolution, and the
  single stamp read probes consult.
- :mod:`manifest` — signed versioned distribution manifests + tier
  discovery.
- :mod:`preflight` — disk headroom (download + working + output).
- :mod:`acquire` — Range-resumable setup-mode acquisition (the only
  sanctioned outbound networking in the product).
- :mod:`repair` — ``doctor setup``: deep re-hash, targeted repair,
  journal reconciliation from filesystem reality.

One authority: installed-ness is proven by artifact bytes + manifest
stamps + SQLite advertisement; this journal is a replay log, never a
second database.
"""

from astrid.core.model_setup.acquire import (
    AcquisitionError,
    AcquisitionResult,
    acquire_artifact,
)
from astrid.core.model_setup.journal import (
    ArtifactState,
    JournalSnapshot,
    SetupJournal,
    SetupJournalError,
    journal_path,
    kill_boundary,
    read_stamp,
    resolve_boot_state,
    setup_dir,
)
from astrid.core.model_setup.manifest import (
    DistributionManifest,
    ManifestError,
    discover_environment,
    load_manifest,
    make_manifest,
    select_bundle,
)
from astrid.core.model_setup.preflight import (
    DiskPreflightError,
    preflight_disk,
    require_disk,
)
from astrid.core.model_setup.repair import (
    RepairReport,
    doctor_setup,
    reconcile_journal,
)

__all__ = [
    "AcquisitionError",
    "AcquisitionResult",
    "ArtifactState",
    "DiskPreflightError",
    "DistributionManifest",
    "JournalSnapshot",
    "ManifestError",
    "RepairReport",
    "SetupJournal",
    "SetupJournalError",
    "acquire_artifact",
    "discover_environment",
    "doctor_setup",
    "journal_path",
    "kill_boundary",
    "load_manifest",
    "make_manifest",
    "preflight_disk",
    "read_stamp",
    "reconcile_journal",
    "require_disk",
    "resolve_boot_state",
    "select_bundle",
    "setup_dir",
]
