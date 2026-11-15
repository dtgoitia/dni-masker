from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "skills" / "pm-semantic-lint" / "scripts"


@pytest.fixture
def run(make_run):
    """run(script, *args): run a pm-semantic-lint script against the fixture product dir."""
    return make_run(SCRIPTS_DIR)
