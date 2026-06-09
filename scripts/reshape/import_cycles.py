#!/usr/bin/env python3
"""Cross-package import-cycle checker for the elegant-architecture restructure.

Builds the static import graph of ``astrid.core`` (or any package root) at a chosen
granularity and reports import cycles among the nodes. Used three ways:

* **baseline** — ``python -m scripts.reshape.import_cycles`` prints every cross-package
  cycle and a count; this is the number the RESTRUCTURE plan drives to zero.
* **per-move gate** — ``--baseline <file>`` compares against a saved JSON snapshot and
  exits non-zero if any *new* cycle appeared (a move that re-introduces a cycle is reverted).
* **snapshot** — ``--write-baseline <file>`` records the current cycle set as JSON.

Granularity (``--granularity``):
* ``top`` (default) — nodes are the immediate children of the root package
  (``astrid.core.project``, ``astrid.core.task``, …). Matches the plan's "23 cross-package cycles".
* ``deep`` — nodes are every sub-package/module; surfaces intra-package cycles too.

Edges are derived from ``import``/``from … import`` statements via ``ast`` (no execution),
including imports nested inside functions (lazy imports still couple the graph). ``TYPE_CHECKING``
guarded imports are included by default (they are real import-time edges under ``from __future__``)
but can be excluded with ``--no-type-checking``.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path


def _module_name(path: Path, root_dir: Path, root_pkg: str) -> str:
    rel = path.relative_to(root_dir).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join([root_pkg, *parts]) if parts else root_pkg


def _iter_imports(tree: ast.AST, module: str, include_type_checking: bool):
    """Yield fully-qualified imported module names referenced from *module*."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module is None and node.level == 0:
                continue
            if node.level:  # relative import → resolve against the current package
                base = module.rsplit(".", node.level)[0]
                target = f"{base}.{node.module}" if node.module else base
            else:
                target = node.module
            yield target
            # `from pkg import name` may import a submodule `pkg.name`; include both forms.
            for alias in node.names:
                if alias.name != "*":
                    yield f"{target}.{alias.name}"


def _node_for(module: str, root_pkg: str, granularity: str) -> str | None:
    """Map a fully-qualified module to its graph node, or None if outside the root."""
    if module != root_pkg and not module.startswith(root_pkg + "."):
        return None
    if module == root_pkg:
        return None
    tail = module[len(root_pkg) + 1 :]
    if granularity == "top":
        return f"{root_pkg}.{tail.split('.')[0]}"
    return module  # deep: keep full path; callers collapse to existing nodes


def build_graph(root_dir: Path, root_pkg: str, granularity: str, include_type_checking: bool):
    files = sorted(root_dir.rglob("*.py"))
    known_modules = {_module_name(p, root_dir, root_pkg) for p in files}
    edges: dict[str, set[str]] = {}
    for path in files:
        if "__pycache__" in path.parts:
            continue
        module = _module_name(path, root_dir, root_pkg)
        src_node = _node_for(module, root_pkg, "top" if granularity == "top" else "deep")
        if src_node is None:
            src_node = module
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:  # surfaced by the ast.parse gate step; skip here
            print(f"warning: skip unparseable {path}: {exc}", file=sys.stderr)
            continue
        for target in _iter_imports(tree, module, include_type_checking):
            # Collapse `pkg.name` to the deepest known module that is a prefix.
            resolved = target
            if granularity == "deep":
                while resolved and resolved not in known_modules:
                    if "." not in resolved:
                        resolved = ""
                        break
                    resolved = resolved.rsplit(".", 1)[0]
            dst_node = _node_for(resolved or target, root_pkg, granularity)
            if dst_node is None or dst_node == src_node:
                continue
            edges.setdefault(src_node, set()).add(dst_node)
            edges.setdefault(dst_node, set())
    return edges


def find_cycles(edges: dict[str, set[str]]) -> list[list[str]]:
    """Return the elementary 2-node cycles plus any larger SCCs (Tarjan)."""
    index = {}
    low = {}
    on_stack = {}
    stack: list[str] = []
    counter = [0]
    sccs: list[list[str]] = []

    def strongconnect(v: str):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on_stack[v] = True
        for w in sorted(edges.get(v, ())):
            if w not in index:
                strongconnect(w)
                low[v] = min(low[v], low[w])
            elif on_stack.get(w):
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                sccs.append(sorted(comp))

    sys.setrecursionlimit(10000)
    for v in sorted(edges):
        if v not in index:
            strongconnect(v)
    return sccs


def cycle_pairs(edges: dict[str, set[str]]) -> list[tuple[str, str]]:
    """All directed 2-cycles A↔B (the plan counts these as the 23 cross-package cycles)."""
    pairs = set()
    for a, outs in edges.items():
        for b in outs:
            if a in edges.get(b, ()):  # b also imports a
                pairs.add(tuple(sorted((a, b))))
    return sorted(pairs)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root-dir", default="astrid/core", help="package source dir (default astrid/core)")
    ap.add_argument("--root-pkg", default="astrid.core", help="dotted root package (default astrid.core)")
    ap.add_argument("--granularity", choices=["top", "deep"], default="top")
    ap.add_argument("--no-type-checking", action="store_true", help="exclude TYPE_CHECKING-guarded imports")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--write-baseline", metavar="FILE", help="write the current cycle set to FILE and exit 0")
    ap.add_argument("--baseline", metavar="FILE", help="compare to FILE; exit 1 if any NEW cycle appears")
    args = ap.parse_args(argv)

    root_dir = Path(args.root_dir).resolve()
    edges = build_graph(root_dir, args.root_pkg, args.granularity, not args.no_type_checking)
    pairs = cycle_pairs(edges)
    sccs = find_cycles(edges)
    payload = {
        "granularity": args.granularity,
        "cycle_pairs": [list(p) for p in pairs],
        "sccs": sccs,
        "pair_count": len(pairs),
    }

    if args.write_baseline:
        Path(args.write_baseline).write_text(json.dumps(payload, indent=2) + "\n")
        print(f"wrote baseline ({len(pairs)} cross-package cycles) → {args.write_baseline}")
        return 0

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"cross-package 2-cycles: {len(pairs)}")
        for a, b in pairs:
            sa = a.split(".")[-1]
            sb = b.split(".")[-1]
            print(f"  {sa} <-> {sb}")
        bigger = [c for c in sccs if len(c) > 2]
        if bigger:
            print(f"larger SCCs (>=3 nodes): {len(bigger)}")
            for comp in bigger:
                print("  " + " -> ".join(n.split(".")[-1] for n in comp))

    if args.baseline:
        base = json.loads(Path(args.baseline).read_text())
        base_pairs = {tuple(p) for p in base["cycle_pairs"]}
        now_pairs = {tuple(p) for p in payload["cycle_pairs"]}
        new = sorted(now_pairs - base_pairs)
        if new:
            print(f"\nFAIL: {len(new)} NEW cross-package cycle(s) introduced:", file=sys.stderr)
            for a, b in new:
                print(f"  {a.split('.')[-1]} <-> {b.split('.')[-1]}", file=sys.stderr)
            return 1
        fixed = len(base_pairs - now_pairs)
        print(f"\nOK: no new cycles (fixed {fixed}, remaining {len(now_pairs)}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
