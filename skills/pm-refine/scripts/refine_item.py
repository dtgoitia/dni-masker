#!/usr/bin/env python3
"""Check an item against the ready gate, and move it through refinement.

  check <ID>   print JSON: the item, its acceptance criteria and open
               questions counts, and what's `missing` for it to be ready
  start <ID>   idea -> clarifying (an item already clarifying is unchanged)
  ready <ID>   idea/clarifying -> ready, or ready-but-blocked if any blocker
               (from `blocked_by` or another item's `blocks`) is still open;
               refused unless the gate passes

The gate: `## Problem` and `## Proposed behaviour` are filled in,
`## Acceptance criteria` has at least one list item and `## Open questions`
is empty. HTML comments don't count as content. Only `idea` and
`clarifying` items can be refined. The user's approval is the skill's job.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Shared helpers live in the repo's top-level scripts/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from pm_graph import Graph  # noqa: E402
from pm_items import Item, load_items, set_field  # noqa: E402
from sync_ready_status import BLOCKED, READY  # noqa: E402

REFINABLE = ("idea", "clarifying")
HEADING_RE = re.compile(r"^#{1,2}\s+(.*?)\s*#*\s*$")
LIST_ITEM_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


class Refused(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


def sections(path: Path) -> dict[str, str]:
    """Body sections by normalised heading, without HTML comments."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        text = text[text.find("\n", end + 1) + 1:] if end != -1 else ""
    result: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in COMMENT_RE.sub("", text).splitlines():
        heading = HEADING_RE.match(line)
        if heading and line.startswith("## "):
            name = heading.group(1).lower().replace("behavior", "behaviour")
            current = result.setdefault(name, [])
        elif heading:
            current = None  # a top-level `#` heading ends the section
        elif current is not None:
            current.append(line)
    return {name: "\n".join(lines).strip() for name, lines in result.items()}


def list_items(content: str) -> int:
    return sum(1 for line in content.splitlines() if LIST_ITEM_RE.match(line))


def report(item: Item) -> dict:
    body = sections(item.path)
    criteria = list_items(body.get("acceptance criteria", ""))
    questions_text = body.get("open questions", "")
    questions = list_items(questions_text) or (1 if questions_text else 0)

    missing = []
    if item.status not in REFINABLE:
        missing.append(f"status is `{item.status}`: only `idea` and `clarifying` items can be refined")
    if not body.get("problem"):
        missing.append("`## Problem` is empty")
    if not body.get("proposed behaviour"):
        missing.append("`## Proposed behaviour` is empty")
    if not criteria:
        missing.append("`## Acceptance criteria` has no list items")
    if questions:
        missing.append(f"`## Open questions` lists {questions} open question(s)")
    return {
        "id": item.id,
        "title": item.title,
        "type": item.type,
        "status": item.status,
        "path": str(item.path),
        "acceptance_criteria": criteria,
        "open_questions": questions,
        "missing": missing,
    }


def find(items: list[Item], item_id: str) -> Item:
    matches = [item for item in items if item.id == item_id]
    if not matches:
        raise Refused(f"{item_id} not found", code=2)
    if len(matches) > 1:
        raise Refused(f"{item_id} is used by more than one file; run /pm-lint first", code=2)
    return matches[0]


def start(item: Item) -> str:
    if item.status == "clarifying":
        return f"unchanged: {item.id} is already clarifying ({item.path})"
    if item.status != "idea":
        raise Refused(f"{item.id} is {item.status}: only `idea` and `clarifying` items can be refined")
    set_field(item.path, "status", "clarifying")
    return f"status: {item.id} idea -> clarifying ({item.path})"


def ready(item: Item, graph: Graph) -> str:
    missing = report(item)["missing"]
    if missing:
        raise Refused("\n".join([f"{item.id} isn't ready:", *(f"  - {m}" for m in missing)]))
    blockers = graph.open_blockers(item.id)
    status = BLOCKED if blockers else READY
    set_field(item.path, "status", status)
    by = f", by {', '.join(blockers)}" if blockers else ""
    return f"status: {item.id} {item.status} -> {status}{by} ({item.path})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--product-dir", default="product", help="product directory (default: ./product)")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [("check", "report what's missing for the item to be ready"),
                            ("start", "move an idea to clarifying"),
                            ("ready", "move the item to ready / ready-but-blocked if the gate passes")]:
        commands.add_parser(name, help=help_text).add_argument("id")
    args = parser.parse_args()

    product_dir = Path(args.product_dir)
    if not (product_dir / "items").is_dir():
        print(f"error: items directory not found: {(product_dir / 'items').resolve()}", file=sys.stderr)
        return 2

    items = load_items(product_dir)
    try:
        item = find(items, args.id)
        if args.command == "check":
            print(json.dumps(report(item), indent=2))
        elif args.command == "start":
            print(start(item))
        else:
            print(ready(item, Graph(items)))
    except Refused as refused:
        print(f"error: {refused}", file=sys.stderr)
        return refused.code
    return 0


if __name__ == "__main__":
    sys.exit(main())
