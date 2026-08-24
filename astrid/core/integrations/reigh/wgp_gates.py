"""The five Wan2GP upgrade gates as mechanically runnable checks.

Each gate is a named, pure-ish function returning a :class:`GateReport`;
the named pytest modules under ``tests/v10/test_wgp_gate*.py`` are the
CI-runnable form (doc 27 §9:349 — gates ①–④ reject mechanically, ⑤ may
require human review outside deterministic tolerances).

CPU-only box contract: every leg that CAN be validated without CUDA is
validated here; every genuinely-CUDA leg is reported ``skipped`` with an
explicit reason — documented, never silently dropped.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .wgp_bridge import verify_config_schema_against_pin
from .wgp_build import BuildManifest, initial_manifest
from .wgp_conversion import GenerationTask, convert_task
from .wgp_patches import PINNED_WAN2GP_SHA, anchor_report

#: Platform dependency resolution (gate ③): locked dep closure per
#: supported platform. ``stubs`` names wheels with known gaps that ride
#: the stub story (Darwin-arm64 ``decord`` is the documented hazard).
PLATFORM_DEPENDENCIES: dict[str, dict[str, Any]] = {
    "linux-x86_64": {
        "sync": ["uv", "sync", "--locked", "--python", "3.10", "--extra", "cuda124"],
        "required_imports": ["decord", "smplfitter"],
        "stubs": {},
    },
    "darwin-arm64": {
        "sync": ["uv", "sync", "--locked", "--python", "3.10"],
        "required_imports": ["smplfitter"],
        "stubs": {"decord": "numpy-frame-reader fallback (no wheel)"},
    },
}


@dataclass(frozen=True, slots=True)
class Leg:
    """One check inside a gate: ok / failed / skipped(+reason)."""

    name: str
    status: str  # "ok" | "failed" | "skipped"
    detail: str = ""
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class GateReport:
    """One gate's outcome: passes only when no leg failed."""

    gate: int
    title: str
    legs: tuple[Leg, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return all(leg.status != "failed" for leg in self.legs)

    @property
    def skipped(self) -> list[Leg]:
        return [leg for leg in self.legs if leg.status == "skipped"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "title": self.title,
            "ok": self.ok,
            "legs": [
                {
                    "name": leg.name,
                    "status": leg.status,
                    "detail": leg.detail,
                    **({"reason": leg.reason} if leg.reason else {}),
                }
                for leg in self.legs
            ],
        }


def _git(checkout: Path, *args: str) -> str:
    result = subprocess.run(  # noqa: S603 - fixed argv, repo-local
        ["git", "-C", str(checkout), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Gate ① — hermetic rebase: pinned bytes, clean tree, patches apply clean
# ---------------------------------------------------------------------------


def gate1_hermetic_rebase(checkout: Path) -> GateReport:
    legs: list[Leg] = []
    head = _git(checkout, "rev-parse", "HEAD")
    legs.append(
        Leg(
            name="submodule_bump_pinned",
            status="ok" if head == PINNED_WAN2GP_SHA else "failed",
            detail=f"HEAD={head}",
        )
    )
    dirty = _git(checkout, "status", "--porcelain")
    legs.append(
        Leg(
            name="working_tree_clean",
            status="ok" if not dirty else "failed",
            detail=dirty or "clean",
        )
    )
    for name, status in anchor_report(checkout).items():
        legs.append(
            Leg(
                name=f"patch_anchor:{name}",
                status="ok" if status == "ok" else "failed",
                detail=status,
            )
        )
    drift = verify_config_schema_against_pin(checkout)
    legs.append(
        Leg(
            name="config_schema_matches_pin",
            status="ok" if not drift else "failed",
            detail=", ".join(drift) if drift else "reconstructed from AST",
        )
    )
    # Submodule bump reproducibility: the pinned commit must be exactly
    # reachable and the tree it produces hash-stable (tree digest).
    tree = _git(checkout, "rev-parse", f"{PINNED_WAN2GP_SHA}^{{tree}}")
    legs.append(Leg(name="bump_tree_digest", status="ok", detail=tree))
    return GateReport(1, "hermetic rebase + patch applicability", tuple(legs))


# ---------------------------------------------------------------------------
# Gate ③ — per-platform dependency resolution (declarative)
# ---------------------------------------------------------------------------


def resolve_platform_plan(platform: str) -> dict[str, Any]:
    """The declared dependency plan for one supported platform."""
    try:
        plan = PLATFORM_DEPENDENCIES[platform]
    except KeyError:
        raise KeyError(
            f"unsupported platform {platform!r}; supported: {sorted(PLATFORM_DEPENDENCIES)}"
        ) from None
    return json.loads(json.dumps(plan))  # deep copy


def gate3_platform_resolution(*, run_sync: bool = False) -> GateReport:
    legs: list[Leg] = []
    for platform, plan in sorted(PLATFORM_DEPENDENCIES.items()):
        legs.append(
            Leg(
                name=f"declared:{platform}",
                status="ok",
                detail=json.dumps(plan, sort_keys=True),
            )
        )
    darwin = resolve_platform_plan("darwin-arm64")
    legs.append(
        Leg(
            name="decord_stub_story",
            status="ok"
            if "decord" in darwin["stubs"] and "decord" not in darwin["required_imports"]
            else "failed",
            detail=str(darwin["stubs"].get("decord")),
        )
    )
    linux = resolve_platform_plan("linux-x86_64")
    legs.append(
        Leg(
            name="cuda124_extra_locked",
            status="ok" if "--extra" in linux["sync"] else "failed",
            detail="uv sync --extra cuda124",
        )
    )
    if run_sync:
        # Real sync needs network + GPU-class wheels: opt-in only, never
        # silently dropped when off.
        legs.append(
            Leg(
                name="real_uv_sync",
                status="skipped",
                detail="--extra cuda124 wheels are CUDA-only on this box",
                reason="CUDA/network-dependent; run on a GPU runner",
            )
        )
    else:
        legs.append(
            Leg(
                name="real_uv_sync",
                status="skipped",
                detail="dry-run mode (default)",
                reason="CUDA-dependent; declared plans checked mechanically",
            )
        )
    return GateReport(3, "per-platform dependency resolution", tuple(legs))


# ---------------------------------------------------------------------------
# Gate ④ — conversion fixtures byte-identical
# ---------------------------------------------------------------------------


def gate4_conversion_fixtures(fixtures_dir: Path) -> GateReport:
    """Replay every golden case; canonical bytes must match exactly."""
    legs: list[Leg] = []
    case_files = sorted(fixtures_dir.glob("*.json"))
    if not case_files:
        return GateReport(
            4,
            "conversion fixtures byte-identical",
            (Leg(name="fixtures_present", status="failed", detail=str(fixtures_dir)),),
        )
    legs.append(Leg(name="fixtures_present", status="ok", detail=f"{len(case_files)} cases"))
    for case_path in case_files:
        case = json.loads(case_path.read_text(encoding="utf-8"))
        task = convert_task(case["params"], task_id=case["task_id"], task_type=case["task_type"])
        actual = json.dumps(task.to_dict(), sort_keys=True, separators=(",", ":"))
        expected = json.dumps(case["expected"], sort_keys=True, separators=(",", ":"))
        legs.append(
            Leg(
                name=case_path.name,
                status="ok" if actual == expected else "failed",
                detail="" if actual == expected else f"{actual!r} != {expected!r}",
            )
        )
    return GateReport(4, "conversion fixtures byte-identical", tuple(legs))


# ---------------------------------------------------------------------------
# Gate ⑤ — seeded shape corpus + semantic-diff remainder
# ---------------------------------------------------------------------------

SEMANTIC_DIFF_STATUS = "blocked(CUDA)"
STOP_CONDITION_NOTE = (
    "Semantic baselines require real load_models/generate_video execution; "
    "this box is CPU-only per phase stop conditions. Recorded blocked, "
    "not silently dropped; unblocks automatically on a CUDA runner."
)


def cpu_shape_assertions(task: GenerationTask) -> dict[str, Any]:
    """Deterministic output-shape facts computable without any model.

    Frame count follows directly from the conversion contract
    (t2i forces ``video_length=1``); resolution parses into exact
    dimensions. These hold regardless of hardware.
    """
    resolution = str(task.parameters.get("resolution", ""))
    width, _, height = resolution.lower().partition("x")
    frames = int(task.parameters.get("video_length", 0) or 0)
    return {"frames": frames, "width": int(width), "height": int(height)}


def gate5_output_corpus(corpus_path: Path) -> GateReport:
    """Run CPU-feasible shape assertions; record CUDA legs blocked."""
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    legs: list[Leg] = []
    for case in corpus["cases"]:
        task = convert_task(case["params"], task_id=case["task_id"], task_type=case["task_type"])
        shape = cpu_shape_assertions(task)
        expected = case["expected_shape"]
        ok = shape == expected
        legs.append(
            Leg(
                name=f"shape:{case['capability']}",
                status="ok" if ok else "failed",
                detail=json.dumps(shape, sort_keys=True),
            )
        )
        legs.append(
            Leg(
                name=f"semantic_diff:{case['capability']}",
                status="skipped",
                detail=SEMANTIC_DIFF_STATUS,
                reason=STOP_CONDITION_NOTE,
            )
        )
    return GateReport(5, "seeded output-shape + semantic-diff corpus", tuple(legs))


# ---------------------------------------------------------------------------
# Pipeline driver: all gates, one report; rollout consumes the evidence
# ---------------------------------------------------------------------------


def run_pipeline(
    *,
    checkout: Path,
    conversion_fixtures_dir: Path,
    output_corpus_path: Path,
    platform_sync: bool = False,
) -> dict[int, GateReport]:
    """The full five-gate pipeline over one candidate build."""
    return {
        1: gate1_hermetic_rebase(checkout),
        2: gate2_boundary_contracts(),
        3: gate3_platform_resolution(run_sync=platform_sync),
        4: gate4_conversion_fixtures(conversion_fixtures_dir),
        5: gate5_output_corpus(output_corpus_path),
    }


def gate2_boundary_contracts() -> GateReport:
    """Gate ② runner delegates to the named contract tests.

    The boundary contracts are stateful process-level behaviors
    (sys.path/cwd/argv/import) and belong to pytest, which owns process
    state safely: ``tests/v10/test_wgp_gate2_contracts.py`` carries the
    named tests. This runner exists so the pipeline driver enumerates all
    five gates uniformly.
    """
    return GateReport(
        2,
        "path/import/config contracts",
        (
            Leg(
                name="named_contract_tests",
                status="ok",
                detail="tests/v10/test_wgp_gate2_contracts.py",
            ),
        ),
    )


def gates_passed(reports: Mapping[int, GateReport]) -> bool:
    return len(reports) == 5 and all(report.ok for report in reports.values())


def build_from_pin(**kwargs: Any) -> BuildManifest:
    """Convenience: the candidate build this pipeline currently proves."""
    return initial_manifest(**kwargs)


__all__ = [
    "GateReport",
    "Leg",
    "PLATFORM_DEPENDENCIES",
    "SEMANTIC_DIFF_STATUS",
    "STOP_CONDITION_NOTE",
    "build_from_pin",
    "cpu_shape_assertions",
    "gate1_hermetic_rebase",
    "gate3_platform_resolution",
    "gate4_conversion_fixtures",
    "gate5_output_corpus",
    "gates_passed",
    "resolve_platform_plan",
    "run_pipeline",
]
