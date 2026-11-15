"""deprecate_item.py: deprecate an item, link its replacement, and review its dependents.

  check <ID>                     the item, its replacements and its open dependents, as JSON
  deprecate <ID> [--superseded-by X]
                                 `status: deprecated` + `deprecated: <now>`; links X with
                                 supersedes / superseded_by on both sides; re-derives the
                                 dependents' ready / ready-but-blocked and lists them
  relink <DEP> <ID> <X>          move DEP's blocker from ID to X, on both sides
  unlink <DEP> <ID>              drop DEP's blocker ID, on both sides
"""

import json

import pytest
from pm_items import parse_frontmatter

SCRIPT = "deprecate_item.py"
NOW = "2026-11-15T12:00:00+01:00"


def fm(path) -> dict:
    return parse_frontmatter(path.read_text())


def item(write_item, item_id, status="ready", **fields):
    return write_item(f"{item_id}-x.md", id=item_id, title=f"title {item_id}", type="feature", status=status, **fields)


def deprecate(run, item_id, *args):
    return run(SCRIPT, "deprecate", item_id, "--now", NOW, *args)


# --- check ------------------------------------------------------------------------------


def test_check_reports_item_replacements_and_open_dependents(write_item, run):
    a = item(write_item, "F-0001", status="done", blocks=["F-0002"], superseded_by=["F-0009"])
    b = item(write_item, "F-0002", status="ready-but-blocked", blocked_by=["F-0001"])
    c = item(write_item, "F-0003", status="idea", blocked_by=["F-0001"])
    item(write_item, "F-0004", status="done", blocked_by=["F-0001"])  # closed: not listed
    item(write_item, "F-0009", status="ready", supersedes=["F-0001"])

    result = run(SCRIPT, "check", "F-0001")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "id": "F-0001",
        "title": "title F-0001",
        "type": "feature",
        "status": "done",
        "path": str(a),
        "superseded_by": ["F-0009"],
        "dependents": [
            {"id": "F-0002", "title": "title F-0002", "type": "feature", "status": "ready-but-blocked",
             "path": str(b)},
            {"id": "F-0003", "title": "title F-0003", "type": "feature", "status": "idea", "path": str(c)},
        ],
    }


def test_check_unknown_id(write_item, run):
    result = run(SCRIPT, "check", "F-0099")

    assert result.returncode == 2
    assert "F-0099 not found" in result.stderr


# --- deprecate: the item ------------------------------------------------------------------


def test_deprecate_sets_status_and_timestamp_only(write_item, run):
    text = (
        "---\nid: F-0001\ntitle: a\ntype: feature\nstatus: done   # comment\n"
        "created: 2026-01-01T00:00:00+00:00\ncompleted: 2026-02-01T00:00:00+00:00\nsuperseded_by: []\n---\n"
        "\n## Notes / history\n\nstatus: done\n"
    )
    a = write_item("F-0001-a.md", text=text)

    result = deprecate(run, "F-0001")

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [f"deprecated: F-0001 ({a})"]
    assert a.read_text() == text.replace("status: done   #", "status: deprecated   #", 1).replace(
        "completed: 2026-02-01T00:00:00+00:00\n", f"completed: 2026-02-01T00:00:00+00:00\ndeprecated: {NOW}\n")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("---\nid: F-0001\nstatus: idea\ncreated: C\ntitle: a\n---\n",
         f"---\nid: F-0001\nstatus: deprecated\ncreated: C\ndeprecated: {NOW}\ntitle: a\n---\n"),
        ("---\nid: F-0001\nstatus: idea\ntitle: a\n---\n",
         f"---\nid: F-0001\nstatus: deprecated\ndeprecated: {NOW}\ntitle: a\n---\n"),
    ],
)
def test_deprecated_timestamp_goes_after_created_or_status(write_item, run, text, expected):
    a = write_item("F-0001-a.md", text=text)

    deprecate(run, "F-0001")

    assert a.read_text() == expected


@pytest.mark.parametrize("status", ["idea", "clarifying", "ready", "ready-but-blocked", "in-progress", "done"])
def test_any_status_but_deprecated_can_be_deprecated(write_item, run, status):
    a = item(write_item, "F-0001", status=status)

    assert deprecate(run, "F-0001").returncode == 0
    assert fm(a)["status"] == "deprecated"


def test_already_deprecated_is_refused(write_item, run):
    a = item(write_item, "F-0001", status="deprecated")
    before = a.read_bytes()

    result = deprecate(run, "F-0001")

    assert result.returncode == 1
    assert "F-0001 is already deprecated" in result.stderr
    assert a.read_bytes() == before


def test_unknown_and_duplicate_ids(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a", status="done")
    write_item("F-0001-b.md", id="F-0001", title="b", status="done")

    assert deprecate(run, "F-0099").returncode == 2
    duplicate = deprecate(run, "F-0001")
    assert duplicate.returncode == 2
    assert "F-0001 is used by more than one file" in duplicate.stderr


def test_missing_items_directory(run, product):
    (product / "items").rmdir()

    result = deprecate(run, "F-0001")

    assert result.returncode == 2
    assert "items directory not found" in result.stderr


# --- deprecate: replacement ---------------------------------------------------------------


def test_superseded_by_is_written_on_both_sides(write_item, run):
    a = item(write_item, "F-0001", status="done")
    x = item(write_item, "F-0009", status="clarifying", supersedes=["F-0005"])
    item(write_item, "F-0005", status="deprecated", superseded_by=["F-0009"])

    result = deprecate(run, "F-0001", "--superseded-by", "F-0009")

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [f"deprecated: F-0001 ({a})", f"superseded by: F-0009 ({x})"]
    assert fm(a)["superseded_by"] == ["F-0009"]
    assert fm(x)["supersedes"] == ["F-0001", "F-0005"]


def test_existing_replacement_link_is_not_duplicated(write_item, run):
    a = item(write_item, "F-0001", status="done", superseded_by=["F-0009"])
    x = item(write_item, "F-0009", status="ready", supersedes=["F-0001"])

    result = deprecate(run, "F-0001", "--superseded-by", "F-0009")

    assert result.returncode == 0, result.stderr
    assert fm(a)["status"] == "deprecated"
    assert fm(a)["superseded_by"] == ["F-0009"]
    assert fm(x)["supersedes"] == ["F-0001"]


@pytest.mark.parametrize(
    ("replacement", "code", "message"),
    [
        ("F-0001", 1, "F-0001 can't supersede itself"),
        ("F-0099", 2, "F-0099 not found"),
        ("F-0002", 1, "replacement F-0002 is deprecated"),
        ("F-0004", 1, "would create a cycle: F-0004 supersedes F-0001 supersedes F-0004"),
    ],
)
def test_invalid_replacements_are_refused(write_item, run, replacement, code, message):
    a = item(write_item, "F-0001", status="done", supersedes=["F-0004"])
    item(write_item, "F-0002", status="deprecated")
    item(write_item, "F-0004", status="ready", superseded_by=["F-0001"])
    before = a.read_bytes()

    result = deprecate(run, "F-0001", "--superseded-by", replacement)

    assert result.returncode == code
    assert message in result.stderr
    assert a.read_bytes() == before


# --- deprecate: dependents -----------------------------------------------------------------


def test_dependents_are_re_derived_and_listed(write_item, run):
    item(write_item, "F-0001", status="in-progress", blocks=["F-0002"])
    b = item(write_item, "F-0002", status="ready-but-blocked", blocked_by=["F-0001"])
    c = item(write_item, "F-0003", status="ready-but-blocked", blocked_by=["F-0001", "F-0008"])
    d = item(write_item, "F-0004", status="clarifying", blocked_by=["F-0001"])
    item(write_item, "F-0005", status="done", blocked_by=["F-0001"])
    item(write_item, "F-0008", status="idea")

    result = deprecate(run, "F-0001")

    assert result.stdout.splitlines()[1:] == [
        f"dependent: F-0002 ready-but-blocked -> ready ({b})",
        f"dependent: F-0003 (status: ready-but-blocked) ({c})",
        f"dependent: F-0004 (status: clarifying) ({d})",
    ]
    assert fm(b)["status"] == "ready"
    assert fm(c)["status"] == "ready-but-blocked"


# --- relink / unlink -------------------------------------------------------------------------


def test_relink_moves_the_blocker_on_all_sides(write_item, run):
    a = item(write_item, "F-0001", status="deprecated", blocks=["F-0002", "F-0003"])
    b = item(write_item, "F-0002", status="ready", blocked_by=["F-0001"])
    item(write_item, "F-0003", status="idea", blocked_by=["F-0001"])
    x = item(write_item, "F-0009", status="clarifying", blocks=["F-0007"])
    item(write_item, "F-0007", status="idea", blocked_by=["F-0009"])

    result = run(SCRIPT, "relink", "F-0002", "F-0001", "F-0009")

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "relinked: F-0002 blocked_by F-0001 -> F-0009",
        f"dependent: F-0002 ready -> ready-but-blocked ({b})",
    ]
    assert fm(a)["blocks"] == ["F-0003"]
    assert fm(b)["blocked_by"] == ["F-0009"]
    assert fm(x)["blocks"] == ["F-0002", "F-0007"]


def test_relink_link_declared_on_one_side_only(write_item, run):
    a = item(write_item, "F-0001", status="deprecated", blocks=["F-0002"])
    b = item(write_item, "F-0002", status="idea")
    x = item(write_item, "F-0009", status="ready")

    assert run(SCRIPT, "relink", "F-0002", "F-0001", "F-0009").returncode == 0
    assert fm(a)["blocks"] == []
    assert fm(b)["blocked_by"] == ["F-0009"]
    assert fm(x)["blocks"] == ["F-0002"]


@pytest.mark.parametrize(
    ("args", "code", "message"),
    [
        (("F-0002", "F-0005", "F-0009"), 1, "F-0002 is not blocked by F-0005"),
        (("F-0002", "F-0001", "F-0002"), 1, "F-0002 can't block itself"),
        (("F-0002", "F-0001", "F-0099"), 2, "F-0099 not found"),
        (("F-0002", "F-0001", "F-0003"), 1, "would create a cycle: F-0003 blocks F-0002 blocks F-0003"),
    ],
)
def test_invalid_relinks_are_refused(write_item, run, args, code, message):
    item(write_item, "F-0001", status="deprecated", blocks=["F-0002"])
    b = item(write_item, "F-0002", status="ready", blocked_by=["F-0001"], blocks=["F-0003"])
    item(write_item, "F-0003", status="idea", blocked_by=["F-0002"])
    item(write_item, "F-0005", status="idea")
    item(write_item, "F-0009", status="ready")
    before = b.read_bytes()

    result = run(SCRIPT, "relink", *args)

    assert result.returncode == code
    assert message in result.stderr
    assert b.read_bytes() == before


def test_unlink_drops_the_blocker_on_both_sides(write_item, run):
    a = item(write_item, "F-0001", status="in-progress", blocks=["F-0002"])
    b = item(write_item, "F-0002", status="ready-but-blocked", blocked_by=["F-0001"])

    result = run(SCRIPT, "unlink", "F-0002", "F-0001")

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "unlinked: F-0002 blocked_by F-0001",
        f"dependent: F-0002 ready-but-blocked -> ready ({b})",
    ]
    assert fm(a)["blocks"] == []
    assert fm(b)["blocked_by"] == []


def test_unlink_requires_an_existing_link(write_item, run):
    item(write_item, "F-0001", status="deprecated")
    item(write_item, "F-0002", status="idea")

    result = run(SCRIPT, "unlink", "F-0002", "F-0001")

    assert result.returncode == 1
    assert "F-0002 is not blocked by F-0001" in result.stderr


def test_only_list_fields_change_and_block_lists_become_inline(write_item, run):
    text = "---\nid: F-0002\ntitle: b   # comment\nstatus: idea\nblocked_by:\n  - F-0001\n---\n\nblocked_by: body\n"
    b = write_item("F-0002-b.md", text=text)
    item(write_item, "F-0001", status="deprecated")

    run(SCRIPT, "unlink", "F-0002", "F-0001")

    assert b.read_text() == text.replace("blocked_by:\n  - F-0001\n", "blocked_by: []\n", 1)
