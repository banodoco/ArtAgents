""":mod:`astrid.core.pack.cli_search` — Agent-index and search command handlers.

Extracted from ``astrid/core/pack/cli.py`` during M4 giant-file split.
Contains ``_handle_agent_index`` (packs agent-index), ``_handle_search``
(packs search), and the search scoring/ranking helpers.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def _handle_agent_index(args: argparse.Namespace) -> int:
    """Handler for ``packs agent-index``."""

    from astrid.core.pack.agent_index import build_agent_index

    pack_id = getattr(args, "pack_id", None)
    result = build_agent_index(pack_id=pack_id)

    if args.text_output:
        # Text table output
        if isinstance(result, dict) and "packs" in result:
            packs = result["packs"]
        elif isinstance(result, dict):
            packs = [result]  # single pack from --pack-id filter
        elif result is None:
            packs = []
        else:
            packs = [result]
        if not packs:
            print("(no packs found)")
            return 0
        for pack_entry in packs:
            pid = pack_entry.get("pack_id", "?")
            name = pack_entry.get("name", pid)
            version = pack_entry.get("version", "")
            purpose = pack_entry.get("purpose", "")
            source_type = pack_entry.get("source_type", "")
            normal_eps = pack_entry.get("normal_entrypoints", [])
            comp_counts = pack_entry.get("component_counts", {})
            secrets_cnt = len(pack_entry.get("secrets", []))

            print(f"━━━ {pid} ━━━")
            print(f"  Name:          {name}")
            if version:
                print(f"  Version:       {version}")
            print(f"  Source:        {source_type}")
            if purpose:
                print(f"  Purpose:       {purpose}")
            if normal_eps:
                print(f"  Entrypoints:   {', '.join(normal_eps)}")
            if comp_counts:
                parts = []
                for k in ("executors", "orchestrators", "elements"):
                    if comp_counts.get(k, 0):
                        parts.append(f"{comp_counts[k]} {k}")
                print(f"  Components:    {', '.join(parts)}")
            if secrets_cnt:
                print(f"  Secrets:       {secrets_cnt} declared")

            do_not = pack_entry.get("do_not_use_for")
            if do_not:
                print(f"  DoNotUseFor:   {do_not}")

            req_ctx = pack_entry.get("required_context", [])
            if req_ctx:
                print(f"  Req. Context:  {', '.join(req_ctx)}")

            keywords = pack_entry.get("keywords", [])
            if keywords:
                print(f"  Keywords:      {', '.join(keywords)}")

            capabilities = pack_entry.get("capabilities", [])
            if capabilities:
                print(f"  Capabilities:  {', '.join(capabilities)}")

            deps = pack_entry.get("dependencies", {})
            if deps:
                dep_parts = []
                for eco, pkg_list in deps.items():
                    if pkg_list:
                        dep_parts.append(f"{eco}:{','.join(pkg_list)}")
                if dep_parts:
                    print(f"  Dependencies:  {'; '.join(dep_parts)}")

            components = pack_entry.get("components", [])
            if components:
                print(f"  Components:    ({len(components)} total)")
                for comp in components:
                    ep_mark = " [ENTRYPOINT]" if comp.get("is_entrypoint") else ""
                    desc = comp.get("description", "")[:80]
                    print(f"    • {comp['id']} ({comp.get('kind', '?')}){ep_mark}: {desc}")

            warnings = pack_entry.get("warnings", [])
            if warnings:
                print("  ⚠ Warnings:")
                for w in warnings:
                    print(f"    • {w}")
            print()  # blank line between packs
    else:
        # JSON output (default)
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")

    return 0


# ---------------------------------------------------------------------------
# pack search
# ---------------------------------------------------------------------------

# Per-field weights for ranking a query term against a pack. Keyword and
# capability hits are the strongest signal (authored for discovery); id/name
# next; purpose/description are softer free-text matches. do_not_use_for is
# deliberately excluded so negative guidance never yields a positive match.
_SEARCH_FIELD_WEIGHTS = (
    ("keywords", 3.0),
    ("capabilities", 3.0),
    ("pack_id", 2.0),
    ("name", 2.0),
    ("purpose", 1.5),
    ("description", 1.0),
)


def _pack_search_text(pack: dict[str, Any], field: str) -> str:
    """Return lowercased searchable text for *field* of an agent-index entry."""
    value = pack.get(field)
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value).lower()
    return str(value or "").lower()


def _score_pack(pack: dict[str, Any], terms: list[str]) -> float:
    """Score *pack* against query *terms*; 0.0 means no match.

    Every term must hit at least one field (AND semantics); a single
    unmatched term drops the pack, keeping multi-word queries precise
    rather than returning anything that matches one common word.
    """
    total = 0.0
    for term in terms:
        best = 0.0
        for field, weight in _SEARCH_FIELD_WEIGHTS:
            if term in _pack_search_text(pack, field):
                best = max(best, weight)
        if best == 0.0:
            return 0.0
        total += best
    return total


def _handle_search(args: argparse.Namespace) -> int:
    """Handler for ``packs search``."""
    from astrid.core.pack.agent_index import build_agent_index

    terms = [t.lower() for t in args.query if t.strip()]
    if not terms:
        print("search: empty query", file=sys.stderr)
        return 2

    index = build_agent_index()
    packs = index.get("packs", []) if isinstance(index, dict) else []

    scored = [
        (score, pack)
        for pack in packs
        if (score := _score_pack(pack, terms)) > 0.0
    ]
    scored.sort(key=lambda sp: (-sp[0], str(sp[1].get("pack_id", ""))))

    total = len(scored)
    limit = args.limit if args.limit and args.limit > 0 else total
    shown = scored[:limit]

    if args.json:
        payload = {
            "query": terms,
            "total": total,
            "shown": len(shown),
            "packs": [
                {**pack, "search_score": round(score, 2)}
                for score, pack in shown
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if not shown:
        print(f"No packs match: {' '.join(terms)}")
        return 0

    for score, pack in shown:
        summary = pack.get("purpose") or pack.get("description") or ""
        keywords = pack.get("keywords") or []
        kw = ", ".join(str(k) for k in keywords[:6])
        line = f"{pack.get('pack_id', '?')}\t{score:g}\t{summary}"
        if kw:
            line += f"\t[{kw}]"
        print(line)

    if total > len(shown):
        print(
            f"\n# showing top {len(shown)} of {total} matches — "
            f"add terms to narrow, or pass --limit to see more"
        )
    return 0
