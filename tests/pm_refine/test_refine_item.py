"""refine_item.py: check an item against the ready gate and move it along.

  check <ID>   JSON report: sections and what's missing to be ready
  start <ID>   idea -> clarifying (clarifying stays)
  ready <ID>   clarifying/idea -> ready or ready-but-blocked, only if the
               gate passes: Problem and Proposed behaviour filled in, at least
               one acceptance criterion, no open questions

Only `idea` and `clarifying` items can be refined. The user's approval is
the skill's job; the script enforces the rest.
"""

import json

import pytest
from pm_items import parse_frontmatter

SCRIPT = "refine_item.py"

COMPLETE = {
    "problem": "Users can't get their data out.",
    "behaviour": "An *Export* button downloads the report as CSV.",
    "criteria": "- [ ] the CSV has one row per report line\n- [ ] the header row names every column",
    "questions": "<!-- what keeps this item at \"clarifying\" -->",
}


def body(problem="", behaviour="", criteria="", questions="", behaviour_heading="Proposed behaviour"):
    return (
        f"## Problem\n\n{problem}\n\n"
        f"## {behaviour_heading}\n\n{behaviour}\n\n"
        f"## Acceptance criteria\n\n{criteria}\n\n"
        f"## Open questions\n\n{questions}\n\n"
        "## Notes / history\n"
    )


def write(write_item, item_id="F-0001", status="clarifying", extra="", **sections):
    text = (f"---\nid: {item_id}\ntitle: Export CSV\ntype: feature\nstatus: {status}\n{extra}---\n\n"
            + body(**sections))
    return write_item(f"{item_id}-export-csv.md", text=text)


def check(run, item_id="F-0001") -> dict:
    result = run(SCRIPT, "check", item_id)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def status_of(path) -> str:
    return parse_frontmatter(path.read_text())["status"]


# --- check ----------------------------------------------------------------------------


def test_check_complete_item(write_item, run):
    a = write(write_item, **COMPLETE)

    assert check(run) == {
        "id": "F-0001",
        "title": "Export CSV",
        "type": "feature",
        "status": "clarifying",
        "path": str(a),
        "acceptance_criteria": 2,
        "open_questions": 0,
        "missing": [],
    }


def test_check_empty_template(write_item, run):
    write(write_item, status="idea", questions=COMPLETE["questions"])

    assert check(run)["missing"] == [
        "`## Problem` is empty",
        "`## Proposed behaviour` is empty",
        "`## Acceptance criteria` has no list items",
    ]


def test_html_comments_and_whitespace_do_not_count(write_item, run):
    write(write_item, **{**COMPLETE, "problem": "<!-- TODO -->\n\n   \n"})

    assert check(run)["missing"] == ["`## Problem` is empty"]


def test_missing_sections_count_as_empty(write_item, run):
    write_item("F-0001-a.md", text="---\nid: F-0001\ntitle: a\ntype: feature\nstatus: idea\n---\n\nfree text\n")

    assert check(run)["missing"] == [
        "`## Problem` is empty",
        "`## Proposed behaviour` is empty",
        "`## Acceptance criteria` has no list items",
    ]


def test_american_spelling_and_heading_case_are_accepted(write_item, run):
    write(write_item, **COMPLETE, behaviour_heading="proposed behavior")

    assert check(run)["missing"] == []


def test_acceptance_criteria_need_list_items(write_item, run):
    write(write_item, **{**COMPLETE, "criteria": "It works well."})

    result = check(run)

    assert result["acceptance_criteria"] == 0
    assert result["missing"] == ["`## Acceptance criteria` has no list items"]


@pytest.mark.parametrize("criteria", ["- a\n- b", "* a\n* b", "1. a\n2. b", "- [ ] a\n- [x] b", "- a\n  - nested\n- b"])
def test_acceptance_criteria_list_syntaxes(write_item, run, criteria):
    write(write_item, **{**COMPLETE, "criteria": criteria})

    assert check(run)["acceptance_criteria"] == 2


@pytest.mark.parametrize(("questions", "count"), [("- sync or async?\n- which formats?", 2), ("Sync or async?", 1)])
def test_open_questions_block_ready(write_item, run, questions, count):
    write(write_item, **{**COMPLETE, "questions": questions})

    result = check(run)

    assert result["open_questions"] == count
    assert result["missing"] == [f"`## Open questions` lists {count} open question(s)"]


@pytest.mark.parametrize("status", ["ready", "ready-but-blocked", "in-progress", "done", "deprecated"])
def test_check_reports_items_that_cannot_be_refined(write_item, run, status):
    write(write_item, status=status, **COMPLETE)

    assert check(run)["missing"] == [f"status is `{status}`: only `idea` and `clarifying` items can be refined"]


def test_check_unknown_id(write_item, run):
    result = run(SCRIPT, "check", "F-0099")

    assert result.returncode == 2
    assert "F-0099 not found" in result.stderr


# --- start ----------------------------------------------------------------------------


def test_start_moves_idea_to_clarifying(write_item, run):
    a = write(write_item, status="idea")
    text = a.read_text()

    result = run(SCRIPT, "start", "F-0001")

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [f"status: F-0001 idea -> clarifying ({a})"]
    assert a.read_text() == text.replace("status: idea", "status: clarifying", 1)


def test_start_keeps_clarifying(write_item, run):
    a = write(write_item, status="clarifying")
    before = a.read_bytes()

    result = run(SCRIPT, "start", "F-0001")

    assert result.returncode == 0
    assert result.stdout.splitlines() == [f"unchanged: F-0001 is already clarifying ({a})"]
    assert a.read_bytes() == before


@pytest.mark.parametrize("status", ["ready", "ready-but-blocked", "in-progress", "done", "deprecated"])
def test_start_refuses_other_statuses(write_item, run, status):
    a = write(write_item, status=status)
    before = a.read_bytes()

    result = run(SCRIPT, "start", "F-0001")

    assert result.returncode == 1
    assert f"F-0001 is {status}: only `idea` and `clarifying` items can be refined" in result.stderr
    assert a.read_bytes() == before


# --- ready -----------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["idea", "clarifying"])
def test_ready_when_the_gate_passes(write_item, run, status):
    a = write(write_item, status=status, **COMPLETE)
    text = a.read_text()

    result = run(SCRIPT, "ready", "F-0001")

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [f"status: F-0001 {status} -> ready ({a})"]
    assert a.read_text() == text.replace(f"status: {status}", "status: ready", 1)


def test_ready_but_blocked_when_a_blocker_is_open(write_item, run):
    a = write(write_item, extra="blocked_by: [Q-0001]\n", **COMPLETE)
    write_item("Q-0001-q.md", id="Q-0001", title="q", type="question", status="clarifying")
    write_item("T-0001-t.md", id="T-0001", title="t", type="technical", status="in-progress", blocks=["F-0001"])

    result = run(SCRIPT, "ready", "F-0001")

    assert result.returncode == 0, result.stderr
    assert status_of(a) == "ready-but-blocked"
    assert result.stdout.splitlines() == [f"status: F-0001 clarifying -> ready-but-blocked, by Q-0001, T-0001 ({a})"]


def test_ready_with_closed_blockers(write_item, run):
    a = write(write_item, extra="blocked_by: [Q-0001]\n", **COMPLETE)
    write_item("Q-0001-q.md", id="Q-0001", title="q", type="question", status="done")

    run(SCRIPT, "ready", "F-0001")

    assert status_of(a) == "ready"


def test_ready_refused_when_the_gate_fails(write_item, run):
    a = write(write_item, **{**COMPLETE, "criteria": "", "questions": "- sync or async?"})
    before = a.read_bytes()

    result = run(SCRIPT, "ready", "F-0001")

    assert result.returncode == 1
    assert result.stderr.splitlines() == [
        "error: F-0001 isn't ready:",
        "  - `## Acceptance criteria` has no list items",
        "  - `## Open questions` lists 1 open question(s)",
    ]
    assert a.read_bytes() == before


@pytest.mark.parametrize("status", ["ready", "ready-but-blocked", "in-progress", "done", "deprecated"])
def test_ready_refuses_other_statuses(write_item, run, status):
    a = write(write_item, status=status, **COMPLETE)
    before = a.read_bytes()

    result = run(SCRIPT, "ready", "F-0001")

    assert result.returncode == 1
    assert f"status is `{status}`: only `idea` and `clarifying` items can be refined" in result.stderr
    assert a.read_bytes() == before


def test_missing_items_directory(run, product):
    (product / "items").rmdir()

    result = run(SCRIPT, "check", "F-0001")

    assert result.returncode == 2
    assert "items directory not found" in result.stderr
