SCRIPT = "check_duplicates.py"


def test_no_duplicates(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a")
    write_item("F-0002-b.md", id="F-0002", title="b")

    result = run(SCRIPT)

    assert result.returncode == 0
    assert "no duplicate IDs found" in result.stdout
    assert result.stderr == ""


def test_same_number_with_different_prefixes_is_not_a_duplicate(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a")
    write_item("T-0001-b.md", id="T-0001", title="b")
    write_item("Q-0001-c.md", id="Q-0001", title="c")

    assert run(SCRIPT).returncode == 0


def test_duplicate_frontmatter_ids_are_reported_on_stderr(write_item, run):
    a = write_item("F-0001-a.md", id="F-0001", title="a")
    b = write_item("F-0001-b.md", id="F-0001", title="b")
    write_item("F-0002-c.md", id="F-0002", title="c")

    result = run(SCRIPT)

    assert result.returncode == 1
    assert "duplicate ID F-0001" in result.stderr
    assert str(a) in result.stderr and str(b) in result.stderr
    assert "F-0002" not in result.stderr
    assert result.stdout == ""


def test_duplicate_detected_across_differently_named_files(write_item, run):
    # The frontmatter ID is what counts, not the file name.
    write_item("F-0001-a.md", id="F-0001", title="a")
    write_item("F-0009-b.md", id="F-0001", title="b")

    result = run(SCRIPT)

    assert result.returncode == 1
    assert "duplicate ID F-0001" in result.stderr


def test_file_name_id_is_used_when_frontmatter_has_no_id(write_item, run):
    write_item("F-0001-a.md", id="F-0001", title="a")
    write_item("F-0001-b.md", text="no frontmatter here\n")

    result = run(SCRIPT)

    assert result.returncode == 1
    assert "duplicate ID F-0001" in result.stderr


def test_files_without_any_id_are_ignored(write_item, run):
    write_item("notes.md", text="just notes\n")
    write_item("other.md", text="more notes\n")

    assert run(SCRIPT).returncode == 0


def test_missing_items_directory(tmp_path, run, product):
    (product / "items").rmdir()

    result = run(SCRIPT)

    assert result.returncode == 2
    assert "items directory not found" in result.stderr


# --- decisions -------------------------------------------------------------------


def test_duplicate_decision_ids_are_reported(write_decision, run):
    a = write_decision("ADR-0001-a.md", id="ADR-0001", title="a", question="Q-0001")
    b = write_decision("ADR-0001-b.md", id="ADR-0001", title="b", question="Q-0002")

    result = run(SCRIPT)

    assert result.returncode == 1
    assert result.stderr.splitlines() == ["duplicate ID ADR-0001:", f"  {a}", f"  {b}"]


def test_pdr_and_adr_with_the_same_number_are_not_duplicates(write_decision, run):
    write_decision("PDR-0001-a.md", id="PDR-0001", title="a")
    write_decision("ADR-0001-b.md", id="ADR-0001", title="b")
    c = write_decision("PDR-0002-c.md", id="PDR-0002", title="c")
    d = write_decision("PDR-0002-d.md", id="PDR-0002", title="d")

    result = run(SCRIPT)

    # Only the real duplicate is reported, which also proves decisions are scanned.
    assert result.stderr.splitlines() == ["duplicate ID PDR-0002:", f"  {c}", f"  {d}"]


def test_decision_id_from_file_name_counts(write_decision, run):
    write_decision("PDR-0002-a.md", title="a")
    write_decision("renamed.md", id="PDR-0002", title="b")

    assert run(SCRIPT).returncode == 1
