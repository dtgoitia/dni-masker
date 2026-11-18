"""register_hooks.py: add or remove the pm-lint hook in an agent's hooks JSON.

Claude Code (~/.claude/settings.json) and Codex (~/.codex/hooks.json) share
the same `hooks` schema. Only entries running pm_lint_hook.py are touched.
"""

import json
import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTER = REPO / "hooks" / "register_hooks.py"
HOOK = REPO / "hooks" / "pm_lint_hook.py"


def register(action: str, settings: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(REGISTER), action, str(settings)],
                          capture_output=True, text=True, check=False)


def command(subcommand: str) -> str:
    return f"python3 {shlex.quote(str(HOOK))} {subcommand}"


OURS = {
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": command("snapshot"), "timeout": 30}]}],
    "Stop": [{"hooks": [{"type": "command", "command": command("check"), "timeout": 60}]}],
}


def test_install_creates_missing_file(tmp_path):
    settings = tmp_path / "nested" / "settings.json"

    result = register("install", settings)

    assert result.returncode == 0, result.stderr
    assert json.loads(settings.read_text()) == {"hooks": OURS}
    assert f"registered: {settings}" in result.stdout


def test_install_keeps_other_settings_and_hooks(tmp_path):
    settings = tmp_path / "settings.json"
    other_stop = {"hooks": [{"type": "command", "command": "notify-send done"}]}
    other_post = {"matcher": "Edit", "hooks": [{"type": "command", "command": "fmt"}]}
    settings.write_text(json.dumps({
        "model": "opus",
        "hooks": {"Stop": [other_stop], "PostToolUse": [other_post]},
    }))

    assert register("install", settings).returncode == 0

    data = json.loads(settings.read_text())
    assert data["model"] == "opus"
    assert data["hooks"]["Stop"] == [other_stop, *OURS["Stop"]]
    assert data["hooks"]["PostToolUse"] == [other_post]
    assert data["hooks"]["UserPromptSubmit"] == OURS["UserPromptSubmit"]


def test_install_is_idempotent(tmp_path):
    settings = tmp_path / "settings.json"
    register("install", settings)
    before = settings.read_text()

    result = register("install", settings)

    assert result.returncode == 0
    assert settings.read_text() == before
    assert f"ok: {settings}" in result.stdout


def test_install_replaces_an_entry_from_another_clone(tmp_path):
    settings = tmp_path / "settings.json"
    old = {"hooks": [{"type": "command", "command": "python3 /old/clone/hooks/pm_lint_hook.py check"}]}
    settings.write_text(json.dumps({"hooks": {"Stop": [old]}}))

    register("install", settings)

    assert json.loads(settings.read_text())["hooks"] == OURS


def test_uninstall_removes_only_our_entries(tmp_path):
    settings = tmp_path / "settings.json"
    other_stop = {"hooks": [{"type": "command", "command": "notify-send done"}]}
    settings.write_text(json.dumps({"model": "opus", "hooks": {"Stop": [other_stop]}}))
    register("install", settings)

    result = register("uninstall", settings)

    assert result.returncode == 0, result.stderr
    assert json.loads(settings.read_text()) == {"model": "opus", "hooks": {"Stop": [other_stop]}}
    assert f"unregistered: {settings}" in result.stdout


def test_uninstall_drops_emptied_hooks_section(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"model": "opus"}))
    assert register("install", settings).returncode == 0
    assert "hooks" in json.loads(settings.read_text())

    assert register("uninstall", settings).returncode == 0

    assert json.loads(settings.read_text()) == {"model": "opus"}


def test_uninstall_missing_file_is_a_no_op(tmp_path):
    settings = tmp_path / "settings.json"

    result = register("uninstall", settings)

    assert result.returncode == 0
    assert not settings.exists()


def test_invalid_json_is_left_untouched(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text("{ not json")

    result = register("install", settings)

    assert result.returncode == 1
    assert "not valid JSON" in result.stderr
    assert settings.read_text() == "{ not json"

