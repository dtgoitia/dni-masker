"""check_decisions.py: links between questions and their decision records."""

SCRIPT = "check_decisions.py"


def problems(result) -> list[str]:
    return result.stderr.splitlines()


def test_consistent_links_have_no_problems(write_item, write_decision, run):
    write_item("Q-0001-a.md", id="Q-0001", title="a", type="question", status="done", decision="ADR-0001")
    write_item("Q-0002-b.md", id="Q-0002", title="b", type="question", status="clarifying")
    write_item("F-0001-c.md", id="F-0001", title="c", type="feature", status="done")
    write_decision("ADR-0001-x.md", id="ADR-0001", title="x", question="Q-0001")

    result = run(SCRIPT)

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["no decision problems found"]


def test_no_decisions_directory_is_fine(write_item, run):
    write_item("Q-0001-a.md", id="Q-0001", title="a", type="question", status="idea")

    assert run(SCRIPT).returncode == 0


# --- decision -> question -----------------------------------------------------------


def test_decision_without_question(write_decision, run):
    d = write_decision("ADR-0001-x.md", id="ADR-0001", title="x")

    result = run(SCRIPT)

    assert result.returncode == 1
    assert problems(result) == [f"missing question: ADR-0001 has no `question` field ({d})"]


def test_decision_with_unknown_question(write_decision, run):
    d = write_decision("ADR-0001-x.md", id="ADR-0001", title="x", question="Q-0009")

    result = run(SCRIPT)

    assert problems(result) == [f"unknown ID: ADR-0001 question Q-0009, which doesn't exist ({d})"]


def test_decision_pointing_to_a_non_question(write_item, write_decision, run):
    write_item("F-0001-a.md", id="F-0001", title="a", type="feature", status="ready")
    d = write_decision("PDR-0001-x.md", id="PDR-0001", title="x", question="F-0001")

    result = run(SCRIPT)

    assert problems(result) == [f"not a question: PDR-0001 question F-0001, which is a feature ({d})"]


def test_question_not_pointing_back(write_item, write_decision, run):
    q = write_item("Q-0001-a.md", id="Q-0001", title="a", type="question", status="in-progress")
    write_decision("ADR-0001-x.md", id="ADR-0001", title="x", question="Q-0001")

    result = run(SCRIPT)

    assert problems(result) == [f"out of sync: ADR-0001 question Q-0001, but Q-0001 has no `decision` ({q})"]


def test_question_pointing_to_another_decision(write_item, write_decision, run):
    q = write_item("Q-0001-a.md", id="Q-0001", title="a", type="question", status="done", decision="ADR-0002")
    write_decision("ADR-0001-x.md", id="ADR-0001", title="x", question="Q-0001")
    write_decision("ADR-0002-y.md", id="ADR-0002", title="y", question="Q-0001")

    result = run(SCRIPT)

    assert problems(result) == [f"out of sync: ADR-0001 question Q-0001, but Q-0001 has decision ADR-0002 ({q})"]


# --- question -> decision -----------------------------------------------------------


def test_question_with_unknown_decision(write_item, run):
    q = write_item("Q-0001-a.md", id="Q-0001", title="a", type="question", status="done", decision="PDR-0009")

    result = run(SCRIPT)

    assert result.returncode == 1
    assert problems(result) == [f"unknown ID: Q-0001 decision PDR-0009, which doesn't exist ({q})"]


def test_decision_not_pointing_back(write_item, write_decision, run):
    write_item("Q-0001-a.md", id="Q-0001", title="a", type="question", status="done", decision="ADR-0001")
    d = write_decision("ADR-0001-x.md", id="ADR-0001", title="x", question="Q-0002")
    write_item("Q-0002-b.md", id="Q-0002", title="b", type="question", status="done", decision="ADR-0001")

    result = run(SCRIPT)

    assert problems(result) == [f"out of sync: Q-0001 decision ADR-0001, but ADR-0001 has question Q-0002 ({d})"]


def test_decision_on_a_non_question(write_item, write_decision, run):
    a = write_item("F-0001-a.md", id="F-0001", title="a", type="feature", status="done", decision="ADR-0001")

    result = run(SCRIPT)

    assert problems(result) == [
        f"not a question: F-0001 has decision ADR-0001, but is a feature ({a})",
        f"unknown ID: F-0001 decision ADR-0001, which doesn't exist ({a})",
    ]


def test_done_question_without_decision(write_item, run):
    q = write_item("Q-0001-a.md", id="Q-0001", title="a", type="question", status="done")

    result = run(SCRIPT)

    assert problems(result) == [f"missing decision: Q-0001 is done but has no `decision` ({q})"]


def test_deprecated_question_without_decision_is_fine(write_item, run):
    write_item("Q-0001-a.md", id="Q-0001", title="a", type="question", status="deprecated")

    assert run(SCRIPT).returncode == 0


# --- location -------------------------------------------------------------------------


def test_adr_in_the_pdrs_directory_is_misplaced(write_item, write_decision, run):
    write_item("Q-0001-a.md", id="Q-0001", title="a", type="question", status="done", decision="ADR-0001")
    d = write_decision("ADR-0001-x.md", directory="pdrs", id="ADR-0001", title="x", question="Q-0001")

    result = run(SCRIPT)

    assert result.returncode == 1
    assert problems(result) == [f"misplaced: ADR-0001 is not in decisions/adrs/ ({d})"]


def test_pdr_at_the_decisions_root_is_misplaced(write_item, write_decision, run):
    write_item("Q-0001-a.md", id="Q-0001", title="a", type="question", status="done", decision="PDR-0001")
    d = write_decision("PDR-0001-x.md", directory="", id="PDR-0001", title="x", question="Q-0001")

    result = run(SCRIPT)

    assert problems(result) == [f"misplaced: PDR-0001 is not in decisions/pdrs/ ({d})"]


def test_location_follows_the_frontmatter_id(write_item, write_decision, run):
    # Named like an ADR, but its frontmatter says PDR: the frontmatter wins.
    write_item("Q-0001-a.md", id="Q-0001", title="a", type="question", status="done", decision="PDR-0001")
    d = write_decision("ADR-0001-x.md", id="PDR-0001", title="x", question="Q-0001")

    result = run(SCRIPT)

    assert problems(result) == [f"misplaced: PDR-0001 is not in decisions/pdrs/ ({d})"]


# --- misc -----------------------------------------------------------------------------


def test_problems_are_sorted_by_id(write_item, write_decision, run):
    write_decision("PDR-0001-x.md", id="PDR-0001", title="x")
    write_decision("ADR-0001-y.md", id="ADR-0001", title="y")
    write_item("Q-0001-a.md", id="Q-0001", title="a", type="question", status="done")

    result = run(SCRIPT)

    assert [p.split(": ")[1].split()[0] for p in problems(result)] == ["ADR-0001", "PDR-0001", "Q-0001"]


def test_missing_items_directory(run, product):
    (product / "items").rmdir()

    result = run(SCRIPT)

    assert result.returncode == 2
    assert "items directory not found" in result.stderr
