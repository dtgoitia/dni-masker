import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"

# Allow importing the shared modules (`pm_items`, ...) directly.
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def run(make_run):
    """run(script, *args): run a shared script against the fixture product dir."""
    return make_run(SCRIPTS_DIR)
