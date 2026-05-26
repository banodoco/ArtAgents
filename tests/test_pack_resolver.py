from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.executor.schema import CommandSpec, ExecutorDefinition
from astrid.core.pack_resolver import CallableNotFoundError, PackResolver, PackResolverError


def _executor(*, executor_id: str, metadata: dict[str, object]) -> ExecutorDefinition:
    return ExecutorDefinition(
        id=executor_id,
        name="Test Executor",
        kind="external",
        version="1.0",
        command=CommandSpec(argv=("echo",)),
        metadata=metadata,
    )


def test_pack_resolver_resolves_runtime_defaults_for_regular_executor() -> None:
    target = PackResolver().resolve(
        _executor(
            executor_id="rendering.render",
            metadata={"runtime_module": "astrid.packs.rendering.executors.render.run"},
        ).metadata,
        owner_id="rendering.render",
    )

    assert target.__module__ == "astrid.packs.rendering.executors.render.run"
    assert target.__name__ == "main"


def test_pack_resolver_uses_custom_metadata_keys_for_youtube_style_targets() -> None:
    target = PackResolver(module_key="callable_module", callable_key="callable_name").resolve(
        {
            "callable_module": "astrid.packs.youtube.executors.upload.src.social_publish",
            "callable_name": "publish_youtube_video",
        },
        owner_id="youtube.upload",
    )

    assert target.__module__ == "astrid.packs.youtube.executors.upload.src.social_publish"
    assert target.__name__ == "publish_youtube_video"


def test_pack_resolver_reports_missing_runtime_metadata_contextually() -> None:
    with pytest.raises(PackResolverError, match=r"test\.missing manifest is missing metadata\.runtime_module"):
        PackResolver().resolve({}, owner_id="test.missing")


def test_pack_resolver_wraps_bad_callable_metadata_contextually() -> None:
    with pytest.raises(
        CallableNotFoundError,
        match=r"test\.broken runtime target math\.pi could not be resolved",
    ):
        PackResolver().resolve(
            {"runtime_module": "math", "runtime_entrypoint": "pi"},
            owner_id="test.broken",
        )
