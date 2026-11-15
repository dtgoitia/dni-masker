"""complete_item.py: `check` an item before completing it, and `complete` it.

`complete` sets `status: done`, records `completed:` (and `decision:` for
questions), then re-derives `ready` / `ready-but-blocked` for the item's
dependents only, reporting what happened to each of them.
"""

import json
import re

import pytest

SCRIPT = "complete_item.py"
NOW = "2026-11-15T12:00:00+01:00"


def check(run, item_id: str) -> dict:
    result = run(SCRIPT, "check", item_id)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def complete(run, item_id: str, *args: str):
    return run(SCRIPT, "complete", item_id, "--now", NOW, *args)


def status_of(path) -> str:
    return next(line for line in path.read_text().splitlines() if line.startswith("status:"))


# --- check -----------------------------------------------------------------------


def test_check_reports_item_details(write_item, run):
    a = write_item("F-0001-a.md", id="F-0001", title="Export CSV", type="feature", status="in-progress")

    assert check(run, "F-0001") == {
        "id": "F-0001",
        "title": "Export CSV",
        "type": "feature",
        "status": "in-progress",
        "path": str(a),
        "open_blockers": [],
    }


def test_check_lists_open_blockers_from_both_sides(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress",
               blocked_by=["T-0001", "Q-0001"])
    write_item("T-0001-b.md", id="T-0001", title="b", status="clarifying")
    write_item("Q-0001-c.md", id="Q-0001", title="c", status="done")
    write_item("Q-0002-d.md", id="Q-0002", title="d", status="idea", blocks=["F-0001"])
    write_item("T-0002-e.md", id="T-0002", title="e", status="deprecated", blocks=["F-0001"])

    assert check(run, "F-0001")["open_blockers"] == [
        {"id": "Q-0002", "title": "d", "status": "idea"},
        {"id": "T-0001", "title": "b", "status": "clarifying"},
    ]


def test_check_unknown_id(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress")

    result = run(SCRIPT, "check", "F-0099")

    assert result.returncode == 2
    assert "F-0099 not found" in result.stderr


# --- complete: the item itself ---------------------------------------------------------


def test_complete_sets_done_and_completed_after_created(write_item, run):
    text = (
        "---\n"
        "id: F-0001\n"
        "title: a\n"
        "type: feature\n"
        "status: in-progress   # comment\n"
        "created: 2026-01-01T00:00:00+00:00\n"
        "blocks: []\n"
        "---\n"
        "\n"
        "## Notes / history\n"
    )
    a = write_item("F-0001-a.md", text=text)

    result = complete(run, "F-0001")

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0] == f"completed: F-0001 ({a})"
    assert a.read_text() == (
        text.replace("status: in-progress", "status: done")
        .replace("created: 2026-01-01T00:00:00+00:00\n", f"created: 2026-01-01T00:00:00+00:00\ncompleted: {NOW}\n")
    )


def test_complete_without_created_puts_completed_after_status(write_item, run):
    a = write_item("F-0001-a.md", text="---\nid: F-0001\nstatus: ready\ntitle: a\n---\n")

    complete(run, "F-0001")

    assert a.read_text() == f"---\nid: F-0001\nstatus: done\ncompleted: {NOW}\ntitle: a\n---\n"


def test_complete_defaults_to_the_current_time(write_item, run):
    a = write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress")

    result = run(SCRIPT, "complete", "F-0001")

    assert result.returncode == 0, result.stderr
    completed = next(line for line in a.read_text().splitlines() if line.startswith("completed:"))
    assert re.fullmatch(r"completed: \d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d", completed)


@pytest.mark.parametrize("status", ["idea", "clarifying", "ready", "ready-but-blocked", "in-progress"])
def test_any_open_status_can_be_completed(write_item, run, status):
    # Warning about unusual statuses is the skill's job, after asking the user.
    a = write_item("F-0001-a.md", id="F-0001", title="a", status=status)

    assert complete(run, "F-0001").returncode == 0
    assert status_of(a) == "status: done"


@pytest.mark.parametrize("status", ["done", "deprecated"])
def test_closed_items_are_refused(write_item, run, status):
    a = write_item("F-0001-a.md", id="F-0001", title="a", status=status)
    before = a.read_bytes()

    result = complete(run, "F-0001")

    assert result.returncode == 1
    assert f"F-0001 is already {status}" in result.stderr
    assert a.read_bytes() == before


def test_complete_unknown_id(write_item, run):
    result = complete(run, "F-0099")

    assert result.returncode == 2
    assert "F-0099 not found" in result.stderr


def test_duplicate_ids_are_refused(write_item, run):
    a = write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress")
    write_item("F-0001-b.md", id="F-0001", title="b", status="in-progress")
    before = a.read_bytes()

    result = complete(run, "F-0001")

    assert result.returncode == 2
    assert "F-0001 is used by more than one file" in result.stderr
    assert a.read_bytes() == before


def test_missing_items_directory(run, product):
    (product / "items").rmdir()

    result = complete(run, "F-0001")

    assert result.returncode == 2
    assert "items directory not found" in result.stderr


# --- complete: dependents -------------------------------------------------------------


def test_dependent_whose_last_blocker_is_completed_becomes_ready(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress", blocks=["F-0002"])
    b = write_item("F-0002-b.md", id="F-0002", title="b", status="ready-but-blocked", blocked_by=["F-0001"])

    result = complete(run, "F-0001")

    assert status_of(b) == "status: ready"
    assert result.stdout.splitlines()[1:] == [f"now ready: F-0002 ({b})"]


def test_dependent_declared_only_with_blocks_is_found(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress", blocks=["F-0002"])
    b = write_item("F-0002-b.md", id="F-0002", title="b", status="ready-but-blocked")

    complete(run, "F-0001")

    assert status_of(b) == "status: ready"


def test_dependent_declared_only_with_blocked_by_is_found(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress")
    b = write_item("F-0002-b.md", id="F-0002", title="b", status="ready-but-blocked", blocked_by=["F-0001"])

    complete(run, "F-0001")

    assert status_of(b) == "status: ready"


def test_dependent_with_other_open_blockers_stays_blocked(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress")
    write_item("T-0001-b.md", id="T-0001", title="b", status="clarifying")
    write_item("Q-0001-c.md", id="Q-0001", title="c", status="ready")
    d = write_item("F-0002-d.md", id="F-0002", title="d", status="ready-but-blocked",
                   blocked_by=["F-0001", "T-0001", "Q-0001"])
    before = d.read_bytes()

    result = complete(run, "F-0001")

    assert d.read_bytes() == before
    assert result.stdout.splitlines()[1:] == [f"still blocked: F-0002 by Q-0001, T-0001 ({d})"]


def test_unblocked_dependent_in_another_status_is_only_reported(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress", blocks=["F-0002"])
    b = write_item("F-0002-b.md", id="F-0002", title="b", status="clarifying", blocked_by=["F-0001"])
    before = b.read_bytes()

    result = complete(run, "F-0001")

    assert b.read_bytes() == before
    assert result.stdout.splitlines()[1:] == [f"no longer blocked: F-0002 (status: clarifying) ({b})"]


def test_closed_dependents_are_not_reported(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress", blocks=["F-0002"])
    write_item("F-0002-b.md", id="F-0002", title="b", status="deprecated", blocked_by=["F-0001"])

    result = complete(run, "F-0001")

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0].startswith("completed: F-0001")
    assert result.stdout.splitlines()[1:] == []


def test_dependents_are_reported_sorted_by_id(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress", blocks=["T-0001", "F-0002"])
    write_item("T-0001-b.md", id="T-0001", title="b", status="ready-but-blocked")
    write_item("F-0002-c.md", id="F-0002", title="c", status="ready-but-blocked")

    result = complete(run, "F-0001")

    assert [line.split(": ")[1].split()[0] for line in result.stdout.splitlines()[1:]] == ["F-0002", "T-0001"]


def test_unrelated_items_are_never_touched(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress")
    # Stale status, but not a dependent of F-0001: /pm-lint's job, not ours.
    stale = write_item("F-0002-b.md", id="F-0002", title="b", status="ready-but-blocked")
    before = stale.read_bytes()

    result = complete(run, "F-0001")

    assert result.returncode == 0, result.stderr
    assert stale.read_bytes() == before


def test_items_blocked_by_the_dependent_are_not_reported(write_item, run):
    # Only direct dependents: F-0003 depends on F-0002, not on F-0001.
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress", blocks=["F-0002"])
    write_item("F-0002-b.md", id="F-0002", title="b", status="ready-but-blocked", blocks=["F-0003"])
    write_item("F-0003-c.md", id="F-0003", title="c", status="ready-but-blocked")

    result = complete(run, "F-0001")

    assert [line.split(": ")[1].split()[0] for line in result.stdout.splitlines()[1:]] == ["F-0002"]


# --- complete: questions and decisions ------------------------------------------------


def test_question_requires_a_decision(write_item, run):
    q = write_item("Q-0001-a.md", id="Q-0001", title="a", type="question", status="in-progress")
    before = q.read_bytes()

    result = complete(run, "Q-0001")

    assert result.returncode == 1
    assert "Q-0001 is a question: pass --decision" in result.stderr
    assert q.read_bytes() == before


@pytest.mark.parametrize("decision", ["PDR-0001", "ADR-0001"])
def test_question_is_completed_with_its_decision(write_item, write_decision, run, decision):
    q = write_item("Q-0001-a.md", text=(
        "---\nid: Q-0001\ntitle: a\ntype: question\nstatus: in-progress\n"
        "created: 2026-01-01T00:00:00+00:00\n---\n"
    ))
    write_decision(f"{decision}-x.md", id=decision, title="x", question="Q-0001")

    result = complete(run, "Q-0001", "--decision", decision)

    assert result.returncode == 0, result.stderr
    assert q.read_text() == (
        "---\nid: Q-0001\ntitle: a\ntype: question\nstatus: done\n"
        f"created: 2026-01-01T00:00:00+00:00\ncompleted: {NOW}\ndecision: {decision}\n---\n"
    )


def test_decision_file_must_exist(write_item, run):
    q = write_item("Q-0001-a.md", id="Q-0001", title="a", type="question", status="in-progress")
    before = q.read_bytes()

    result = complete(run, "Q-0001", "--decision", "ADR-0001")

    assert result.returncode == 1
    assert "decision ADR-0001 not found" in result.stderr
    assert q.read_bytes() == before


def test_decision_must_point_back_to_the_question(write_item, write_decision, run):
    q = write_item("Q-0001-a.md", id="Q-0001", title="a", type="question", status="in-progress")
    write_decision("ADR-0001-x.md", id="ADR-0001", title="x", question="Q-0002")
    before = q.read_bytes()

    result = complete(run, "Q-0001", "--decision", "ADR-0001")

    assert result.returncode == 1
    assert "ADR-0001 has `question: Q-0002`, expected Q-0001" in result.stderr
    assert q.read_bytes() == before


@pytest.mark.parametrize("decision", ["ADR-1", "XDR-0001", "Q-0001"])
def test_decision_id_must_be_well_formed(write_item, run, decision):
    write_item("Q-0001-a.md", id="Q-0001", title="a", type="question", status="in-progress")

    result = complete(run, "Q-0001", "--decision", decision)

    assert result.returncode == 1
    assert f"invalid decision ID: {decision}" in result.stderr


def test_decision_is_only_for_questions(write_item, write_decision, run):
    a = write_item("F-0001-a.md", id="F-0001", title="a", type="feature", status="in-progress")
    write_decision("ADR-0001-x.md", id="ADR-0001", title="x", question="F-0001")
    before = a.read_bytes()

    result = complete(run, "F-0001", "--decision", "ADR-0001")

    assert result.returncode == 1
    assert "--decision is only for questions" in result.stderr
    assert a.read_bytes() == before
