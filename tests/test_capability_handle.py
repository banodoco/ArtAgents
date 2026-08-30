"""Tests for CapabilityHandle, Provenance, and the adapter functions
that convert native definitions (executor / orchestrator / element)
into the shared identity handle.

All definitions are constructed inline — no real registry loads.
"""

from __future__ import annotations

import copy
from dataclasses import asdict
from pathlib import Path

from astrid.core.contracts.schema import (
    CapabilityHandle,
    Port,
    Output,
    Provenance,
    SafetyDeclaration,
    AliasRecord,
    IsolationMetadata,
    CachePolicy,
    CommandSpec,
)
from astrid.core.execution.executor.schema import (
    ExecutorDefinition,
    GraphMetadata,
    to_capability_handle as executor_to_handle,
)
from astrid.core.execution.orchestrator.schema import (
    OrchestratorDefinition,
    RuntimeSpec,
    to_capability_handle as orchestrator_to_handle,
)
from astrid.core.element.schema import (
    ElementDefinition,
    ElementDependencies,
    to_capability_handle as element_to_handle,
)


# ---------------------------------------------------------------------------
# Helpers — construct minimal valid definitions
# ---------------------------------------------------------------------------

def _make_executor(**overrides) -> ExecutorDefinition:
    kwargs: dict = dict(
        id="rendering.render",
        name="Render Executor",
        kind="built_in",
        version="1.0.0",
        description="Renders video frames",
        short_description="Render frames",
        keywords=("render", "video"),
        inputs=(Port(name="input_path", type="path"),),
        outputs=(Output(name="output_path", type="path"),),
        command=CommandSpec(argv=("render.sh",)),
        cache=CachePolicy(),
        conditions=(),
        graph=GraphMetadata(depends_on=("editorial.transcribe",)),
        clip_kinds_supported=(),
        pipeline_requirements=(),
        isolation=IsolationMetadata(network=False),
        metadata={"source": "pack"},
        external_runtime=None,
    )
    kwargs.update(overrides)
    return ExecutorDefinition(**kwargs)


def _make_orchestrator(**overrides) -> OrchestratorDefinition:
    kwargs: dict = dict(
        id="builtin.pipeline",
        name="Pipeline Orchestrator",
        kind="built_in",
        version="2.0.0",
        runtime=RuntimeSpec(kind="python", module="astrid.core.gateway", function="run"),
        description="Runs the full pipeline",
        short_description="Pipeline runner",
        keywords=("pipeline",),
        inputs=(Port(name="brief", type="string"),),
        outputs=(Output(name="result", type="json"),),
        child_executors=("rendering.render", "editorial.transcribe"),
        child_orchestrators=(),
        cache=CachePolicy(),
        isolation=IsolationMetadata(network=True),
        metadata={"source": "pack"},
    )
    kwargs.update(overrides)
    return OrchestratorDefinition(**kwargs)


def _make_element(**overrides) -> ElementDefinition:
    kwargs: dict = dict(
        id="blur",
        kind="effects",
        root=Path("/fake/pack/elements/effects/blur"),
        source="pack:builtin",
        editable=False,
        priority=30,
        component=Path("/fake/pack/elements/effects/blur/component.tsx"),
        schema={"type": "object"},
        defaults={"radius": 5},
        metadata={"name": "Gaussian Blur", "version": "1.2.0", "pack_id": "builtin"},
        dependencies=ElementDependencies(),
        description="Applies a Gaussian blur effect",
        short_description="Gaussian blur",
        keywords=("blur", "filter"),
    )
    kwargs.update(overrides)
    return ElementDefinition(**kwargs)


# ===================================================================
# CapabilityHandle.to_dict() round-trip
# ===================================================================


class TestCapabilityHandleRoundTrip:
    """CapabilityHandle.to_dict() produces a dict that faithfully represents
    all fields."""

    def test_to_dict_includes_all_fields(self):
        prov = Provenance(source="pack", pack_id="builtin", manifest_path="", content_root="")
        safety = SafetyDeclaration(network=True)
        alias = AliasRecord(alias="render", canonical_id="rendering.render")
        port = Port(name="input", type="path")
        out = Output(name="result", type="path")

        handle = CapabilityHandle(
            canonical_id="rendering.render",
            local_id="render",
            pack_id="builtin",
            kind="built_in",
            name="Render",
            version="1.0.0",
            provenance=prov,
            safety=safety,
            description="Renders frames",
            short_description="Render",
            keywords=("video", "render"),
            category="video",
            status="stable",
            visibility="public",
            aliases=(alias,),
            inputs=(port,),
            outputs=(out,),
            deprecated=False,
            deprecated_alternatives=(),
            deprecation_message="",
        )

        d = handle.to_dict()

        assert d["canonical_id"] == "rendering.render"
        assert d["local_id"] == "render"
        assert d["pack_id"] == "builtin"
        assert d["kind"] == "built_in"
        assert d["name"] == "Render"
        assert d["version"] == "1.0.0"
        assert d["provenance"]["source"] == "pack"
        assert d["provenance"]["pack_id"] == "builtin"
        assert d["safety"]["network"] is True
        assert d["description"] == "Renders frames"
        assert d["short_description"] == "Render"
        assert d["keywords"] == ("video", "render")
        assert d["category"] == "video"
        assert d["status"] == "stable"
        assert d["visibility"] == "public"
        assert len(d["aliases"]) == 1
        assert d["aliases"][0]["alias"] == "render"
        assert len(d["inputs"]) == 1
        assert d["inputs"][0]["name"] == "input"
        assert len(d["outputs"]) == 1
        assert d["outputs"][0]["name"] == "result"
        assert d["deprecated"] is False

    def test_to_dict_uses_asdict(self):
        """to_dict() delegates to dataclasses.asdict, so nested dataclasses
        are recursively converted."""
        handle = CapabilityHandle(
            canonical_id="test.foo",
            local_id="foo",
            pack_id="test",
            kind="built_in",
            name="Foo",
            version="0.1",
            provenance=Provenance(source="pack"),
        )
        d = handle.to_dict()
        # Provenance is a nested dataclass — asdict converts it to a dict
        assert isinstance(d["provenance"], dict)
        assert d["provenance"]["source"] == "pack"


# ===================================================================
# Provenance construction
# ===================================================================


class TestProvenanceConstruction:
    """Provenance frozen dataclass behaves as expected."""

    def test_defaults_are_empty_strings(self):
        p = Provenance(source="pack")
        assert p.pack_id == ""
        assert p.manifest_path == ""
        assert p.content_root == ""
        assert p.resolved_alias is None

    def test_all_fields_can_be_set(self):
        p = Provenance(
            source="pack",
            pack_id="builtin",
            manifest_path="executor.yaml",
            content_root="/packs/builtin",
            resolved_alias="old_render",
        )
        assert p.source == "pack"
        assert p.pack_id == "builtin"
        assert p.manifest_path == "executor.yaml"
        assert p.content_root == "/packs/builtin"
        assert p.resolved_alias == "old_render"

    def test_frozen(self):
        p = Provenance(source="pack")
        try:
            p.source = "other"  # type: ignore[misc]
            assert False, "Provenance should be frozen"
        except Exception:
            pass  # expected


# ===================================================================
# Executor adapter
# ===================================================================


class TestExecutorToCapabilityHandle:
    """to_capability_handle(ExecutorDefinition) maps fields correctly."""

    def test_basic_mapping(self):
        ex = _make_executor()
        h = executor_to_handle(ex)

        assert h.canonical_id == "rendering.render"
        assert h.local_id == "render"
        assert h.pack_id == "rendering"
        assert h.kind == "built_in"
        assert h.name == "Render Executor"
        assert h.version == "1.0.0"
        assert h.description == "Renders video frames"
        assert h.short_description == "Render frames"
        assert h.keywords == ("render", "video")
        assert len(h.inputs) == 1
        assert h.inputs[0].name == "input_path"
        assert len(h.outputs) == 1
        assert h.outputs[0].name == "output_path"

    def test_provenance_source_from_metadata(self):
        ex = _make_executor(metadata={"source": "pack"})
        h = executor_to_handle(ex)
        assert h.provenance.source == "pack"

    def test_provenance_source_defaults_to_pack(self):
        ex = _make_executor(metadata={})
        h = executor_to_handle(ex)
        assert h.provenance.source == "pack"

    def test_provenance_empty_defaults(self):
        """manifest_path and content_root should be empty strings (not set by adapter)."""
        ex = _make_executor()
        h = executor_to_handle(ex)
        assert h.provenance.manifest_path == ""
        assert h.provenance.content_root == ""

    def test_safety_network_from_isolation(self):
        ex = _make_executor(isolation=IsolationMetadata(network=True))
        h = executor_to_handle(ex)
        assert h.safety.network is True

    def test_safety_secrets_merge_isolation_and_metadata(self):
        ex = _make_executor(
            isolation=IsolationMetadata(network=True, secrets_required=("FAL_KEY",)),
            metadata={"secrets_required": ["OPENAI_API_KEY", "FAL_KEY"]},
        )
        h = executor_to_handle(ex)
        assert h.safety.secrets_required == ("FAL_KEY", "OPENAI_API_KEY")

    def test_safety_network_default_false(self):
        ex = _make_executor(isolation=IsolationMetadata())
        h = executor_to_handle(ex)
        assert h.safety.network is False

    def test_local_id_without_dot_falls_back_to_full_id(self):
        ex = _make_executor(id="renderer")
        h = executor_to_handle(ex)
        assert h.canonical_id == "renderer"
        assert h.local_id == "renderer"
        assert h.pack_id == "renderer"

    def test_external_kind_preserved(self):
        ex = _make_executor(id="custom.tool", kind="external")
        h = executor_to_handle(ex)
        assert h.kind == "external"
        assert h.pack_id == "custom"
        assert h.local_id == "tool"


# ===================================================================
# Orchestrator adapter
# ===================================================================


class TestOrchestratorToCapabilityHandle:
    """to_capability_handle(OrchestratorDefinition) maps fields correctly."""

    def test_basic_mapping(self):
        orch = _make_orchestrator()
        h = orchestrator_to_handle(orch)

        assert h.canonical_id == "builtin.pipeline"
        assert h.local_id == "pipeline"
        assert h.pack_id == "builtin"
        assert h.kind == "built_in"
        assert h.name == "Pipeline Orchestrator"
        assert h.version == "2.0.0"

    def test_provenance_source_from_metadata(self):
        orch = _make_orchestrator(metadata={"source": "pack"})
        h = orchestrator_to_handle(orch)
        assert h.provenance.source == "pack"

    def test_provenance_source_defaults_to_pack(self):
        orch = _make_orchestrator(metadata={})
        h = orchestrator_to_handle(orch)
        assert h.provenance.source == "pack"

    def test_provenance_empty_defaults(self):
        orch = _make_orchestrator()
        h = orchestrator_to_handle(orch)
        assert h.provenance.manifest_path == ""
        assert h.provenance.content_root == ""

    def test_safety_network_from_isolation(self):
        orch = _make_orchestrator(isolation=IsolationMetadata(network=True))
        h = orchestrator_to_handle(orch)
        assert h.safety.network is True

    def test_safety_network_default_false(self):
        orch = _make_orchestrator(isolation=IsolationMetadata())
        h = orchestrator_to_handle(orch)
        assert h.safety.network is False

    def test_inputs_outputs_preserved(self):
        orch = _make_orchestrator()
        h = orchestrator_to_handle(orch)
        assert len(h.inputs) == 1
        assert h.inputs[0].name == "brief"
        assert len(h.outputs) == 1
        assert h.outputs[0].name == "result"


# ===================================================================
# Element adapter
# ===================================================================


class TestElementToCapabilityHandle:
    """to_capability_handle(ElementDefinition) maps fields correctly."""

    def test_canonical_id_slash_separator(self):
        el = _make_element()
        h = element_to_handle(el)
        assert h.canonical_id == "effects/blur"

    def test_local_id_is_element_id(self):
        el = _make_element()
        h = element_to_handle(el)
        assert h.local_id == "blur"

    def test_pack_id_from_metadata(self):
        el = _make_element(metadata={"pack_id": "builtin"})
        h = element_to_handle(el)
        assert h.pack_id == "builtin"

    def test_pack_id_defaults_to_empty(self):
        el = _make_element(metadata={})
        h = element_to_handle(el)
        assert h.pack_id == ""

    def test_kind_preserved(self):
        el = _make_element(kind="animations")
        h = element_to_handle(el)
        assert h.kind == "animations"

    def test_name_from_metadata_name(self):
        el = _make_element(metadata={"name": "Gaussian Blur"})
        h = element_to_handle(el)
        assert h.name == "Gaussian Blur"

    def test_name_fallback_to_label(self):
        el = _make_element(metadata={"label": "Blur Effect"})
        h = element_to_handle(el)
        assert h.name == "Blur Effect"

    def test_name_fallback_to_id(self):
        el = _make_element(metadata={})
        h = element_to_handle(el)
        assert h.name == "blur"

    def test_version_from_metadata(self):
        el = _make_element(metadata={"version": "1.2.0"})
        h = element_to_handle(el)
        assert h.version == "1.2.0"

    def test_version_defaults_to_empty(self):
        el = _make_element(metadata={})
        h = element_to_handle(el)
        assert h.version == ""

    def test_provenance_source_preserved_as_is(self):
        """Element provenance.source is passed through from definition.source."""
        el = _make_element(source="pack:builtin")
        h = element_to_handle(el)
        assert h.provenance.source == "pack:builtin"

    def test_provenance_source_active_theme(self):
        """active_theme is a valid provenance.source for elements."""
        el = _make_element(source="active_theme")
        h = element_to_handle(el)
        assert h.provenance.source == "active_theme"

    def test_provenance_source_asymmetry(self):
        """Executor provenance.source is 'pack', while element can be
        'pack:builtin' or 'active_theme'."""
        ex = _make_executor(metadata={"source": "pack"})
        el = _make_element(source="pack:builtin")

        ex_h = executor_to_handle(ex)
        el_h = element_to_handle(el)

        assert ex_h.provenance.source == "pack"
        assert el_h.provenance.source == "pack:builtin"

    def test_safety_network_always_false(self):
        """Elements have no network isolation concept."""
        el = _make_element()
        h = element_to_handle(el)
        assert h.safety.network is False

    def test_inputs_outputs_empty(self):
        """Elements have no Port/Output model — adapters supply empty tuples."""
        el = _make_element()
        h = element_to_handle(el)
        assert h.inputs == ()
        assert h.outputs == ()

    def test_provenance_empty_defaults(self):
        el = _make_element()
        h = element_to_handle(el)
        assert h.provenance.manifest_path == ""
        assert h.provenance.content_root == ""

    def test_description_and_keywords(self):
        el = _make_element()
        h = element_to_handle(el)
        assert h.description == "Applies a Gaussian blur effect"
        assert h.short_description == "Gaussian blur"
        assert h.keywords == ("blur", "filter")

    def test_different_element_kinds(self):
        for kind in ("effects", "animations", "transitions"):
            el = _make_element(id="test", kind=kind)
            h = element_to_handle(el)
            assert h.canonical_id == f"{kind}/test"
            assert h.kind == kind


# ===================================================================
# SafetyDeclaration construction
# ===================================================================


class TestSafetyDeclaration:
    def test_defaults(self):
        s = SafetyDeclaration()
        assert s.network is False
        assert s.cost_estimate == ""
        assert s.secrets_required == ()
        assert s.permissions == ()

    def test_network_flag(self):
        s = SafetyDeclaration(network=True)
        assert s.network is True


# ===================================================================
# Cross-adapter consistency
# ===================================================================


class TestCrossAdapterConsistency:
    """All three adapters produce CapabilityHandle with the same shape."""

    def test_all_three_produce_same_type(self):
        ex_h = executor_to_handle(_make_executor())
        orch_h = orchestrator_to_handle(_make_orchestrator())
        el_h = element_to_handle(_make_element())

        for h in (ex_h, orch_h, el_h):
            assert isinstance(h, CapabilityHandle)
            assert isinstance(h.provenance, Provenance)
            assert isinstance(h.safety, SafetyDeclaration)
            # to_dict must work on all
            d = h.to_dict()
            assert "canonical_id" in d
            assert "provenance" in d
            assert "safety" in d

    def test_aliases_empty_by_default(self):
        for adapter in (executor_to_handle, orchestrator_to_handle, element_to_handle):
            if adapter is executor_to_handle:
                h = adapter(_make_executor())
            elif adapter is orchestrator_to_handle:
                h = adapter(_make_orchestrator())
            else:
                h = adapter(_make_element())
            assert h.aliases == ()

    def test_deprecated_defaults(self):
        for adapter in (executor_to_handle, orchestrator_to_handle, element_to_handle):
            if adapter is executor_to_handle:
                h = adapter(_make_executor())
            elif adapter is orchestrator_to_handle:
                h = adapter(_make_orchestrator())
            else:
                h = adapter(_make_element())
            assert h.deprecated is False
            assert h.deprecated_alternatives == ()
            assert h.deprecation_message == ""
