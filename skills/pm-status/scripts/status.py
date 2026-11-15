#!/usr/bin/env python3
"""Report the product items that are ready, in progress and blocked.

Items are grouped by their `status` field as written; items with any other
status (idea, clarifying, done, deprecated) are left out, as are files with
no `id`. The script never writes files: stale `ready` / `ready-but-blocked`
statuses are /pm-lint's concern.

Prints JSON:
  ready        `ready` items, in the order /pm-next picks them (most open work
               unblocked first, then oldest `created`, then lowest ID), with
               `unblocks`: the open items they unblock, directly or transitively
  in_progress  `in-progress` items, by ID
  blocked      `ready-but-blocked` items, by ID, with `open_blockers`
               (id, title, type, status; unknown IDs have null fields)
"""

import argparse
import json
import sys
from pathlib import Path

# Shared helpers live in the repo's top-level scripts/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from pm_graph import Graph  # noqa: E402
from pm_items import Item, load_items  # noqa: E402
from sync_ready_status import BLOCKED, READY  # noqa: E402

IN_PROGRESS = "in-progress"


def entry(item: Item, **extra) -> dict:
    return {"id": item.id, "title": item.title, "type": item.type, "path": str(item.path), **extra}


def status_report(product_dir: Path) -> dict:
    graph = Graph(load_items(product_dir))

    def with_status(status: str) -> list[Item]:
        return sorted((i for i in graph.by_id.values() if i.status == status), key=lambda i: i.id)

    return {
        "ready": [entry(i, unblocks=graph.unblocks(i.id))
                  for i in sorted(with_status(READY), key=graph.rank_key)],
        "in_progress": [entry(i) for i in with_status(IN_PROGRESS)],
        "blocked": [entry(i, open_blockers=[graph.describe(b) for b in graph.open_blockers(i.id)])
                    for i in with_status(BLOCKED)],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--product-dir", default="product", help="product directory (default: ./product)")
    args = parser.parse_args()

    product_dir = Path(args.product_dir)
    if not (product_dir / "items").is_dir():
        print(f"error: items directory not found: {(product_dir / 'items').resolve()}", file=sys.stderr)
        return 2

    print(json.dumps(status_report(product_dir), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
