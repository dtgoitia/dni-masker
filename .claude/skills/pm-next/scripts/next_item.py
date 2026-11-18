#!/usr/bin/env python3
"""Pick the next unblocked ready item and claim it by setting `in-progress`.

Candidates are features and technical items whose status is `ready` (or a
stale `ready-but-blocked`) and whose blockers, declared on either side
(`blocked_by` / `blocks`), are all done or deprecated. Questions are never
picked: people answer them (see /pm-complete).

The candidate that unblocks the most open items, directly or transitively,
wins. Ties go to the oldest `created`, then the lowest ID. A lock on the
items directory keeps concurrent runs from claiming the same item.

Prints JSON:
  picked           the claimed item (id, title, type, path, unblocks, context)
                   or null; `context` lists the files to read before starting:
                   related items and the decisions of related questions
  waiting          ready features/technical items with open blockers
  ready_questions  unblocked questions waiting for an answer
"""

import argparse
import fcntl
import json
import os
import sys
from pathlib import Path

# Shared helpers live in the repo's top-level scripts/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
from pm_graph import Graph  # noqa: E402
from pm_items import RELATION_FIELDS, load_decisions, load_items, set_field  # noqa: E402
from sync_ready_status import BLOCKED, READY  # noqa: E402

WORK_TYPES = {"feature", "technical"}


def select(product_dir: Path) -> dict:
    graph = Graph(load_items(product_dir))
    by_id, open_blockers, describe = graph.by_id, graph.open_blockers, graph.describe

    ready = [i for i in by_id.values() if i.status in (READY, BLOCKED)]
    candidates = [i for i in ready if i.type in WORK_TYPES and not open_blockers(i.id)]
    waiting = [i for i in ready if i.type in WORK_TYPES and open_blockers(i.id)]
    questions = [i for i in ready if i.type == "question" and not open_blockers(i.id)]

    result: dict = {
        "picked": None,
        "waiting": [{"id": i.id, "title": i.title, "status": i.status,
                     "open_blockers": [describe(b) for b in open_blockers(i.id)]}
                    for i in sorted(waiting, key=lambda i: i.id)],
        "ready_questions": [{"id": i.id, "title": i.title, "path": str(i.path)}
                            for i in sorted(questions, key=lambda i: i.id)],
    }
    if not candidates:
        return result

    best = min(candidates, key=graph.rank_key)
    related = {r for field in RELATION_FIELDS for r in best.relations[field]}
    related |= graph.blockers[best.id] | graph.dependents[best.id]
    related.discard(best.id)
    decision_paths = {d.id: d.path for d in load_decisions(product_dir) if d.id}
    context = set()
    for related_id in related:
        item = by_id.get(related_id)
        if item is None:
            continue
        context.add(str(item.path))
        if item.decision in decision_paths:
            context.add(str(decision_paths[item.decision]))

    result["picked"] = {
        "id": best.id,
        "title": best.title,
        "type": best.type,
        "path": str(best.path),
        "unblocks": graph.unblocks(best.id),
        "context": sorted(context),
    }
    result["_item"] = best
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--product-dir", default="product", help="product directory (default: ./product)")
    parser.add_argument("--dry-run", action="store_true", help="report the pick without claiming it")
    args = parser.parse_args()

    items_dir = Path(args.product_dir) / "items"
    if not items_dir.is_dir():
        print(f"error: items directory not found: {items_dir.resolve()}", file=sys.stderr)
        return 2

    lock = os.open(items_dir, os.O_RDONLY)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)  # held until the claim is written
        result = select(Path(args.product_dir))
        item = result.pop("_item", None)
        if item is not None and not args.dry_run:
            set_field(item.path, "status", "in-progress")
    finally:
        os.close(lock)

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
