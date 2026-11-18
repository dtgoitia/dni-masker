import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO / ".claude" / "skills" / "pm-deprecate" / "scripts"

# Allow importing the shared modules (`pm_items`, ...) directly.
sys.path.insert(0, str(REPO / "scripts"))


@pytest.fixture
def run(make_run):
    """run(script, *args): run a pm-deprecate script against the fixture product dir."""
    return make_run(SCRIPTS_DIR)
