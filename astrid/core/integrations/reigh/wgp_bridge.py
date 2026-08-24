"""In-process Wan2GP boundary: cwd/sys.path contract (Batch B7, gate ②).

Preserves the reigh-worker boot contract byte-for-byte (doc 03 §1.2,
``server.py``): the vendored tree goes on ``sys.path``, then
``os.chdir(<Wan2GP>/)``, ``sys.argv = ["worker.py"]``, env spoofs
(``WORKER_ID``, ``WAN2GP_WORKER_MODE=true``), ``import wgp``, and
``--wgp-*`` style overrides applied onto ``wgp.server_config``. Any
failure refuses typed and closed; the boundary restores cwd/argv/path/env
in ``finally`` so a refused attempt never leaks process state.

*wgp_config.json key schema* (T7.1) is reconstructed below against the
pinned bytes — :data:`DEFAULT_SERVER_CONFIG` records the default literal
from pinned ``wgp.py`` and :func:`verify_config_schema_against_pin`
re-derives the key set from those bytes by AST so drift rejects
mechanically. Boot rewrites **only** this file, and only schema keys.
"""

from __future__ import annotations

import ast
import contextlib
import importlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from astrid.core.foundation.paths import REPO_ROOT

WGP_CHECKOUT_ENV = "REIGH_WGP_HOME"
"""Env override for the pinned Wan2GP tree root."""

DEFAULT_CHECKOUT = REPO_ROOT.parent / "vendor" / "Wan2GP"
"""The vendored submodule location (sibling of the Astrid repo root)."""


class WgpBridgeRefused(Exception):
    """Typed fail-closed base for every bridge refusal."""


class CheckoutUnavailable(WgpBridgeRefused):
    """The pinned Wan2GP tree is missing or incomplete."""


class WgpImportUnavailable(WgpBridgeRefused):
    """``import wgp`` failed inside the boundary; names the prerequisite."""


def resolve_checkout(
    checkout: str | Path | None = None,
) -> Path:
    """Resolve the pinned tree: explicit arg > env > vendored default."""
    if checkout is not None:
        resolved = Path(checkout)
    else:
        env = os.environ.get(WGP_CHECKOUT_ENV)
        resolved = Path(env) if env else DEFAULT_CHECKOUT
    return resolved.resolve()


def require_checkout(checkout: str | Path | None = None) -> Path:
    """Resolve AND verify the tree's load-bearing bytes exist."""
    resolved = resolve_checkout(checkout)
    worker_entry = resolved / "wgp.py"
    if not worker_entry.is_file():
        raise CheckoutUnavailable(
            f"pinned Wan2GP tree not found at {resolved} "
            f"(expected {worker_entry}; set {WGP_CHECKOUT_ENV}); "
            "vendor it with: git clone --branch reigh-sprint-3 "
            "https://github.com/banodoco/Wan2GP "
            f"{DEFAULT_CHECKOUT} && git checkout "
            "181bb71a21008032e4771e11663f33e4489c4512"
        )
    return resolved


def ensure_wan2gp_on_path(checkout: Path) -> bool:
    """Put the pinned tree at the FRONT of ``sys.path``.

    Returns whether this call inserted an entry (idempotent); callers
    running under the session boundary restore via that flag instead of
    guessing.
    """
    text = str(checkout)
    if text in sys.path:
        return False
    sys.path.insert(0, text)
    return True


# ---------------------------------------------------------------------------
# wgp_config.json key schema — reconstructed against the pinned SHA
# (181bb71a21008032e4771e11663f33e4489c4512), exists nowhere else.
# ---------------------------------------------------------------------------

DEFAULT_SERVER_CONFIG: dict[str, Any] = {
    "attention_mode": "auto",
    "transformer_types": [],
    "transformer_quantization": "int8",
    "text_encoder_quantization": "int8",
    "lm_decoder_engine": "",
    "save_path": "outputs",
    "image_save_path": "outputs",
    "compile": "",
    "metadata_type": "metadata",
    "boost": 1,
    "enable_int8_kernels": 1,
    "clear_file_list": 5,
    "enable_4k_resolutions": 0,
    "max_reserved_loras": -1,
    "vae_config": 0,
    "profile": 3,
    "video_profile": 3,
    "image_profile": 3,
    "audio_profile": 3.5,
    "preload_model_policy": [],
    "UI_theme": "default",
    "checkpoints_paths": ["ckpts"],
    "loras_root": "loras",
    "save_queue_if_crash": 1,
    "queue_color_scheme": "pastel",
    "model_hierarchy_type": 1,
    "mmaudio_mode": 0,
    "mmaudio_persistence": 1,
    "rife_version": "v4",
    "prompt_enhancer_quantization": "quanto_int8",
    "prompt_enhancer_temperature": 0.6,
    "prompt_enhancer_top_p": 0.9,
    "prompt_enhancer_randomize_seed": True,
    "audio_save_path": "outputs",
}

WGP_CONFIG_SCHEMA: frozenset[str] = frozenset(DEFAULT_SERVER_CONFIG)
CONFIG_FILENAME = "wgp_config.json"


def _pinned_default_config_keys(wgp_py: Path) -> set[str]:
    """AST-derive the default ``server_config`` keys from pinned bytes.

    Walks the ``server_config = {...}`` assignment in *wgp_py* and returns
    its string-literal keys — the authoritative schema, straight from the
    pinned source, no execution needed (CPU-safe).
    """
    tree = ast.parse(wgp_py.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "server_config"
            and isinstance(node.value, ast.Dict)
        ):
            keys = set()
            for key in node.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
            return keys
    raise WgpBridgeRefused(
        f"no server_config default literal found in {wgp_py}"
    )


def verify_config_schema_against_pin(checkout: Path) -> list[str]:
    """Reconstruct the schema from pinned bytes; report disagreements.

    Empty list = our recorded :data:`WGP_CONFIG_SCHEMA` matches the pin
    exactly (gate ①/② assertion).
    """
    pinned = _pinned_default_config_keys(checkout / "wgp.py")
    recorded = set(WGP_CONFIG_SCHEMA)
    return sorted(pinned.symmetric_difference(recorded))


def rewrite_config(
    checkout: Path,
    overrides: Mapping[str, Any],
) -> Path:
    """Rewrite ONLY ``wgp_config.json``, ONLY with schema keys.

    Unknown keys refuse typed — a config override outside the pinned
    schema is a caller bug, never silently dropped. Returns the config
    path.
    """
    unknown = sorted(set(overrides) - WGP_CONFIG_SCHEMA)
    if unknown:
        raise WgpBridgeRefused(
            f"server_config overrides outside the pinned schema: {unknown}"
        )
    config_path = checkout / CONFIG_FILENAME
    current: dict[str, Any] = {}
    if config_path.is_file():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise WgpBridgeRefused(
                f"{config_path} is not valid JSON: {exc}"
            ) from None
        if isinstance(loaded, dict):
            current = loaded
    merged = {
        **{k: v for k, v in current.items() if k in WGP_CONFIG_SCHEMA},
        **dict(overrides),
    }
    fd, tmp_name = tempfile.mkstemp(
        dir=str(checkout), prefix=".cfg-", suffix=".json"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as writer:
            writer.write(json.dumps(merged, indent=2, sort_keys=True) + "\n")
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(tmp_name, config_path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return config_path


@dataclass(frozen=True, slots=True)
class WgpSession:
    """One live in-process WGP boundary."""

    checkout: Path
    wgp_module: Any


class wgp_session:
    """The full boot boundary as a context manager.

    Enters: path insert → chdir → argv spoof → env spoofs →
    ``import wgp`` → server_config overrides. Exits: everything restored
    in reverse, even on refusal. Overrides are applied to the live
    ``wgp.server_config`` mapping AND persisted through
    :func:`rewrite_config` (boot rewrites only that file).
    """

    def __init__(
        self,
        *,
        checkout: str | Path | None = None,
        server_config_overrides: Mapping[str, Any] | None = None,
    ) -> None:
        self._checkout_arg = checkout
        self._overrides = dict(server_config_overrides or {})
        self._restore_path_entry: str | None = None
        self._cwd: str | None = None
        self._argv: list[str] | None = None
        self._env: dict[str, str | None] = {}

    def __enter__(self) -> WgpSession:
        checkout = require_checkout(self._checkout_arg)
        if ensure_wan2gp_on_path(checkout):
            self._restore_path_entry = str(checkout)
        self._cwd = os.getcwd()
        self._argv = list(sys.argv)
        for name in ("WORKER_ID", "WAN2GP_WORKER_MODE"):
            self._env[name] = os.environ.get(name)
        os.environ.setdefault("WORKER_ID", "astrid-wgp")
        os.environ["WAN2GP_WORKER_MODE"] = "true"
        try:
            os.chdir(checkout)
            sys.argv[:] = ["worker.py"]
            wgp_module = importlib.import_module("wgp")
            if self._overrides:
                rewrite_config(checkout, self._overrides)
                server_config = getattr(wgp_module, "server_config", None)
                if isinstance(server_config, dict):
                    server_config.update(self._overrides)
        except WgpBridgeRefused:
            self._restore()
            raise
        except ImportError as exc:
            self._restore()
            raise WgpImportUnavailable(
                f"import wgp failed at pin ({exc}); install the pinned "
                "dependency closure (uv sync --extra cuda124 upstream / "
                "Astrid equivalent) before executing WGP work"
            ) from None
        except BaseException:
            self._restore()
            raise
        return WgpSession(checkout=checkout, wgp_module=wgp_module)

    def __exit__(self, *exc_info: object) -> None:
        self._restore()

    def _restore(self) -> None:
        if self._cwd is not None:
            os.chdir(self._cwd)
            self._cwd = None
        if self._argv is not None:
            sys.argv[:] = self._argv
            self._argv = None
        if self._restore_path_entry is not None:
            with contextlib.suppress(ValueError):
                sys.path.remove(self._restore_path_entry)
            self._restore_path_entry = None
        for name, prior in self._env.items():
            if prior is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = prior
        self._env.clear()
