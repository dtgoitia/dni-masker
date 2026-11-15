import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / "hooks"


def run_hook(command: str, stdin: str, state_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / "pm_lint_hook.py"), command],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
        env={"PM_AI_HOOK_STATE_DIR": str(state_dir), "PATH": "/usr/bin:/bin"},
    )


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    return tmp_path / "state"


@pytest.fixture
def hook(product: Path, state_dir: Path):
    """hook(command, session="s1", cwd=<project root>, **payload): run pm_lint_hook.py like an agent would."""

    def run(command: str, session: str = "s1", cwd: Path | None = None, **payload) -> subprocess.CompletedProcess[str]:
        stdin = {"session_id": session, "cwd": str(cwd or product.parent),
                 "hook_event_name": "UserPromptSubmit" if command == "snapshot" else "Stop", **payload}
        return run_hook(command, json.dumps(stdin), state_dir)

    return run


@pytest.fixture
def raw_hook(state_dir: Path):
    """raw_hook(command, stdin): run pm_lint_hook.py with arbitrary stdin."""
    return lambda command, stdin: run_hook(command, stdin, state_dir)
