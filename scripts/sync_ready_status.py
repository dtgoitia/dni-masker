#!/usr/bin/env python3
"""Switch items between `ready` and `ready-but-blocked` based on their blockers.

An item is `ready-but-blocked` while at least one of its blockers is neither
`done` nor `deprecated`, and `ready` otherwise. A blocker is declared either
on the blocked item (`blocked_by`) or on the blocker (`blocks`); both sides
count. Items with any other status are never changed.

Only the `status:` value in the frontmatter is rewritten (quotes and trailing
comments are kept). Changes are printed on stdout, sorted by item ID.
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from pm_items import Item, load_items, set_field

READY, BLOCKED = "ready", "ready-but-blocked"
CLOSED = {"done", "deprecated"}


def blockers_of(items: list[Item]) -> dict[str, set[str]]:
    """Map each item ID to the IDs of the items that block it, from both sides."""
    blockers: dict[str, set[str]] = defaultdict(set)
    for item in items:
        if not item.id:
            continue
        blockers[item.id].update(item.relations["blocked_by"])
        for blocked in item.relations["blocks"]:
            blockers[blocked].add(item.id)
    return blockers


def expected_status(item: Item, blockers: set[str], status_by_id: dict[str, set[str | None]]) -> str:
    # Unknown or duplicated IDs are pm-lint's concern; they count as open here.
    is_open = any(not status_by_id.get(b) or not status_by_id[b] <= CLOSED for b in blockers)
    return BLOCKED if is_open else READY


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--product-dir", default="product", help="product directory (default: ./product)")
    parser.add_argument("--dry-run", action="store_true", help="only print planned changes")
    args = parser.parse_args()

    product_dir = Path(args.product_dir)
    if not (product_dir / "items").is_dir():
        print(f"error: items directory not found: {(product_dir / 'items').resolve()}", file=sys.stderr)
        return 2

    items = load_items(product_dir)
    blockers = blockers_of(items)
    status_by_id: dict[str, set[str | None]] = defaultdict(set)
    for item in items:
        if item.id:
            status_by_id[item.id].add(item.status)

    changes = []
    for item in items:
        if not item.id or item.status not in (READY, BLOCKED):
            continue
        status = expected_status(item, blockers[item.id], status_by_id)
        if status != item.status:
            changes.append((item, status))

    for item, status in sorted(changes, key=lambda change: (change[0].id, str(change[0].path))):
        print(f"{'would update' if args.dry_run else 'updated'}: {item.id} {item.status} -> {status} ({item.path})")
        if not args.dry_run:
            set_field(item.path, "status", status)

    if not changes:
        print("all ready statuses are up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
