"""status.py: report the items that are ready, in progress and blocked.

Items are grouped by their `status` field as written (`ready`,
`in-progress`, `ready-but-blocked`); every other status is left out. Ready
items are listed in the order /pm-next picks them; the other groups by ID.
Blocked items list their open blockers. The script never writes files.
"""

import json

import pytest

SCRIPT = "status.py"


def report(run, *args) -> dict:
    result = run(SCRIPT, *args)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def ids(entries: list[dict]) -> list[str]:
    return [e["id"] for e in entries]


def item(write_item, item_id, status="ready", **fields):
    item_type = {"F": "feature", "T": "technical", "Q": "question"}[item_id[0]]
    return write_item(f"{item_id}-x.md", id=item_id, title=f"title {item_id}", type=item_type,
                      status=status, **fields)


# --- grouping ---------------------------------------------------------------------


def test_empty_product(run):
    assert report(run) == {"ready": [], "in_progress": [], "blocked": []}


def test_groups_items_by_status(write_item, run):
    for i, status in enumerate(["idea", "clarifying", "ready", "ready-but-blocked", "in-progress",
                                "done", "deprecated"], start=1):
        item(write_item, f"F-{i:04d}", status=status)

    result = report(run)

    assert ids(result["ready"]) == ["F-0003"]
    assert ids(result["blocked"]) == ["F-0004"]
    assert ids(result["in_progress"]) == ["F-0005"]


def test_entries_describe_the_item(write_item, run):
    a = item(write_item, "F-0001", blocks=["F-0002"])
    b = item(write_item, "F-0002", status="ready-but-blocked")
    c = item(write_item, "T-0001", status="in-progress")

    result = report(run)

    assert result["ready"] == [
        {"id": "F-0001", "title": "title F-0001", "type": "feature", "path": str(a), "unblocks": ["F-0002"]}
    ]
    assert result["blocked"] == [
        {"id": "F-0002", "title": "title F-0002", "type": "feature", "path": str(b),
         "open_blockers": [{"id": "F-0001", "title": "title F-0001", "type": "feature", "status": "ready"}]}
    ]
    assert result["in_progress"] == [
        {"id": "T-0001", "title": "title T-0001", "type": "technical", "path": str(c)}
    ]


def test_questions_are_included(write_item, run):
    item(write_item, "Q-0001")
    item(write_item, "Q-0002", status="ready-but-blocked", blocked_by=["Q-0001"])

    result = report(run)

    assert ids(result["ready"]) == ["Q-0001"]
    assert ids(result["blocked"]) == ["Q-0002"]


def test_items_without_id_are_skipped(write_item, run):
    write_item("notes.md", title="no id", status="ready")

    assert report(run)["ready"] == []


# --- statuses are trusted -----------------------------------------------------------


def test_stale_ready_item_stays_ready(write_item, run):
    item(write_item, "F-0001", status="idea")
    item(write_item, "F-0002", blocked_by=["F-0001"])

    result = report(run)

    assert ids(result["ready"]) == ["F-0002"]
    assert result["blocked"] == []


def test_stale_blocked_item_stays_blocked_with_no_open_blockers(write_item, run):
    item(write_item, "F-0001", status="done")
    item(write_item, "F-0002", status="ready-but-blocked", blocked_by=["F-0001"])

    blocked = report(run)["blocked"]

    assert ids(blocked) == ["F-0002"]
    assert blocked[0]["open_blockers"] == []


def test_unknown_blockers_are_reported_as_open(write_item, run):
    item(write_item, "F-0001", status="ready-but-blocked", blocked_by=["F-0099"])

    assert report(run)["blocked"][0]["open_blockers"] == [
        {"id": "F-0099", "title": None, "type": None, "status": None}
    ]


# --- ordering -----------------------------------------------------------------------


def test_ready_items_are_ordered_like_pm_next(write_item, run):
    item(write_item, "F-0001", created="2026-03-01T00:00:00+00:00")
    item(write_item, "F-0002")
    item(write_item, "F-0003", created="2026-01-01T00:00:00+00:00")
    item(write_item, "F-0004", blocks=["F-0005"], created="2026-05-01T00:00:00+00:00")
    item(write_item, "F-0005", status="idea")

    assert ids(report(run)["ready"]) == ["F-0004", "F-0003", "F-0001", "F-0002"]


def test_other_groups_are_ordered_by_id(write_item, run):
    for item_id in ["F-0003", "T-0001", "F-0001"]:
        item(write_item, item_id, status="in-progress")
    for item_id in ["Q-0002", "F-0002"]:
        item(write_item, item_id, status="ready-but-blocked")

    result = report(run)

    assert ids(result["in_progress"]) == ["F-0001", "F-0003", "T-0001"]
    assert ids(result["blocked"]) == ["F-0002", "Q-0002"]


# --- read-only and errors -------------------------------------------------------------


@pytest.mark.parametrize("status", ["ready", "ready-but-blocked"])
def test_never_writes_files(write_item, run, status):
    item(write_item, "F-0001", status="done")
    path = item(write_item, "F-0002", status=status, blocked_by=["F-0001"] if status != "ready" else ["F-0099"])
    before = path.read_text()

    report(run)

    assert path.read_text() == before


def test_missing_items_directory(run, product):
    (product / "items").rmdir()

    result = run(SCRIPT)

    assert result.returncode == 2
    assert "items directory not found" in result.stderr
