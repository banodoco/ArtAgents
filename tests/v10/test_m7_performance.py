"""Report-only Sprint 7 performance evidence for the representative fixture."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pytest

from astrid.application import compose_standard_application
from tests.v10._m7_fixture import build_m7_fixture

SAMPLE_COUNT = 3
WARM_SAMPLE_COUNT = 8


def _elapsed(operation: Callable[[], Any]) -> float:
    started = time.perf_counter_ns()
    operation()
    return (time.perf_counter_ns() - started) / 1_000_000


def _percentile(samples: list[float], fraction: float) -> float:
    ordered = sorted(samples)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _statistics(samples: list[float]) -> dict[str, Any]:
    assert samples
    return {
        "sample_count": len(samples),
        "samples_ms": [round(value, 6) for value in samples],
        "median_ms": round(_percentile(samples, 0.50), 6),
        "p95_ms": round(_percentile(samples, 0.95), 6),
        "max_ms": round(max(samples), 6),
    }


def _assert_success(result: Any) -> Any:
    assert result.ok, result.error
    return result.data


def _gallery_and_list(app: Any) -> None:
    project = _assert_success(app.projects_service.list())
    timelines = _assert_success(app.timelines_service.list("m7-representative"))
    media = _assert_success(app.media_service.list("m7-representative"))
    gallery = (app.projects_root / "gallery" / "index.html").read_bytes()
    assert project and timelines and len(media) == 4 and gallery


def _timeline_load_save(app: Any, ordinal: int) -> None:
    loaded = _assert_success(
        app.timelines_service.show("m7-representative", "main")
    )
    saved = _assert_success(
        app.timelines_service.save(
            "m7-representative",
            "main",
            config=loaded["config"],
            registry=loaded["registry"],
            expected_version=loaded["config_version"],
            idempotency_key=f"m7-performance-save-{ordinal}",
        )
    )
    assert saved["config_version"] == loaded["config_version"] + 1


def _change_feed(app: Any) -> None:
    project_id = "m7-project-id"
    events = app.event_log.list_events(project_id=project_id)
    assert events


def _media_verify(app: Any, ordinal: int) -> None:
    verified = _assert_success(
        app.media_service.verify(
            "m7-representative",
            "m7-media-managed-source",
            realm="managed_local",
            idempotency_key=f"m7-performance-verify-{ordinal}",
        )
    )
    assert verified["id"] == "m7-media-managed-source"


def _bootstrap(root: Path) -> None:
    app = compose_standard_application(projects_root=root)
    app.close()


def _fresh_operation(
    root: Path,
    operation: Callable[[Any, int], None],
    ordinal: int,
) -> float:
    build_m7_fixture(root)
    with compose_standard_application(projects_root=root) as app:
        return _elapsed(lambda: operation(app, ordinal))


def _environment() -> dict[str, str]:
    try:
        pytest_version = importlib.metadata.version("pytest")
    except importlib.metadata.PackageNotFoundError:
        pytest_version = pytest.__version__
    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
        "pytest": pytest_version,
    }


def test_m7_performance_report_records_cold_warm_report_only_evidence(
    tmp_path: Path,
) -> None:
    """Measure supported public reads/writes without inventing host budgets."""
    artifact_path = tmp_path / "performance.json"
    fixture_root = tmp_path / "warm-fixture"
    fixture = build_m7_fixture(fixture_root)
    assert fixture.snapshot["fixture_identity"]["fixture_id"] == fixture.spec["fixture_id"]

    operations: dict[str, Callable[[Any, int], None]] = {
        "gallery_list": lambda app, _ordinal: _gallery_and_list(app),
        "timeline_load_save": _timeline_load_save,
        "change_feed": lambda app, _ordinal: _change_feed(app),
        "media_verify": _media_verify,
    }
    measurements: dict[str, dict[str, Any]] = {}

    cold_bootstrap: list[float] = []
    for ordinal in range(SAMPLE_COUNT):
        root = tmp_path / f"cold-bootstrap-{ordinal}"
        build_m7_fixture(root)
        cold_bootstrap.append(_elapsed(lambda root=root: _bootstrap(root)))
    measurements["bootstrap"] = {
        "definition": "fresh fixture root, first standard application composition",
        "cold": _statistics(cold_bootstrap),
    }

    warm_bootstrap = [_elapsed(lambda: _bootstrap(fixture_root)) for _ in range(SAMPLE_COUNT)]
    measurements["bootstrap"]["warm"] = _statistics(warm_bootstrap)

    for name, operation in operations.items():
        cold = [
            _fresh_operation(
                tmp_path / f"cold-{name}-{ordinal}", operation, ordinal
            )
            for ordinal in range(SAMPLE_COUNT)
        ]
        with compose_standard_application(projects_root=fixture_root) as app:
            warm = [
                _elapsed(lambda ordinal=ordinal: operation(app, ordinal))
                for ordinal in range(WARM_SAMPLE_COUNT)
            ]
        measurements[name] = {
            "definition": "public repository-backed operation on the fixture",
            "cold": _statistics(cold),
            "warm": _statistics(warm),
        }

    artifact = {
        "schema": "astrid.m7_performance.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture": {
            "fixture_id": fixture.spec["fixture_id"],
            "fixture_version": fixture.spec["fixture_version"],
            "spec_sha256": fixture.snapshot["fixture_identity"]["spec_sha256"],
            "source": str(fixture.spec["provenance"]["source"]),
            "baseline": fixture.spec["baseline"],
        },
        "environment": _environment(),
        "sample_policy": {
            "cold_samples": SAMPLE_COUNT,
            "warm_samples": WARM_SAMPLE_COUNT,
            "clock": "time.perf_counter_ns",
            "unit": "milliseconds",
        },
        "budget_status": "unresolved",
        "budget_source": None,
        "report_only": True,
        "comparisons": [],
        "operations": measurements,
    }
    artifact_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    persisted = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert persisted["budget_status"] == "unresolved"
    assert persisted["report_only"] is True
    assert set(persisted["operations"]) == {
        "bootstrap",
        "gallery_list",
        "timeline_load_save",
        "change_feed",
        "media_verify",
    }


__all__ = ["test_m7_performance_report_records_cold_warm_report_only_evidence"]
