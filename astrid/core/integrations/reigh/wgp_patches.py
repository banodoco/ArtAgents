"""Declarative WGP-global patchset (Batch B7, gate 1).

The reigh-worker runbook (doc 03 §3.2, ``task_processor.py:
_execute_generation_with_patches``) patches WGP globals under a lock and
restores them in ``finally``. This module is the Astrid-side equivalent,
rebuilt as **data**: each patch names its target knob, how a task config
builds its replacement value, and the *pinned-bytes anchor* whose exact
presence in the vendored Wan2GP tree proves the patch still applies.

Gate ① (hermetic rebase) runs :func:`anchor_report` mechanically: every
anchor must match exactly once in the pinned tree or the build is
rejected — drift can never be report-only. Runtime application
(:func:`applied`) sets module attributes under a process lock and
restores every prior value in ``finally``, including "attribute was
absent", so a failed attempt never leaks patched state.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PINNED_WAN2GP_SHA = "181bb71a21008032e4771e11663f33e4489c4512"
"""The one vendored Wan2GP commit this patchset applies to."""

UPSTREAM_BASE_SHA = "664b26e1dfbae94b4945b76fd9f882e3387a16de"
"""Upstream banodoco/Wan2GP ``main`` head the fork is rebased onto.

Verified mechanically: ``git merge-base <pin> origin/main`` at vendor
time equals this commit, i.e. the fork carries upstream main in full.
"""


@dataclass(frozen=True, slots=True)
class WgpPatch:
    """One named global patch: knob + value builder + pinned anchor.

    ``target_file``/``anchor_regex`` are relative to the checkout root;
    the anchor must occur exactly once (gate ①). ``target_attr`` is the
    module attribute set on the imported ``wgp`` module for the duration
    of one generation attempt; ``make_value`` derives it from the task's
    phase config.
    """

    name: str
    target_attr: str
    target_file: str
    anchor_regex: str
    make_value: Callable[[Mapping[str, Any]], Any]


def _phase_config_value(config: Mapping[str, Any]) -> Any:
    return config.get("phase_config")


def _svi2pro_value(config: Mapping[str, Any]) -> Any:
    return bool(config.get("svi2pro", False))


def _sliding_window_value(config: Mapping[str, Any]) -> Any:
    return int(config.get("sliding_window_size", 0))


def _sliding_window_defaults_value(config: Mapping[str, Any]) -> Any:
    return dict(config.get("sliding_window_defaults") or {})


def _svi_empty_frames_mode_value(config: Mapping[str, Any]) -> Any:
    return str(config.get("svi_empty_frames_mode", "zero"))


#: The five documented patches, declared once — never registered at
#: runtime, never discovered (growth by declaration).
PATCHES: tuple[WgpPatch, ...] = (
    WgpPatch(
        name="phase_config",
        target_attr="model_switch_phase",
        target_file="wgp.py",
        anchor_regex=r'model_switch_phase = inputs\["model_switch_phase"\]',
        make_value=_phase_config_value,
    ),
    WgpPatch(
        name="svi2pro",
        target_attr="svi_pro",
        target_file="models/wan/wan_handler.py",
        anchor_regex=r"def test_svi2pro\(base_model_type\):",
        make_value=_svi2pro_value,
    ),
    WgpPatch(
        name="sliding_window",
        target_attr="sliding_window_size",
        target_file="wgp.py",
        anchor_regex=r"def compute_sliding_window_no\(current_video_length, "
        r"sliding_window_size, discard_last_frames, reuse_frames\):",
        make_value=_sliding_window_value,
    ),
    WgpPatch(
        name="sliding_window_defaults",
        target_attr="sliding_window_defaults",
        target_file="wgp.py",
        anchor_regex=r"(?m)^ {8}sliding_window_defaults = model_def\.get\("
        r'"sliding_window_defaults", \{\}\)',
        make_value=_sliding_window_defaults_value,
    ),
    WgpPatch(
        name="svi_empty_frames_mode",
        target_attr="uni3c_zero_empty_frames",
        target_file="wgp.py",
        anchor_regex=r"uni3c_zero_empty_frames=True,",
        make_value=_svi_empty_frames_mode_value,
    ),
)

_PATCHSET_LOCK = threading.Lock()
_MISSING = object()


def patchset_hash() -> str:
    """Stable SHA-256 over the declared patchset (manifest field).

    The hash covers names, targets, anchors, and value-builder bytecode —
    any semantic change to the patchset changes the build manifest.
    """
    import hashlib
    import json

    declared = [
        {
            "name": p.name,
            "target_attr": p.target_attr,
            "target_file": p.target_file,
            "anchor_regex": p.anchor_regex,
            "make_value_source": p.make_value.__code__.co_code.hex(),
        }
        for p in PATCHES
    ]
    payload = json.dumps(declared, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def anchor_report(checkout: Path) -> dict[str, str]:
    """Match every patch anchor against the checkout bytes.

    Returns ``{patch_name: status}`` where status is ``"ok"``,
    ``"missing"`` (no match), or ``"ambiguous:N"`` (N > 1 matches).
    Gate ① passes only when every status is ``"ok"``.
    """
    report: dict[str, str] = {}
    for patch in PATCHES:
        path = checkout / patch.target_file
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            report[patch.name] = "missing"
            continue
        hits = re.findall(patch.anchor_regex, text)
        if len(hits) == 1:
            report[patch.name] = "ok"
        elif not hits:
            report[patch.name] = "missing"
        else:
            report[patch.name] = f"ambiguous:{len(hits)}"
    return report


@contextmanager
def applied(wgp_module: Any, config: Mapping[str, Any]) -> Iterator[None]:
    """Apply every patch to *wgp_module* under the lock; restore after.

    Values absent before application (``_MISSING``) are deleted again on
    exit, so the restore reproduces the pre-patch module surface exactly.
    Exceptions inside the body propagate after restoration — patched
    state never leaks past a failed attempt.
    """
    with _PATCHSET_LOCK:
        saved: list[tuple[WgpPatch, Any]] = []
        try:
            for patch in PATCHES:
                saved.append((patch, getattr(wgp_module, patch.target_attr, _MISSING)))
                setattr(wgp_module, patch.target_attr, patch.make_value(config))
            yield
        finally:
            for patch, prior in reversed(saved):
                if prior is _MISSING:
                    try:
                        delattr(wgp_module, patch.target_attr)
                    except AttributeError:
                        pass
                else:
                    setattr(wgp_module, patch.target_attr, prior)
