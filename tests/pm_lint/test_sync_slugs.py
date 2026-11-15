import pytest
from _items import slugify


SCRIPT = "sync_slugs.py"


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("Export reports as CSV", "export-reports-as-csv"),
        ("  Support   dark mode!! ", "support-dark-mode"),
        ("Ünïcode títle", "unicode-title"),
        ("Should exports be sync or async?", "should-exports-be-sync-or-async"),
        ("Migrate DB to Postgres 17", "migrate-db-to-postgres-17"),
        ("!!!", ""),
        # cut at a word boundary to at most 50 characters
        (
            "Migrate DB to Postgres 17 — très important, with a very long title indeed!!",
            "migrate-db-to-postgres-17-tres-important-with-a",
        ),
    ],
)
def test_slugify(title, slug):
    assert slugify(title) == slug
    assert len(slugify(title)) <= 50


def test_renames_file_to_match_title(item_names, write_item, run, product):
    write_item("F-0001-old-name.md", id="F-0001", title="Export reports as CSV")

    result = run(SCRIPT)

    assert result.returncode == 0
    assert "renamed" in result.stdout
    assert item_names() == ["F-0001-export-reports-as-csv.md"]


def test_renames_file_without_slug(item_names, write_item, run, product):
    write_item("T-0002.md", id="T-0002", title="Add rate limits")

    run(SCRIPT)

    assert item_names() == ["T-0002-add-rate-limits.md"]


def test_title_is_source_of_truth_and_content_is_preserved(write_item, run, product):
    path = write_item("F-0001-a.md", id="F-0001", title='"Dark mode"   # quoted title')
    content = path.read_text()

    run(SCRIPT)

    renamed = product / "items" / "F-0001-dark-mode.md"
    assert renamed.read_text() == content


def test_dry_run_does_not_rename(item_names, write_item, run, product):
    write_item("F-0001-old-name.md", id="F-0001", title="New name")

    result = run(SCRIPT, "--dry-run")

    assert result.returncode == 0
    assert "would rename" in result.stdout
    assert "F-0001-new-name.md" in result.stdout
    assert item_names() == ["F-0001-old-name.md"]


def test_matching_names_are_left_alone(item_names, write_item, run, product):
    write_item("F-0001-dark-mode.md", id="F-0001", title="Dark mode")

    result = run(SCRIPT)

    assert result.returncode == 0
    assert "all file names match their titles" in result.stdout
    assert item_names() == ["F-0001-dark-mode.md"]


@pytest.mark.parametrize(
    ("name", "fields", "reason"),
    [
        ("F-0001-a.md", {"title": "No id"}, "missing `id` or `title`"),
        ("F-0001-a.md", {"id": "F-0001"}, "missing `id` or `title`"),
        ("Q-0009-a.md", {"id": "Q-0001", "title": "Mismatch"}, "file name ID Q-0009 != frontmatter ID Q-0001"),
    ],
)
def test_skips_files_that_cannot_be_renamed_safely(item_names, write_item, run, product, name, fields, reason):
    write_item(name, **fields)

    result = run(SCRIPT)

    assert result.returncode == 1
    assert reason in result.stderr
    assert item_names() == [name]


def test_skips_when_target_already_exists(item_names, write_item, run, product):
    write_item("F-0001-dark-mode.md", id="F-0001", title="Dark mode")
    write_item("F-0001-old.md", id="F-0001", title="Dark mode")

    result = run(SCRIPT)

    assert result.returncode == 1
    assert "target F-0001-dark-mode.md already exists" in result.stderr
    assert item_names() == ["F-0001-dark-mode.md", "F-0001-old.md"]


def test_title_without_slug_characters_uses_bare_id(item_names, write_item, run, product):
    write_item("F-0001-old.md", id="F-0001", title="!!!")

    run(SCRIPT)

    assert item_names() == ["F-0001.md"]


def test_other_files_are_processed_when_one_is_skipped(item_names, write_item, run, product):
    write_item("notes.md", text="no frontmatter\n")
    write_item("F-0001-old.md", id="F-0001", title="New")

    result = run(SCRIPT)

    assert result.returncode == 1
    assert item_names() == ["F-0001-new.md", "notes.md"]


# --- decisions -------------------------------------------------------------------


def test_renames_decision_to_match_title(write_decision, run, product):
    write_decision("ADR-0001-old.md", id="ADR-0001", title="Use Postgres for exports", question="Q-0001")

    result = run(SCRIPT)

    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in (product / "decisions" / "adrs").iterdir()) == ["ADR-0001-use-postgres-for-exports.md"]


def test_decision_with_mismatched_ids_is_skipped(write_decision, run, product):
    write_decision("PDR-0002-a.md", id="PDR-0001", title="a")

    result = run(SCRIPT)

    assert result.returncode == 1
    assert "file name ID PDR-0002 != frontmatter ID PDR-0001" in result.stderr
    assert sorted(p.name for p in (product / "decisions" / "pdrs").iterdir()) == ["PDR-0002-a.md"]


def test_missing_decisions_directory_is_fine(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a")

    assert run(SCRIPT).returncode == 0
