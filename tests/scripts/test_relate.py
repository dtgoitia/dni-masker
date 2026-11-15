"""relate.py: add or remove a relationship on both items at once.

`A blocks B` is written as `blocks: [B]` on A and `blocked_by: [A]` on B (and
likewise for supersedes / superseded_by; related_to is symmetric). Self links,
unknown IDs and cycles are refused. A blocking change re-derives `ready` /
`ready-but-blocked` for the blocked item.
"""

import pytest
from pm_items import parse_frontmatter

SCRIPT = "relate.py"


def fm(path) -> dict:
    return parse_frontmatter(path.read_text())


def item(write_item, item_id, status="clarifying", **fields):
    return write_item(f"{item_id}-x.md", id=item_id, title=item_id, type="feature", status=status, **fields)


# --- add ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("relation", "a_field", "b_field"),
    [
        ("blocks", "blocks", "blocked_by"),
        ("blocked_by", "blocked_by", "blocks"),
        ("supersedes", "supersedes", "superseded_by"),
        ("superseded_by", "superseded_by", "supersedes"),
        ("related_to", "related_to", "related_to"),
    ],
)
def test_add_writes_both_sides(write_item, run, relation, a_field, b_field):
    a = item(write_item, "F-0001")
    b = item(write_item, "F-0002")

    result = run(SCRIPT, "add", "F-0001", relation, "F-0002")

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [f"added: F-0001 {relation} F-0002"]
    assert fm(a)[a_field] == ["F-0002"]
    assert fm(b)[b_field] == ["F-0001"]


def test_add_keeps_existing_entries_sorted(write_item, run):
    a = item(write_item, "F-0001", blocks=["F-0009", "F-0003"])
    item(write_item, "F-0002")
    item(write_item, "F-0003", blocked_by=["F-0001"])
    item(write_item, "F-0009", blocked_by=["F-0001"])

    run(SCRIPT, "add", "F-0001", "blocks", "F-0002")

    assert fm(a)["blocks"] == ["F-0002", "F-0003", "F-0009"]


def test_add_existing_relation_is_unchanged(write_item, run):
    a = item(write_item, "F-0001", blocks=["F-0002"])
    b = item(write_item, "F-0002", blocked_by=["F-0001"])
    before = (a.read_bytes(), b.read_bytes())

    result = run(SCRIPT, "add", "F-0001", "blocks", "F-0002")

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["unchanged: F-0001 blocks F-0002"]
    assert (a.read_bytes(), b.read_bytes()) == before


def test_add_completes_a_one_sided_relation(write_item, run):
    item(write_item, "F-0001", blocks=["F-0002"])
    b = item(write_item, "F-0002")

    result = run(SCRIPT, "add", "F-0001", "blocks", "F-0002")

    assert result.stdout.splitlines() == ["added: F-0001 blocks F-0002"]
    assert fm(b)["blocked_by"] == ["F-0001"]


def test_only_the_relation_fields_change(write_item, run):
    text = "---\nid: F-0001\ntitle: a   # comment\nstatus: idea\nblocks: []\n---\n\nblocks: [body]\n"
    a = write_item("F-0001-a.md", text=text)
    item(write_item, "F-0002")

    run(SCRIPT, "add", "F-0001", "blocks", "F-0002")

    assert a.read_text() == text.replace("blocks: []", "blocks: [F-0002]", 1)


# --- refusals ------------------------------------------------------------------------


def test_self_relation_is_refused(write_item, run):
    a = item(write_item, "F-0001")
    before = a.read_bytes()

    result = run(SCRIPT, "add", "F-0001", "blocks", "F-0001")

    assert result.returncode == 1
    assert "F-0001 can't be related to itself" in result.stderr
    assert a.read_bytes() == before


def test_unknown_id_is_refused(write_item, run):
    a = item(write_item, "F-0001")
    before = a.read_bytes()

    result = run(SCRIPT, "add", "F-0001", "blocks", "F-0099")

    assert result.returncode == 2
    assert "F-0099 not found" in result.stderr
    assert a.read_bytes() == before


def test_duplicate_id_is_refused(write_item, run):
    item(write_item, "F-0001")
    write_item("F-0002-a.md", id="F-0002", title="a", status="idea")
    write_item("F-0002-b.md", id="F-0002", title="b", status="idea")

    result = run(SCRIPT, "add", "F-0001", "blocks", "F-0002")

    assert result.returncode == 2
    assert "F-0002 is used by more than one file" in result.stderr


@pytest.mark.parametrize(
    ("args", "cycle"),
    [
        (("F-0003", "blocks", "F-0001"), "F-0003 blocks F-0001 blocks F-0002 blocks F-0003"),
        (("F-0001", "blocked_by", "F-0003"), "F-0003 blocks F-0001 blocks F-0002 blocks F-0003"),
    ],
)
def test_blocking_cycle_is_refused(write_item, run, args, cycle):
    # Existing chain declared from both sides: F-0001 blocks F-0002, F-0003 blocked_by F-0002.
    a = item(write_item, "F-0001", blocks=["F-0002"])
    item(write_item, "F-0002", blocked_by=["F-0001"])
    c = item(write_item, "F-0003", blocked_by=["F-0002"])
    before = (a.read_bytes(), c.read_bytes())

    result = run(SCRIPT, "add", *args)

    assert result.returncode == 1
    assert f"would create a cycle: {cycle}" in result.stderr
    assert (a.read_bytes(), c.read_bytes()) == before


def test_supersession_cycle_is_refused(write_item, run):
    item(write_item, "F-0001", supersedes=["F-0002"])
    item(write_item, "F-0002", superseded_by=["F-0001"])

    result = run(SCRIPT, "add", "F-0002", "supersedes", "F-0001")

    assert result.returncode == 1
    assert "would create a cycle: F-0002 supersedes F-0001 supersedes F-0002" in result.stderr


def test_related_to_never_forms_a_cycle(write_item, run):
    item(write_item, "F-0001", related_to=["F-0002"])
    item(write_item, "F-0002", related_to=["F-0001", "F-0003"])
    item(write_item, "F-0003", related_to=["F-0002"])

    assert run(SCRIPT, "add", "F-0003", "related_to", "F-0001").returncode == 0


def test_blocking_and_supersession_cycles_are_separate(write_item, run):
    item(write_item, "F-0001", blocks=["F-0002"])
    item(write_item, "F-0002", blocked_by=["F-0001"])

    assert run(SCRIPT, "add", "F-0002", "supersedes", "F-0001").returncode == 0


# --- remove ------------------------------------------------------------------------


def test_remove_clears_both_sides(write_item, run):
    a = item(write_item, "F-0001", blocks=["F-0002", "F-0003"])
    b = item(write_item, "F-0002", blocked_by=["F-0001"])
    item(write_item, "F-0003", blocked_by=["F-0001"])

    result = run(SCRIPT, "remove", "F-0002", "blocked_by", "F-0001")

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["removed: F-0002 blocked_by F-0001"]
    assert fm(a)["blocks"] == ["F-0003"]
    assert fm(b)["blocked_by"] == []


def test_remove_missing_relation_is_unchanged(write_item, run):
    a = item(write_item, "F-0001")
    item(write_item, "F-0002")
    before = a.read_bytes()

    result = run(SCRIPT, "remove", "F-0001", "blocks", "F-0002")

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["unchanged: F-0001 blocks F-0002"]
    assert a.read_bytes() == before


# --- ready statuses ------------------------------------------------------------------


def test_blocking_a_ready_item_makes_it_ready_but_blocked(write_item, run):
    item(write_item, "F-0001", status="in-progress")
    b = item(write_item, "F-0002", status="ready")

    result = run(SCRIPT, "add", "F-0001", "blocks", "F-0002")

    assert fm(b)["status"] == "ready-but-blocked"
    assert result.stdout.splitlines() == [
        "added: F-0001 blocks F-0002",
        f"status: F-0002 ready -> ready-but-blocked ({b})",
    ]


def test_blocked_by_a_closed_item_stays_ready(write_item, run):
    item(write_item, "F-0001", status="done")
    b = item(write_item, "F-0002", status="ready")

    result = run(SCRIPT, "add", "F-0002", "blocked_by", "F-0001")

    assert fm(b)["status"] == "ready"
    assert result.stdout.splitlines() == ["added: F-0002 blocked_by F-0001"]


def test_removing_the_last_open_blocker_makes_it_ready(write_item, run):
    item(write_item, "F-0001", status="in-progress", blocks=["F-0002"])
    b = item(write_item, "F-0002", status="ready-but-blocked", blocked_by=["F-0001"])

    result = run(SCRIPT, "remove", "F-0001", "blocks", "F-0002")

    assert fm(b)["status"] == "ready"
    assert result.stdout.splitlines()[-1] == f"status: F-0002 ready-but-blocked -> ready ({b})"


@pytest.mark.parametrize("status", ["idea", "clarifying", "in-progress"])
def test_other_statuses_are_left_alone(write_item, run, status):
    item(write_item, "F-0001", status="in-progress")
    b = item(write_item, "F-0002", status=status)

    result = run(SCRIPT, "add", "F-0001", "blocks", "F-0002")

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["added: F-0001 blocks F-0002"]
    assert fm(b)["status"] == status


def test_missing_items_directory(run, product):
    (product / "items").rmdir()

    result = run(SCRIPT, "add", "F-0001", "blocks", "F-0002")

    assert result.returncode == 2
    assert "items directory not found" in result.stderr
