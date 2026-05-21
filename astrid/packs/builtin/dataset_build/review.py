"""Review data and decision application helpers."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from astrid.core.project.jsonio import write_json_atomic

from .items import repo_relative_path, utc_now_iso
from .state import make_initial_state, write_review_state


def write_review_data(path: str | Path, items: list[Mapping[str, Any]]) -> Path:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"items": [dict(item) for item in items]}
    write_json_atomic(out_path, payload)
    return out_path


def write_initial_review_state(
    path: str | Path,
    *,
    run_id: str,
    writer_id: str,
    buckets: Mapping[str, int | Mapping[str, Any]] | None = None,
    config_hash: str | None = None,
    schema_version_source: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    state = make_initial_state(
        run_id=run_id,
        writer_id=writer_id,
        buckets=buckets,
        config_hash=config_hash,
        schema_version_source=schema_version_source,
        status="reviewing",
        now=now,
    )
    return write_review_state(path, state, now=now)


def write_human_review_final(run_dir: str | Path, payload: Mapping[str, Any]) -> Path:
    out_path = Path(run_dir) / "review_server" / "human_review.final.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path


def apply_review_decisions(
    items: list[Mapping[str, Any]],
    state: Mapping[str, Any],
    *,
    persist_caption_sidecars: bool = True,
    now: str | None = None,
) -> list[dict[str, Any]]:
    decisions = state.get("review_decisions") or {}
    output: list[dict[str, Any]] = []
    for item in items:
        updated = copy.deepcopy(dict(item))
        item_id = str(updated["item_id"])
        decision = dict(decisions.get(item_id) or {})
        normalized = _normalize_decision(decision.get("decision", updated.get("review_status", "pending")))
        if normalized == "accept":
            updated["review_status"] = "accepted"
        elif normalized == "reject":
            updated["review_status"] = "rejected"
        else:
            updated["review_status"] = "pending"
        if decision:
            final_decision = {
                "item_id": item_id,
                "decision": normalized,
                "reject_reason": decision.get("reject_reason"),
                "edited_caption": decision.get("edited_caption"),
                "reviewed_at": decision.get("reviewed_at") or now or utc_now_iso(),
                "state_version": int(decision.get("state_version", state.get("state_version", 0))),
            }
            if decision.get("reviewer_id"):
                final_decision["reviewer_id"] = str(decision["reviewer_id"])
            updated["review_decision"] = final_decision
        edited_caption = decision.get("edited_caption")
        if isinstance(edited_caption, str) and edited_caption:
            caption = dict(updated.get("caption") or {})
            caption["text"] = edited_caption
            caption.setdefault("schema_version", 1)
            caption.setdefault("confidence", 1.0)
            caption.setdefault("model", "human_review")
            updated["caption"] = caption
        if updated["review_status"] == "accepted" and persist_caption_sidecars:
            _persist_caption_sidecar(updated)
        output.append(updated)
    return output


def _persist_caption_sidecar(item: dict[str, Any]) -> Path:
    media_path = Path(str(item["media_path"])).expanduser()
    if not media_path.is_absolute():
        from astrid._paths import REPO_ROOT

        media_path = (REPO_ROOT / media_path).resolve()
    caption = dict(item.get("caption") or {})
    caption.setdefault("text", "")
    caption.setdefault("schema_version", 1)
    caption.setdefault("confidence", 0.0)
    caption.setdefault("model", "")
    sidecar = media_path.with_name(f"{item['item_id']}.caption.json")
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(json.dumps(caption, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    item["caption_file"] = repo_relative_path(sidecar)
    return sidecar


def _normalize_decision(value: Any) -> str:
    if value in {"accepted", "accept", True}:
        return "accept"
    if value in {"rejected", "reject", False}:
        return "reject"
    return "pending"
