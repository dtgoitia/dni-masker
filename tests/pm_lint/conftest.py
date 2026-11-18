import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "skills" / "pm-lint" / "scripts"

# Allow importing the skill's helper modules (`_items`, `check_relations`) directly.
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def run(make_run):
    """run(script, *args): run a pm-lint script against the fixture product dir."""
    return make_run(SCRIPTS_DIR)
