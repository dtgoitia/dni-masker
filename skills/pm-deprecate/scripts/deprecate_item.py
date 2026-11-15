#!/usr/bin/env python3
"""Deprecate an item, link its replacement, and review the items it was blocking.

  check <ID>               print the item, its replacements and its open
                           dependents as JSON
  deprecate <ID> [--superseded-by X]
                           set `status: deprecated` and `deprecated: <now>`;
                           with X, write `superseded_by: [X]` on the item and
                           `supersedes: [ID]` on X; then re-derive `ready` /
                           `ready-but-blocked` for the item's open dependents
                           and list them for review
  relink <DEP> <ID> <X>    move DEP's blocker from ID to X, on every side
  unlink <DEP> <ID>        drop DEP's blocker ID, on both sides

Relationships count from both sides (`blocks` / `blocked_by`, `supersedes` /
`superseded_by`). Self links, unknown IDs and cycles are refused, leaving
every file untouched. Only the frontmatter fields named above change.
"""

import argparse
import json
import re
import sys
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

# Shared helpers live in the repo's top-level scripts/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from pm_graph import Graph  # noqa: E402
from pm_items import Item, load_items, parse_frontmatter, set_field  # noqa: E402
from sync_ready_status import BLOCKED, CLOSED, READY  # noqa: E402

LIST_ENTRY_RE = re.compile(r"^\s*-\s")


class Refused(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


def set_list(path: Path, key: str, values: list[str]) -> None:
    """Write a list field inline (`key: [a, b]`), whatever syntax it had; changes nothing else.

    A trailing comment on an inline list is kept. A missing field is added at
    the end of the frontmatter.
    """
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    value = "[" + ", ".join(values) + "]"
    for i in range(1, end):
        if not lines[i].startswith(f"{key}:"):
            continue
        rest = lines[i][len(key) + 1:].rstrip("\r\n")
        comment = re.search(r"\]([ \t]+#.*)$", rest)
        lines[i] = f"{key}: {value}{comment.group(1) if comment else ''}\n"
        j = i + 1
        while j < end and LIST_ENTRY_RE.match(lines[j]):  # drop block-list entries
            j += 1
        del lines[i + 1:j]
        break
    else:
        lines.insert(end, f"{key}: {value}\n")
    path.write_text("".join(lines), encoding="utf-8")


def edit_list(item: Item, key: str, add: str | None = None, remove: str | None = None) -> None:
    current = parse_frontmatter(item.path.read_text(encoding="utf-8")).get(key)
    values = set(current) if isinstance(current, list) else set()
    if remove:
        values.discard(remove)
    if add:
        values.add(add)
    set_list(item.path, key, sorted(values))


class Product:
    def __init__(self, product_dir: Path):
        self.product_dir = product_dir
        self.reload()

    def reload(self) -> None:
        self.items = load_items(self.product_dir)
        self.graph = Graph(self.items)
        self.all_by_id: dict[str, list[Item]] = defaultdict(list)
        for item in self.items:
            if item.id:
                self.all_by_id[item.id].append(item)

    def find(self, item_id: str) -> Item:
        matches = self.all_by_id.get(item_id, [])
        if not matches:
            raise Refused(f"{item_id} not found", code=2)
        if len(matches) > 1:
            raise Refused(f"{item_id} is used by more than one file; run /pm-lint first", code=2)
        return matches[0]

    def edges(self, forward: str, backward: str) -> dict[str, set[str]]:
        """`A forward B` edges, merged from `forward` on A and `backward` on B."""
        edges: dict[str, set[str]] = defaultdict(set)
        for item in self.items:
            if item.id:
                edges[item.id].update(item.relations[forward])
                for other in item.relations[backward]:
                    edges[other].add(item.id)
        return edges

    def open_dependents(self, item_id: str) -> list[Item]:
        dependents = sorted(self.graph.dependents[item_id])
        return [self.graph.by_id[d] for d in dependents
                if d in self.graph.by_id and self.graph.by_id[d].status not in CLOSED]

    def rederive(self, item: Item) -> str:
        """Re-derive `ready` / `ready-but-blocked` for `item` and describe it for review."""
        if item.status in (READY, BLOCKED):
            status = BLOCKED if self.graph.open_blockers(item.id) else READY
            if status != item.status:
                set_field(item.path, "status", status)
                line = f"dependent: {item.id} {item.status} -> {status} ({item.path})"
                item.status = status
                return line
        return f"dependent: {item.id} (status: {item.status}) ({item.path})"


def path_between(edges: dict[str, set[str]], start: str, goal: str) -> list[str] | None:
    """Shortest path start -> ... -> goal following `edges`, or None."""
    previous: dict[str, str | None] = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            path = [node]
            while previous[path[-1]] is not None:
                path.append(previous[path[-1]])
            return path[::-1]
        for nxt in sorted(edges.get(node, ())):
            if nxt not in previous:
                previous[nxt] = node
                queue.append(nxt)
    return None


def refuse_cycle(edges: dict[str, set[str]], source: str, target: str, verb: str) -> None:
    """Refuse adding `source verb target` if target already reaches source."""
    path = path_between(edges, target, source)
    if path:
        cycle = f" {verb} ".join([source, *path])
        raise Refused(f"{source} {verb} {target} would create a cycle: {cycle}")


def check(product: Product, item_id: str) -> None:
    item = product.find(item_id)
    supersession = product.edges("superseded_by", "supersedes")
    print(json.dumps({
        "id": item.id,
        "title": item.title,
        "type": item.type,
        "status": item.status,
        "path": str(item.path),
        "superseded_by": sorted(supersession[item_id]),
        "dependents": [{"id": d.id, "title": d.title, "type": d.type, "status": d.status, "path": str(d.path)}
                       for d in product.open_dependents(item_id)],
    }, indent=2))


def deprecate(product: Product, item_id: str, replacement_id: str | None, now: str) -> None:
    item = product.find(item_id)
    if item.status == "deprecated":
        raise Refused(f"{item_id} is already deprecated")
    replacement = None
    if replacement_id is not None:
        if replacement_id == item_id:
            raise Refused(f"{item_id} can't supersede itself")
        replacement = product.find(replacement_id)
        if replacement.status == "deprecated":
            raise Refused(f"replacement {replacement_id} is deprecated")
        refuse_cycle(product.edges("supersedes", "superseded_by"), replacement_id, item_id, "supersedes")

    fields = parse_frontmatter(item.path.read_text(encoding="utf-8"))
    after = next((key for key in ("completed", "created") if key in fields), "status")
    set_field(item.path, "status", "deprecated")
    set_field(item.path, "deprecated", now, after=after)
    print(f"deprecated: {item_id} ({item.path})")
    if replacement is not None:
        edit_list(item, "superseded_by", add=replacement_id)
        edit_list(replacement, "supersedes", add=item_id)
        print(f"superseded by: {replacement_id} ({replacement.path})")

    product.reload()
    for dependent in product.open_dependents(item_id):
        print(product.rederive(dependent))


def unlink_blocker(product: Product, dependent: Item, blocker: Item) -> None:
    edit_list(dependent, "blocked_by", remove=blocker.id)
    edit_list(blocker, "blocks", remove=dependent.id)


def relink(product: Product, dependent_id: str, old_id: str, new_id: str) -> None:
    dependent = product.find(dependent_id)
    old = product.find(old_id)
    if old_id not in product.graph.blockers[dependent_id]:
        raise Refused(f"{dependent_id} is not blocked by {old_id}")
    if new_id == dependent_id:
        raise Refused(f"{dependent_id} can't block itself")
    new = product.find(new_id)
    blocking = product.edges("blocks", "blocked_by")
    blocking[old_id].discard(dependent_id)
    refuse_cycle(blocking, new_id, dependent_id, "blocks")

    unlink_blocker(product, dependent, old)
    edit_list(dependent, "blocked_by", add=new_id)
    edit_list(new, "blocks", add=dependent_id)
    print(f"relinked: {dependent_id} blocked_by {old_id} -> {new_id}")
    product.reload()
    line = product.rederive(product.find(dependent_id))
    if "->" in line:
        print(line)


def unlink(product: Product, dependent_id: str, blocker_id: str) -> None:
    dependent = product.find(dependent_id)
    blocker = product.find(blocker_id)
    if blocker_id not in product.graph.blockers[dependent_id]:
        raise Refused(f"{dependent_id} is not blocked by {blocker_id}")

    unlink_blocker(product, dependent, blocker)
    print(f"unlinked: {dependent_id} blocked_by {blocker_id}")
    product.reload()
    line = product.rederive(product.find(dependent_id))
    if "->" in line:
        print(line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--product-dir", default="product", help="product directory (default: ./product)")
    commands = parser.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("check", help="print the item, its replacements and open dependents as JSON")
    cmd.add_argument("id")
    cmd = commands.add_parser("deprecate", help="mark the item as deprecated")
    cmd.add_argument("id")
    cmd.add_argument("--superseded-by", help="ID of the item that replaces it")
    cmd.add_argument("--now", help="deprecation timestamp (default: current local time, ISO 8601)")
    cmd = commands.add_parser("relink", help="move a dependent's blocker to another item")
    cmd.add_argument("dependent")
    cmd.add_argument("old")
    cmd.add_argument("new")
    cmd = commands.add_parser("unlink", help="drop a dependent's blocker")
    cmd.add_argument("dependent")
    cmd.add_argument("blocker")
    args = parser.parse_args()

    product_dir = Path(args.product_dir)
    if not (product_dir / "items").is_dir():
        print(f"error: items directory not found: {(product_dir / 'items').resolve()}", file=sys.stderr)
        return 2

    product = Product(product_dir)
    try:
        if args.command == "check":
            check(product, args.id)
        elif args.command == "deprecate":
            now = args.now or datetime.now().astimezone().isoformat(timespec="seconds")
            deprecate(product, args.id, args.superseded_by, now)
        elif args.command == "relink":
            relink(product, args.dependent, args.old, args.new)
        else:
            unlink(product, args.dependent, args.blocker)
    except Refused as refused:
        print(f"error: {refused}", file=sys.stderr)
        return refused.code
    return 0


if __name__ == "__main__":
    sys.exit(main())
