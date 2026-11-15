"""corpus.py: print every product file in one deterministic read.

Output: an index (one tab-separated line per file: ID, kind, status, title,
path), then each file's full content under a `===== <path> =====` header.
Order: vision.md, decisions by ID, items by ID, then any file without an ID
by path.
"""

SCRIPT = "corpus.py"


def sections(stdout: str) -> list[str]:
    return [line for line in stdout.splitlines() if line.startswith("===== ")]


def index(stdout: str) -> list[list[str]]:
    head = stdout.split("\n# Files\n", 1)[0]
    return [line.split("\t") for line in head.splitlines()[2:] if line]


def test_full_output(write_item, write_decision, run, product):
    vision = product / "vision.md"
    vision.write_text("# Vision\n\nBe fast.\n")
    item = write_item("F-0001-a.md", id="F-0001", title="Export CSV", type="feature", status="ready")
    decision = write_decision("ADR-0001-x.md", id="ADR-0001", title="Use Postgres", question="Q-0001")

    result = run(SCRIPT)

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "# Index\n"
        "\n"
        f"vision\tvision\t-\t-\t{vision}\n"
        f"ADR-0001\tdecision\t-\tUse Postgres\t{decision}\n"
        f"F-0001\tfeature\tready\tExport CSV\t{item}\n"
        "\n"
        "# Files\n"
        "\n"
        f"===== {vision} =====\n"
        f"{vision.read_text()}"
        "\n"
        f"===== {decision} =====\n"
        f"{decision.read_text()}"
        "\n"
        f"===== {item} =====\n"
        f"{item.read_text()}"
    )


def test_order_is_vision_then_decisions_then_items_by_id(write_item, write_decision, run, product):
    (product / "vision.md").write_text("v\n")
    write_item("T-0001-a.md", id="T-0001", title="a", type="technical", status="idea")
    write_item("F-0002-b.md", id="F-0002", title="b", type="feature", status="done")
    write_item("Q-0001-c.md", id="Q-0001", title="c", type="question", status="clarifying")
    write_decision("PDR-0001-x.md", id="PDR-0001", title="x")
    write_decision("ADR-0002-y.md", id="ADR-0002", title="y")

    result = run(SCRIPT)

    assert [row[0] for row in index(result.stdout)] == ["vision", "ADR-0002", "PDR-0001", "F-0002", "Q-0001", "T-0001"]
    assert [s.split("/")[-1].rstrip(" =") for s in sections(result.stdout)] == [
        "vision.md", "ADR-0002-y.md", "PDR-0001-x.md", "F-0002-b.md", "Q-0001-c.md", "T-0001-a.md",
    ]


def test_items_of_every_status_are_included(write_item, run):
    statuses = ["idea", "clarifying", "ready", "ready-but-blocked", "in-progress", "done", "deprecated"]
    for n, status in enumerate(statuses, start=1):
        write_item(f"F-000{n}-x.md", id=f"F-000{n}", title="x", type="feature", status=status)

    assert [row[2] for row in index(run(SCRIPT).stdout)] == statuses


def test_files_without_an_id_come_last_by_path(write_item, run, product):
    write_item("notes.md", text="just notes\n")
    write_item("F-0001-a.md", id="F-0001", title="a", type="feature", status="idea")
    write_item("draft.md", text="---\ntitle: draft\n---\n")

    rows = index(run(SCRIPT).stdout)

    assert rows == [
        ["F-0001", "feature", "idea", "a", str(product / "items" / "F-0001-a.md")],
        ["-", "-", "-", "draft", str(product / "items" / "draft.md")],
        ["-", "-", "-", "-", str(product / "items" / "notes.md")],
    ]


def test_tabs_in_titles_do_not_break_the_index(write_item, run):
    write_item("F-0001-a.md", text='---\nid: F-0001\ntitle: "a\tb"\ntype: feature\nstatus: idea\n---\n')

    assert index(run(SCRIPT).stdout)[0][3] == "a b"


def test_file_without_trailing_newline_does_not_merge_with_next_header(write_item, run, product):
    write_item("F-0001-a.md", text="---\nid: F-0001\ntitle: a\n---\nno newline at end")
    b = write_item("F-0002-b.md", id="F-0002", title="b")

    assert f"no newline at end\n\n===== {b} =====\n" in run(SCRIPT).stdout


def test_missing_vision_and_decisions_are_fine(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", type="feature", status="idea")

    result = run(SCRIPT)

    assert result.returncode == 0, result.stderr
    assert [row[0] for row in index(result.stdout)] == ["F-0001"]


def test_empty_product(run):
    result = run(SCRIPT)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "# Index\n\n(no product files)\n"


def test_missing_items_directory(run, product):
    (product / "items").rmdir()

    result = run(SCRIPT)

    assert result.returncode == 2
    assert "items directory not found" in result.stderr
