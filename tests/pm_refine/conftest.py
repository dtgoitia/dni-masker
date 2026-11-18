from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "skills" / "pm-refine" / "scripts"


@pytest.fixture
def run(make_run):
    """run(script, *args): run a pm-refine script against the fixture product dir."""
    return make_run(SCRIPTS_DIR)
