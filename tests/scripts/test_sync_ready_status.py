"""sync_ready_status.py: switch items between `ready` and `ready-but-blocked`.

An item is `ready-but-blocked` while at least one of its blockers is neither
`done` nor `deprecated`. A blocker is declared either on the blocked item
(`blocked_by`) or on the blocker itself (`blocks`).
"""

import pytest

SCRIPT = "sync_ready_status.py"
OPEN = ["idea", "clarifying", "ready", "ready-but-blocked", "in-progress"]
CLOSED = ["done", "deprecated"]


def status_of(path) -> str:
    return next(line for line in path.read_text().splitlines() if line.startswith("status:"))


# --- ready -> ready-but-blocked ------------------------------------------------


@pytest.mark.parametrize("blocker_status", OPEN)
def test_ready_with_open_blocker_becomes_blocked(write_item, run, blocker_status):
    if blocker_status == "ready-but-blocked":
        # Give F-0001 an open blocker of its own, so its status is consistent.
        write_item("Q-0001-z.md", id="Q-0001", title="z", status="idea", blocks=["F-0001"])
    write_item("F-0001-a.md", id="F-0001", title="a", status=blocker_status, blocks=["F-0002"])
    b = write_item("F-0002-b.md", id="F-0002", title="b", status="ready", blocked_by=["F-0001"])

    result = run(SCRIPT)

    assert result.returncode == 0, result.stderr
    assert status_of(b) == "status: ready-but-blocked"
    assert result.stdout.splitlines() == [f"updated: F-0002 ready -> ready-but-blocked ({b})"]


def test_blocker_declared_only_with_blocks(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress", blocks=["F-0002"])
    b = write_item("F-0002-b.md", id="F-0002", title="b", status="ready")

    run(SCRIPT)

    assert status_of(b) == "status: ready-but-blocked"


def test_blocker_declared_only_with_blocked_by(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress")
    b = write_item("F-0002-b.md", id="F-0002", title="b", status="ready", blocked_by=["F-0001"])

    run(SCRIPT)

    assert status_of(b) == "status: ready-but-blocked"


def test_one_open_blocker_among_closed_ones_still_blocks(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="done")
    write_item("F-0002-b.md", id="F-0002", title="b", status="deprecated")
    write_item("T-0001-c.md", id="T-0001", title="c", status="clarifying")
    d = write_item("F-0003-d.md", id="F-0003", title="d", status="ready",
                   blocked_by=["F-0001", "F-0002", "T-0001"])

    run(SCRIPT)

    assert status_of(d) == "status: ready-but-blocked"


# --- ready-but-blocked -> ready ------------------------------------------------


@pytest.mark.parametrize("blocker_status", CLOSED)
def test_blocked_with_closed_blockers_becomes_ready(write_item, run, blocker_status):
    write_item("F-0001-a.md", id="F-0001", title="a", status=blocker_status, blocks=["F-0002"])
    b = write_item("F-0002-b.md", id="F-0002", title="b", status="ready-but-blocked", blocked_by=["F-0001"])

    result = run(SCRIPT)

    assert result.returncode == 0, result.stderr
    assert status_of(b) == "status: ready"
    assert result.stdout.splitlines() == [f"updated: F-0002 ready-but-blocked -> ready ({b})"]


def test_blocked_without_any_blockers_becomes_ready(write_item, run):
    b = write_item("F-0002-b.md", id="F-0002", title="b", status="ready-but-blocked", blocked_by=[])

    run(SCRIPT)

    assert status_of(b) == "status: ready"


# --- no change ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "blocker_status"),
    [("ready", "done"), ("ready", "deprecated"), ("ready-but-blocked", "in-progress")],
)
def test_correct_status_is_left_untouched(write_item, run, status, blocker_status):
    write_item("F-0001-a.md", id="F-0001", title="a", status=blocker_status, blocks=["F-0002"])
    b = write_item("F-0002-b.md", id="F-0002", title="b", status=status, blocked_by=["F-0001"])
    before = b.read_bytes()

    result = run(SCRIPT)

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["all ready statuses are up to date"]
    assert b.read_bytes() == before


def test_ready_without_blockers_is_left_untouched(write_item, run):
    a = write_item("F-0001-a.md", id="F-0001", title="a", status="ready")
    before = a.read_bytes()

    result = run(SCRIPT)

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["all ready statuses are up to date"]
    assert a.read_bytes() == before


@pytest.mark.parametrize("status", ["idea", "clarifying", "in-progress", "done", "deprecated"])
def test_other_statuses_are_never_changed(write_item, run, status):
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress", blocks=["F-0002"])
    b = write_item("F-0002-b.md", id="F-0002", title="b", status=status, blocked_by=["F-0001"])
    before = b.read_bytes()

    result = run(SCRIPT)

    assert result.returncode == 0
    assert b.read_bytes() == before


def test_items_without_status_are_ignored(write_item, run):
    a = write_item("F-0001-a.md", id="F-0001", title="a", blocked_by=["F-0002"])
    write_item("F-0002-b.md", id="F-0002", title="b", status="in-progress")
    before = a.read_bytes()

    assert run(SCRIPT).returncode == 0
    assert a.read_bytes() == before


# --- determinism / file editing -------------------------------------------------


def test_only_the_status_value_changes(write_item, run):
    text = (
        "---\n"
        "id: F-0002\n"
        "title: b\n"
        "type: feature\n"
        'status: "ready"   # idea | clarifying | ready | ready-but-blocked | ...\n'
        "blocked_by:\n"
        "  - F-0001\n"
        "---\n"
        "\n"
        "## Notes / history\n"
        "\n"
        "status: ready\n"  # body text that looks like frontmatter must not change
    )
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress")
    b = write_item("F-0002-b.md", text=text)

    run(SCRIPT)

    assert b.read_text() == text.replace('status: "ready"', 'status: "ready-but-blocked"', 1)


def test_second_run_changes_nothing(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress", blocks=["F-0002"])
    write_item("F-0002-b.md", id="F-0002", title="b", status="ready", blocked_by=["F-0001"])
    write_item("F-0003-c.md", id="F-0003", title="c", status="ready-but-blocked")

    first = run(SCRIPT)
    second = run(SCRIPT)

    assert len(first.stdout.splitlines()) == 2
    assert second.stdout.splitlines() == ["all ready statuses are up to date"]


def test_output_is_sorted_by_id(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress", blocks=["T-0001", "F-0002"])
    write_item("T-0001-c.md", id="T-0001", title="c", status="ready")
    write_item("F-0002-b.md", id="F-0002", title="b", status="ready")

    result = run(SCRIPT)

    assert [line.split()[1] for line in result.stdout.splitlines()] == ["F-0002", "T-0001"]


def test_chain_only_unblocks_items_whose_blockers_are_closed(write_item, run):
    # A (done) blocks B (ready-but-blocked) blocks C (ready-but-blocked).
    # B becomes ready, but `ready` is still open, so C stays blocked.
    write_item("F-0001-a.md", id="F-0001", title="a", status="done", blocks=["F-0002"])
    b = write_item("F-0002-b.md", id="F-0002", title="b", status="ready-but-blocked",
                   blocked_by=["F-0001"], blocks=["F-0003"])
    c = write_item("F-0003-c.md", id="F-0003", title="c", status="ready-but-blocked", blocked_by=["F-0002"])

    run(SCRIPT)

    assert status_of(b) == "status: ready"
    assert status_of(c) == "status: ready-but-blocked"


def test_block_list_syntax_is_understood(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress")
    b = write_item("F-0002-b.md", text="---\nid: F-0002\nstatus: ready\nblocked_by:\n  - F-0001\n---\n")

    run(SCRIPT)

    assert status_of(b) == "status: ready-but-blocked"


# --- options / errors -------------------------------------------------------------


def test_dry_run_reports_without_writing(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="in-progress", blocks=["F-0002"])
    b = write_item("F-0002-b.md", id="F-0002", title="b", status="ready", blocked_by=["F-0001"])
    before = b.read_bytes()

    result = run(SCRIPT, "--dry-run")

    assert result.returncode == 0
    assert result.stdout.splitlines() == [f"would update: F-0002 ready -> ready-but-blocked ({b})"]
    assert b.read_bytes() == before


def test_missing_items_directory(run, product):
    (product / "items").rmdir()

    result = run(SCRIPT)

    assert result.returncode == 2
    assert "items directory not found" in result.stderr
