"""
M0 Contract Interfaces — Python Protocol definitions.

This is the single M0 handoff contract for interface signatures.
M1 MUST port or import from this shape rather than creating a competing
contracts.py location under builtin/dataset_build/.

These are Protocol classes — non-runtime, no registration, no package creation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator, Protocol, runtime_checkable

# ── Forward type references (schemas frozen in contracts/schemas/) ──────────

# CandidateItem: contracts/schemas/candidate-item.schema.json
CandidateItem = dict[str, Any]

# ReviewItem: contracts/schemas/review-item.schema.json
ReviewItem = dict[str, Any]

# ReviewDecision: contracts/schemas/review-decision.schema.json
ReviewDecision = dict[str, Any]

# RunState: contracts/schemas/run-state.schema.json
RunState = dict[str, Any]

# FilterStats: contracts/schemas/filter-stats.schema.json
FilterStats = dict[str, Any]


# ── Result types ────────────────────────────────────────────────────────────

class CaptionResult:
    """Result from a caption provider."""
    text: str
    schema_version: int
    confidence: float
    model: str
    raw_response: dict[str, Any] | None = None

    def __init__(self, text: str, schema_version: int = 1,
                 confidence: float = 0.0, model: str = "",
                 raw_response: dict[str, Any] | None = None):
        self.text = text
        self.schema_version = schema_version
        self.confidence = confidence
        self.model = model
        self.raw_response = raw_response


class FilterResult:
    """Result from a filter stage."""
    passed: list[ReviewItem]
    rejected: list[ReviewItem]
    stats: FilterStats

    def __init__(self, passed: list[ReviewItem], rejected: list[ReviewItem],
                 stats: FilterStats):
        self.passed = passed
        self.rejected = rejected
        self.stats = stats


class CostEstimate:
    """Estimated cost for a compute operation."""
    gpu_hours: float
    estimated_cost_usd: float
    backend: str
    details: dict[str, Any]

    def __init__(self, gpu_hours: float, estimated_cost_usd: float,
                 backend: str, details: dict[str, Any] | None = None):
        self.gpu_hours = gpu_hours
        self.estimated_cost_usd = estimated_cost_usd
        self.backend = backend
        self.details = details or {}


class ComputeHandle:
    """Opaque handle to a provisioned compute resource."""
    backend: str
    pod_id: str
    status: str
    metadata: dict[str, Any]

    def __init__(self, backend: str, pod_id: str, status: str = "provisioned",
                 metadata: dict[str, Any] | None = None):
        self.backend = backend
        self.pod_id = pod_id
        self.status = status
        self.metadata = metadata or {}


# ── Protocol interfaces ─────────────────────────────────────────────────────

@runtime_checkable
class SourceProvider(Protocol):
    """Acquire candidate media items from a source.

    First concrete provider: YouTube/video acquisition.
    Placeholders: local_folder, reigh_asset, stock_api, generated,
                  image, audio, paired.
    """
    def acquire(self, config: dict[str, Any]) -> Iterator[CandidateItem]:
        """Yield CandidateItems from the configured source.

        Args:
            config: Provider-specific config block from dataset config.

        Yields:
            CandidateItem dicts conforming to candidate-item.schema.json.
        """
        ...


@runtime_checkable
class CaptionProvider(Protocol):
    """Generate captions for a candidate media item.

    First concrete provider: wraps existing visual/video understanding paths.
    """
    def caption(self, item: CandidateItem, config: dict[str, Any]) -> CaptionResult:
        """Generate a caption for a candidate item.

        Args:
            item: CandidateItem to caption.
            config: Caption provider config from dataset config.

        Returns:
            CaptionResult with text, confidence, model info.
        """
        ...


@runtime_checkable
class FilterStage(Protocol):
    """Apply a filter to a set of review items.

    Filters are composable and ordered. Each stage receives items from the
    previous stage and returns passed/rejected subsets plus stats.
    """
    @property
    def stage_id(self) -> str:
        """Unique identifier for this filter stage."""
        ...

    @property
    def stage_order(self) -> int:
        """Execution order in the filter pipeline (0-based)."""
        ...

    def apply(self, items: list[ReviewItem], state: RunState,
              config: dict[str, Any]) -> FilterResult:
        """Apply this filter stage.

        Args:
            items: Review items to filter.
            state: Current run state (read-only for filter decisions).
            config: Filter stage config from dataset config.

        Returns:
            FilterResult with passed, rejected, and stats.
        """
        ...


@runtime_checkable
class ManifestAdapter(Protocol):
    """Export accepted review items to a trainer-specific manifest format.

    First concrete adapter: ai-toolkit-ltx (flat clips with caption sidecars).
    """
    @property
    def format_id(self) -> str:
        """Manifest format identifier (e.g., 'ai-toolkit-ltx')."""
        ...

    def validate(self, items: list[ReviewItem]) -> list[str]:
        """Validate that items can be exported to this format.

        Args:
            items: Accepted ReviewItems to validate.

        Returns:
            List of error strings. Empty list means valid.
        """
        ...

    def export(self, accepted_items: list[ReviewItem]) -> Path:
        """Export accepted items to a manifest file.

        Args:
            accepted_items: ReviewItems with review_status='accepted'.

        Returns:
            Path to the written manifest file.
        """
        ...


@runtime_checkable
class TrainerAdapter(Protocol):
    """Adapter for a specific training framework.

    First concrete adapter: ai-toolkit-ltx.
    """
    @property
    def trainer_id(self) -> str:
        """Trainer identifier (e.g., 'ai-toolkit-ltx')."""
        ...

    def validate_manifest(self, manifest_path: Path) -> list[str]:
        """Validate that a manifest is compatible with this trainer.

        Args:
            manifest_path: Path to the manifest file.

        Returns:
            List of error strings. Empty list means valid.
        """
        ...

    def build_config(self, dataset_manifest: Path,
                     trainer_config: dict[str, Any]) -> Path:
        """Build the trainer-specific config from dataset manifest + trainer config.

        Args:
            dataset_manifest: Path to the canonical or adapter manifest.
            trainer_config: Trainer-specific config block.

        Returns:
            Path to the written trainer config file.
        """
        ...


@runtime_checkable
class ComputeBackend(Protocol):
    """Provision and manage compute resources for training.

    First concrete backend: RunPod.
    """
    @property
    def backend_id(self) -> str:
        """Backend identifier (e.g., 'runpod')."""
        ...

    def provision(self, config: dict[str, Any]) -> ComputeHandle:
        """Provision compute resources.

        Args:
            config: Compute backend config block.

        Returns:
            ComputeHandle for the provisioned resource.
        """
        ...

    def teardown(self, handle: ComputeHandle) -> None:
        """Tear down provisioned compute resources.

        Args:
            handle: Handle from provision().
        """
        ...

    def estimate_cost(self, config: dict[str, Any]) -> CostEstimate:
        """Estimate cost for a compute configuration.

        Args:
            config: Compute backend config block.

        Returns:
            CostEstimate with gpu_hours and estimated_cost_usd.
        """
        ...
