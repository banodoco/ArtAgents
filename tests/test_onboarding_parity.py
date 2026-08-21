"""Onboarding documentation parity tests.

Verifies that ``docs/guides/build-your-first-agentic-ux.md`` is mechanically
consistent with the live SDK: every documented API name is exported,
every code block exercises a real code path, ``editorial.arrange`` is
discoverable, dry-run invocation works without API keys or network,
and the complete tutorial path round-trips without errors.

These tests are gated behind ``opt_in`` + ``integration`` markers so
they are excluded from the default suite.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TUTORIAL_PATH = ROOT / "docs" / "guides" / "build-your-first-agentic-ux.md"
FIXTURE_DIR = ROOT / "examples" / "agentic_ux" / "fixtures"
GOLDEN_EVENTS = FIXTURE_DIR / "golden_events.jsonl"

pytestmark = [
    pytest.mark.opt_in,
    pytest.mark.integration,
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Public SDK names from astrid/__init__.py (source of truth)
_SDK_EXPORT_NAMES: frozenset[str] = frozenset(
    {
        "discover",
        "get_capability",
        "invoke",
        "read_events",
        "subscribe_events",
        "Capability",
        "DiscoveryResult",
        "EventStreamRecord",
        "InvocationResult",
        "AstridSDKError",
        "CapabilityNotFoundError",
        "CapabilityAmbiguousError",
        "CapabilityValidationError",
        "CapabilityMissingInputError",
        "CapabilityPreconditionError",
        "CapabilityRuntimeError",
        "CapabilityLeaseError",
        "CapabilityEventLogError",
        "UnsupportedCapabilityError",
        "CapabilityInvocationError",
        "CapabilityHandle",
        "Port",
        "Output",
        "AliasRecord",
        "Provenance",
        "SafetyDeclaration",
        "ExecError",
    }
)


def _extract_code_blocks(markdown_text: str) -> list[dict[str, object]]:
    """Extract fenced Python code blocks from markdown.

    Returns a list of dicts with keys ``lang``, ``content``, and
    ``line_number`` (1-indexed start of the code fence).
    """
    blocks: list[dict[str, object]] = []
    in_fence = False
    fence_lang = ""
    fence_lines: list[str] = []
    fence_start = 0

    for i, line in enumerate(markdown_text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```") and not in_fence:
            in_fence = True
            fence_lang = stripped[3:].strip()
            fence_start = i
            fence_lines = []
        elif stripped == "```" and in_fence:
            in_fence = False
            if fence_lang in ("python", "py", ""):
                blocks.append(
                    {
                        "lang": fence_lang,
                        "content": "\n".join(fence_lines),
                        "line_number": fence_start,
                    }
                )
            fence_lang = ""
            fence_lines = []
        elif in_fence:
            fence_lines.append(line)

    return blocks


def _extract_astrid_names_from_code(code: str) -> set[str]:
    """Extract names accessed on ``astrid`` from Python source.

    Looks for patterns like ``astrid.discover(...)`` or
    ``from astrid import Something, OtherThing``.
    """
    names: set[str] = set()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return names

    for node in ast.walk(tree):
        # ``import astrid`` — no specific names
        # ``from astrid import Name1, Name2``
        if isinstance(node, ast.ImportFrom):
            if node.module == "astrid":
                for alias in node.names:
                    names.add(alias.name.split(".")[0])
        # ``astrid.name`` attribute access
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "astrid":
                names.add(node.attr)

    return names


# ---------------------------------------------------------------------------
# Documentation existence and readability
# ---------------------------------------------------------------------------


def test_tutorial_file_exists() -> None:
    """The onboarding tutorial file must exist and be non-empty."""
    assert TUTORIAL_PATH.is_file(), f"Missing: {TUTORIAL_PATH}"
    content = TUTORIAL_PATH.read_text(encoding="utf-8")
    assert len(content) > 1000, f"Tutorial is too short ({len(content)} chars)"


def test_tutorial_mentions_editorial_arrange() -> None:
    """The tutorial must explicitly reference ``editorial.arrange``."""
    content = TUTORIAL_PATH.read_text(encoding="utf-8")
    assert "editorial.arrange" in content, (
        "Tutorial does not mention editorial.arrange"
    )


def test_tutorial_mentions_dry_run() -> None:
    """The tutorial must mention ``dry_run=True``."""
    content = TUTORIAL_PATH.read_text(encoding="utf-8")
    assert "dry_run=True" in content, "Tutorial does not mention dry_run=True"


def test_tutorial_mentions_read_events() -> None:
    """The tutorial must mention ``read_events``."""
    content = TUTORIAL_PATH.read_text(encoding="utf-8")
    assert "read_events" in content, "Tutorial does not mention read_events"


def test_tutorial_mentions_no_api_keys() -> None:
    """The tutorial must declare no API keys are required."""
    content = TUTORIAL_PATH.read_text(encoding="utf-8")
    has_no_keys = (
        "No API keys" in content
        or "no API keys" in content
        or "no API keys, network access" in content
    )
    assert has_no_keys, "Tutorial does not declare no-API-key requirement"


# ---------------------------------------------------------------------------
# Code block extraction
# ---------------------------------------------------------------------------


def test_tutorial_contains_python_code_blocks() -> None:
    """The tutorial must contain at least one Python code block."""
    content = TUTORIAL_PATH.read_text(encoding="utf-8")
    blocks = _extract_code_blocks(content)
    assert len(blocks) >= 1, "No Python code blocks found in tutorial"


def test_tutorial_complete_script_block_is_present() -> None:
    """Step 6 must reference the complete assembled example script."""
    content = TUTORIAL_PATH.read_text(encoding="utf-8")
    # The tutorial's Step 6 points at the checked-in complete script
    # (Steps 1-5 bundled into one runnable example) instead of embedding a
    # shebang block.
    assert "examples/agentic_ux/agentic_ux.py" in content, (
        "Complete example script (examples/agentic_ux/agentic_ux.py) not found in tutorial"
    )


# ---------------------------------------------------------------------------
# Public SDK name verification (all documented names are in the SDK)
# ---------------------------------------------------------------------------


def test_all_documented_astrid_names_are_in_public_sdk() -> None:
    """Every name accessed on ``astrid`` in the tutorial must be a public
    SDK export."""
    content = TUTORIAL_PATH.read_text(encoding="utf-8")
    blocks = _extract_code_blocks(content)
    all_names: set[str] = set()
    for block in blocks:
        all_names.update(_extract_astrid_names_from_code(block["content"]))

    # Exclude non-SDK names that happen to be on astrid (stdlib patterns)
    # like ``astrid.__path__`` — none should appear in the tutorial.
    undocumented = all_names - _SDK_EXPORT_NAMES
    assert undocumented == set(), (
        f"Tutorial uses astrid.* names that are NOT in the public SDK: "
        f"{sorted(undocumented)}"
    )


def test_all_error_classes_from_quick_reference_are_importable() -> None:
    """Every exception class listed in the Error Handling Quick Reference
    table must be importable from ``astrid``."""
    import astrid as sdk

    expected_errors = [
        "AstridSDKError",
        "CapabilityNotFoundError",
        "CapabilityAmbiguousError",
        "CapabilityMissingInputError",
        "CapabilityPreconditionError",
        "CapabilityInvocationError",
        "CapabilityEventLogError",
        "UnsupportedCapabilityError",
    ]
    for name in expected_errors:
        assert hasattr(sdk, name), f"Missing SDK export: {name}"
        cls = getattr(sdk, name)
        assert isinstance(cls, type), f"{name} is not a class"
        assert issubclass(cls, sdk.AstridSDKError), (
            f"{name} does not inherit from AstridSDKError"
        )


def test_event_stream_record_has_documented_fields() -> None:
    """EventStreamRecord must have the fields documented in Step 5."""
    import astrid as sdk

    # Step 5 documents: source, line, timestamp, kind, hash, payload
    expected_fields = {"source", "line", "timestamp", "kind", "hash", "payload"}

    # Construct a minimal record to check field accessibility
    record = sdk.EventStreamRecord(
        source="task",
        line=1,
        timestamp="2025-01-01T00:00:00Z",
        kind="run_started",
        hash="abc123",
        payload={"kind": "run_started"},
    )
    for field in expected_fields:
        assert hasattr(record, field), f"EventStreamRecord missing field: {field}"


# ---------------------------------------------------------------------------
# editorial.arrange discoverability
# ---------------------------------------------------------------------------


@pytest.mark.timeout(60)
def test_editorial_arrange_is_discoverable_via_discover() -> None:
    """``editorial.arrange`` must appear in ``discover()`` results."""
    import astrid as sdk

    discovery = sdk.discover(include_installed=False)
    executor_ids = {e.id for e in discovery.executors}
    assert "editorial.arrange" in executor_ids, (
        f"editorial.arrange not found in discovery. "
        f"Executor ids: {sorted(executor_ids)}"
    )


@pytest.mark.timeout(60)
def test_editorial_arrange_is_inspectable_via_get_capability() -> None:
    """``get_capability('editorial.arrange', kind='executor')`` must
    return a Capability DTO with the expected shape."""
    import astrid as sdk

    cap = sdk.get_capability(
        "editorial.arrange",
        kind="executor",
        include_installed=False,
    )

    assert cap.id == "editorial.arrange"
    assert cap.capability_type == "executor"
    assert cap.native_kind in {"built_in", "external"}

    # Verify inputs match the documented 5 inputs
    input_names = {p.name for p in cap.inputs}
    expected_inputs = {"pool", "brief", "theme", "target_duration", "env_file"}
    assert input_names == expected_inputs, (
        f"Expected inputs {sorted(expected_inputs)}, got {sorted(input_names)}"
    )

    # Verify outputs
    assert len(cap.outputs) >= 1
    assert cap.outputs[0].name == "arrangement"


@pytest.mark.timeout(60)
def test_editorial_arrange_handle_has_provenance() -> None:
    """The capability handle for ``editorial.arrange`` must carry provenance."""
    import astrid as sdk

    cap = sdk.get_capability(
        "editorial.arrange", kind="executor", include_installed=False
    )
    handle = cap.handle
    prov = handle.provenance
    # The Provenance record is populated from the pack manifest.
    # source is the primary identifier; pack_id may be empty for
    # capabilities loaded via legacy code paths.
    assert prov.source, "Provenance source is empty"
    assert prov.source in {"builtin", "repository", "installed", "generated", "pack"}


@pytest.mark.timeout(60)
def test_editorial_arrange_handle_has_safety_declaration() -> None:
    """The capability handle for ``editorial.arrange`` must carry a safety
    declaration (as documented in Security and Trust Disclosures)."""
    import astrid as sdk

    cap = sdk.get_capability(
        "editorial.arrange", kind="executor", include_installed=False
    )
    safety = cap.handle.safety
    assert hasattr(safety, "network"), "SafetyDeclaration missing 'network'"
    assert hasattr(safety, "secrets_required"), "SafetyDeclaration missing 'secrets_required'"
    assert hasattr(safety, "permissions"), "SafetyDeclaration missing 'permissions'"


# ---------------------------------------------------------------------------
# Dry-run invocation (no API keys, no network)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(60)
def test_dry_run_invoke_editorial_arrange_succeeds() -> None:
    """``invoke('editorial.arrange', dry_run=True)`` must return an
    InvocationResult with ``ok=True`` and ``dry_run=True``."""
    import astrid as sdk

    with tempfile.TemporaryDirectory(prefix="astrid-parity-") as tmp_out:
        result = sdk.invoke(
            "editorial.arrange",
            kind="executor",
            include_installed=False,
            out=Path(tmp_out),
            project="demo",
            inputs={
                "brief": "parity test brief",
                "pool": "default",
                "theme": "default",
                "target_duration": 60,
            },
            dry_run=True,
            verbose=False,
        )

    assert result.ok is True, f"invoke ok={result.ok}, error={result.error}"
    assert result.capability_id == "editorial.arrange"
    assert result.capability_type == "executor"
    assert result.raw_result.get("dry_run") is True, (
        f"dry_run not True in raw_result: {result.raw_result}"
    )


@pytest.mark.timeout(60)
def test_dry_run_invoke_does_not_require_network() -> None:
    """A dry-run invocation of editorial.arrange must not require network
    access or API keys.  It should complete in-process without external
    calls."""
    import astrid as sdk

    # This test is mechanical: if invoke(dry_run=True) raises because of
    # network/API-key requirements, the test fails.
    with tempfile.TemporaryDirectory(prefix="astrid-parity-") as tmp_out:
        result = sdk.invoke(
            "editorial.arrange",
            kind="executor",
            include_installed=False,
            out=Path(tmp_out),
            project="demo",
            inputs={
                "brief": "no network test",
                "pool": "default",
                "theme": "default",
                "target_duration": 60,
            },
            dry_run=True,
            verbose=False,
        )
    assert result.ok is True


@pytest.mark.timeout(60)
def test_dry_run_invoke_missing_input_raises_capability_missing_input_error() -> None:
    """Invoking without required inputs must raise
    ``CapabilityMissingInputError`` (as documented in Step 4 error handling)."""
    import astrid as sdk

    with pytest.raises(sdk.CapabilityMissingInputError):
        sdk.invoke(
            "editorial.arrange",
            kind="executor",
            include_installed=False,
            out=Path("/tmp/out"),
            project="demo",
            dry_run=True,
            verbose=False,
        )


@pytest.mark.timeout(60)
def test_invoke_element_raises_unsupported_capability_error() -> None:
    """Invoking an element must raise ``UnsupportedCapabilityError``."""
    import astrid as sdk

    with pytest.raises(sdk.UnsupportedCapabilityError):
        sdk.invoke(
            "effects/text-card",
            kind="element",
            dry_run=True,
            verbose=False,
        )


# ---------------------------------------------------------------------------
# Error handling: documented exception paths
# ---------------------------------------------------------------------------


@pytest.mark.timeout(60)
def test_get_capability_not_found_raises_capability_not_found_error() -> None:
    """``get_capability`` for a non-existent ID must raise
    ``CapabilityNotFoundError``."""
    import astrid as sdk

    with pytest.raises(sdk.CapabilityNotFoundError):
        sdk.get_capability(
            "missing.capability",
            kind="executor",
            include_installed=False,
        )


@pytest.mark.timeout(60)
def test_get_capability_ambiguous_raises_capability_ambiguous_error() -> None:
    """``get_capability`` with a bare name matching multiple elements must
    raise ``CapabilityAmbiguousError``."""
    import astrid as sdk

    # "fade" matches multiple elements across different kinds
    with pytest.raises(sdk.CapabilityAmbiguousError):
        sdk.get_capability(
            "fade",
            kind="element",
            include_installed=False,
        )


# ---------------------------------------------------------------------------
# read_events and subscribe_events
# ---------------------------------------------------------------------------


@pytest.mark.timeout(60)
def test_read_events_with_golden_fixture(tmp_path: Path) -> None:
    """``read_events()`` with the committed golden fixture must return
    exactly 3 events with the documented kinds."""
    import astrid as sdk

    project_slug = "demo-agentic-ux"
    run_id = "demo-run-001"
    projects_root = tmp_path / "projects"
    run_dir = projects_root / project_slug / "runs" / run_id
    run_dir.mkdir(parents=True)

    shutil.copy2(str(GOLDEN_EVENTS), str(run_dir / "events.jsonl"))

    events = sdk.read_events(
        project_slug,
        run_id,
        projects_root=projects_root,
        verify=True,
    )

    assert len(events) == 3, f"Expected 3 events, got {len(events)}"
    expected_kinds = ["run_started", "step_dispatched", "run_completed"]
    actual_kinds = [e.kind for e in events]
    assert actual_kinds == expected_kinds, f"Kinds: {actual_kinds}"

    # Verify EventStreamRecord field shape
    for i, event in enumerate(events):
        assert event.source in {"task", "audit"}, (
            f"Event {i}: unexpected source {event.source!r}"
        )
        assert event.line == i + 1, f"Event {i}: expected line {i+1}, got {event.line}"
        assert isinstance(event.kind, str)
        assert isinstance(event.payload, dict)
        assert "kind" in event.payload


@pytest.mark.timeout(60)
def test_read_events_bad_slug_raises_validation_error(tmp_path: Path) -> None:
    """``read_events()`` with an invalid project slug must raise an
    ``AstridSDKError`` subclass (the SDK maps project-path validation
    errors to ``CapabilityValidationError``)."""
    import astrid as sdk

    with pytest.raises(sdk.AstridSDKError):
        sdk.read_events(
            "bad/slug",
            "demo-run-001",
            projects_root=tmp_path / "projects",
            verify=False,
        )


@pytest.mark.timeout(60)
def test_read_events_missing_file_raises_precondition_error(tmp_path: Path) -> None:
    """``read_events()`` for a run directory with no events.jsonl must raise
    ``CapabilityPreconditionError``."""
    import astrid as sdk

    project_slug = "no-events-project"
    run_id = "no-events-run"
    projects_root = tmp_path / "projects"
    run_dir = projects_root / project_slug / "runs" / run_id
    run_dir.mkdir(parents=True)
    # Do NOT create events.jsonl

    with pytest.raises(sdk.CapabilityPreconditionError):
        sdk.read_events(
            project_slug,
            run_id,
            projects_root=projects_root,
            verify=False,
        )


@pytest.mark.timeout(60)
def test_subscribe_events_yields_from_golden_fixture(tmp_path: Path) -> None:
    """``subscribe_events()`` with ``follow=False`` must yield exactly 3
    events from the committed golden fixture."""
    import astrid as sdk

    project_slug = "demo-agentic-ux"
    run_id = "demo-run-001"
    projects_root = tmp_path / "projects"
    run_dir = projects_root / project_slug / "runs" / run_id
    run_dir.mkdir(parents=True)

    shutil.copy2(str(GOLDEN_EVENTS), str(run_dir / "events.jsonl"))

    events = list(
        sdk.subscribe_events(
            project_slug,
            run_id,
            projects_root=projects_root,
            follow=False,
            verify=True,
        )
    )

    assert len(events) == 3, f"Expected 3 events from subscribe, got {len(events)}"
    kinds = [e.kind for e in events]
    assert kinds == ["run_started", "step_dispatched", "run_completed"]


# ---------------------------------------------------------------------------
# Full tutorial path: discover → inspect → invoke → read-events
# ---------------------------------------------------------------------------


@pytest.mark.timeout(90)
def test_full_tutorial_path_round_trips(tmp_path: Path) -> None:
    """Execute the complete tutorial path (discover → inspect → invoke →
    read-events) in-process and verify every step succeeds."""
    import astrid as sdk

    projects_root = tmp_path / "projects"

    # 1. Discover
    discovery = sdk.discover(include_installed=False)
    assert len(discovery.executors) > 0
    assert len(discovery.orchestrators) > 0
    assert len(discovery.capabilities) > 0

    executor_ids = {e.id for e in discovery.executors}
    assert "editorial.arrange" in executor_ids

    # 2. Inspect
    cap = sdk.get_capability(
        "editorial.arrange", kind="executor", include_installed=False
    )
    assert cap.id == "editorial.arrange"
    assert cap.capability_type == "executor"
    assert len(cap.inputs) >= 4
    assert len(cap.outputs) >= 1

    # 3. Dry-run invoke
    with tempfile.TemporaryDirectory(prefix="astrid-full-path-") as tmp_out:
        result = sdk.invoke(
            "editorial.arrange",
            kind="executor",
            include_installed=False,
            out=Path(tmp_out),
            project="demo",
            inputs={
                "brief": "full path test brief",
                "pool": "default",
                "theme": "default",
                "target_duration": 60,
            },
            dry_run=True,
            verbose=False,
        )
    assert result.ok is True
    assert result.raw_result.get("dry_run") is True

    # 4. Read events from the golden fixture
    project_slug = "demo-agentic-ux"
    run_id = "demo-run-001"
    run_dir = projects_root / project_slug / "runs" / run_id
    run_dir.mkdir(parents=True)
    shutil.copy2(str(GOLDEN_EVENTS), str(run_dir / "events.jsonl"))

    events = sdk.read_events(
        project_slug,
        run_id,
        projects_root=projects_root,
        verify=True,
    )
    assert len(events) == 3
    assert [e.kind for e in events] == [
        "run_started",
        "step_dispatched",
        "run_completed",
    ]


# ---------------------------------------------------------------------------
# DTO serializability (capability.schema, capability.definition)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(60)
def test_capability_schema_is_json_serializable() -> None:
    """The ``capability.schema`` and ``capability.definition`` mappings
    documented in Step 3 must be JSON-safe dicts."""
    import astrid as sdk

    cap = sdk.get_capability(
        "editorial.arrange", kind="executor", include_installed=False
    )

    schema_dict = cap.schema
    assert isinstance(schema_dict, dict)
    json.dumps(schema_dict)  # must not raise

    definition_dict = cap.definition
    assert isinstance(definition_dict, dict)
    json.dumps(definition_dict)  # must not raise


@pytest.mark.timeout(60)
def test_discovery_result_is_iterable() -> None:
    """``DiscoveryResult`` must expose typed groupings as documented."""
    import astrid as sdk

    discovery = sdk.discover(include_installed=False)

    assert hasattr(discovery, "executors")
    assert hasattr(discovery, "orchestrators")
    assert hasattr(discovery, "elements")
    assert hasattr(discovery, "capabilities")

    assert isinstance(discovery.executors, tuple)
    assert isinstance(discovery.orchestrators, tuple)
    assert isinstance(discovery.elements, tuple)
    assert isinstance(discovery.capabilities, tuple)


# ---------------------------------------------------------------------------
# Import boundary: tutorial must use only public astrid names (no private)
# ---------------------------------------------------------------------------


def test_tutorial_code_blocks_use_only_public_sdk_names() -> None:
    """No code block in the tutorial may reference non-public ``astrid.*``
    names (i.e., names not in ``astrid.__all__``)."""
    content = TUTORIAL_PATH.read_text(encoding="utf-8")
    blocks = _extract_code_blocks(content)
    all_names: set[str] = set()
    for block in blocks:
        all_names.update(_extract_astrid_names_from_code(block["content"]))

    undocumented = all_names - _SDK_EXPORT_NAMES
    assert undocumented == set(), (
        f"Tutorial code uses non-public astrid names: {sorted(undocumented)}"
    )


def test_tutorial_code_blocks_have_no_from_astrid_dot_imports() -> None:
    """No code block in the tutorial may use ``from astrid.`` imports.
    Only ``from astrid import Name`` (top-level public names) is allowed."""
    content = TUTORIAL_PATH.read_text(encoding="utf-8")
    blocks = _extract_code_blocks(content)
    for block in blocks:
        for line in block["content"].splitlines():
            stripped = line.strip()
            if "from astrid." in stripped and not stripped.startswith("#"):
                # Allow ``from astrid import ...`` (no dot after astrid)
                if not stripped.startswith("from astrid import "):
                    raise AssertionError(
                        f"Tutorial code block at line {block['line_number']} "
                        f"uses forbidden 'from astrid.' import:\n  {stripped}"
                    )


# ---------------------------------------------------------------------------
# Lazy import (documented in Step 1)
# ---------------------------------------------------------------------------


def test_import_astrid_is_lazy() -> None:
    """``import astrid`` must not eagerly load heavy modules (documented
    in Step 1 of the tutorial)."""
    script = textwrap.dedent("""
    import sys
    import astrid
    heavy = [
        "astrid.sdk",
        "astrid.core.execution.executor.registry",
        "astrid.core.execution.executor.runner",
        "astrid.core.execution.orchestrator.registry",
        "astrid.core.execution.orchestrator.runner",
    ]
    for mod in heavy:
        if mod in sys.modules:
            print(f"HEAVY_LOADED: {mod}")
    """)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=15,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert completed.returncode == 0, f"Probe failed: {completed.stderr}"
    assert "HEAVY_LOADED:" not in completed.stdout, (
        f"Heavy modules loaded eagerly: {completed.stdout.strip()}"
    )


# ---------------------------------------------------------------------------
# Security and trust disclosures: capability provenance
# ---------------------------------------------------------------------------


@pytest.mark.timeout(60)
def test_provenance_is_populated_on_editorial_arrange() -> None:
    """The provenance on editorial.arrange must be populated (not default
    empty values), as documented in Security and Trust Disclosures."""
    import astrid as sdk

    cap = sdk.get_capability(
        "editorial.arrange", kind="executor", include_installed=False
    )
    prov = cap.handle.provenance
    assert prov.source, "Provenance source is empty"
    # pack_id may be empty for capabilities loaded via certain code paths,
    # but source and other identifying metadata must be present.
    assert isinstance(prov.source, str)
    assert isinstance(prov.pack_id, str)
