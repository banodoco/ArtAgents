from __future__ import annotations

from pathlib import Path
from typing import Any

from .transport import parse_ledger_bytes, verify_ledger_path


def load_ledger(run_dir: Path | str) -> list[dict[str, Any]]:
    ledger_path = Path(run_dir).resolve() / "audit" / "ledger.jsonl"
    if not ledger_path.is_file():
        raise FileNotFoundError(f"audit ledger not found: {ledger_path}")
    events = []
    for line_number, event in enumerate(parse_ledger_bytes(ledger_path.read_bytes()), start=1):
        event["_ledger_line"] = line_number
        events.append(event)
    return events


def verify_audit_ledger(run_dir: Path | str) -> tuple[bool, int | None, str]:
    ledger_path = Path(run_dir).resolve() / "audit" / "ledger.jsonl"
    return verify_ledger_path(ledger_path)


def build_graph(events: list[dict[str, Any]]) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges_by_key: dict[tuple[str, str], dict[str, str]] = {}
    decisions: list[dict[str, Any]] = []
    for event in events:
        event_type = event.get("event")
        if event_type == "asset.created":
            node_id = str(event["asset_id"])
            nodes[node_id] = {**event, "id": node_id, "node_type": "asset"}
            for parent in event.get("parents") or []:
                edges_by_key[(str(parent), node_id)] = {"from": str(parent), "to": node_id}
        elif event_type == "node.created":
            node_id = str(event["node_id"])
            nodes[node_id] = {**event, "id": node_id, "node_type": "node"}
            for parent in event.get("parents") or []:
                edges_by_key[(str(parent), node_id)] = {"from": str(parent), "to": node_id}
            for output in event.get("outputs") or []:
                edges_by_key[(node_id, str(output))] = {"from": node_id, "to": str(output)}
        elif event_type == "decision.created":
            decisions.append(event)
    ordered_nodes = sorted(
        nodes.values(),
        key=lambda node: (str(node.get("stage") or ""), int(node.get("_ledger_line", 0)), str(node.get("id"))),
    )
    ordered_edges = sorted(edges_by_key.values(), key=lambda edge: (edge["from"], edge["to"]))
    return {"nodes": ordered_nodes, "edges": ordered_edges, "decisions": decisions, "events": events}
