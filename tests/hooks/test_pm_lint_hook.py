"""pm_lint_hook.py: run /pm-lint's checks when a turn changed product frontmatter.

`snapshot` (UserPromptSubmit) fingerprints the frontmatter of every file in
product/items/ and product/decisions/. `check` (Stop) re-fingerprints them
and, if anything changed, runs the pm-lint checks. On problems it exits 2
with the report on stderr, so the agent keeps working; if the agent is
already continuing because of a stop hook, it only shows a warning.
"""

import json

import pytest


def consistent_pair(write_item):
    write_item("F-0001-a.md", id="F-0001", title="a", type="feature", status="in-progress", blocks=["F-0002"])
    return write_item("F-0002-b.md", id="F-0002", title="b", type="feature", status="ready-but-blocked",
                      blocked_by=["F-0001"])


def assert_blocked(result, *problems: str):
    # Exit 2 alone isn't enough: Python also exits 2 when the script is missing.
    assert result.returncode == 2, result.stderr
    assert "/pm-lint" in result.stderr
    for problem in problems:
        assert problem in result.stderr


def assert_silent_success(result):
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


# --- when it runs -------------------------------------------------------------------------


def test_no_changes_no_lint(write_item, hook):
    write_item("F-0001-a.md", id="F-0001", title="a", blocks=["F-0099"])  # broken, but untouched

    hook("snapshot")

    assert_silent_success(hook("check"))


def test_body_only_changes_do_not_trigger(write_item, hook):
    a = write_item("F-0001-a.md", id="F-0001", title="a", blocks=["F-0099"])  # broken, but frontmatter untouched
    hook("snapshot")

    a.write_text(a.read_text() + "\nmore body text\n")

    assert_silent_success(hook("check"))


def test_frontmatter_change_with_problems_blocks_the_stop(write_item, hook):
    a = write_item("F-0001-a.md", id="F-0001", title="a", type="feature", status="ready")
    hook("snapshot")

    a.write_text(a.read_text().replace("status: ready", "status: ready\nblocks: [F-0002]"))
    write_item("F-0002-b.md", id="F-0002", title="b", type="feature", status="idea")

    result = hook("check")

    assert result.returncode == 2
    assert "out of sync: F-0001 blocks F-0002" in result.stderr
    assert "/pm-lint" in result.stderr


def test_frontmatter_change_without_problems_passes(write_item, hook):
    hook("snapshot")

    consistent_pair(write_item)

    assert_silent_success(hook("check"))


def test_new_file_triggers(write_item, hook):
    hook("snapshot")

    write_item("F-0001-a.md", id="F-0001", title="a", blocks=["F-0099"])

    assert_blocked(hook("check"), "unknown ID: F-0001 blocks F-0099")


def test_deleted_file_triggers(write_item, hook):
    write_item("F-0001-a.md", id="F-0001", title="a", type="feature", status="idea", blocks=["F-0002"])
    b = write_item("F-0002-b.md", id="F-0002", title="b", type="feature", status="idea", blocked_by=["F-0001"])
    hook("snapshot")

    b.unlink()

    result = hook("check")

    assert result.returncode == 2
    assert "unknown ID: F-0001 blocks F-0002" in result.stderr


def test_decision_frontmatter_change_triggers(write_item, write_decision, hook):
    write_item("Q-0001-a.md", id="Q-0001", title="a", type="question", status="done", decision="ADR-0001")
    d = write_decision("ADR-0001-x.md", id="ADR-0001", title="x", question="Q-0001")
    hook("snapshot")

    d.write_text(d.read_text().replace("question: Q-0001", "question: Q-0002"))

    result = hook("check")

    assert result.returncode == 2
    assert "unknown ID: ADR-0001 question Q-0002" in result.stderr


# --- what it checks ------------------------------------------------------------------------


def test_duplicate_ids_are_reported(write_item, hook):
    hook("snapshot")

    write_item("F-0001-a.md", id="F-0001", title="a")
    write_item("F-0001-b.md", id="F-0001", title="b")

    result = hook("check")

    assert result.returncode == 2
    assert "duplicate ID F-0001" in result.stderr


def test_stale_file_names_are_reported(write_item, hook):
    a = write_item("F-0001-a.md", id="F-0001", title="a")
    hook("snapshot")

    a.write_text(a.read_text().replace("title: a", "title: Export CSV"))

    result = hook("check")

    assert result.returncode == 2
    assert "F-0001-a.md -> F-0001-export-csv.md" in result.stderr
    assert a.exists()  # reported, never renamed by the hook


def test_stale_ready_statuses_are_reported(write_item, hook):
    b = consistent_pair(write_item)
    hook("snapshot")

    b.write_text(b.read_text().replace("status: ready-but-blocked", "status: ready"))

    result = hook("check")

    assert result.returncode == 2
    assert "F-0002 ready -> ready-but-blocked" in result.stderr
    assert "status: ready\n" in b.read_text()  # reported, never fixed by the hook


# --- loop protection ---------------------------------------------------------------------------


def test_continued_stop_only_warns(write_item, hook):
    hook("snapshot")
    write_item("F-0001-a.md", id="F-0001", title="a", blocks=["F-0099"])

    result = hook("check", stop_hook_active=True)

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "unknown ID: F-0001 blocks F-0099" in output["systemMessage"]


def test_continued_stop_after_fix_is_silent(write_item, hook):
    hook("snapshot")
    a = write_item("F-0001-a.md", id="F-0001", title="a", blocks=["F-0099"])
    assert_blocked(hook("check"))

    a.write_text(a.read_text().replace("blocks: [F-0099]", "blocks: []"))

    assert_silent_success(hook("check", stop_hook_active=True))


# --- state and robustness -------------------------------------------------------------------------


def test_check_without_snapshot_does_nothing(write_item, hook):
    write_item("F-0001-a.md", id="F-0001", title="a", blocks=["F-0099"])

    assert_silent_success(hook("check"))


def test_projects_without_product_dir_are_ignored(tmp_path, hook):
    other = tmp_path / "other-project"
    other.mkdir()

    assert_silent_success(hook("snapshot", cwd=other))
    assert_silent_success(hook("check", cwd=other))


def test_product_dir_is_found_from_a_subdirectory(write_item, hook, product):
    sub = product.parent / "src" / "deep"
    sub.mkdir(parents=True)
    hook("snapshot", cwd=sub)

    write_item("F-0001-a.md", id="F-0001", title="a", blocks=["F-0099"])

    assert_blocked(hook("check", cwd=sub), "unknown ID: F-0001 blocks F-0099")


def test_product_dir_is_found_from_a_subdirectory_up_to_the_git_root(write_item, hook, product):
    (product.parent / ".git").mkdir()
    sub = product.parent / "src" / "deep"
    sub.mkdir(parents=True)
    hook("snapshot", cwd=sub)

    write_item("F-0001-a.md", id="F-0001", title="a", blocks=["F-0099"])

    assert_blocked(hook("check", cwd=sub), "unknown ID: F-0001 blocks F-0099")


@pytest.mark.parametrize("git", ["dir", "file"])  # a .git file: worktrees and submodules
def test_search_stops_at_the_git_root(write_item, hook, product, git):
    nested = product.parent / "vendor" / "nested-repo"
    (nested / "src").mkdir(parents=True)
    if git == "dir":
        (nested / ".git").mkdir()
    else:
        (nested / ".git").write_text("gitdir: /somewhere/else\n", encoding="utf-8")
    hook("snapshot", cwd=nested / "src")

    write_item("F-0001-a.md", id="F-0001", title="a", blocks=["F-0099"])  # the enclosing project's product/

    assert_silent_success(hook("check", cwd=nested / "src"))


def test_check_uses_the_snapshot_project_even_if_cwd_moved(write_item, hook, tmp_path):
    hook("snapshot")
    write_item("F-0001-a.md", id="F-0001", title="a", blocks=["F-0099"])
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    assert_blocked(hook("check", cwd=elsewhere), "unknown ID: F-0001 blocks F-0099")


def test_sessions_are_independent(write_item, hook):
    hook("snapshot", session="s1")
    write_item("F-0001-a.md", id="F-0001", title="a", blocks=["F-0099"])
    hook("snapshot", session="s2")  # s2's turn starts after the change

    assert_blocked(hook("check", session="s1"), "unknown ID: F-0001 blocks F-0099")
    assert_silent_success(hook("check", session="s2"))


def test_snapshot_prints_nothing(write_item, hook):
    # UserPromptSubmit stdout is added to the agent's context in both Claude and Codex.
    write_item("F-0001-a.md", id="F-0001", title="a")

    assert_silent_success(hook("snapshot"))


@pytest.mark.parametrize("stdin", ["", "not json", "{}"])
def test_bad_input_is_a_non_blocking_error(raw_hook, stdin):
    result = raw_hook("check", stdin)

    assert result.returncode == 1
    assert "pm_lint_hook" in result.stderr
