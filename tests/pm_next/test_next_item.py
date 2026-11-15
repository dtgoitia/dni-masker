"""next_item.py: pick the next unblocked ready item and claim it.

Candidates are features and technical items whose status is `ready` (or a
stale `ready-but-blocked`) and whose blockers are all done or deprecated.
The one that unblocks the most open work (transitively) wins; ties go to the
oldest `created`, then the lowest ID. The pick is claimed by setting
`status: in-progress`.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = "next_item.py"
SCRIPT_PATH = Path(__file__).resolve().parents[2] / "skills" / "pm-next" / "scripts" / SCRIPT


def pick(run, *args) -> dict:
    result = run(SCRIPT, *args)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def picked_id(run, *args) -> str | None:
    picked = pick(run, *args)["picked"]
    return picked and picked["id"]


def status_of(path) -> str:
    return next(line for line in path.read_text().splitlines() if line.startswith("status:"))


def feature(write_item, item_id, status="ready", **fields):
    return write_item(f"{item_id}-x.md", id=item_id, title=f"title {item_id}",
                      type="technical" if item_id.startswith("T") else "feature", status=status, **fields)


# --- picking and claiming --------------------------------------------------------


def test_picks_and_claims_the_only_candidate(write_item, run):
    text = (
        "---\nid: F-0001\ntitle: Export CSV\ntype: feature\nstatus: ready   # comment\n"
        "created: 2026-01-01T00:00:00+00:00\n---\n\n## Problem\n\nstatus: ready\n"
    )
    a = write_item("F-0001-export-csv.md", text=text)

    result = pick(run)

    assert result["picked"] == {
        "id": "F-0001",
        "title": "Export CSV",
        "type": "feature",
        "path": str(a),
        "unblocks": [],
        "context": [],
    }
    assert a.read_text() == text.replace("status: ready   #", "status: in-progress   #", 1)


def test_nothing_to_pick(write_item, run):
    a = feature(write_item, "F-0001", status="in-progress")
    before = a.read_bytes()

    result = pick(run)

    assert result == {"picked": None, "waiting": [], "ready_questions": []}
    assert a.read_bytes() == before


def test_a_claimed_item_is_not_picked_again(write_item, run):
    feature(write_item, "F-0001")

    assert picked_id(run) == "F-0001"
    assert picked_id(run) is None


@pytest.mark.parametrize("status", ["idea", "clarifying", "in-progress", "done", "deprecated"])
def test_only_ready_items_are_candidates(write_item, run, status):
    feature(write_item, "F-0001", status=status)

    assert picked_id(run) is None


def test_technical_items_are_candidates(write_item, run):
    feature(write_item, "T-0001")

    assert picked_id(run) == "T-0001"


def test_dry_run_does_not_claim(write_item, run):
    a = feature(write_item, "F-0001")
    before = a.read_bytes()

    assert picked_id(run, "--dry-run") == "F-0001"
    assert a.read_bytes() == before


# --- blockers --------------------------------------------------------------------------


def test_ready_item_with_open_blocker_is_skipped_and_waiting(write_item, run):
    # Stale `ready`: its blocker isn't done, so it must not be picked.
    a = feature(write_item, "F-0001", blocked_by=["Q-0001"])
    write_item("Q-0001-q.md", id="Q-0001", title="Sync or async?", type="question", status="clarifying")
    before = a.read_bytes()

    result = pick(run)

    assert result["picked"] is None
    assert result["waiting"] == [{
        "id": "F-0001",
        "title": "title F-0001",
        "status": "ready",
        "open_blockers": [{"id": "Q-0001", "title": "Sync or async?", "type": "question", "status": "clarifying"}],
    }]
    assert a.read_bytes() == before


def test_blocker_declared_with_blocks_counts(write_item, run):
    feature(write_item, "F-0001")
    feature(write_item, "F-0002", status="in-progress", blocks=["F-0001"])

    assert picked_id(run) is None


def test_stale_blocked_item_with_closed_blockers_is_a_candidate(write_item, run):
    feature(write_item, "F-0001", status="ready-but-blocked", blocked_by=["F-0002", "F-0003"])
    feature(write_item, "F-0002", status="done")
    feature(write_item, "F-0003", status="deprecated")

    assert picked_id(run) == "F-0001"


def test_waiting_lists_only_ready_features_and_technical_items(write_item, run):
    feature(write_item, "F-0001", status="ready-but-blocked", blocked_by=["F-0009"])
    feature(write_item, "F-0002", status="clarifying", blocked_by=["F-0009"])
    feature(write_item, "T-0001", status="ready-but-blocked", blocked_by=["F-0009"])
    feature(write_item, "F-0009", status="in-progress")

    assert [w["id"] for w in pick(run)["waiting"]] == ["F-0001", "T-0001"]


# --- questions ---------------------------------------------------------------------------


def test_questions_are_never_picked_but_reported(write_item, run):
    q = write_item("Q-0001-q.md", id="Q-0001", title="Sync or async?", type="question", status="ready")
    before = q.read_bytes()

    result = pick(run)

    assert result["picked"] is None
    assert result["ready_questions"] == [{"id": "Q-0001", "title": "Sync or async?", "path": str(q)}]
    assert q.read_bytes() == before


def test_blocked_questions_are_not_reported_as_ready(write_item, run):
    write_item("Q-0001-q.md", id="Q-0001", title="q", type="question", status="ready-but-blocked",
               blocked_by=["F-0001"])
    feature(write_item, "F-0001", status="in-progress")

    assert pick(run)["ready_questions"] == []


# --- ordering -------------------------------------------------------------------------------


def test_most_unblocking_item_wins(write_item, run):
    feature(write_item, "F-0001")
    feature(write_item, "F-0002", blocks=["F-0003", "F-0004"])
    feature(write_item, "F-0003", status="ready-but-blocked")
    feature(write_item, "F-0004", status="clarifying")

    result = pick(run)

    assert result["picked"]["id"] == "F-0002"
    assert result["picked"]["unblocks"] == ["F-0003", "F-0004"]


def test_unblocked_work_is_counted_transitively(write_item, run):
    # F-0001 blocks 2 items directly; F-0002 blocks 1, which blocks 2 more.
    feature(write_item, "F-0001", blocks=["F-0011", "F-0012"])
    feature(write_item, "F-0011", status="idea")
    feature(write_item, "F-0012", status="idea")
    feature(write_item, "F-0002", blocks=["F-0021"])
    feature(write_item, "F-0021", status="ready-but-blocked", blocks=["F-0022", "F-0023"])
    feature(write_item, "F-0022", status="idea")
    feature(write_item, "F-0023", status="idea")

    result = pick(run)

    assert result["picked"]["id"] == "F-0002"
    assert result["picked"]["unblocks"] == ["F-0021", "F-0022", "F-0023"]


def test_closed_dependents_do_not_count(write_item, run):
    feature(write_item, "F-0001", blocks=["F-0011", "F-0012"])
    feature(write_item, "F-0011", status="done")
    feature(write_item, "F-0012", status="deprecated")
    feature(write_item, "F-0002", blocks=["F-0021"])
    feature(write_item, "F-0021", status="idea")

    assert picked_id(run) == "F-0002"


def test_dependency_cycles_do_not_loop_forever(write_item, run):
    feature(write_item, "F-0001", blocks=["F-0002"])
    feature(write_item, "F-0002", status="idea", blocks=["F-0003"])
    feature(write_item, "F-0003", status="idea", blocks=["F-0002"])

    result = pick(run)

    assert result["picked"]["unblocks"] == ["F-0002", "F-0003"]


def test_ties_go_to_the_oldest_created(write_item, run):
    feature(write_item, "F-0001", created="2026-03-01T00:00:00+00:00")
    feature(write_item, "F-0002", created="2026-02-01T00:00:00+00:00")

    assert picked_id(run) == "F-0002"


def test_created_timestamps_compare_across_time_zones(write_item, run):
    # 10:00+02:00 is 08:00 UTC, earlier than 09:00+00:00.
    feature(write_item, "F-0001", created="2026-03-01T09:00:00+00:00")
    feature(write_item, "F-0002", created="2026-03-01T10:00:00+02:00")

    assert picked_id(run) == "F-0002"


def test_items_without_created_come_after_dated_ones(write_item, run):
    feature(write_item, "F-0001")
    feature(write_item, "F-0002", created="2026-03-01T00:00:00+00:00")

    assert picked_id(run) == "F-0002"


def test_remaining_ties_go_to_the_lowest_id(write_item, run):
    feature(write_item, "T-0001")
    feature(write_item, "F-0002")

    assert picked_id(run) == "F-0002"


# --- context ------------------------------------------------------------------------------------


def test_context_lists_related_items_and_their_decisions(write_item, write_decision, run, product):
    feature(write_item, "F-0001", related_to=["F-0005"], blocked_by=["Q-0001"], supersedes=["F-0006"])
    q = write_item("Q-0001-q.md", id="Q-0001", title="q", type="question", status="done", decision="ADR-0001")
    d = write_decision("ADR-0001-x.md", id="ADR-0001", title="x", question="Q-0001")
    related = feature(write_item, "F-0005", status="idea")
    superseded = feature(write_item, "F-0006", status="deprecated")
    blocker = feature(write_item, "F-0007", status="done", blocks=["F-0001"])
    dependent = feature(write_item, "F-0008", status="idea", blocked_by=["F-0001"])
    feature(write_item, "F-0009", status="idea")  # unrelated

    context = pick(run)["picked"]["context"]

    assert context == sorted(str(p) for p in [q, d, related, superseded, blocker, dependent])


# --- concurrency / errors --------------------------------------------------------------------------


def test_concurrent_runs_never_claim_the_same_item(write_item, product):
    for n in range(1, 4):
        feature(write_item, f"F-000{n}")
    command = [sys.executable, str(SCRIPT_PATH), "--product-dir", str(product)]

    processes = [subprocess.Popen(command, stdout=subprocess.PIPE, text=True) for _ in range(8)]
    picks = [json.loads(p.communicate()[0])["picked"] for p in processes]

    claimed = sorted(p["id"] for p in picks if p)
    assert claimed == ["F-0001", "F-0002", "F-0003"]


def test_missing_items_directory(run, product):
    (product / "items").rmdir()

    result = run(SCRIPT)

    assert result.returncode == 2
    assert "items directory not found" in result.stderr
