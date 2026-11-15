"""pm_graph: the blocking graph between items, and the order /pm-next picks in.

Blockers are declared on either side (`blocked_by` / `blocks`). An item is
open unless it is done or deprecated; unknown IDs count as open. Items are
ranked by how much open work they unblock (transitively), then oldest
`created`, then lowest ID.
"""

from pm_graph import Graph
from pm_items import load_items


def graph(product) -> Graph:
    return Graph(load_items(product))


def item(write_item, item_id, status="ready", **fields):
    return write_item(f"{item_id}-x.md", id=item_id, title=f"title {item_id}", type="feature",
                      status=status, **fields)


def ranked_ids(product) -> list[str]:
    g = graph(product)
    return [i.id for i in sorted(g.by_id.values(), key=g.rank_key)]


def test_blockers_count_from_both_sides(write_item, product):
    item(write_item, "F-0001", blocks=["F-0003"])
    item(write_item, "F-0002")
    item(write_item, "F-0003", blocked_by=["F-0002"])

    g = graph(product)

    assert g.blockers["F-0003"] == {"F-0001", "F-0002"}
    assert g.dependents["F-0001"] == {"F-0003"}


def test_open_blockers_skip_closed_and_keep_unknown(write_item, product):
    item(write_item, "F-0001", status="done")
    item(write_item, "F-0002", status="deprecated")
    item(write_item, "F-0003", status="idea")
    item(write_item, "F-0004", blocked_by=["F-0001", "F-0002", "F-0003", "F-0099"])

    assert graph(product).open_blockers("F-0004") == ["F-0003", "F-0099"]


def test_unblocks_is_transitive_open_and_cycle_safe(write_item, product):
    item(write_item, "F-0001", blocks=["F-0002"], blocked_by=["F-0004"])
    item(write_item, "F-0002", blocks=["F-0003", "F-0005"])
    item(write_item, "F-0003", blocks=["F-0004"])
    item(write_item, "F-0004")
    item(write_item, "F-0005", status="done")

    assert graph(product).unblocks("F-0001") == ["F-0002", "F-0003", "F-0004"]


def test_duplicate_ids_keep_the_first_file(write_item, product):
    write_item("F-0001-a.md", id="F-0001", title="first", status="ready")
    write_item("F-0001-b.md", id="F-0001", title="second", status="ready")

    assert graph(product).by_id["F-0001"].title == "first"


def test_rank_most_unblocking_then_oldest_then_lowest_id(write_item, product):
    item(write_item, "F-0001", created="2026-03-01T00:00:00+00:00")
    item(write_item, "F-0002")  # no created: after dated items
    item(write_item, "F-0003", created="2026-01-01T00:00:00+00:00")
    item(write_item, "F-0004", blocks=["F-0005"], created="2026-05-01T00:00:00+00:00")
    item(write_item, "F-0005", status="idea", created="2026-01-01T00:00:00+00:00")
    item(write_item, "F-0006")

    assert ranked_ids(product) == ["F-0004", "F-0003", "F-0005", "F-0001", "F-0002", "F-0006"]
