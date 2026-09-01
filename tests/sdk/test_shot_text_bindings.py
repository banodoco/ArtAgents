"""Remote SDK coverage for runtime-owned immutable shot text bindings."""

from __future__ import annotations

from astrid.sdk.remote import RemoteShots


class _Transport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def list_project_shot_text_bindings(self, *args, **kwargs):
        self.calls.append(("list", args, kwargs))
        return ([{"binding_id": "b1"}], None)

    def get_project_shot_text_binding(self, *args, **kwargs):
        self.calls.append(("get", args, kwargs))
        return {"binding_id": "b1"}

    def set_project_shot_text_binding(self, *args, **kwargs):
        self.calls.append(("set", args, kwargs))
        return {"data": {"binding_id": "b1"}, "receipt": None}

    def set_project_shot_text_binding_by_id(self, *args, **kwargs):
        self.calls.append(("set_by_id", args, kwargs))
        return {"data": {"binding_id": "b1"}, "receipt": None}

    def rebind_project_shot_text_binding(self, *args, **kwargs):
        self.calls.append(("rebind", args, kwargs))
        return {"data": {"binding_id": "b1"}, "receipt": None}


def test_text_binding_methods_are_thin_runtime_adapters() -> None:
    transport = _Transport()
    shots = RemoteShots(transport)

    assert shots.list_text_bindings("p1", shot_id="s1", kind="prompt", slot="hero").ok
    assert shots.show_text_binding("p1", "b1").ok
    assert shots.set_text_binding(
        "p1", shot_id="s1", kind="prompt", slot="hero", text="hello", expected_head=0,
        idempotency_key="set-1",
    ).ok
    assert shots.set_text_binding(
        "p1", shot_id="ignored", kind="prompt", text="world", expected_head=1,
        binding_id="b1", idempotency_key="set-2",
    ).ok
    assert shots.rebind_text_binding(
        "p1", "b1", media_id="sha256:" + "a" * 64, expected_head=1,
        idempotency_key="rebind-1",
    ).ok

    assert transport.calls == [
        ("list", ("p1",), {"shot_id": "s1", "kind": "prompt", "slot": "hero"}),
        ("get", ("p1", "b1"), {}),
        (
            "set", ("p1", {"shot_id": "s1", "kind": "prompt", "text": "hello", "expected_head": 0, "slot": "hero"}),
            {"idempotency_key": "set-1"},
        ),
        (
            "set_by_id", ("p1", "b1", {"binding_id": "b1", "text": "world", "expected_head": 1}),
            {"idempotency_key": "set-2"},
        ),
        (
            "rebind", ("p1", "b1"),
            {"media_id": "sha256:" + "a" * 64, "expected_head": 1, "idempotency_key": "rebind-1"},
        ),
    ]
