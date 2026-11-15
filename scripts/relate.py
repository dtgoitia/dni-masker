#!/usr/bin/env python3
"""Add or remove a relationship between two items, on both of them at once.

  relate.py add|remove <A> <relation> <B>

`A blocks B` is written as `blocks: [B]` on A and `blocked_by: [A]` on B;
likewise `supersedes` / `superseded_by`, and `related_to` on both sides.
Adding a relationship that would close a cycle (in the blocking or the
supersession graph) is refused, as are self links and unknown IDs. When a
blocking relationship changes, the blocked item switches between `ready` and
`ready-but-blocked` as needed; other statuses are never changed.
"""

import argparse
import sys
from collections import defaultdict, deque
from pathlib import Path

from pm_graph import Graph
from pm_items import Item, load_items, set_field, set_list
from sync_ready_status import BLOCKED, READY

INVERSE = {
    "blocks": "blocked_by",
    "blocked_by": "blocks",
    "supersedes": "superseded_by",
    "superseded_by": "supersedes",
    "related_to": "related_to",
}
# relation -> (directed graph it belongs to, True if the edge points from B to A)
DIRECTED = {
    "blocks": ("blocks", False),
    "blocked_by": ("blocks", True),
    "supersedes": ("supersedes", False),
    "superseded_by": ("supersedes", True),
}


class Refused(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


def find(items: list[Item], item_id: str) -> Item:
    matches = [item for item in items if item.id == item_id]
    if not matches:
        raise Refused(f"{item_id} not found", code=2)
    if len(matches) > 1:
        raise Refused(f"{item_id} is used by more than one file; run /pm-lint first", code=2)
    return matches[0]


def edges(items: list[Item], verb: str) -> dict[str, set[str]]:
    """The `verb` graph (blocks or supersedes), merged from both sides."""
    graph: dict[str, set[str]] = defaultdict(set)
    for item in items:
        if not item.id:
            continue
        for other in item.relations[verb]:
            graph[item.id].add(other)
        for other in item.relations[INVERSE[verb]]:
            graph[other].add(item.id)
    return graph


def path_between(graph: dict[str, set[str]], start: str, goal: str) -> list[str] | None:
    """Shortest path from start to goal (breadth-first, by ID order)."""
    previous: dict[str, str | None] = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            path = [node]
            while previous[path[-1]] is not None:
                path.append(previous[path[-1]])
            return path[::-1]
        for nxt in sorted(graph[node]):
            if nxt not in previous:
                previous[nxt] = node
                queue.append(nxt)
    return None


def relate(product_dir: Path, action: str, a_id: str, relation: str, b_id: str) -> list[str]:
    if a_id == b_id:
        raise Refused(f"{a_id} can't be related to itself")
    items = load_items(product_dir)
    a, b = find(items, a_id), find(items, b_id)
    inverse = INVERSE[relation]
    a_has, b_has = b_id in a.relations[relation], a_id in b.relations[inverse]
    phrase = f"{a_id} {relation} {b_id}"

    if action == "add":
        if a_has and b_has:
            return [f"unchanged: {phrase}"]
        if relation in DIRECTED:
            verb, reverse = DIRECTED[relation]
            src, dst = (b_id, a_id) if reverse else (a_id, b_id)
            back = path_between(edges(items, verb), dst, src)
            if back:
                raise Refused(f"{phrase} would create a cycle: {f' {verb} '.join([src, *back])}")
        if not a_has:
            set_list(a.path, relation, sorted({*a.relations[relation], b_id}))
        if not b_has:
            set_list(b.path, inverse, sorted({*b.relations[inverse], a_id}))
        output = [f"added: {phrase}"]
    else:
        if not a_has and not b_has:
            return [f"unchanged: {phrase}"]
        if a_has:
            set_list(a.path, relation, sorted(set(a.relations[relation]) - {b_id}))
        if b_has:
            set_list(b.path, inverse, sorted(set(b.relations[inverse]) - {a_id}))
        output = [f"removed: {phrase}"]

    if relation in ("blocks", "blocked_by"):
        blocked_id = a_id if relation == "blocked_by" else b_id
        graph = Graph(load_items(product_dir))
        blocked = graph.by_id[blocked_id]
        if blocked.status in (READY, BLOCKED):
            status = BLOCKED if graph.open_blockers(blocked_id) else READY
            if status != blocked.status:
                set_field(blocked.path, "status", status)
                output.append(f"status: {blocked_id} {blocked.status} -> {status} ({blocked.path})")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--product-dir", default="product", help="product directory (default: ./product)")
    parser.add_argument("action", choices=["add", "remove"])
    parser.add_argument("a", metavar="A")
    parser.add_argument("relation", choices=sorted(INVERSE))
    parser.add_argument("b", metavar="B")
    args = parser.parse_args()

    product_dir = Path(args.product_dir)
    if not (product_dir / "items").is_dir():
        print(f"error: items directory not found: {(product_dir / 'items').resolve()}", file=sys.stderr)
        return 2
    try:
        for line in relate(product_dir, args.action, args.a, args.relation, args.b):
            print(line)
    except Refused as refused:
        print(f"error: {refused}", file=sys.stderr)
        return refused.code
    return 0


if __name__ == "__main__":
    sys.exit(main())
