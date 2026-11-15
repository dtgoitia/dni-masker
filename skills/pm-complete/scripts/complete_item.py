#!/usr/bin/env python3
"""Check an item before completing it, and mark it as done.

  check <ID>     print the item and its open blockers as JSON
  complete <ID>  set `status: done` and `completed: <now>` (and `decision:`
                 for questions), then re-derive `ready` / `ready-but-blocked`
                 for the item's direct dependents and report on each of them

Blockers and dependents come from both sides of a relationship: `blocked_by`
on the dependent and `blocks` on the blocker. Only the frontmatter fields
named above are changed.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Shared helpers live in the repo's top-level scripts/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from pm_items import Item, load_items, parse_frontmatter, set_field  # noqa: E402
from sync_ready_status import BLOCKED, CLOSED, READY, blockers_of  # noqa: E402

DECISION_ID_RE = re.compile(r"(PDR|ADR)-\d{4,}")


class Refused(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


class Graph:
    def __init__(self, items: list[Item]):
        self.by_id: dict[str, list[Item]] = defaultdict(list)
        for item in items:
            if item.id:
                self.by_id[item.id].append(item)
        self.blockers = blockers_of(items)

    def find(self, item_id: str) -> Item:
        matches = self.by_id.get(item_id, [])
        if not matches:
            raise Refused(f"{item_id} not found", code=2)
        if len(matches) > 1:
            raise Refused(f"{item_id} is used by more than one file; run /pm-lint first", code=2)
        return matches[0]

    def is_closed(self, item_id: str) -> bool:
        # Unknown IDs count as open; reporting them is /pm-lint's job.
        statuses = {item.status for item in self.by_id.get(item_id, [])}
        return bool(statuses) and statuses <= CLOSED

    def open_blockers(self, item_id: str) -> list[str]:
        return sorted(b for b in self.blockers[item_id] if not self.is_closed(b))

    def dependents(self, item_id: str) -> list[str]:
        return sorted(d for d, blockers in self.blockers.items() if item_id in blockers)


def check(graph: Graph, item_id: str) -> None:
    item = graph.find(item_id)

    def describe(blocker_id: str) -> dict[str, str | None]:
        found = graph.by_id.get(blocker_id)
        return {"id": blocker_id, "title": found[0].title if found else None,
                "status": found[0].status if found else None}

    print(json.dumps({
        "id": item.id,
        "title": item.title,
        "type": item.type,
        "status": item.status,
        "path": str(item.path),
        "open_blockers": [describe(b) for b in graph.open_blockers(item_id)],
    }, indent=2))


def find_decision(product_dir: Path, decision_id: str) -> tuple[Path, dict]:
    for path in sorted((product_dir / "decisions").rglob("*.md")):
        try:
            fm = parse_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if fm.get("id") == decision_id or re.match(rf"{decision_id}(-|\.md$)", path.name):
            return path, fm
    raise Refused(f"decision {decision_id} not found in {product_dir / 'decisions'}")


def complete(graph: Graph, product_dir: Path, item_id: str, decision: str | None, now: str) -> None:
    item = graph.find(item_id)
    if item.status in CLOSED:
        raise Refused(f"{item_id} is already {item.status}")
    if decision is not None:
        if not DECISION_ID_RE.fullmatch(decision):
            raise Refused(f"invalid decision ID: {decision} (expected PDR-nnnn or ADR-nnnn)")
        if item.type != "question":
            raise Refused("--decision is only for questions")
        _, fm = find_decision(product_dir, decision)
        if fm.get("question") != item_id:
            raise Refused(f"{decision} has `question: {fm.get('question')}`, expected {item_id}")
    elif item.type == "question":
        raise Refused(f"{item_id} is a question: pass --decision <PDR-nnnn|ADR-nnnn>")

    has_created = "created" in parse_frontmatter(item.path.read_text(encoding="utf-8"))
    set_field(item.path, "status", "done")
    set_field(item.path, "completed", now, after="created" if has_created else "status")
    if decision is not None:
        set_field(item.path, "decision", decision, after="completed")
    item.status = "done"
    print(f"completed: {item_id} ({item.path})")

    for dependent_id in graph.dependents(item_id):
        for dependent in graph.by_id.get(dependent_id, []):
            if dependent.status in CLOSED:
                continue
            still_open = graph.open_blockers(dependent_id)
            if dependent.status in (READY, BLOCKED):
                status = BLOCKED if still_open else READY
                if status != dependent.status:
                    set_field(dependent.path, "status", status)
                    dependent.status = status
            if still_open:
                print(f"still blocked: {dependent_id} by {', '.join(still_open)} ({dependent.path})")
            elif dependent.status == READY:
                print(f"now ready: {dependent_id} ({dependent.path})")
            else:
                print(f"no longer blocked: {dependent_id} (status: {dependent.status}) ({dependent.path})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--product-dir", default="product", help="product directory (default: ./product)")
    commands = parser.add_subparsers(dest="command", required=True)
    check_cmd = commands.add_parser("check", help="print the item and its open blockers as JSON")
    check_cmd.add_argument("id")
    complete_cmd = commands.add_parser("complete", help="mark the item as done and update its dependents")
    complete_cmd.add_argument("id")
    complete_cmd.add_argument("--decision", help="decision record (PDR-nnnn / ADR-nnnn); required for questions")
    complete_cmd.add_argument("--now", help="completion timestamp (default: current local time, ISO 8601)")
    args = parser.parse_args()

    product_dir = Path(args.product_dir)
    if not (product_dir / "items").is_dir():
        print(f"error: items directory not found: {(product_dir / 'items').resolve()}", file=sys.stderr)
        return 2

    graph = Graph(load_items(product_dir))
    try:
        if args.command == "check":
            check(graph, args.id)
        else:
            now = args.now or datetime.now().astimezone().isoformat(timespec="seconds")
            complete(graph, product_dir, args.id, args.decision, now)
    except Refused as refused:
        print(f"error: {refused}", file=sys.stderr)
        return refused.code
    return 0


if __name__ == "__main__":
    sys.exit(main())
