import pytest
from _items import parse_frontmatter
from check_relations import find_cycles

SCRIPT = "check_relations.py"


def problems(result) -> list[str]:
    return [line for line in result.stderr.splitlines() if not line.startswith("warning:")]


# --- frontmatter parsing -----------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("blocks: [F-0001, T-0002]", ["F-0001", "T-0002"]),
        ('blocks: ["F-0001", \'T-0002\']', ["F-0001", "T-0002"]),
        ("blocks: []", []),
        ("blocks:\n  - F-0001\n  - T-0002", ["F-0001", "T-0002"]),
        ("blocks:\n- F-0001\n- T-0002   # comment", ["F-0001", "T-0002"]),
    ],
)
def test_parse_list_syntaxes(text, expected):
    assert parse_frontmatter(f"---\n{text}\nid: F-0009\n---\n") == {"blocks": expected, "id": "F-0009"}


def test_parse_without_frontmatter():
    assert parse_frontmatter("no frontmatter\n") == {}


# --- cycle detection -----------------------------------------------------------


@pytest.mark.parametrize(
    ("edges", "cycles"),
    [
        ({"A": {"B"}, "B": set()}, []),
        ({"A": {"B"}, "B": {"A"}}, [["A", "B", "A"]]),
        ({"A": {"B"}, "B": {"C"}, "C": {"A"}}, [["A", "B", "C", "A"]]),
        # diamond: no cycle
        ({"A": {"B", "C"}, "B": {"D"}, "C": {"D"}, "D": set()}, []),
        # two independent cycles
        ({"A": {"B"}, "B": {"A"}, "C": {"D"}, "D": {"C"}}, [["A", "B", "A"], ["C", "D", "C"]]),
        # dead end inside the walk: A->B->D (D only leads back via C)
        ({"A": {"B"}, "B": {"D", "C"}, "C": {"A"}, "D": {"B"}}, [["A", "B", "C", "A"]]),
    ],
)
def test_find_cycles(edges, cycles):
    assert find_cycles(edges) == cycles


# --- end-to-end ----------------------------------------------------------------


def test_consistent_items_have_no_problems(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", blocks=["F-0002"], related_to=["Q-0001"],
               superseded_by=["F-0003"])
    write_item("F-0002-b.md", id="F-0002", title="b", blocked_by=["F-0001"])
    write_item("F-0003-c.md", id="F-0003", title="c", supersedes=["F-0001"])
    write_item("Q-0001-d.md", id="Q-0001", title="d", related_to=[], blocks=[])

    result = run(SCRIPT)

    assert result.returncode == 0
    assert "no relationship problems found" in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize("field", ["related_to", "blocks", "blocked_by", "supersedes", "superseded_by"])
def test_self_reference(write_item, run, field):
    path = write_item("F-0001-a.md", id="F-0001", title="a", **{field: ["F-0001"]})

    result = run(SCRIPT)

    assert result.returncode == 1
    assert problems(result) == [f"self-reference: F-0001 {field} itself ({path})"]


@pytest.mark.parametrize("field", ["related_to", "blocks", "blocked_by", "supersedes", "superseded_by"])
def test_unknown_id(write_item, run, field):
    path = write_item("F-0001-a.md", id="F-0001", title="a", **{field: ["F-0099"]})

    result = run(SCRIPT)

    assert result.returncode == 1
    assert problems(result) == [f"unknown ID: F-0001 {field} F-0099, which doesn't exist ({path})"]


@pytest.mark.parametrize(
    ("field", "inverse"),
    [
        ("blocks", "blocked_by"),
        ("blocked_by", "blocks"),
        ("supersedes", "superseded_by"),
        ("superseded_by", "supersedes"),
    ],
)
def test_out_of_sync_pair(write_item, run, field, inverse):
    write_item("F-0001-a.md", id="F-0001", title="a", **{field: ["F-0002"]})
    other = write_item("F-0002-b.md", id="F-0002", title="b")

    result = run(SCRIPT)

    assert result.returncode == 1
    assert problems(result) == [f"out of sync: F-0001 {field} F-0002, but F-0002 doesn't list F-0001 in {inverse} ({other})"]


def test_inverse_in_the_wrong_field_is_out_of_sync(write_item, run):
    # F-0002 mentions F-0001, but in `related_to` rather than `blocked_by`.
    write_item("F-0001-a.md", id="F-0001", title="a", blocks=["F-0002"])
    write_item("F-0002-b.md", id="F-0002", title="b", related_to=["F-0001"])

    result = run(SCRIPT)

    assert any(p.startswith("out of sync: F-0001 blocks F-0002") for p in problems(result))


def test_related_to_is_not_checked_for_symmetry_or_cycles(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", related_to=["F-0002"])
    write_item("F-0002-b.md", id="F-0002", title="b", related_to=["F-0001", "F-0003"])
    write_item("F-0003-c.md", id="F-0003", title="c")

    assert run(SCRIPT).returncode == 0


def test_blocking_cycle(write_item, run):
    write_item("T-0001-a.md", id="T-0001", title="a", blocks=["T-0002"], blocked_by=["T-0003"])
    write_item("T-0002-b.md", id="T-0002", title="b", blocks=["T-0003"], blocked_by=["T-0001"])
    write_item("T-0003-c.md", id="T-0003", title="c", blocks=["T-0001"], blocked_by=["T-0002"])

    result = run(SCRIPT)

    assert result.returncode == 1
    assert problems(result) == ["blocking cycle: T-0001 blocks T-0002 blocks T-0003 blocks T-0001"]


def test_supersession_cycle(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", supersedes=["F-0002"], superseded_by=["F-0002"])
    write_item("F-0002-b.md", id="F-0002", title="b", supersedes=["F-0001"], superseded_by=["F-0001"])

    result = run(SCRIPT)

    assert result.returncode == 1
    assert problems(result) == ["supersession cycle: F-0001 supersedes F-0002 supersedes F-0001"]


def test_cycle_found_from_one_sided_declarations(write_item, run):
    # Each link is declared on one side only, using both field directions.
    write_item("T-0001-a.md", id="T-0001", title="a", blocks=["T-0002"])
    write_item("T-0002-b.md", id="T-0002", title="b")
    write_item("T-0003-c.md", id="T-0003", title="c", blocked_by=["T-0002"], blocks=["T-0001"])

    result = run(SCRIPT)

    assert "blocking cycle: T-0001 blocks T-0002 blocks T-0003 blocks T-0001" in problems(result)
    assert sum(p.startswith("out of sync:") for p in problems(result)) == 3


def test_blocking_and_supersession_graphs_are_separate(write_item, run):
    # F-0001 blocks F-0002 and F-0002 supersedes F-0001: not a cycle.
    write_item("F-0001-a.md", id="F-0001", title="a", blocks=["F-0002"], superseded_by=["F-0002"])
    write_item("F-0002-b.md", id="F-0002", title="b", blocked_by=["F-0001"], supersedes=["F-0001"])

    assert run(SCRIPT).returncode == 0


def test_block_list_syntax_is_understood(write_item, run):
    write_item("F-0001-a.md", text="---\nid: F-0001\ntitle: a\nblocks:\n  - F-0002\n---\n")
    write_item("F-0002-b.md", text="---\nid: F-0002\ntitle: b\nblocked_by:\n  - F-0001   # comment\n---\n")

    assert run(SCRIPT).returncode == 0


def test_duplicate_ids_produce_a_warning(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a")
    write_item("F-0001-b.md", id="F-0001", title="b")

    result = run(SCRIPT)

    assert "warning: duplicate IDs found" in result.stderr
    assert problems(result) == []


def test_missing_items_directory(run, product):
    (product / "items").rmdir()

    result = run(SCRIPT)

    assert result.returncode == 2
    assert "items directory not found" in result.stderr
