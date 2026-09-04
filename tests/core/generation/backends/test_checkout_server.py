from __future__ import annotations

import hashlib
import io
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import pytest

import astrid.core.generation.backends.vibecomfy as backend_module
from astrid.core.generation.backends.vibecomfy import (
    COMFYUI_VERSION,
    VIBECOMFY_ENGINE_REVISION,
    CheckoutServerAdapter,
    _validate_checkout_server_url,
)
from astrid.core.model_catalog.schema import BackendSpec, ModeSpec, ModelEntry

RUNTIME_A = "c3d4e5f6-a7b8-49cd-8e01-23456789abcd"


class _Workflow:
    def __init__(self) -> None:
        self.metadata: dict[str, object] = {"unbound_inputs": {}}
        self.inputs: dict[str, object] = {}

    def set_input(self, name: str, value: object) -> None:
        self.inputs[name] = value


class _Response(io.BytesIO):
    status = 200

    def __init__(self, body: bytes, *, payload: object | None = None) -> None:
        super().__init__(body)
        self._payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def json(self) -> object:
        if self._payload is None:
            raise AssertionError("json() was not configured")
        return self._payload


def _entry(template_hash: str, template: str = "image/z_image") -> ModelEntry:
    return ModelEntry(
        id="z-image",
        modality="image",
        modes={
            "t2i": ModeSpec(
                supports=("prompt", "seed", "size"),
                requires=("prompt",),
                backends={
                    "local": BackendSpec(
                        template=template,
                        template_hash=template_hash,
                    )
                },
            )
        },
    )


def _fake_vibe_modules(
    workflow: _Workflow,
    result: object,
    *,
    record: object,
    discovery: object,
) -> dict[str, types.ModuleType]:
    root = types.ModuleType("vibecomfy")
    ready = types.ModuleType("vibecomfy.registry.ready")
    runtime = types.ModuleType("vibecomfy.runtime.run")
    ready.repo_ready_template_discovery = Mock(return_value=discovery)  # type: ignore[attr-defined]
    ready.resolve_ready_template = Mock(return_value=record)  # type: ignore[attr-defined]
    ready.workflow_from_ready = Mock(return_value=workflow)  # type: ignore[attr-defined]
    runtime.run_sync = Mock(return_value=result)  # type: ignore[attr-defined]
    return {
        "vibecomfy": root,
        "vibecomfy.registry": types.ModuleType("vibecomfy.registry"),
        "vibecomfy.registry.ready": ready,
        "vibecomfy.runtime": types.ModuleType("vibecomfy.runtime"),
        "vibecomfy.runtime.run": runtime,
    }


def _template_record(tmp_path: Path, *, template_id: str = "image/z_image", source_scope: str = "repo") -> tuple[object, str]:
    template_path = tmp_path / "ready_templates" / "image" / "z_image.py"
    template_path.parent.mkdir(parents=True)
    template_path.write_bytes(b"def build():\n    return object()\n")
    digest = hashlib.sha256(template_path.read_bytes()).hexdigest()
    return (
        SimpleNamespace(
            template_id=template_id,
            path=template_path,
            root=template_path.parents[2],
            source_scope=source_scope,
        ),
        digest,
    )


def _patch_remote_open(monkeypatch: pytest.MonkeyPatch, *, output: bytes = b"png") -> list[str]:
    calls: list[str] = []

    def open_remote(request: object, *, timeout: float) -> _Response:
        del timeout
        url = request.full_url  # type: ignore[attr-defined]
        calls.append(url)
        if url.endswith("/system_stats"):
            return _Response(
                b'{"system":{"comfyui_version":"0.26.0"}}',
                payload={"system": {"comfyui_version": COMFYUI_VERSION}},
            )
        return _Response(output)

    monkeypatch.setattr(backend_module, "_open_checkout_http", open_remote)
    return calls


def test_repo_loader_requires_canonical_repo_record_and_verifies_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record, digest = _template_record(tmp_path)
    workflow = _Workflow()
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "comfy_outputs": [
                    {"filename": "x.png", "subfolder": "renders", "type": "output"}
                ]
            }
        ),
        encoding="utf-8",
    )
    result = SimpleNamespace(metadata_path=metadata_path, outputs=["/must/not/read"])
    discovery = object()
    modules = _fake_vibe_modules(
        workflow, result, record=record, discovery=discovery
    )
    calls = _patch_remote_open(monkeypatch)
    with patch.dict(sys.modules, modules):
        adapter = CheckoutServerAdapter("HTTPS://GPU.EXAMPLE.TEST:8888/")
        generated = adapter.generate(
            entry=_entry(f"sha256:{digest}"),
            mode="t2i",
            params={"prompt": "a cat", "seed": 7, "size": "512x384"},
            out_dir=tmp_path / "out",
            model_bytes_digest="sha256:" + "a" * 64,
            runtime_instance_id=RUNTIME_A,
        )
    ready = modules["vibecomfy.registry.ready"]
    assert ready.resolve_ready_template.call_args.args == ("image/z_image", discovery)
    assert ready.workflow_from_ready.call_args.args == ("image/z_image",)
    assert ready.workflow_from_ready.call_args.kwargs["_discovery"] is discovery
    assert calls[0] == "https://gpu.example.test:8888/system_stats"
    assert calls[1] == "https://gpu.example.test:8888/system_stats"
    assert calls[2].endswith("/view?filename=x.png&subfolder=renders&type=output")


def test_repo_loader_rejects_wrong_hash_before_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record, _digest = _template_record(tmp_path)
    modules = _fake_vibe_modules(
        _Workflow(),
        SimpleNamespace(metadata_path=tmp_path / "unused.json"),
        record=record,
        discovery=object(),
    )
    _patch_remote_open(monkeypatch)
    with patch.dict(sys.modules, modules):
        with pytest.raises(ValueError, match="sha256 pin"):
            CheckoutServerAdapter("https://gpu.example.test").generate(
                entry=_entry("sha256:" + "0" * 64),
                mode="t2i",
                params={"prompt": "a cat"},
                out_dir=tmp_path / "out",
                model_bytes_digest="sha256:" + "a" * 64,
                runtime_instance_id=RUNTIME_A,
            )
    assert not modules["vibecomfy.registry.ready"].workflow_from_ready.called



@pytest.mark.parametrize("record_id", ["z_image", "../z_image", "image/../z_image"])
def test_repo_loader_rejects_non_category_record(
    tmp_path: Path, record_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    record, digest = _template_record(tmp_path, template_id=record_id)
    modules = _fake_vibe_modules(
        _Workflow(),
        SimpleNamespace(metadata_path=tmp_path / "unused.json"),
        record=record,
        discovery=object(),
    )
    _patch_remote_open(monkeypatch)
    with patch.dict(sys.modules, modules):
        with pytest.raises(ValueError, match="canonical repo template"):
            CheckoutServerAdapter("https://gpu.example.test").generate(
                entry=_entry(f"sha256:{digest}"),
                mode="t2i",
                params={"prompt": "a cat"},
                out_dir=tmp_path / "out",
                model_bytes_digest="sha256:" + "a" * 64,
                runtime_instance_id=RUNTIME_A,
            )

def test_repo_loader_rejects_dynamic_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record, digest = _template_record(tmp_path, source_scope="dynamic")
    modules = _fake_vibe_modules(
        _Workflow(),
        SimpleNamespace(metadata_path=tmp_path / "unused.json"),
        record=record,
        discovery=object(),
    )
    _patch_remote_open(monkeypatch)
    with patch.dict(sys.modules, modules):
        with pytest.raises(ValueError, match="canonical repo template"):
            CheckoutServerAdapter("https://gpu.example.test").generate(
                entry=_entry(f"sha256:{digest}"),
                mode="t2i",
                params={"prompt": "a cat"},
                out_dir=tmp_path / "out",
                model_bytes_digest="sha256:" + "a" * 64,
                runtime_instance_id=RUNTIME_A,
            )


def test_remote_output_custody_downloads_metadata_descriptors_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record, digest = _template_record(tmp_path)
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "comfy_outputs": {"9": {"images": [
                    {"filename": "remote.png", "subfolder": "", "type": "output"}
                ]}}}
        ),
        encoding="utf-8",
    )
    result = SimpleNamespace(metadata_path=metadata_path, outputs=[str(tmp_path / "local.png")])
    modules = _fake_vibe_modules(
        _Workflow(), result, record=record, discovery=object()
    )
    calls = _patch_remote_open(monkeypatch)
    from unittest.mock import patch

    with patch.dict(sys.modules, modules):
        generated = CheckoutServerAdapter("https://GPU.EXAMPLE.TEST:8888/").generate(
            entry=_entry(f"sha256:{digest}"),
            mode="t2i",
            params={"prompt": "a cat"},
            out_dir=tmp_path / "out",
            model_bytes_digest="sha256:" + "a" * 64,
            runtime_instance_id=RUNTIME_A,
        )
    assert len(calls) == 3
    assert calls[0] == "https://gpu.example.test:8888/system_stats"
    assert calls[1] == "https://gpu.example.test:8888/system_stats"
    query = parse_qs(urlsplit(calls[2]).query, keep_blank_values=True)
    assert query == {"filename": ["remote.png"], "subfolder": [""], "type": ["output"]}
    assert generated.image_paths[0].read_bytes() == b"png"
    assert not list((tmp_path / "out").glob(".checkout-download-*"))
    assert modules["vibecomfy.runtime.run"].run_sync.call_args.kwargs == {
        "server_url": "https://gpu.example.test:8888"
    }


@pytest.mark.parametrize(
    "descriptors",
    [
        [],
        [{"filename": "../escape.png", "subfolder": "", "type": "output"}],
        [{"filename": "ok.png", "subfolder": "../escape", "type": "output"}],
        [{"filename": "ok.png", "subfolder": "", "type": "input"}],
        [{"filename": "ok.png", "subfolder": "", "type": "output", "extra": "x"}],
    ],
)
def test_remote_output_custody_rejects_empty_or_malformed_descriptors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    descriptors: list[dict[str, str]],
) -> None:
    record, digest = _template_record(tmp_path)
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps({"comfy_outputs": descriptors}), encoding="utf-8")
    result = SimpleNamespace(metadata_path=metadata_path)
    modules = _fake_vibe_modules(_Workflow(), result, record=record, discovery=object())
    _patch_remote_open(monkeypatch)
    from unittest.mock import patch

    with patch.dict(sys.modules, modules):
        with pytest.raises(ValueError):
            CheckoutServerAdapter("https://gpu.example.test").generate(
                entry=_entry(f"sha256:{digest}"),
                mode="t2i",
                params={"prompt": "a cat"},
                out_dir=tmp_path / "out",
                model_bytes_digest="sha256:" + "a" * 64,
                runtime_instance_id=RUNTIME_A,
            )


@pytest.mark.parametrize(
    "value",
    [
        "https://user:pass@example.test",
        "https://example.test?token=secret",
        "https://example.test#fragment",
        "https://example.test/path",
        "https:// example.test",
        "https://example.test\\path",
        "https://example.test:notaport",
        "https://example.test:0",
        "https://example.test:65536",
        "https://example..test",
        "https://-example.test",
    ],
)
def test_checkout_server_url_rejects_unsafe_origins(value: str) -> None:
    with pytest.raises(ValueError):
        _validate_checkout_server_url(value)


def test_checkout_server_url_accepts_canonical_origin() -> None:
    assert _validate_checkout_server_url("HTTPS://GPU.EXAMPLE.TEST:8888/") == (
        "https://gpu.example.test:8888"
    )


def test_system_stats_probe_requires_exact_version_and_bounds_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = CheckoutServerAdapter("https://gpu.example.test")
    monkeypatch.setattr(
        backend_module,
        "_open_checkout_http",
        lambda request, *, timeout: _Response(
            b"x" * (64 * 1024 + 1),
            payload={"system": {"comfyui_version": COMFYUI_VERSION}},
        ),
    )
    with pytest.raises(ValueError, match="too large"):
        adapter._probe_system_stats()
    assert not adapter._system_stats_verified
    assert not any(
        path.is_file() and b"x" * 64 in path.read_bytes()
        for path in tmp_path.rglob("*")
    )

    monkeypatch.setattr(
        backend_module,
        "_open_checkout_http",
        lambda request, *, timeout: _Response(
            b'{"system":{"comfyui_version":"0.25.0"}}',
            payload={"system": {"comfyui_version": "0.25.0"}},
        ),
    )
    with pytest.raises(ValueError, match="0.26.0"):
        adapter._probe_system_stats()
    assert not adapter._system_stats_verified
    monkeypatch.setattr(
        backend_module,
        "_open_checkout_http",
        lambda request, *, timeout: _Response(
            b'{"system":{"comfyui_version":"0.26.0"}}',
            payload={"system": {"comfyui_version": COMFYUI_VERSION}},
        ),
    )
    adapter._probe_system_stats()
    assert adapter.runtime_instance_id is None


def test_generate_requires_digest_and_canonical_runtime_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "vibecomfy", types.ModuleType("vibecomfy"))
    adapter = CheckoutServerAdapter("https://gpu.example.test")
    entry = _entry("sha256:" + "a" * 64)
    with pytest.raises(ValueError, match="model_bytes_digest"):
        adapter.generate(
            entry=entry,
            mode="t2i",
            params={"prompt": "a cat"},
            out_dir=tmp_path / "out",
            runtime_instance_id=RUNTIME_A,
        )
    with pytest.raises(ValueError, match="runtime_instance_id"):
        adapter.generate(
            entry=entry,
            mode="t2i",
            params={"prompt": "a cat"},
            out_dir=tmp_path / "out",
            model_bytes_digest="sha256:" + "a" * 64,
        )


def test_generate_rejects_unscoped_fingerprint_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "vibecomfy", types.ModuleType("vibecomfy"))
    with pytest.raises(ValueError, match="canonical session fingerprint"):
        CheckoutServerAdapter("https://gpu.example.test").generate(
            entry=_entry("sha256:" + "a" * 64),
            mode="t2i",
            params={"prompt": "a cat"},
            out_dir=tmp_path / "out",
            fingerprint="caller-override",
            model_bytes_digest="sha256:" + "a" * 64,
            runtime_instance_id=RUNTIME_A,
        )


def test_checkout_server_records_pinned_engine_contract() -> None:
    assert VIBECOMFY_ENGINE_REVISION == "dc8d962a8e330015bbb209080292fad248f1ceb3"
    assert COMFYUI_VERSION == "0.26.0"

def test_generate_failure_discards_prepared_warmth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = CheckoutServerAdapter("https://gpu.example.test")
    adapter._probe_system_stats = Mock(return_value=None)  # type: ignore[method-assign]
    with patch.object(
        backend_module.VibeComfyBackend,
        "generate",
        side_effect=RuntimeError("template preflight failed"),
    ):
        with pytest.raises(RuntimeError, match="template preflight failed"):
            adapter.generate(
                entry=_entry("sha256:" + "a" * 64),
                mode="t2i",
                params={"prompt": "a cat"},
                out_dir=tmp_path / "out",
                model_bytes_digest="sha256:" + "a" * 64,
                runtime_instance_id=RUNTIME_A,
            )

    assert adapter._engine.warm is False
    assert adapter._engine.last_warm_reused is False
    second = adapter._engine.prepare_session(
        "same-fingerprint",
        "same-warmth",
        runtime_instance_id=RUNTIME_A,
        model_bytes_digest="sha256:" + "a" * 64,
    )
    assert second["lifecycle"] == "cold"
    assert second["warm_reused"] is False
