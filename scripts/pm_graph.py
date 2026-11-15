"""The blocking graph between items, and the order in which /pm-next picks them.

A blocker is declared either on the blocked item (`blocked_by`) or on the
blocker (`blocks`); both sides count. An item is open unless it is `done` or
`deprecated`; unknown IDs count as open (dangling references are /pm-lint's
concern, as are duplicate IDs: the first file wins here).
"""

from collections import defaultdict
from datetime import datetime

from pm_items import Item
from sync_ready_status import CLOSED, blockers_of


def created_key(item: Item) -> tuple[int, float]:
    try:
        return 0, datetime.fromisoformat(item.created or "").timestamp()
    except ValueError:
        return 1, 0.0  # missing or unparsable: after every dated item


class Graph:
    def __init__(self, items: list[Item]):
        self.by_id: dict[str, Item] = {}
        for item in items:
            if item.id:
                self.by_id.setdefault(item.id, item)
        self.blockers = blockers_of(items)
        self.dependents: dict[str, set[str]] = defaultdict(set)
        for item_id, item_blockers in self.blockers.items():
            for blocker in item_blockers:
                self.dependents[blocker].add(item_id)

    def is_open(self, item_id: str) -> bool:
        item = self.by_id.get(item_id)
        return item is None or item.status not in CLOSED

    def open_blockers(self, item_id: str) -> list[str]:
        return sorted(b for b in self.blockers[item_id] if self.is_open(b))

    def unblocks(self, item_id: str) -> list[str]:
        """Open items that depend on `item_id`, directly or transitively."""
        seen: set[str] = set()
        stack = [item_id]
        while stack:
            for dependent in self.dependents[stack.pop()]:
                if dependent != item_id and dependent not in seen and self.is_open(dependent):
                    seen.add(dependent)
                    stack.append(dependent)
        return sorted(seen)

    def describe(self, item_id: str) -> dict:
        item = self.by_id.get(item_id)
        return {"id": item_id, "title": item and item.title, "type": item and item.type,
                "status": item and item.status}

    def rank_key(self, item: Item) -> tuple:
        """Most open work unblocked first, then the oldest `created`, then the lowest ID."""
        return -len(self.unblocks(item.id)), created_key(item), item.id
