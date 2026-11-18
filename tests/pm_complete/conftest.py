from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "skills" / "pm-complete" / "scripts"


@pytest.fixture
def run(make_run):
    """run(script, *args): run a pm-complete script against the fixture product dir."""
    return make_run(SCRIPTS_DIR)

