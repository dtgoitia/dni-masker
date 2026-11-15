#!/usr/bin/env python3
"""Add or remove the pm-lint hook in an agent's hooks JSON file.

  register_hooks.py install <file>    add the hook (replacing any older entry)
  register_hooks.py uninstall <file>  remove it

Claude Code (~/.claude/settings.json) and Codex (~/.codex/hooks.json) share
the same `hooks` schema. Only handlers whose command runs pm_lint_hook.py
are touched; every other setting and hook is kept as is.
"""

import json
import shlex
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent / "pm_lint_hook.py"
MARKER = "pm_lint_hook.py"
ENTRIES = {  # event -> (subcommand, timeout in seconds)
    "UserPromptSubmit": ("snapshot", 30),
    "Stop": ("check", 60),
}


def is_ours(handler: dict) -> bool:
    return MARKER in str(handler.get("command", ""))


def remove_ours(hooks: dict) -> None:
    for event in list(hooks):
        groups = []
        for group in hooks[event]:
            handlers = [h for h in group.get("hooks", []) if not is_ours(h)]
            if handlers:
                groups.append({**group, "hooks": handlers})
            elif not group.get("hooks"):
                groups.append(group)  # not ours: keep as found
        if groups:
            hooks[event] = groups
        else:
            del hooks[event]


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in ("install", "uninstall"):
        print("usage: register_hooks.py install|uninstall <settings.json>", file=sys.stderr)
        return 2
    action, path = sys.argv[1], Path(sys.argv[2])

    if not path.exists():
        if action == "uninstall":
            print(f"nothing to remove: {path}")
            return 0
        data: dict = {}
    else:
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except ValueError as error:
            print(f"error: {path} is not valid JSON ({error}); left untouched", file=sys.stderr)
            return 1
        if not isinstance(data, dict) or not isinstance(data.get("hooks", {}), dict):
            print(f"error: {path} doesn't look like a settings file; left untouched", file=sys.stderr)
            return 1

    before = json.dumps(data, sort_keys=True)
    hooks = data.setdefault("hooks", {})
    remove_ours(hooks)
    if action == "install":
        for event, (subcommand, timeout) in ENTRIES.items():
            command = f"python3 {shlex.quote(str(HOOK))} {subcommand}"
            hooks.setdefault(event, []).append({"hooks": [{"type": "command", "command": command, "timeout": timeout}]})
    if not hooks:
        del data["hooks"]

    if json.dumps(data, sort_keys=True) == before and path.exists():
        print(f"{'ok' if action == 'install' else 'nothing to remove'}: {path}")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"{'registered' if action == 'install' else 'unregistered'}: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
