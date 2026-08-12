from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from astrid.core.contracts.errors import AstridError
from astrid.packs.understanding.executors.visual_understand import run as visual_understand


ANSWER_SCHEMA = {
    "additionalProperties": False,
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "type": "object",
}


def _write_images(tmp_path: Path, count: int) -> tuple[Path, ...]:
    paths: list[Path] = []
    for index in range(count):
        path = tmp_path / f"page-{index + 1}.png"
        Image.new("RGB", (8, 8), (index * 30, 20, 200 - index * 20)).save(path)
        paths.append(path)
    return tuple(paths)


def _fake_transport(
    monkeypatch: pytest.MonkeyPatch,
    *,
    response: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def send(*, api_key: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        calls.append({"api_key": api_key, "payload": payload, "timeout": timeout})
        return response or {
            "id": "resp_ordered_123",
            "model": "gpt-5.6-sol-2026-08-01",
            "output_text": json.dumps({"answer": "ok"}),
            "usage": {"input_tokens": 31, "output_tokens": 4, "total_tokens": 35},
        }

    monkeypatch.setattr(visual_understand, "load_api_key", lambda **_kwargs: "test-key")
    monkeypatch.setattr(visual_understand, "_send_responses_request", send)
    return calls


def _image_blocks(call: dict[str, Any]) -> list[dict[str, Any]]:
    content = call["payload"]["input"][0]["content"]
    return [block for block in content if block["type"] == "input_image"]


def _data_url_bytes(data_url: str) -> bytes:
    _, encoded = data_url.split(",", 1)
    return base64.b64decode(encoded)


def test_image_hash_order_is_preserved(monkeypatch, tmp_path):
    images = _write_images(tmp_path, 3)
    ordered = (images[2], images[0], images[1])
    _fake_transport(monkeypatch)

    evidence = visual_understand.understand_ordered(
        ordered,
        prompt="Read every page in order.",
        model="gpt-5.6-sol",
    )

    assert evidence.image_paths == tuple(str(path) for path in ordered)
    assert evidence.image_hashes == tuple(
        hashlib.sha256(path.read_bytes()).hexdigest() for path in ordered
    )


def test_request_uses_separate_original_blocks_not_a_contact_sheet(monkeypatch, tmp_path):
    images = _write_images(tmp_path, 3)
    calls = _fake_transport(monkeypatch)

    visual_understand.understand_ordered(
        images,
        prompt="Read every page in order.",
        model="gpt-5.6-sol",
    )

    assert len(calls) == 1
    blocks = _image_blocks(calls[0])
    assert len(blocks) == 3
    assert [_data_url_bytes(block["image_url"]) for block in blocks] == [
        path.read_bytes() for path in images
    ]


def test_explicit_model_is_required_and_aliases_are_rejected(monkeypatch, tmp_path):
    images = _write_images(tmp_path, 1)
    calls = _fake_transport(monkeypatch)

    with pytest.raises(AstridError, match="rejects model alias"):
        visual_understand.understand_ordered(images, prompt="Read.", model="best")
    assert calls == []

    evidence = visual_understand.understand_ordered(
        images,
        prompt="Read.",
        model="gpt-5.6-sol",
    )
    assert evidence.model == "gpt-5.6-sol"
    assert calls[0]["payload"]["model"] == "gpt-5.6-sol"


def test_cost_ceiling_is_hard_and_boundary_is_allowed(monkeypatch, tmp_path):
    images = _write_images(tmp_path, 5)
    calls = _fake_transport(monkeypatch)

    with pytest.raises(AstridError, match="cost ceiling exceeded"):
        visual_understand.understand_ordered(
            images,
            prompt="Read.",
            model="gpt-5.6-sol",
            settings={"cost_ceiling": 4},
        )
    assert calls == []

    evidence = visual_understand.understand_ordered(
        images[:4],
        prompt="Read.",
        model="gpt-5.6-sol",
        settings={"cost_ceiling": 4},
    )
    assert evidence.cost_ceiling == 4
    assert evidence.settings["cost_ceiling"] == 4
    assert len(_image_blocks(calls[0])) == 4


def test_full_request_and_response_provenance_is_recorded(monkeypatch, tmp_path):
    images = _write_images(tmp_path, 2)
    calls = _fake_transport(monkeypatch)
    prompt = "Answer the fixture questions."

    evidence = visual_understand.understand_ordered(
        images,
        prompt=prompt,
        model="gpt-5.6-sol",
        settings={"cost_ceiling": 2, "detail": "low", "max_output_tokens": 321},
        structured=ANSWER_SCHEMA,
    )

    assert evidence.prompt_sha256 == hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    assert evidence.image_hashes == tuple(
        hashlib.sha256(path.read_bytes()).hexdigest() for path in images
    )
    assert evidence.response_id == "resp_ordered_123"
    assert evidence.returned_model == "gpt-5.6-sol-2026-08-01"
    assert evidence.usage == {"input_tokens": 31, "output_tokens": 4, "total_tokens": 35}
    assert evidence.answers == {"answer": "ok"}
    assert evidence.settings["detail"] == "low"
    assert evidence.settings["max_output_tokens"] == 321
    assert evidence.settings["structured"]["schema"] == ANSWER_SCHEMA
    assert calls[0]["payload"]["text"]["format"]["type"] == "json_schema"


def test_structured_answers_are_validated_client_side(monkeypatch, tmp_path):
    images = _write_images(tmp_path, 1)
    calls = _fake_transport(
        monkeypatch,
        response={
            "id": "resp_bad",
            "model": "gpt-5.6-sol-2026-08-01",
            "output_text": json.dumps({"wrong": 42}),
            "usage": {"total_tokens": 10},
        },
    )

    with pytest.raises(AstridError, match="client-side schema validation"):
        visual_understand.understand_ordered(
            images,
            prompt="Read.",
            model="gpt-5.6-sol",
            structured=ANSWER_SCHEMA,
        )
    assert len(calls) == 1


def test_evidence_serialization_is_byte_stable(monkeypatch, tmp_path):
    images = _write_images(tmp_path, 2)
    _fake_transport(monkeypatch)

    evidence = visual_understand.understand_ordered(
        images,
        prompt="Read deterministically.",
        model="gpt-5.6-sol",
        settings={"cost_ceiling": 2, "detail": "high"},
        structured=ANSWER_SCHEMA,
    )

    first_dict = evidence.to_dict()
    second_dict = evidence.to_dict()
    assert first_dict == second_dict
    assert evidence.to_json_bytes() == evidence.to_json_bytes()
    assert b"created_at" not in evidence.to_json_bytes()
    assert json.loads(evidence.to_json()) == first_dict
