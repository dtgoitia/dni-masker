#!/usr/bin/env python3
"""Agent hook: run /pm-lint's checks when a turn changed product frontmatter.

Works with Claude Code and Codex, which send the same JSON on stdin.

  snapshot  (UserPromptSubmit) fingerprint the frontmatter of every file in
            product/items/ and product/decisions/ for this session
  check     (Stop) if any fingerprint changed during the turn (edited,
            created or deleted file), run the pm-lint checks. On problems,
            exit 2 with the report on stderr: the agent keeps working and
            runs /pm-lint. If the agent is already continuing because of a
            stop hook (`stop_hook_active`), only show a warning, so the hook
            can't loop.

The product directory is the nearest `product/items/` found from the
session's working directory upwards, stopping at the git root (the first
directory holding `.git`); projects without one are ignored.
Snapshots live in $PM_AI_HOOK_STATE_DIR, by default
${XDG_STATE_HOME:-~/.local/state}/pm-ai/hooks. The hook never changes
product files.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LINT_SCRIPTS = REPO / ".claude" / "skills" / "pm-lint" / "scripts"
SHARED_SCRIPTS = REPO / "scripts"
STATE_MAX_AGE = 7 * 24 * 3600  # snapshots older than this are cleaned up


class HookError(Exception):
    pass


def state_dir() -> Path:
    if os.environ.get("PM_AI_HOOK_STATE_DIR"):
        return Path(os.environ["PM_AI_HOOK_STATE_DIR"])
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "pm-ai" / "hooks"


def state_file(session_id: str) -> Path:
    return state_dir() / (hashlib.sha256(session_id.encode()).hexdigest()[:32] + ".json")


def find_product_dir(cwd: Path) -> Path | None:
    for directory in (cwd, *cwd.parents):
        if (directory / "product" / "items").is_dir():
            return directory / "product"
        if (directory / ".git").exists():  # a directory, or a file in worktrees and submodules
            return None  # don't pick up an enclosing project's product/
    return None


def frontmatter_of(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return ""
    if not lines or lines[0].strip() != "---":
        return ""
    for end in range(1, len(lines)):
        if lines[end].strip() == "---":
            return "\n".join(lines[: end + 1])
    return "\n".join(lines)


def fingerprints(product_dir: Path) -> dict[str, str]:
    result = {}
    for sub in ("items", "decisions"):
        for path in sorted((product_dir / sub).rglob("*.md")):
            result[str(path.relative_to(product_dir))] = hashlib.sha256(frontmatter_of(path).encode()).hexdigest()
    return result


def lint(product_dir: Path) -> list[str]:
    """Run the pm-lint checks without changing anything; return the problems found."""

    def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(script), "--product-dir", str(product_dir), *args],
                              capture_output=True, text=True, check=False)

    problems: list[str] = []
    for script, args, prefix in [
        (LINT_SCRIPTS / "check_duplicates.py", (), None),
        (LINT_SCRIPTS / "sync_slugs.py", ("--dry-run",), "would rename:"),
        (LINT_SCRIPTS / "check_relations.py", (), None),
        (LINT_SCRIPTS / "check_decisions.py", (), None),
        (SHARED_SCRIPTS / "sync_ready_status.py", ("--dry-run",), "would update:"),
    ]:
        result = run(script, *args)
        problems += [line for line in result.stderr.splitlines() if line.strip()]
        if prefix:
            problems += [line for line in result.stdout.splitlines() if line.startswith(prefix)]
    return problems


def snapshot(payload: dict) -> None:
    directory = state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for old in directory.glob("*.json"):
        try:
            if now - old.stat().st_mtime > STATE_MAX_AGE:
                old.unlink()
        except OSError:
            pass

    target = state_file(payload["session_id"])
    product_dir = find_product_dir(Path(payload["cwd"]))
    if product_dir is None:
        target.unlink(missing_ok=True)
        return
    target.write_text(json.dumps({"product_dir": str(product_dir), "fingerprints": fingerprints(product_dir)}),
                      encoding="utf-8")


def check(payload: dict) -> int:
    try:
        state = json.loads(state_file(payload["session_id"]).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0  # no snapshot for this turn (e.g. no product/ directory)
    product_dir = Path(state["product_dir"])
    if not (product_dir / "items").is_dir() or fingerprints(product_dir) == state["fingerprints"]:
        return 0

    problems = lint(product_dir)
    if not problems:
        return 0
    report = "\n".join(f"  - {p}" for p in problems)
    if payload.get("stop_hook_active"):
        print(json.dumps({"systemMessage": f"pm-lint still reports problems in {product_dir}:\n{report}\n"
                                           "Run /pm-lint to fix them."}))
        return 0
    print(f"pm-lint: this turn changed the frontmatter of product items in {product_dir}, and pm-lint found "
          f"problems:\n{report}\n"
          "Run /pm-lint to fix them (it asks the user before changing anything).", file=sys.stderr)
    return 2


def main() -> int:
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "check"):
            raise HookError("usage: pm_lint_hook.py snapshot|check (hook JSON on stdin)")
        try:
            payload = json.loads(sys.stdin.read())
        except ValueError as error:
            raise HookError(f"invalid JSON on stdin: {error}") from error
        if not isinstance(payload, dict) or not payload.get("session_id") or not payload.get("cwd"):
            raise HookError("stdin JSON must include `session_id` and `cwd`")
        if sys.argv[1] == "snapshot":
            snapshot(payload)
            return 0
        return check(payload)
    except HookError as error:
        print(f"pm_lint_hook: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
