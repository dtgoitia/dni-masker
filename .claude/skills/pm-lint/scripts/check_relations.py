#!/usr/bin/env python3
"""Check relationships between items for cycles and inconsistencies.

Reports on stderr (exit code 1 if anything is found):
  - self-references: an item listing itself in any relationship field
  - unknown IDs: references to items that don't exist
  - out-of-sync pairs: `A blocked_by B` without `B blocks A` (and vice
    versa); same for `supersedes` / `superseded_by`
  - cycles in the blocking graph (A blocks B blocks ... blocks A) and in
    the supersession graph (A supersedes B supersedes ... supersedes A)

`related_to` is symmetric and has no direction, so it can't form a
meaningful cycle; it is only checked for self-references and unknown IDs.
Both sides of each pair are merged before looking for cycles, so a cycle is
found even when the declarations are out of sync.
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from _items import RELATION_FIELDS, Item, load_items

# field -> (inverse field, graph name, True if the edge points away from this item)
DIRECTED = {
    "blocks": ("blocked_by", "blocking", True),
    "blocked_by": ("blocks", "blocking", False),
    "supersedes": ("superseded_by", "supersession", True),
    "superseded_by": ("supersedes", "supersession", False),
}
VERB = {"blocking": "blocks", "supersession": "supersedes"}


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Return one representative cycle per strongly connected component."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[set[str]] = []

    def strongconnect(v: str) -> None:  # Tarjan's algorithm
        index[v] = low[v] = len(index)
        stack.append(v)
        on_stack.add(v)
        for w in sorted(graph[v]):
            if w not in index:
                strongconnect(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            component = set()
            while True:
                w = stack.pop()
                on_stack.discard(w)
                component.add(w)
                if w == v:
                    break
            if len(component) > 1:
                components.append(component)

    sys.setrecursionlimit(max(1000, 4 * len(graph) + 100))
    for v in sorted(graph):
        if v not in index:
            strongconnect(v)

    cycles = []
    for component in components:
        # Every node in a strongly connected component lies on a cycle through
        # `start`; walk depth-first inside the component until we return to it.
        start = min(component)
        path, seen = [start], {start}
        while start not in graph[path[-1]]:
            step = next((n for n in sorted(graph[path[-1]] & component) if n not in seen), None)
            if step is None:
                path.pop()  # dead end: backtrack
            else:
                path.append(step)
                seen.add(step)
        cycles.append(path + [start])
    return sorted(cycles)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--product-dir", default="product", help="product directory (default: ./product)")
    args = parser.parse_args()

    product_dir = Path(args.product_dir)
    if not (product_dir / "items").is_dir():
        print(f"error: items directory not found: {(product_dir / 'items').resolve()}", file=sys.stderr)
        return 2

    by_id: dict[str, list[Item]] = defaultdict(list)
    for item in load_items(product_dir):
        if item.id:
            by_id[item.id].append(item)

    def refs(item_id: str, field: str) -> set[str]:
        return {r for item in by_id[item_id] for r in item.relations[field]}

    def where(item_id: str) -> str:
        return ", ".join(str(item.path) for item in by_id[item_id])

    problems: list[str] = []
    graphs: dict[str, dict[str, set[str]]] = {"blocking": defaultdict(set), "supersession": defaultdict(set)}

    for item_id in sorted(by_id):
        for field in RELATION_FIELDS:
            for ref in sorted(refs(item_id, field)):
                if ref == item_id:
                    problems.append(f"self-reference: {item_id} {field} itself ({where(item_id)})")
                    continue
                if ref not in by_id:
                    problems.append(f"unknown ID: {item_id} {field} {ref}, which doesn't exist ({where(item_id)})")
                    continue
                if field not in DIRECTED:
                    continue
                inverse, graph, outgoing = DIRECTED[field]
                src, dst = (item_id, ref) if outgoing else (ref, item_id)
                graphs[graph][src].add(dst)
                graphs[graph][dst]  # make sure every node is a key
                if item_id not in refs(ref, inverse):
                    problems.append(
                        f"out of sync: {item_id} {field} {ref}, but {ref} doesn't list {item_id}"
                        f" in {inverse} ({where(ref)})"
                    )

    for graph, edges in graphs.items():
        for cycle in find_cycles(edges):
            problems.append(f"{graph} cycle: {f' {VERB[graph]} '.join(cycle)}")

    if any(len(items) > 1 for items in by_id.values()):
        print("warning: duplicate IDs found; resolve them first (check_duplicates.py) for reliable results",
              file=sys.stderr)
    for problem in problems:
        print(problem, file=sys.stderr)
    if not problems:
        print("no relationship problems found")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
