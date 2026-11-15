import pytest
from pm_items import parse_frontmatter


@pytest.mark.parametrize(
    ("line", "value"),
    [
        ("status: ready", "ready"),
        ("status: ready   # comment", "ready"),
        ('status: "ready"', "ready"),
        ("status: 'ready'", "ready"),
        ('status: "ready"   # comment', "ready"),
        ("status: 'ready' # comment", "ready"),
        ('title: "Use # in titles"', "Use # in titles"),
        ('title: "Use # in titles"  # comment', "Use # in titles"),
        ('title: "a"  # see "b"', "a"),
    ],
)
def test_parse_scalar(line, value):
    key = line.split(":")[0]
    assert parse_frontmatter(f"---\n{line}\n---\n") == {key: value}


# --- set_field -----------------------------------------------------------------

FM = "---\nid: F-0001\ncreated: 2026-01-01T00:00:00+00:00\nstatus: ready\n---\n\nstatus: body text\n"


def test_set_field_replaces_existing_value(tmp_path):
    from pm_items import set_field

    path = tmp_path / "item.md"
    path.write_text(FM)

    set_field(path, "status", "done")

    assert path.read_text() == FM.replace("status: ready", "status: done")


def test_set_field_keeps_quotes_and_comment(tmp_path):
    from pm_items import set_field

    path = tmp_path / "item.md"
    path.write_text('---\nid: F-0001\nstatus: "ready"   # comment\n---\n')

    set_field(path, "status", "done")

    assert path.read_text() == '---\nid: F-0001\nstatus: "done"   # comment\n---\n'


def test_set_field_inserts_after_given_key(tmp_path):
    from pm_items import set_field

    path = tmp_path / "item.md"
    path.write_text(FM)

    set_field(path, "completed", "2026-02-02T00:00:00+00:00", after="created")

    assert path.read_text() == FM.replace(
        "created: 2026-01-01T00:00:00+00:00\n",
        "created: 2026-01-01T00:00:00+00:00\ncompleted: 2026-02-02T00:00:00+00:00\n",
    )


def test_set_field_inserts_at_end_of_frontmatter_without_anchor(tmp_path):
    from pm_items import set_field

    path = tmp_path / "item.md"
    path.write_text(FM)

    set_field(path, "decision", "ADR-0001", after="missing")

    assert path.read_text() == FM.replace("status: ready\n---", "status: ready\ndecision: ADR-0001\n---")


def test_set_field_never_touches_the_body(tmp_path):
    from pm_items import set_field

    path = tmp_path / "item.md"
    path.write_text("---\nid: F-0001\n---\n\nstatus: body text\n")

    set_field(path, "status", "done")

    assert path.read_text() == "---\nid: F-0001\nstatus: done\n---\n\nstatus: body text\n"


# --- set_list ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("blocks: []\n", "blocks: [F-0002, F-0003]\n"),
        ("blocks: [F-0002]   # comment\n", "blocks: [F-0002, F-0003]   # comment\n"),
        ("blocks:\n  - F-0002\n", "blocks: [F-0002, F-0003]\n"),
        ("blocks:\n- F-0002\n- F-0009\n", "blocks: [F-0002, F-0003]\n"),
    ],
)
def test_set_list_rewrites_any_list_syntax_inline(tmp_path, before, after):
    from pm_items import set_list

    path = tmp_path / "item.md"
    path.write_text(f"---\nid: F-0001\n{before}status: ready\n---\n\nblocks: body\n")

    set_list(path, "blocks", ["F-0002", "F-0003"])

    assert path.read_text() == f"---\nid: F-0001\n{after}status: ready\n---\n\nblocks: body\n"


def test_set_list_writes_an_empty_list(tmp_path):
    from pm_items import set_list

    path = tmp_path / "item.md"
    path.write_text("---\nid: F-0001\nblocks: [F-0002]\n---\n")

    set_list(path, "blocks", [])

    assert path.read_text() == "---\nid: F-0001\nblocks: []\n---\n"


def test_set_list_inserts_a_missing_field_at_the_end(tmp_path):
    from pm_items import set_list

    path = tmp_path / "item.md"
    path.write_text("---\nid: F-0001\n---\n")

    set_list(path, "related_to", ["Q-0001"])

    assert path.read_text() == "---\nid: F-0001\nrelated_to: [Q-0001]\n---\n"
