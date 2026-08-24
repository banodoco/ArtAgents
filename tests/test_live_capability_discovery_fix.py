"""Focused regressions for the live capability-discovery UX wave."""

from __future__ import annotations

import astrid
import pytest


def test_networked_understanding_describes_credentials_and_outputs() -> None:
    audio = astrid.get_capability(
        "understanding.audio_understand",
        kind="executor",
        include_installed=False,
    )
    transcript = astrid.get_capability(
        "editorial.transcribe",
        kind="executor",
        include_installed=False,
    )

    assert audio.handle.safety.network is True
    assert audio.handle.safety.secrets_required == ("OPENAI_API_KEY",)
    assert audio.definition["metadata"]["env"] == ["OPENAI_API_KEY"]
    assert {"network", "environment"}.issubset(audio.handle.safety.permissions)
    assert {port.name for port in audio.inputs} >= {"audio"}
    assert {output.name for output in audio.outputs} >= {"analysis", "manifest"}

    assert transcript.handle.safety.network is True
    assert transcript.handle.safety.secrets_required == ("OPENAI_API_KEY",)
    assert transcript.definition["metadata"]["env"] == ["OPENAI_API_KEY"]
    assert {"network", "environment"}.issubset(transcript.handle.safety.permissions)
    assert transcript.schema["scoped_configs"] == ["credentials.openai"]
    assert {port.name for port in transcript.inputs} >= {"audio"}
    assert {output.name for output in transcript.outputs} >= {
        "transcript",
        "subtitle",
        "transcript_text",
        "chunk_plan",
        "manifest",
    }


def test_understand_dry_run_validates_mode_and_selected_modality(tmp_path) -> None:
    with pytest.raises(astrid.CapabilityValidationError, match="valid options: audio, image, video, visual"):
        astrid.invoke(
            "understanding.understand",
            kind="executor",
            include_installed=False,
            project="demo",
            inputs={"mode": "bogus"},
            dry_run=True,
        )

    with pytest.raises(astrid.CapabilityMissingInputError, match="missing required input.*audio"):
        astrid.invoke(
            "understanding.understand",
            kind="executor",
            include_installed=False,
            project="demo",
            inputs={"mode": "audio"},
            dry_run=True,
        )

    source = tmp_path / "clip.wav"
    source.write_bytes(b"fake")
    result = astrid.invoke(
        "understanding.understand",
        kind="executor",
        include_installed=False,
        project="demo",
        inputs={"mode": "audio", "audio": str(source)},
        dry_run=True,
    )
    assert result.ok is True
    assert "--audio" in result.raw_result["command"]


def test_networked_transcribe_sdk_dispatch_does_not_trip_orchestrator_guard(tmp_projects_root) -> None:
    from astrid.core.project.project import create_project

    create_project("demo", root=tmp_projects_root)
    result = astrid.invoke(
        "editorial.transcribe",
        kind="executor",
        include_installed=False,
        project="demo",
        inputs={"audio": "/tmp/fake.wav"},
        dry_run=True,
    )

    assert result.ok is True
    assert "astrid.packs.editorial.executors.transcribe.run" in result.raw_result["command"]


def test_hype_inputs_are_typed_and_preserved_in_command() -> None:
    result = astrid.invoke(
        "video_editing.hype",
        kind="orchestrator",
        project="demo",
        inputs={"video": "source.mp4", "brief": "brief.txt"},
        dry_run=True,
        include_installed=False,
    )

    command = result.raw_result["command"]
    assert "--video" in command and "source.mp4" in command
    assert "--brief" in command and "brief.txt" in command

    with pytest.raises(astrid.CapabilityValidationError, match="orchestrator_args"):
        astrid.invoke(
            "video_editing.event_talks",
            kind="orchestrator",
            project="demo",
            inputs={"source": "source.mp4"},
            dry_run=True,
            include_installed=False,
        )


def test_lookup_errors_offer_bounded_id_and_kind_recovery() -> None:
    with pytest.raises(astrid.CapabilityNotFoundError, match="nearest matches:.*generation.generate_image"):
        astrid.get_capability(
            "generation.generate_imge",
            kind="executor",
            include_installed=False,
        )

    with pytest.raises(astrid.CapabilityNotFoundError, match="registered as executor; retry with kind='executor'"):
        astrid.get_capability(
            "generation.generate_image",
            kind="orchestrator",
            include_installed=False,
        )

    with pytest.raises(astrid.CapabilityNotFoundError) as far:
        astrid.get_capability(
            "far.unknown.capability.edge.zzzz",
            kind="executor",
            include_installed=False,
        )
    far_message = str(far.value)
    assert "no close catalog match" in far_message
    assert "discover(include_installed=False)" in far_message
    assert "nearest matches" not in far_message
