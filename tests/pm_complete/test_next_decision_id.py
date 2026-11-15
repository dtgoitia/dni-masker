SCRIPT = "next_decision_id.py"


def test_first_ids(run, product):
    assert run(SCRIPT, "pdr").stdout.splitlines() == ["PDR-0001"]
    assert run(SCRIPT, "adr").stdout.splitlines() == ["ADR-0001"]


def test_prints_path_for_title(run, product):
    result = run(SCRIPT, "adr", "--title", "Use Postgres for exports!")

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "ADR-0001", str(product / "decisions" / "adrs" / "ADR-0001-use-postgres-for-exports.md"),
    ]


def test_pdrs_go_to_their_own_directory(run, product):
    result = run(SCRIPT, "pdr", "--title", "Exports are async")

    assert result.stdout.splitlines() == ["PDR-0001", str(product / "decisions" / "pdrs" / "PDR-0001-exports-are-async.md")]


def test_misplaced_decisions_still_count(write_decision, run):
    # A PDR in adrs/ (or anywhere under decisions/) must not have its number reused.
    write_decision("PDR-0003-a.md", directory="adrs", id="PDR-0003")

    assert run(SCRIPT, "pdr").stdout.splitlines() == ["PDR-0004"]


def test_kinds_have_independent_counters(write_decision, run):
    write_decision("PDR-0001-a.md", id="PDR-0001")
    write_decision("PDR-0002-b.md", id="PDR-0002")
    write_decision("ADR-0001-c.md", id="ADR-0001")

    assert run(SCRIPT, "pdr").stdout.splitlines() == ["PDR-0003"]
    assert run(SCRIPT, "adr").stdout.splitlines() == ["ADR-0002"]


def test_ids_in_file_names_and_frontmatter_both_count(write_decision, run):
    write_decision("ADR-0004-a.md", title="a")
    write_decision("renamed.md", id="ADR-0007")

    assert run(SCRIPT, "adr").stdout.splitlines() == ["ADR-0008"]


def test_item_ids_do_not_count(write_item, run):
    write_item("Q-0005-a.md", id="Q-0005", title="a", decision="ADR-0005")

    assert run(SCRIPT, "adr").stdout.splitlines() == ["ADR-0001"]


def test_missing_product_directory(run, product):
    (product / "items").rmdir()
    product.rmdir()

    result = run(SCRIPT, "adr")

    assert result.returncode == 1
    assert "product directory not found" in result.stderr
