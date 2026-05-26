from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from astrid.core.executor.registry import load_default_registry, resolve_executor_callable
from astrid.core.pack_resolver import (
    CallableNotFoundError,
    PackResolver,
    PackResolverError,
    importlib_resolve,
    resolve_callable_from_metadata,
)


def _write_fixture_module(tmp_path: Path, module_name: str, body: str) -> None:
    (tmp_path / f"{module_name}.py").write_text(textwrap.dedent(body), encoding="utf-8")


def test_importlib_resolve_returns_callable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_fixture_module(
        tmp_path,
        "resolver_ok",
        """
        def build():
            return "ok"
        """,
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    target = importlib_resolve("resolver_ok", "build")

    assert target() == "ok"


def test_resolve_callable_from_metadata_defaults_to_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_fixture_module(
        tmp_path,
        "resolver_default_main",
        """
        def main():
            return "main"
        """,
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    target = resolve_callable_from_metadata(
        {"runtime_module": "resolver_default_main"},
        owner_id="test.executor",
    )

    assert target() == "main"


def test_pack_resolver_validates_metadata_strictly() -> None:
    with pytest.raises(PackResolverError, match=r"test\.executor manifest is missing metadata\.runtime_module"):
        resolve_callable_from_metadata({}, owner_id="test.executor")

    with pytest.raises(PackResolverError, match=r"test\.executor manifest has invalid metadata\.runtime_entrypoint"):
        resolve_callable_from_metadata(
            {"runtime_module": "math", "runtime_entrypoint": ""},
            owner_id="test.executor",
        )


def test_resolve_callable_from_metadata_wraps_missing_module_contextually() -> None:
    with pytest.raises(
        PackResolverError,
        match=r"test\.executor runtime target missing_resolver_module\.build could not be resolved",
    ):
        resolve_callable_from_metadata(
            {
                "runtime_module": "missing_resolver_module",
                "runtime_entrypoint": "build",
            },
            owner_id="test.executor",
        )


def test_resolve_callable_from_metadata_wraps_missing_attribute_contextually(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_fixture_module(
        tmp_path,
        "resolver_missing_attr",
        """
        value = 1
        """,
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(
        CallableNotFoundError,
        match=r"test\.executor runtime target resolver_missing_attr\.build could not be resolved",
    ):
        resolve_callable_from_metadata(
            {
                "runtime_module": "resolver_missing_attr",
                "runtime_entrypoint": "build",
            },
            owner_id="test.executor",
        )


def test_resolve_callable_from_metadata_wraps_non_callable_attribute_contextually(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_fixture_module(
        tmp_path,
        "resolver_non_callable",
        """
        build = "not callable"
        """,
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(
        CallableNotFoundError,
        match=r"test\.executor runtime target resolver_non_callable\.build could not be resolved",
    ):
        resolve_callable_from_metadata(
            {
                "runtime_module": "resolver_non_callable",
                "runtime_entrypoint": "build",
            },
            owner_id="test.executor",
        )


def test_pack_resolver_uses_configured_metadata_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_fixture_module(
        tmp_path,
        "resolver_custom_keys",
        """
        def entry():
            return "custom"
        """,
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    target = PackResolver(module_key="module", callable_key="callable").resolve(
        {"module": "resolver_custom_keys", "callable": "entry"},
        owner_id="test.executor",
    )

    assert target() == "custom"


def test_resolve_executor_callable_uses_manifest_metadata() -> None:
    registry = load_default_registry()
    executor = registry.get("rendering.render")

    target = resolve_executor_callable(executor)

    assert target.__module__ == "astrid.packs.rendering.executors.render.run"
    assert target.__name__ == "main"
