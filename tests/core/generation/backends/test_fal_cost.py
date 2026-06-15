"""Fixture tests for FalBackend cost selection logic.

Covers:
  - API-reported cost preferred over registry price
  - Registry price fallback when API cost is missing
  - Registry price fallback when API cost is non-numeric (invalid)
  - Registry fallback multiplies by actual asset count
  - Unpriced backends keep cost_usd=None
  - API cost of 0 (valid, zero-cost response) is used as-is
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.core.generation.backends.fal import FalBackend
from astrid.core.model_catalog.schema import BackendSpec, ModelEntry, ModeSpec, Price

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_entry(
    *,
    model_id: str = "flux-dev",
    mode: str = "t2i",
    endpoint: str = "fal-ai/flux/dev",
    price: Price | None = None,
    lora_endpoint: str | None = None,
    modality: str = "image",
    supports: tuple[str, ...] | None = None,
) -> ModelEntry:
    """Build a minimal ModelEntry with a single cloud backend."""
    if supports is None:
        supports = ("prompt", "seed", "size")
    return ModelEntry(
        id=model_id,
        modality=modality,
        modes={
            mode: ModeSpec(
                supports=supports,
                requires=("prompt",),
                backends={
                    "cloud": BackendSpec(
                        endpoint=endpoint,
                        lora_endpoint=lora_endpoint,
                        param_map={feature: feature for feature in supports},
                        price=price,
                    )
                },
            )
        },
    )


def _make_fal_result(
    *,
    images: list[dict[str, str]] | None = None,
    cost: float | int | str | None = None,
    request_id: str | None = None,
) -> dict:
    """Build a fal-style result dict.

    *images*: list of ``{"url": "https://..."}`` dicts (default: 1 image).
    """
    if images is None:
        images = [{"url": "https://example.com/output_000.png"}]
    result: dict = {"images": images}
    if cost is not None:
        result["cost"] = cost
    if request_id is not None:
        result["request_id"] = request_id
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFalCostSelection:
    """Cost precedence: API cost > registry price > None."""

    def test_api_cost_preferred_over_registry_price(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the fal API reports a cost, it is used even when registry
        price is also available."""
        from astrid.core.generation.backends import fal as fal_mod

        monkeypatch.setenv("FAL_KEY", "test-key")
        out_dir = tmp_path / "out"

        result = _make_fal_result(cost=0.05)
        entry = _make_entry(price=Price(usd=0.025, unit="image"))

        with patch.object(fal_mod, "fal_submit_and_poll", return_value=result):
            # Prevent real HTTP downloads
            with patch.object(
                fal_mod.FalBackend,
                "_resolve_api_key",
                return_value="test-key",
            ):
                backend = FalBackend()
                # The client.get_bytes would fail — mock it
                with patch.object(
                    backend._client, "get_bytes", return_value=b"\x89PNG\r\n\x1a\n"
                ):
                    gen_result = backend.generate(
                        entry=entry,
                        mode="t2i",
                        params={"prompt": "test", "seed": 42},
                        out_dir=out_dir,
                    )

        # API reported 0.05; registry price is 0.025 — API must win
        assert gen_result.cost_usd == 0.05

    def test_registry_fallback_when_api_cost_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the API result has no 'cost' key, fall back to
        len(asset_urls) * price.usd."""
        from astrid.core.generation.backends import fal as fal_mod

        monkeypatch.setenv("FAL_KEY", "test-key")
        out_dir = tmp_path / "out"

        # Two images, no cost key
        result = _make_fal_result(
            images=[
                {"url": "https://example.com/output_000.png"},
                {"url": "https://example.com/output_001.png"},
            ],
            cost=None,  # key absent
        )
        entry = _make_entry(price=Price(usd=0.025, unit="image"))

        with patch.object(fal_mod, "fal_submit_and_poll", return_value=result):
            with patch.object(
                fal_mod.FalBackend,
                "_resolve_api_key",
                return_value="test-key",
            ):
                backend = FalBackend()
                with patch.object(
                    backend._client, "get_bytes", return_value=b"\x89PNG\r\n\x1a\n"
                ):
                    gen_result = backend.generate(
                        entry=entry,
                        mode="t2i",
                        params={"prompt": "test", "seed": 42},
                        out_dir=out_dir,
                    )

        # 2 assets × $0.025 = $0.05
        assert gen_result.cost_usd == 0.05

    def test_registry_fallback_when_api_cost_invalid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the API result has a non-numeric 'cost' (e.g. string),
        fall back to registry price."""
        from astrid.core.generation.backends import fal as fal_mod

        monkeypatch.setenv("FAL_KEY", "test-key")
        out_dir = tmp_path / "out"

        result = _make_fal_result(cost="n/a")  # non-numeric
        entry = _make_entry(price=Price(usd=0.025, unit="image"))

        with patch.object(fal_mod, "fal_submit_and_poll", return_value=result):
            with patch.object(
                fal_mod.FalBackend,
                "_resolve_api_key",
                return_value="test-key",
            ):
                backend = FalBackend()
                with patch.object(
                    backend._client, "get_bytes", return_value=b"\x89PNG\r\n\x1a\n"
                ):
                    gen_result = backend.generate(
                        entry=entry,
                        mode="t2i",
                        params={"prompt": "test", "seed": 42},
                        out_dir=out_dir,
                    )

        # Invalid API cost → fallback to 1 asset × $0.025 = $0.025
        assert gen_result.cost_usd == 0.025

    def test_unpriced_backend_keeps_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the backend has no registry price and the API reports no
        cost, cost_usd stays None."""
        from astrid.core.generation.backends import fal as fal_mod

        monkeypatch.setenv("FAL_KEY", "test-key")
        out_dir = tmp_path / "out"

        result = _make_fal_result(cost=None)  # no cost key
        entry = _make_entry(price=None)  # no registry price

        with patch.object(fal_mod, "fal_submit_and_poll", return_value=result):
            with patch.object(
                fal_mod.FalBackend,
                "_resolve_api_key",
                return_value="test-key",
            ):
                backend = FalBackend()
                with patch.object(
                    backend._client, "get_bytes", return_value=b"\x89PNG\r\n\x1a\n"
                ):
                    gen_result = backend.generate(
                        entry=entry,
                        mode="t2i",
                        params={"prompt": "test", "seed": 42},
                        out_dir=out_dir,
                    )

        assert gen_result.cost_usd is None

    def test_api_zero_cost_used_as_is(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A valid API cost of 0 (free tier / zero-cost response) is
        used directly, not overridden by registry price."""
        from astrid.core.generation.backends import fal as fal_mod

        monkeypatch.setenv("FAL_KEY", "test-key")
        out_dir = tmp_path / "out"

        result = _make_fal_result(cost=0.0)
        entry = _make_entry(price=Price(usd=0.025, unit="image"))

        with patch.object(fal_mod, "fal_submit_and_poll", return_value=result):
            with patch.object(
                fal_mod.FalBackend,
                "_resolve_api_key",
                return_value="test-key",
            ):
                backend = FalBackend()
                with patch.object(
                    backend._client, "get_bytes", return_value=b"\x89PNG\r\n\x1a\n"
                ):
                    gen_result = backend.generate(
                        entry=entry,
                        mode="t2i",
                        params={"prompt": "test", "seed": 42},
                        out_dir=out_dir,
                    )

        # Zero is a valid cost — registry fallback must not override it
        assert gen_result.cost_usd == 0.0

    def test_registry_fallback_with_single_asset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With one asset and registry price, fallback equals price.usd."""
        from astrid.core.generation.backends import fal as fal_mod

        monkeypatch.setenv("FAL_KEY", "test-key")
        out_dir = tmp_path / "out"

        result = _make_fal_result(
            images=[{"url": "https://example.com/output_000.png"}],
            cost=None,
        )
        entry = _make_entry(price=Price(usd=0.025, unit="image"))

        with patch.object(fal_mod, "fal_submit_and_poll", return_value=result):
            with patch.object(
                fal_mod.FalBackend,
                "_resolve_api_key",
                return_value="test-key",
            ):
                backend = FalBackend()
                with patch.object(
                    backend._client, "get_bytes", return_value=b"\x89PNG\r\n\x1a\n"
                ):
                    gen_result = backend.generate(
                        entry=entry,
                        mode="t2i",
                        params={"prompt": "test", "seed": 42},
                        out_dir=out_dir,
                    )

        assert gen_result.cost_usd == 0.025

    def test_api_cost_none_with_priced_backend(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicit None cost in result (JSON null) still falls back to
        registry price."""
        from astrid.core.generation.backends import fal as fal_mod

        monkeypatch.setenv("FAL_KEY", "test-key")
        out_dir = tmp_path / "out"

        # Explicit None as value (not just missing key)
        result = _make_fal_result(cost=None)
        entry = _make_entry(price=Price(usd=0.025, unit="image"))

        with patch.object(fal_mod, "fal_submit_and_poll", return_value=result):
            with patch.object(
                fal_mod.FalBackend,
                "_resolve_api_key",
                return_value="test-key",
            ):
                backend = FalBackend()
                with patch.object(
                    backend._client, "get_bytes", return_value=b"\x89PNG\r\n\x1a\n"
                ):
                    gen_result = backend.generate(
                        entry=entry,
                        mode="t2i",
                        params={"prompt": "test", "seed": 42},
                        out_dir=out_dir,
                    )

        assert gen_result.cost_usd == 0.025

    def test_second_based_registry_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When price unit is 'second', fallback uses params['duration'] * usd."""
        from astrid.core.generation.backends import fal as fal_mod

        monkeypatch.setenv("FAL_KEY", "test-key")
        out_dir = tmp_path / "out"

        result = {
            "audio": {"url": "https://example.com/output_000.mp3"},
            # No API-reported cost
        }
        entry = _make_entry(
            model_id="ace-step",
            mode="music",
            endpoint="fal-ai/ace-step/prompt-to-audio",
            modality="audio",
            supports=("prompt", "seed", "duration"),
            price=Price(usd=0.0002, unit="second"),
        )

        with patch.object(fal_mod, "fal_submit_and_poll", return_value=result):
            with patch.object(
                fal_mod.FalBackend,
                "_resolve_api_key",
                return_value="test-key",
            ):
                backend = FalBackend()
                with patch.object(
                    backend._client, "get_bytes", return_value=b"fake_mp3_data"
                ):
                    gen_result = backend.generate(
                        entry=entry,
                        mode="music",
                        params={"prompt": "test", "seed": 42, "duration": 30},
                        out_dir=out_dir,
                    )

        # 30 seconds * $0.0002/second = $0.006
        assert gen_result.cost_usd == 0.006

    def test_second_based_registry_fallback_no_duration(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When price unit is 'second' and duration is absent, cost is zero."""
        from astrid.core.generation.backends import fal as fal_mod

        monkeypatch.setenv("FAL_KEY", "test-key")
        out_dir = tmp_path / "out"

        result = {
            "audio": {"url": "https://example.com/output_000.mp3"},
        }
        entry = _make_entry(
            model_id="ace-step",
            mode="music",
            endpoint="fal-ai/ace-step/prompt-to-audio",
            modality="audio",
            supports=("prompt", "seed", "duration"),
            price=Price(usd=0.0002, unit="second"),
        )

        with patch.object(fal_mod, "fal_submit_and_poll", return_value=result):
            with patch.object(
                fal_mod.FalBackend,
                "_resolve_api_key",
                return_value="test-key",
            ):
                backend = FalBackend()
                with patch.object(
                    backend._client, "get_bytes", return_value=b"fake_mp3_data"
                ):
                    gen_result = backend.generate(
                        entry=entry,
                        mode="music",
                        params={"prompt": "test", "seed": 42},
                        out_dir=out_dir,
                    )

        assert gen_result.cost_usd == 0.0
