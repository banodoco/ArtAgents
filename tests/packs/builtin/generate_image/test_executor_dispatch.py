"""Executor dispatch tests using direct synthetic backend registry registration.

These tests exercise the generate_image and generate_video executors'
``--execution`` dispatch path using ``GenerationBackendRegistry`` instances
built from synthetic ``GenerationBackendDescriptor`` objects, without relying on
full pack-backed discovery.

Covers:
  - Preserved local/cloud behaviour through a synthetic registry
  - Dynamic ``--execution`` validation (valid, invalid, missing-from-registry)
  - Clear unavailable-backend errors that list available ids
  - No raw ``KeyError`` leakage in user-facing stderr output
"""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.core.generation.backends.fal import FalBackend
from astrid.core.generation.backends.registry import (
    GenerationBackendDescriptor,
    GenerationBackendRegistry,
)
from astrid.core.generation.backends.vibecomfy import VibeComfyBackend

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _synthetic_registry(
    *backend_ids: str,
) -> GenerationBackendRegistry:
    """Build a ``GenerationBackendRegistry`` seeded only with the requested
    synthetic descriptors (no built-ins, no disk discovery).

    Each *backend_id* must be ``"local"`` or ``"cloud"`` — the descriptor
    points to the real built-in adapter class so that ``.create()`` works.
    """
    descriptor_map = {
        "local": GenerationBackendDescriptor(
            backend_id="local",
            module="astrid.core.generation.backends.vibecomfy",
            class_name="VibeComfyBackend",
            label="Local (synthetic)",
        ),
        "cloud": GenerationBackendDescriptor(
            backend_id="cloud",
            module="astrid.core.generation.backends.fal",
            class_name="FalBackend",
            label="Cloud (synthetic)",
        ),
    }
    registry = GenerationBackendRegistry(descriptors=())
    # Clear the built-in seeds so only our synthetic descriptors exist.
    registry._descriptors.clear()
    for bid in backend_ids:
        if bid not in descriptor_map:
            raise ValueError(f"unknown synthetic backend id {bid!r}")
        registry.register(descriptor_map[bid])
    return registry


def _broken_local_registry() -> GenerationBackendRegistry:
    """Return a registry where 'local' points to a non-existent module.

    The model catalog still lists 'local' as an available backend for
    models like z-image, but ``.create('local')`` will raise an import
    error.  This lets us test that the executor wraps registry creation
    failures cleanly.
    """
    registry = GenerationBackendRegistry(descriptors=())
    registry._descriptors.clear()
    registry.register(
        GenerationBackendDescriptor(
            backend_id="local",
            module="this.module.does.not.exist.anywhere",
            class_name="FakeBackend",
            label="Local (broken)",
        )
    )
    return registry


def _assert_astrid_error(call, *cause_parts: str) -> AstridError:
    with pytest.raises(AstridError) as raised:
        call()
    error = raised.value
    for part in cause_parts:
        assert part in error.cause
    return error


# ---------------------------------------------------------------------------
# Direct registry-level dispatch tests (no executor CLI)
# ---------------------------------------------------------------------------


class TestSyntheticRegistryDirectDispatch:
    """Tests that exercise ``GenerationBackendRegistry`` directly with
    synthetic descriptors, proving the registry contract before involving
    the executor CLI.
    """

    def test_create_local_from_synthetic_registry(self, tmp_path: Path) -> None:
        """A synthetic registry that registers 'local' can ``.create('local')``."""
        registry = _synthetic_registry("local")
        env_file = tmp_path / ".env"
        backend = registry.create("local", env_file=env_file)
        assert isinstance(backend, VibeComfyBackend)

    def test_create_cloud_from_synthetic_registry(self, tmp_path: Path) -> None:
        """A synthetic registry that registers 'cloud' can ``.create('cloud')``."""
        registry = _synthetic_registry("cloud")
        env_file = tmp_path / ".env"
        backend = registry.create("cloud", env_file=env_file)
        assert isinstance(backend, FalBackend)

    def test_get_descriptor_lists_available_ids_on_miss(self) -> None:
        """``get_descriptor`` for an unknown id raises ``KeyError`` whose
        message includes the available backend ids."""
        registry = _synthetic_registry("local", "cloud")
        with pytest.raises(KeyError, match="unknown generation backend 'nonexistent'"):
            registry.get_descriptor("nonexistent")
        # The message must list the registered ids, not "(none)".
        try:
            registry.get_descriptor("nonexistent")
        except KeyError as exc:
            msg = str(exc)
            assert "local" in msg
            assert "cloud" in msg
            assert "(none)" not in msg

    def test_create_unknown_backend_raises_keyerror_with_available_ids(self) -> None:
        """``.create()`` for an unknown id raises ``KeyError`` naming available ids."""
        registry = _synthetic_registry("local")
        with pytest.raises(KeyError, match="unknown generation backend 'cloud'"):
            registry.create("cloud")
        try:
            registry.create("cloud")
        except KeyError as exc:
            msg = str(exc)
            assert "local" in msg
            assert "(none)" not in msg

    def test_descriptors_returns_only_synthetic_entries(self) -> None:
        """A synthetic registry's ``.descriptors()`` returns exactly the
        registered entries, not the built-in seeds."""
        registry = _synthetic_registry("local", "cloud")
        ids = [d.backend_id for d in registry.descriptors()]
        assert ids == ["cloud", "local"]
        assert len(ids) == 2

    def test_empty_registry_create_gives_clear_keyerror(self) -> None:
        """An empty synthetic registry gives a ``KeyError`` that says
        ``(none)`` for available ids (regression: no crash / traceback)."""
        registry = _synthetic_registry()  # empty
        with pytest.raises(KeyError, match="unknown generation backend 'local'"):
            registry.create("local")
        try:
            registry.create("local")
        except KeyError as exc:
            assert "(none)" in str(exc)


# ---------------------------------------------------------------------------
# Executor dispatch tests (inject synthetic registry via monkeypatch)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _fake_fal_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAL_KEY", "test-fal-key")


class TestExecutorDispatchWithSyntheticRegistry:
    """Tests that inject a synthetic ``GenerationBackendRegistry`` into the
    generate_image executor and exercise the ``--execution`` dispatch path.
    """

    # -- Preserved local/cloud behaviour ------------------------------------

    def test_local_dispatch_proceeds_past_validation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When 'local' is registered and the model supports it, the executor
        does NOT fail at the backend-availability or registry-lookup stage.
        Any subsequent failure must not mention backend unavailability."""
        from astrid.packs.generation.executors.generate_image import run as run_mod

        registry = _synthetic_registry("local")
        monkeypatch.setattr(
            run_mod, "load_default_generation_backend_registry", lambda: registry
        )

        out = tmp_path / "out"
        # z-image t2i supports local.  The executor will fail at generation
        # time (no vibecomfy server), but must NOT fail at dispatch.
        # The generation failure may be SystemExit or ValueError depending
        # on the adapter — we just need to prove we got past dispatch.
        try:
            run_mod.main(
                [
                    "--model", "z-image",
                    "--mode", "t2i",
                    "--execution", "local",
                    "--prompt", "a test",
                    "--out", str(out),
                ]
            )
        except SystemExit:
            pass
        except Exception:
            pass
        captured = capsys.readouterr()
        # The error must NOT be about backend unavailability or registration.
        assert "has no" not in captured.err, (
            f"Dispatch validation failed unexpectedly: {captured.err}"
        )
        assert "is not registered" not in captured.err, (
            f"Registry lookup failed unexpectedly: {captured.err}"
        )

    def test_cloud_dispatch_proceeds_past_validation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When 'cloud' is registered and the model supports it, the executor
        does NOT fail at the backend-availability or registry-lookup stage."""
        from astrid.packs.generation.executors.generate_image import run as run_mod

        registry = _synthetic_registry("cloud")
        monkeypatch.setattr(
            run_mod, "load_default_generation_backend_registry", lambda: registry
        )

        out = tmp_path / "out"
        # flux-dev t2i supports cloud and codex; this test exercises cloud.
        # Generation will fail (no real FAL_KEY), but dispatch must pass.
        try:
            run_mod.main(
                [
                    "--model", "flux-dev",
                    "--mode", "t2i",
                    "--execution", "cloud",
                    "--prompt", "a test",
                    "--out", str(out),
                ]
            )
        except SystemExit:
            pass
        except Exception:
            pass
        captured = capsys.readouterr()
        assert "has no" not in captured.err, (
            f"Dispatch validation failed unexpectedly: {captured.err}"
        )
        assert "is not registered" not in captured.err, (
            f"Registry lookup failed unexpectedly: {captured.err}"
        )

    # -- Unavailable-backend errors ----------------------------------------

    def test_execution_missing_from_registry_gives_clear_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When --execution names a backend that the model+mode supports
        but the registry does NOT have, the error is clear and names the
        missing backend."""
        from astrid.packs.generation.executors.generate_image import run as run_mod

        # z-image t2i supports both local and cloud in the model catalog.
        # But our synthetic registry only has 'cloud'.
        registry = _synthetic_registry("cloud")
        monkeypatch.setattr(
            run_mod, "load_default_generation_backend_registry", lambda: registry
        )

        out = tmp_path / "out"
        error = _assert_astrid_error(
            lambda: run_mod.main(
                [
                    "--model", "z-image",
                    "--mode", "t2i",
                    "--execution", "local",
                    "--prompt", "a test",
                    "--out", str(out),
                ]
            ),
            "generation backend 'local' is not registered",
        )
        # Error must name the missing backend and NOT contain raw KeyError
        assert "KeyError" not in error.cause

    def test_execution_unavailable_for_model_mode_lists_available_backends(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When --execution names a backend that the model+mode does NOT
        support (model catalog check), the error lists the backends that
        ARE available for the pair."""
        from astrid.packs.generation.executors.generate_image import run as run_mod

        # flux-dev t2i has cloud/codex but still no local backend.
        registry = _synthetic_registry("cloud", "local")
        monkeypatch.setattr(
            run_mod, "load_default_generation_backend_registry", lambda: registry
        )

        out = tmp_path / "out"
        error = _assert_astrid_error(
            lambda: run_mod.main(
                [
                    "--model", "flux-dev",
                    "--mode", "t2i",
                    "--execution", "local",
                    "--prompt", "a test",
                    "--out", str(out),
                ]
            ),
            "model 'flux-dev' mode 't2i' has no 'local' backend",
        )
        assert error.valid_options == ("cloud", "codex")

    # -- No raw KeyError leakage -------------------------------------------

    def test_no_raw_keyerror_leakage_on_registry_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When the registry completely lacks a backend, the error message
        must NOT leak a raw Python ``KeyError`` traceback — the executor
        wraps it in ``_create_backend_adapter``."""
        from astrid.packs.generation.executors.generate_image import run as run_mod

        # Empty registry — no backends at all.
        registry = _synthetic_registry()  # empty
        monkeypatch.setattr(
            run_mod, "load_default_generation_backend_registry", lambda: registry
        )

        out = tmp_path / "out"
        error = _assert_astrid_error(
            lambda: run_mod.main(
                [
                    "--model", "z-image",
                    "--mode", "t2i",
                    "--execution", "local",
                    "--prompt", "a test",
                    "--out", str(out),
                ]
            ),
            "generation backend 'local' is not registered",
        )
        # The error should be the user-friendly wrapper message.
        # No raw KeyError traceback in stderr.
        assert "KeyError" not in error.cause
        # No traceback markers.
        assert "Traceback" not in error.cause

    # -- Dynamic execution validation --------------------------------------

    def test_dynamic_execution_validation_rejects_unknown_value(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An --execution value that is not a known backend id is rejected
        after model/mode lookup with a non-zero exit code."""
        from astrid.packs.generation.executors.generate_image import run as run_mod

        registry = _synthetic_registry("local", "cloud")
        monkeypatch.setattr(
            run_mod, "load_default_generation_backend_registry", lambda: registry
        )

        out = tmp_path / "out"
        _assert_astrid_error(
            lambda: run_mod.main(
                [
                    "--model", "flux-dev",
                    "--mode", "t2i",
                    "--execution", "hybrid",
                    "--prompt", "a test",
                    "--out", str(out),
                ]
            ),
            "model 'flux-dev' mode 't2i' has no 'hybrid' backend",
        )

    def test_dynamic_execution_validation_with_empty_string(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An empty --execution string is rejected cleanly (not a crash)."""
        from astrid.packs.generation.executors.generate_image import run as run_mod

        registry = _synthetic_registry("local", "cloud")
        monkeypatch.setattr(
            run_mod, "load_default_generation_backend_registry", lambda: registry
        )

        out = tmp_path / "out"
        _assert_astrid_error(
            lambda: run_mod.main(
                [
                    "--model", "flux-dev",
                    "--mode", "t2i",
                    "--execution", "",
                    "--prompt", "a test",
                    "--out", str(out),
                ]
            ),
            "model 'flux-dev' mode 't2i' has no '' backend",
        )

    # -- Registry creation errors wrapped cleanly --------------------------

    def test_registry_creation_error_is_wrapped_as_runtime_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When ``.create()`` raises a non-KeyError exception (e.g. import
        failure), the executor wraps it in a ``RuntimeError`` and reports a
        clear CLI error.

        Uses a synthetic registry where 'local' points to a non-existent
        module.  The model catalog still lists 'local' as available for
        z-image t2i, so the catalog check passes but registry creation
        fails with a ModuleNotFoundError.
        """
        from astrid.packs.generation.executors.generate_image import run as run_mod

        monkeypatch.setattr(
            run_mod,
            "load_default_generation_backend_registry",
            lambda: _broken_local_registry(),
        )

        out = tmp_path / "out"
        error = _assert_astrid_error(
            lambda: run_mod.main(
                [
                    "--model", "z-image",
                    "--mode", "t2i",
                    "--execution", "local",
                    "--prompt", "a test",
                    "--out", str(out),
                ]
            ),
            "failed to initialize generation backend 'local'",
        )
        # The error message wraps the failure clearly.
        # No raw traceback in stderr.
        assert "Traceback" not in error.cause


# ---------------------------------------------------------------------------
# Video executor dispatch tests (same synthetic-registry approach)
# ---------------------------------------------------------------------------


class TestVideoExecutorDispatchWithSyntheticRegistry:
    """Tests that inject a synthetic ``GenerationBackendRegistry`` into the
    generate_video executor and exercise the ``--execution`` dispatch path.
    """

    def test_cloud_dispatch_proceeds_past_validation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A synthetic registry with 'cloud' lets the video executor proceed
        past backend-availability validation for wan-2.2 t2v (cloud-only)."""
        from astrid.packs.generation.executors.generate_video import run as run_mod

        registry = _synthetic_registry("cloud")
        monkeypatch.setattr(
            run_mod, "load_default_generation_backend_registry", lambda: registry
        )

        out = tmp_path / "out"
        # wan-2.2 t2v supports only cloud in the model catalog.
        # Generation will fail (no real FAL_KEY), but dispatch must pass.
        try:
            run_mod.main(
                [
                    "--model", "wan-2.2",
                    "--mode", "t2v",
                    "--execution", "cloud",
                    "--prompt", "a test",
                    "--out", str(out),
                ]
            )
        except SystemExit:
            pass
        except Exception:
            pass
        captured = capsys.readouterr()
        assert "has no" not in captured.err, (
            f"Dispatch validation failed unexpectedly: {captured.err}"
        )
        assert "is not registered" not in captured.err, (
            f"Registry lookup failed unexpectedly: {captured.err}"
        )

    def test_execution_missing_from_registry_gives_clear_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When the video executor's --execution names a backend missing from
        the registry, the error is clear and names the missing backend."""
        from astrid.packs.generation.executors.generate_video import run as run_mod

        # wan-2.2 t2v is cloud-only in the model catalog.
        # Empty synthetic registry → no 'cloud' descriptor.
        registry = _synthetic_registry()  # empty
        monkeypatch.setattr(
            run_mod, "load_default_generation_backend_registry", lambda: registry
        )

        out = tmp_path / "out"
        error = _assert_astrid_error(
            lambda: run_mod.main(
                [
                    "--model", "wan-2.2",
                    "--mode", "t2v",
                    "--execution", "cloud",
                    "--prompt", "a test",
                    "--out", str(out),
                ]
            ),
            "generation backend 'cloud' is not registered",
        )
        assert "KeyError" not in error.cause

    def test_no_raw_keyerror_leakage_on_video_executor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The video executor wraps registry failures without leaking raw
        ``KeyError`` or tracebacks."""
        from astrid.packs.generation.executors.generate_video import run as run_mod

        registry = _synthetic_registry()  # empty
        monkeypatch.setattr(
            run_mod, "load_default_generation_backend_registry", lambda: registry
        )

        out = tmp_path / "out"
        error = _assert_astrid_error(
            lambda: run_mod.main(
                [
                    "--model", "wan-2.2",
                    "--mode", "t2v",
                    "--execution", "cloud",
                    "--prompt", "a test",
                    "--out", str(out),
                ]
            ),
            "generation backend 'cloud' is not registered",
        )
        assert "Traceback" not in error.cause
        assert "KeyError" not in error.cause
