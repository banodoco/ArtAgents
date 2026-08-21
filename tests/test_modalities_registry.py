import json
import pkgutil

from astrid.core import modalities


def test_exact_renderer_modules_and_registration_order() -> None:
    modules = {
        module.name
        for module in pkgutil.iter_modules(modalities.__path__)
        if not module.name.startswith("_")
    }

    assert modules == {"image_grid", "audio_waveform", "generic_card"}
    assert modalities.renderer_ids() == ["image_grid", "audio_waveform", "generic_card"]
    assert modalities.fallback_chain()[-1] == "generic_card"


def test_dispatches_by_artifact_kind_with_loud_generic_fallback() -> None:
    image = modalities.resolve_artifact({"kind": "image", "path": "runs/example/a.png"})
    audio = modalities.resolve_artifact({"kind": "audio", "path": "runs/example/a.wav"})
    unknown = modalities.resolve_artifact({"kind": "model_3d", "path": "runs/example/model.glb"})

    assert image["renderer"] == "image_grid"
    assert image["fallback"] is False
    assert audio["renderer"] == "audio_waveform"
    assert audio["fallback"] is False
    assert unknown["renderer"] == "generic_card"
    assert unknown["fallback"] is True
    assert unknown["diagnostic"] == "no renderer for kind:model_3d"
    assert '<aside class="renderer-fallback">no renderer for kind:model_3d</aside>' == unknown["html_aside"]
    assert unknown["payload"]["diagnostic"] == "no renderer for kind:model_3d"


def test_modality_declarations_do_not_expose_deferred_preview_modes() -> None:
    payload = {
        "list": modalities.list_renderers(),
        "inspect": [modalities.inspect_renderer(renderer_id) for renderer_id in modalities.renderer_ids()],
        "resolve": [
            modalities.resolve_artifact({"kind": "image"}),
            modalities.resolve_artifact({"kind": "audio"}),
            modalities.resolve_artifact({"kind": "unknown"}),
        ],
    }

    assert "preview_modes" not in json.dumps(payload, sort_keys=True)
